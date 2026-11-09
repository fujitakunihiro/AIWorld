"""Collect completed lane-study checks and actual UE images."""
import hashlib,json,re,struct
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data';SAVED=ROOT/'unreal/AIWorld/Saved';DOCS=ROOT/'docs'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    packet=read(DATA/'paris-lane.json');base=read(DATA/'paris-reference.json');assert packet['georeference']==base['georeference'];assert packet['records'][:len(base['records'])]==base['records']
    tests=(ROOT/'backups/lane-python-tests.log').read_text(encoding='utf-8-sig');assert 'Ran 5 tests' in tests and '\nOK' in tests
    build=(ROOT/'backups/lane-build.log').read_text(encoding='utf-8-sig');assert 'Result: Succeeded' in build
    bake=(ROOT/'backups/lane-bake.log').read_text(encoding='utf-8-sig');assert 'PARIS_LANE_ASSETS_READY' in bake and 'Success - 0 error(s)' in bake
    native={}
    for filename,count in [('paris-reference-regression-automation.log',11),('paris-reference-reference-automation.log',1),('paris-lane-automation.log',1)]:
        text=(SAVED/filename).read_text(encoding='utf-8-sig');results=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\}',text);assert len(results)==count and all(s=='Success' for s,_ in results),filename;native[filename]=[n for _,n in results]
    for item in packet['objects']:
        for key in ['asset','material']:assert (ROOT/'unreal/AIWorld/Content'/(item[key][6:]+'.uasset')).is_file(),item[key]
    captures={}
    for name in ['before','after','rain','night']:
        p=DOCS/f'paris-lane-{name}.png';perf=read(DOCS/f'paris-lane-{name}-performance.json')
        with p.open('rb') as f:h=f.read(24)
        assert struct.unpack('>II',h[16:24])==(1280,720);assert perf['rhi']=='D3D12' and perf['shader_feature_level']=='SM6' and perf['lane_look'];assert perf['lane_baseline']==(name=='before');assert not perf['people_enabled'] and not perf['traffic_enabled'];assert perf['lane']==packet['lane']
        captures[name]=dict(file=p.name,sha256=sha(p),fps=perf['fps'],frame_p95_ms=perf['frame_p95_ms'],quality='High / 100% / 1280x720 / static comparison')
    source_mesh_hash=sha(DATA/'paris-digital-twin-meshes.bin');assert source_mesh_hash==read(DATA/'paris-road-detail.json')['source_mesh_sha256']
    result=dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),recipe=packet['recipe'],street=packet['lane'],camera=packet['camera'],georeference=packet['georeference'],source_scene_sha256=packet['source_scene_sha256'],source_geometry_unchanged=True,source_mesh_sha256=source_mesh_hash,base_reference_records_preserved=True,python_tests=5,native_tests=native,regeneration_test_passed=True,generated_sha256=sha(ROOT/'unreal/assets/paris-lane/Generated/lane.json'),captures=captures,installed_models=len(packet['objects']),reference_photo_parity_achieved=False,parking_occupancy_and_design_inferred=True,actual_laying_pattern_not_surveyed=True,target_60fps_achieved=False,backup=(ROOT/'backups/current-lane-backup.txt').read_text(encoding='utf-8-sig').strip())
    (DOCS/'paris-lane-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(python_passed=5,native_passed=sum(map(len,native.values())),fps={k:round(v['fps'],2) for k,v in captures.items()},bicycles=packet['lane']['bicycles'],storefronts=packet['lane']['storefronts']),ensure_ascii=False))
if __name__=='__main__':main()
