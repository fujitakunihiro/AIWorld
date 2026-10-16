"""Read-only diagnosis of actual exported mesh counts and local render setup."""
import collections
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def diagnose():
    scene=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json').read_text(encoding='utf-8-sig'))
    landmark=next(x for x in scene['landmarks'] if x['name']=='Notre-Dame');sid=landmark['source_id']
    feature=next(x for x in scene['pick_features'] if x['id']==sid)
    triangles=vertices=0
    for obj in scene['objects']:
        if obj['kind']!='building':continue
        for span in obj.get('appearance_ranges',[]):
            if span['source_id']!=sid:continue
            a,b=span['start'],span['start']+span['count'];vertices+=span['count']
            triangles+=sum(all(a<=v<b for v in obj['indices'][i:i+3]) for i in range(0,len(obj['indices']),3))
    result=dict(format='paris_scene_diagnosis_v1',source_id=sid,notre_dame_body_triangles=triangles,
        notre_dame_body_vertices=vertices,notre_dame_properties=feature['properties'],
        footprint_cm=feature['polygons_cm'],landmark=landmark,georeference=scene['georeference'],
        scene_triangles=sum(len(o['indices'])//3 for o in scene['objects']),
        mesh_kind_counts=dict(collections.Counter(o['kind'] for o in scene['objects'])),
        mesh_generation='GIS footprint gutter walls and inferred roofs; no cathedral-specific mesh',
        current_quality_center_cm=scene['quality_centre_ue_cm'],
        imported_landmark_assets=[str(p.relative_to(ROOT)) for p in (ROOT/'unreal/AIWorld/Content').rglob('*NotreDame*.uasset')])
    target=ROOT/'docs/paris-v2-diagnosis-geometry.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['source_id','notre_dame_body_triangles','notre_dame_body_vertices','scene_triangles','imported_landmark_assets']}))


if __name__=='__main__':diagnose()
