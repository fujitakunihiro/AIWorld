"""Record only completed build, tests and fresh GPU captures."""
import json,re,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]


def write(saved,backup):
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    build=(backup/'build.log').read_text(encoding='utf-8-sig');python=(backup/'python-tests.log').read_text(encoding='utf-8-sig');bake=(saved/'paris-weathering-bake.log').read_text(encoding='utf-8-sig')
    assert 'Result: Succeeded' in build
    assert re.search(r'Ran 6 tests.*\bOK\b',python,re.S) and 'FAILED' not in python
    assert 'PARIS_WEATHERING_ASSETS_READY' in bake and not re.search('LogPython: Error|LogMaterial: Error',bake)
    (backup/'bake-full.log').write_text(bake,encoding='utf-8')
    native=(saved/'paris-weathering-automation.log').read_text(encoding='utf-8-sig');results=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\}',native)
    assert len(results)==10 and all(r=='Success' for r,_ in results)
    data=read(ROOT/'unreal/AIWorld/Content/Data/paris-weathering.json');previous=read(backup/'unreal/AIWorld/Content/Data/paris-weathering.json');mapdata=read(ROOT/'unreal/AIWorld/Content/Data/paris-minimap.json')
    assert data['source_scene_sha256']==previous['source_scene_sha256']==mapdata['source_scene_sha256']
    assert data['records'][:len(previous['records'])]==previous['records'];assert data['objects'][:2]==previous['objects']
    assert read(ROOT/'unreal/AIWorld/Content/Data/paris-luxury.json')==read(backup/'unreal/AIWorld/Content/Data/paris-luxury.json')
    views={}
    for view in ('street','close','before','walk'):
        name='paris-grime-map-'+view;log=(saved/(name+'.log')).read_text(encoding='utf-8-sig');r=read(ROOT/'docs'/(name+'-performance.json'))
        assert 'PARIS_TWIN_READY' in log and not re.search('Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error|Fatal error',log)
        assert (ROOT/'docs'/(name+'.png')).is_file();assert r['minimap_ready'] and r['minimap_triangles']==sum(len(g['triangles_cm']) for g in mapdata['groups'])
        assert r['weathering_components']==(0 if view=='before' else len(data['objects']))
        if view=='walk':assert r['walking'] and r['third_person'] and r['minimap_observer']=='現在地'
        views[view]={key:r[key] for key in ('fps','frame_p95_ms','viewport_width','viewport_height','weathering_components','weathering_visible','minimap_ready','minimap_triangles','minimap_observer','walking','third_person')}
    result=dict(recipe=data['recipe'],source_scene_sha256=data['source_scene_sha256'],backup=str(backup.relative_to(ROOT)),build='Succeeded',bake='Succeeded',python_tests=6,native_tests=[dict(name=n,result=r) for r,n in results],counts=dict(Counter(r['kind'] for r in data['records'])),mesh_groups=len(data['objects']),minimap_triangles=sum(len(g['triangles_cm']) for g in mapdata['groups']),previous_core_geometry_preserved=True,previous_core_records_preserved=True,festival_manifest_preserved=True,coordinate_frame='Shared EPSG:2154 origin; UE cm; X east, Y south',decoration_inferred=True,rendered_views=views,frame_rate_target=60)
    (ROOT/'docs/paris-grime-map-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(views,ensure_ascii=False,indent=2))


if __name__=='__main__':write(Path(sys.argv[1]),Path(sys.argv[2]).resolve())
