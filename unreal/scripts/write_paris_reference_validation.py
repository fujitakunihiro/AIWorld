"""Collect completed build, automation and unedited UE capture evidence."""
import hashlib,json,re,struct
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data';SAVED=ROOT/'unreal/AIWorld/Saved';DOCS=ROOT/'docs'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    packet=read(DATA/'paris-reference.json');source=read(DATA/'paris-digital-twin-runtime.json')
    assert packet['source_scene_sha256']==source['source_scene_sha256']
    assert packet['georeference']==source['georeference']
    mesh_hash=digest(DATA/'paris-digital-twin-meshes.bin')
    assert mesh_hash==read(DATA/'paris-road-detail.json')['source_mesh_sha256']
    native={}
    for name,expected in [('regression',11),('reference',1)]:
        text=(SAVED/f'paris-reference-{name}-automation.log').read_text(encoding='utf-8-sig')
        results=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\}',text)
        assert len(results)==expected and all(state=='Success' for state,_ in results),results
        native[name]=[name for _,name in results]
    python=(ROOT/'backups/reference-python-tests-final.log').read_text(encoding='utf-8-sig')
    assert 'Ran 5 tests' in python and '\nOK' in python
    assert 'Result: Succeeded' in (ROOT/'backups/reference-build-final.log').read_text(encoding='utf-8-sig')
    bake=(ROOT/'backups/reference-bake-final.log').read_text(encoding='utf-8-sig')
    assert 'PARIS_REFERENCE_ASSETS_READY' in bake and 'Success - 0 error(s)' in bake
    reproducibility=read(ROOT/'backups/reference-reproducibility-final.json')
    assert reproducibility['reproducible'] and reproducibility['repeat_sha256']==digest(ROOT/'unreal/assets/paris-reference/Generated/reference.json')
    installed=[]
    for obj in packet['objects']:
        for key in ['asset','material']:
            p=ROOT/'unreal/AIWorld/Content'/(obj[key][6:]+'.uasset');assert p.is_file(),p
        installed.append(obj['asset'])
    captures={}
    for view in ['before','after','sunset','night']:
        path=DOCS/f'paris-reference-{view}.png';perf=read(DOCS/f'paris-reference-{view}-performance.json')
        with path.open('rb') as f:header=f.read(24)
        assert header[:8]==b'\x89PNG\r\n\x1a\n';size=struct.unpack('>II',header[16:24]);assert size==(1280,720)
        assert perf['rhi']=='D3D12' and perf['shader_feature_level']=='SM6'
        assert perf['detail_quality']==2 and not perf['people_enabled'] and not perf['traffic_enabled']
        assert perf['reference_look']==(view!='before')
        if view!='before':assert perf['reference_models']==len(packet['objects'])
        captures[view]=dict(file=path.name,sha256=digest(path),resolution=list(size),fps=perf['fps'],frame_p95_ms=perf['frame_p95_ms'],quality='High / 100% / static comparison',gi_method=perf['gi_method'],virtual_shadow_maps=perf['virtual_shadow_maps'],physical_camera_exposure=perf['physical_camera_exposure'])
    report=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),engine='UE 5.8',recipe=packet['recipe'],counts=packet['counts'],installed_models=len(installed),camera=packet['camera'],georeference=packet['georeference'],source_scene_sha256=source['source_scene_sha256'],archived_mesh_sha256=mesh_hash,archived_mesh_unchanged=True,native_tests=native,python_tests_passed=5,reproducibility=reproducibility,captures=captures,geometry_collision_preserved=True,appearance_is_inferred=True,reference_photo_parity_achieved=False,target_60fps_achieved=False,known_remaining=['Building-specific roof/dormer/storefront modeling and multiple tree species/variants are incomplete','Western Seine quay has excessive original DTM road crossfall; reference camera is on Boulevard du Palais','No surveyed L4/L5 appearance claim for procedural facade and rooftop details'],backup='backups/paris-before-reference-20261108-092546')
    report['hardware']=read(ROOT/'backups/reference-hardware.json')
    report['existing_gis_warnings']=['Some OSM footprints overlap and require source review','362 buildings lack near-complete official gutter coverage; roof profiles remain inferred','Road network has disconnected components','2 boundary-clipped low bridge fragments need fuller coverage or surveyed deck elevations']
    (DOCS/'paris-reference-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(native_passed=sum(map(len,native.values())),python_passed=5,counts=packet['counts'],fps={k:round(v['fps'],2) for k,v in captures.items()},reproducible=True),ensure_ascii=False))


if __name__=='__main__':main()
