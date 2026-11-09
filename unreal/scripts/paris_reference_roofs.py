"""Inferred chimney stacks seated on eligible, archived flat roof triangles."""
import math
from pathlib import Path
import numpy as np
from shapely.geometry import Point,shape
from shapely.strtree import STRtree
from generate_paris_frontages import Mesh
from paris_district_layout import DTYPE


def add_roofs(result,scene,district):
    mesh=Mesh(bevel_cm=.4);o=[0,0,0];t=[1,0,0];n=[0,1,0]
    for z,size,c in [(38,[75,48,110],[192,182,160,255]),(96,[83,56,9],[141,141,131,255]),(-8,[85,58,12],[124,124,116,255])]:mesh.box(o,t,n,[0,0,z],size,c)
    for x in [-24,0,24]:
        # Hollow terracotta flues: outer wall, inner wall and a rim.
        for k in range(12):
            a=k*math.tau/12;b=(k+1)*math.tau/12;mid=(a+b)/2
            def p(angle,r,z):return [x+r*math.cos(angle),r*math.sin(angle),z]
            mesh.face([p(a,9,100),p(b,9,100),p(b,9,142),p(a,9,142)],[math.cos(mid),math.sin(mid),0],[158,91,58,255])
            mesh.face([p(a,6,142),p(b,6,142),p(b,6,116),p(a,6,116)],[-math.cos(mid),-math.sin(mid),0],[61,49,40,255])
            mesh.face([p(a,9,142),p(b,9,142),p(b,6,142),p(a,6,142)],[0,0,1],[174,106,70,255])
    model=mesh.item('roof_chimney','M_ParisLuxuryMarketSolid');model['asset']='/Game/ParisPhotoreal/Reference/SM_ParisReference_roof_chimney_'+model['geometry_sha256'][:12];result['objects'].append(model)
    permitted=set(result['building_ids']);features=[f for f in district['layers']['buildings'] if f['properties']['source_id'] in permitted];polys=[shape(f['geometry']) for f in features];tree=STRtree(polys);ox,oy=district['origin_projected_m'];blob=np.memmap(Path(__file__).resolve().parents[1]/'AIWorld/Content/Data/paris-digital-twin-meshes.bin',dtype='u1',mode='r');best={}
    for obj in scene['objects']:
        if obj['kind']!='roof':continue
        b=obj['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        for index,ids in enumerate(ix):
            if float(v['n'][ids[0],2])<.94:continue
            pts=v['p'][ids].astype(float);p=pts.mean(axis=0);area=abs(float(np.cross(pts[1]-pts[0],pts[2]-pts[0])[2]))*.5
            if area<30000:continue
            point=Point(ox+p[0]/100,oy-p[1]/100)
            for i in tree.query(point):
                if not polys[i].contains(point) or polys[i].boundary.distance(point)<1:continue
                sid=features[i]['properties']['source_id']
                if sid not in obj['properties']['source_ids']:continue
                candidate=(area,obj['id'],index,p.tolist())
                if sid not in best or candidate[:3]>best[sid][:3]:best[sid]=candidate
    for sid,(_,source,index,p) in sorted(best.items()):
        result['records'].append(dict(kind='roof_chimney',source_id=sid,source_mesh_id=source,source_triangle_index=index,anchor_cm=p,yaw_degrees=int(sid.split('/')[-1])%180,scale_xyz=[1,1,1],models=['roof_chimney'],placement_provenance='inferred chimney on archived flat roof; not surveyed rooftop equipment'))
    result['counts']['chimneys']=len(best)
