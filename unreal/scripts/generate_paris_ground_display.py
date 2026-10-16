"""Remove covered terrain only from rendering, preserving the archived GIS.

Independent terrain/road triangulations interpolate the same DEM differently.
The original terrain sometimes protrudes a few cm through mapped roads. Cut
its display below the exact planar road/sidewalk/park/water mesh coverage;
neither the source triangles nor physics / WGS84 data are modified.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/AIWorld/Content/Data'
KINDS={'road','sidewalk','path','park','water','bridge'}
DTYPE=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])


def input_meshes():
    scene=json.loads((FOLDER/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    blob=np.memmap(FOLDER/'paris-digital-twin-meshes.bin',dtype='u1',mode='r')
    def read(o):
        b=o['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ids=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        return v,ids
    source=next(o for o in scene['objects'] if o['kind']=='ground');verts,ids=read(source)
    cover=[];source_ids=[]
    for o in scene['objects']:
        if o['kind'] not in KINDS:continue
        v,ix=read(o)
        for t in v['p'][ix]:
            pg=Polygon(t[:,:2])
            if pg.area>1.e-6:cover.append(pg)
        source_ids.append(o['id'])
    return scene,source,verts,ids,unary_union(cover),source_ids


def generate():
    scene,source,vertices,ids,coverage,source_ids=input_meshes()
    positions=[];normals=[];indices=[];original_area=0.;remaining_area=0.
    for index in ids:
        tri=vertices['p'][index].astype('f8');pg=Polygon(tri[:,:2]);original_area+=pg.area
        visible=pg.difference(coverage);remaining_area+=visible.area
        if visible.is_empty:continue
        u=tri[1]-tri[0];v=tri[2]-tri[0];den=u[0]*v[1]-u[1]*v[0]
        if abs(den)<1.e-9:continue
        n=vertices['n'][index[0]].astype('f8');n/=np.linalg.norm(n)
        parts=sorted(shapely.constrained_delaunay_triangles(visible).geoms,key=lambda p:p.normalize().wkb_hex)
        for t in parts:
            coords=list(t.exterior.coords)[:-1]
            if t.area<1.e-8:continue
            start=len(positions)
            for x,y in coords:
                dx,dy=x-tri[0,0],y-tri[0,1];s=(dx*v[1]-dy*v[0])/den;r=(u[0]*dy-u[1]*dx)/den
                positions.append([round(x,6),round(y,6),round(float(tri[0,2]+s*u[2]+r*v[2]),6)]);normals.append(n.tolist())
            a,b,c=positions[-3:];cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            indices.extend([start,start+2,start+1] if cross*n[2]>0 else [start,start+1,start+2])
    color=''.join(f'{c:02x}' for c in vertices['c'][0][:3])
    mesh=dict(positions_cm=positions,normals=normals,indices=indices,color=color)
    sha=hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(format='paris_covered_terrain_display_v1',source_scene_sha256=scene['source_scene_sha256'],
        geometry_sha256=sha,asset='/Game/ParisPhotoreal/Ground/SM_ParisTerrainCut_'+sha[:12],
        source_terrain_id=source['id'],coverage_mesh_ids=source_ids,coverage_kinds=sorted(KINDS),
        original_area_m2=original_area/10000,visible_area_m2=remaining_area/10000,
        geometry_provenance='Original terrain clipped only for display below exact existing surface coverage; all source GIS and collision retained. No artificial Z offset.',
        triangles=len(indices)//3,**mesh)


if __name__=='__main__':
    result=generate();(FOLDER/'paris-photo-ground-source.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['triangles','original_area_m2','visible_area_m2','geometry_sha256']}))
