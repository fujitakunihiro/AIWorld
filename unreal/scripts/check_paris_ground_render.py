"""Compare saved UE RenderData with the archived terrain/surface coverage."""
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from generate_paris_ground_display import ROOT,FOLDER,input_meshes

data=json.loads((ROOT/'unreal/AIWorld/Saved/paris-v5-ground-render-data.json').read_text(encoding='utf-8'))
meta=json.loads((FOLDER/'paris-photo-ground.json').read_text(encoding='utf-8'))
if data['asset']!=meta['asset']:raise RuntimeError('Exported a different ground asset')
_,_,original,ids,coverage,_=input_meshes()
ps=np.array(data['positions_cm']);tri=ps[np.array(data['indices'])]
actual=unary_union([Polygon(t[:,:2]) for t in tri if Polygon(t[:,:2]).area>1.e-9])
full=unary_union([Polygon(t[:,:2]) for t in original['p'][ids]])
expected=full.difference(coverage);difference=actual.symmetric_difference(expected)
# A 0.5mm edge band bounds the float32 render packing, not GIS displacement.
outside_band=difference.difference(expected.boundary.buffer(.05))
old=original['p'][ids].astype('f8');a=old[:,0];u=old[:,1]-a;v=old[:,2]-a;den=u[:,0]*v[:,1]-u[:,1]*v[:,0]
z_error=0.
for p in ps[::113]:
    d=p[:2]-a[:,:2];s=(d[:,0]*v[:,1]-d[:,1]*v[:,0])/den;r=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/den
    hit=(s>=-1.e-5)&(r>=-1.e-5)&(s+r<=1.00001)
    if not hit.any():raise RuntimeError('Render vertex left original terrain')
    z=a[:,2]+s*u[:,2]+r*v[:,2];z_error=max(z_error,float(min(abs(z[hit]-p[2]))))
report=dict(asset=data['asset'],generated_triangles=meta['triangles'],render_triangles=data['render_triangles'],copied_render_triangles=len(tri),
    symmetric_difference_m2=difference.area/10000,area_difference_outside_0_5mm_edge_band_m2=outside_band.area/10000,
    max_sampled_z_error_cm=z_error,expected_area_m2=expected.area/10000,
    passed=outside_band.area/10000<.0001 and z_error<.02)
print(json.dumps(report,indent=2))
if not report['passed']:raise RuntimeError('UE ground render coverage/height contract failed')
