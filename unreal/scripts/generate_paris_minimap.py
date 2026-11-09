"""Offline vector minimap in the shared UE centimetre frame; no imagery or API."""
import json,sys
from pathlib import Path
import numpy as np
from shapely import constrained_delaunay_triangles,make_valid
from shapely.geometry import shape,box
from shapely.ops import transform
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data'


def generate():
    scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'))
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    ox,oy=district['origin_projected_m'];half=scene['extent_m']*50;clip=box(-half,-half,half,half)
    local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-ox)*100,-(np.asarray(y)-oy)*100),g)
    groups=[];features=[]
    for layer,color in [('water',[37,105,139]),('parks',[61,88,66]),('roads',[181,173,149]),('buildings',[105,123,133])]:
        triangles=[]
        for f in district['layers'].get(layer,[]):
            g=make_valid(local(shape(f['geometry']))).intersection(clip).simplify(25,preserve_topology=True)
            if g.is_empty or g.area<100:continue
            start=len(triangles)
            for tri in constrained_delaunay_triangles(g).geoms:
                if tri.area<1:continue
                triangles.append([[round(x,3),round(y,3)] for x,y in list(tri.exterior.coords)[:3]])
            if len(triangles)>start:features.append(dict(layer=layer,source_id=f['properties']['source_id'],triangle_start=start,triangle_count=len(triangles)-start))
        groups.append(dict(kind=layer,color=color,triangles_cm=triangles))
    return dict(format='paris_vector_minimap_v1',source_scene_sha256=scene['source_scene_sha256'],georeference=scene['georeference'],bounds_cm=[-half,-half,half,half],north='Lambert-93 grid north; UE negative Y',groups=groups,features=features,landmarks=scene['landmarks'],attribution='OpenStreetMap contributors / IGN / Ville de Paris')


if __name__=='__main__':
    d=generate();(DATA/'paris-minimap.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(dict(features=len(d['features']),triangles=sum(len(g['triangles_cm']) for g in d['groups']))))
