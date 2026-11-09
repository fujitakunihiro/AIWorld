"""Collect completed street-display checks and unmodified UE screenshots."""
import json,re,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]


def write(saved,backup):
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    assert 'Result: Succeeded' in (backup/'build.log').read_text(encoding='utf-8-sig')
    assert re.search(r'Ran 12 tests.*\bOK\b',(backup/'python-tests.log').read_text(encoding='utf-8-sig'),re.S)
    final=(backup/'final-props-tests.log').read_text(encoding='utf-8-sig');assert re.search(r'Ran 2 tests.*\bOK\b',final,re.S) and 'reproduce exactly' in final
    bake=(saved/'paris-luxury-bake.log').read_text(encoding='utf-8-sig');assert 'PARIS_LUXURY_ASSETS_READY' in bake and not re.search('LogPython: Error|LogMaterial: Error|LogEditorAssetSubsystem: Error',bake)
    native=(saved/'paris-street-props-automation.log').read_text(encoding='utf-8-sig');tests=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\}',native);assert len(tests)==11 and all(r=='Success' for r,_ in tests)
    d=read(ROOT/'unreal/AIWorld/Content/Data/paris-luxury.json');old=read(backup/'unreal/AIWorld/Content/Data/paris-luxury.json');models={o['id']:o for o in d['objects']};assert all(models[o['id']]==o for o in old['objects']);records={json.dumps(r,sort_keys=True) for r in d['records']};assert all(json.dumps(r,sort_keys=True) in records for r in old['records']);assert d['district_views']==old['district_views']
    for file in ('paris-weathering.json','paris-minimap.json'):
        assert read(ROOT/'unreal/AIWorld/Content/Data'/file)==read(backup/'unreal/AIWorld/Content/Data'/file)
    count=Counter(r['kind'] for r in d['records']);views={}
    for view in ('after','before','cafe','night'):
        name='paris-street-props-'+view;r=read(ROOT/'docs'/(name+'-performance.json'));log=(saved/(name+'.log')).read_text(encoding='utf-8-sig')
        assert (ROOT/'docs'/(name+'.png')).is_file() and not re.search('Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error',log)
        assert r['luxury_models']==77 and r['street_shop_displays']==count['street_display'] and r['street_terrace_parasols']==count['terrace_parasol'] and r['minimap_ready']
        assert r['street_prop_visible_parts']==(0 if view=='before' else 9)
        views[view]={k:r[k] for k in ('fps','frame_p95_ms','viewport_width','viewport_height','street_prop_visible_parts','minimap_ready')}
    result=dict(recipe=d['decoration_recipe'],source_scene_sha256=d['source_scene_sha256'],backup=str(backup.relative_to(ROOT)),build='Succeeded',bake='Succeeded',python_tests=12,targeted_rechecks=2,native_tests=[dict(name=n,result=r) for r,n in tests],counts=dict(count),display_types=dict(Counter(r['display_type'] for r in d['records'] if r['kind']=='street_display')),models=77,previous_68_models_preserved=True,previous_records_and_cameras_preserved=True,weathering_and_minimap_manifests_preserved=True,placement_inferred=True,rendered_views=views,frame_rate_target=60)
    (ROOT/'docs/paris-street-props-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(views,indent=2))


if __name__=='__main__':write(Path(sys.argv[1]),Path(sys.argv[2]).resolve())
