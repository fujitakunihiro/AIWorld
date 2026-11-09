"""Collect completed checks and rendered performance; never infer test success."""
import json,re,sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def write(saved,backup):
    d=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-luxury.json').read_text(encoding='utf-8'))
    party_mode=d['decoration_recipe']=='paris_festival_party_v8';realism_mode=party_mode or d['decoration_recipe']=='paris_street_realism_v7';warm_mode=realism_mode or d['decoration_recipe']=='paris_warm_windows_v6';garland_mode=warm_mode or d['decoration_recipe']=='paris_street_garlands_v5';expected_tests=11 if party_mode else 10 if realism_mode else 9 if warm_mode else 8 if garland_mode else 7
    if party_mode:
        final_mesh=(backup/'final-mesh-tests.log').read_text(encoding='utf-8-sig')
        if not re.search(r'Ran 2 tests.*\bOK\b',final_mesh,re.S) or 'original 59 mesh buffers unchanged' not in final_mesh:raise RuntimeError('Final wire mesh validation has not passed')
    python=(backup/'python-tests.log').read_text(encoding='utf-8-sig')
    if not re.search(r'Ran '+str(expected_tests)+r' tests.*\bOK\b',python,re.S):raise RuntimeError('Python tests have not passed')
    build=(backup/('build.log' if garland_mode else 'build-final.log')).read_text(encoding='utf-8-sig')
    if 'Result: Succeeded' not in build:raise RuntimeError('Native build has not passed')
    if party_mode:
        bake=(backup/'bake.log').read_text(encoding='utf-8-sig')
        if 'PARIS_LUXURY_ASSETS_READY' not in bake or re.search('LogPython: Error|LogMaterial: Error|LogEditorAssetSubsystem: Error',bake):raise RuntimeError('Festival asset bake has not passed')
    if garland_mode:
        if 'Verified preservation of every previous window decoration' not in python:raise RuntimeError('Preservation check has not passed')
        previous=json.loads((backup/'unreal/AIWorld/Content/Data/paris-luxury.json').read_text(encoding='utf-8'))
        models={o['id']:o for o in d['objects']}
        if not all(models.get(o['id'])==o for o in previous['objects']):raise RuntimeError('An existing mesh changed')
        current_records={json.dumps(r,sort_keys=True) for r in d['records']}
        if not all(json.dumps(r,sort_keys=True) in current_records for r in previous['records']):raise RuntimeError('An existing decoration moved or changed')
    elif 'Verified unchanged GIS records, all 45 mesh hashes' not in (backup/'manifest-refresh.log').read_text(encoding='utf-8-sig'):raise RuntimeError('Camera-only refresh has not been verified')
    native=(saved/'paris-luxury-automation.log').read_text(encoding='utf-8-sig')
    results=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\}',native)
    if len(results)!=(9 if party_mode else 8 if realism_mode else 6) or any(result!='Success' for result,_ in results):raise RuntimeError('UE tests have not passed')
    views={}
    names=['paris-party-night','paris-party-baseline-night','paris-party-sunset','paris-party-overview-night'] if party_mode else ['paris-realism-after','paris-realism-sunset','paris-realism-night','paris-realism-overview-after'] if realism_mode else ['paris-window-lights-after','paris-window-lights-sunset','paris-window-lights-night','paris-window-lights-overview-night'] if warm_mode else ['paris-garlands-after','paris-garlands-night','paris-garlands-overview-after'] if garland_mode else ['paris-district-after','paris-district-night','paris-district-northwest-after','paris-district-northwest-night','paris-district-southwest-after']
    for name in names:
        log=(saved/(name+'.log')).read_text(encoding='utf-8-sig')
        if re.search('Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error',log):raise RuntimeError('Material compilation failed in '+name)
        r=json.loads((ROOT/'docs'/(name+'-performance.json')).read_text(encoding='utf-8-sig'))
        if r.get('luxury_models')!=len(d['objects']) or r.get('luxury_canopies')!=395:raise RuntimeError('Stale scene capture '+name)
        if garland_mode and (r.get('luxury_upper_windows')!=2400 or r.get('luxury_street_garlands')!=47):raise RuntimeError('Missing v5 decoration '+name)
        if warm_mode and r.get('luxury_lit_windows')!=sum(item['kind']=='night_window' for item in d['records']):raise RuntimeError('Missing warm window layer '+name)
        if realism_mode and r.get('luxury_relief_windows')!=sum(item['kind']=='facade_relief' for item in d['records']):raise RuntimeError('Missing relief layer '+name)
        if party_mode:
            active=name!='paris-party-baseline-night'
            if r.get('festival_enabled')!=active or (r.get('festival_visible_parts')!=9 if active else r.get('festival_visible_parts')!=0):raise RuntimeError('Festival visibility does not match the capture '+name)
            if r.get('night_light_pool')!=34:raise RuntimeError('Festival expanded the fixed light pool')
        if not (ROOT/'docs'/(name+'.png')).is_file():raise RuntimeError('Missing screenshot '+name)
        views[name]=dict(fps=r['fps'],frame_p95_ms=r['frame_p95_ms'],width=r['viewport_width'],height=r['viewport_height'],quality=r['detail_quality'],material_compilation_errors=0)
        if realism_mode:views[name].update(skeletal_humans=r['pedestrians_skeletal'],skeletal_budget=r['human_skeletal_budget'])
        if party_mode:views[name].update(festival_enabled=r['festival_enabled'],festival_visible_parts=r['festival_visible_parts'],night_light_pool=r['night_light_pool'],active_night_lights=r['night_active_lights'])
    windows=[r for r in d['records'] if r['kind']=='window']
    report=dict(recipe=d['decoration_recipe'],source_scene_sha256=d['source_scene_sha256'],backup=str(backup.relative_to(ROOT)),build='Succeeded',python_tests=expected_tests,native_tests=[dict(name=name,result=result) for result,name in results],counts=dict(Counter(r['kind'] for r in d['records'])),models=len(d['objects']),window_buildings=len({r['source_id'] for r in windows}),existing_planters_reused=sum(r['uses_existing_planter'] for r in windows),hanging_baskets=sum(r.get('hanging_baskets',0) for r in d['records']),coverage=d['coverage'],district_views=d['district_views'],previous_window_decoration_preserved=garland_mode,camera_only_refresh_verified=not garland_mode,rendered_views=views,inferred_decoration=True,frame_rate_target=60)
    if garland_mode:
        spans=[r for r in d['records'] if r['kind']=='street_garland'];report.update(previous_models_preserved=True,previous_records_preserved=True,overhead_flags=sum(r['flags'] for r in spans),overhead_bulbs=sum(r['bulbs'] for r in spans),minimum_overhead_clearance_cm=min(r['minimum_clearance_cm'] for r in spans))
    if warm_mode:
        lights=[r for r in d['records'] if r['kind']=='night_window'];report.update(lit_windows=len(lights),lit_window_buildings=len({r['source_id'] for r in lights}),daytime_overlay_masked=True,occupancy_inferred=True)
    if realism_mode:report.update(relief_windows=sum(item['kind']=='facade_relief' for item in d['records']))
    if party_mode:
        spans=[r for r in d['records'] if r['kind']=='party_canopy'];report.update(festival_lanterns=sum(r['lanterns'] for r in spans),festival_fairy_lights=sum(r['fairy_lights'] for r in spans),festival_minimum_clearance_cm=min(r['minimum_clearance_cm'] for r in spans),normal_mode_restoration_tested=True,fixed_night_light_pool=34)
    out=ROOT/('docs/paris-party-validation.json' if party_mode else 'docs/paris-realism-validation.json' if realism_mode else 'docs/paris-window-lights-validation.json' if warm_mode else 'docs/paris-garlands-validation.json' if garland_mode else 'docs/paris-district-validation.json');out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report['rendered_views'],indent=2))


if __name__=='__main__':write(Path(sys.argv[1]),Path(sys.argv[2]).resolve())
