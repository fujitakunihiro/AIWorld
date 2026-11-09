"""Create original advertising props at archived OSM positions, entirely offline."""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'unreal/scripts'),str(ROOT/'gis')]
from generate_paris_frontages import Mesh
from paris_twin.coordinates import Georeference
from paris_twin.io import paths,read
from paris_twin.street_furniture import source_nodes
from paris_twin.terrain import Terrain

DATA=ROOT/'unreal/AIWorld/Content/Data'
GENERATED=ROOT/'unreal/assets/paris-morris/Generated/morris.json'
DTYPE=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])


def lathe(mesh,profile,color,sides=40):
    for (z0,r0),(z1,r1) in zip(profile,profile[1:]):
        for j in range(sides):
            a=j*math.tau/sides;b=(j+1)*math.tau/sides;m=(a+b)/2
            dz=z1-z0;dr=r1-r0
            normal=[math.cos(m)*dz,math.sin(m)*dz,-dr]
            length=math.sqrt(sum(v*v for v in normal))
            if length<1e-8:continue
            normal=[v/length for v in normal]
            points=[[r*math.cos(q),r*math.sin(q),z] for z,r,q in ((z0,r0,a),(z0,r0,b),(z1,r1,b),(z1,r1,a))]
            start=len(mesh.positions_cm)
            mesh.face(points,normal,color)
            # Smooth around the circumference while preserving the sharp
            # profile changes between mouldings and roof courses.
            for i in range(start,len(mesh.positions_cm)):
                p=mesh.positions_cm[i];radial=math.hypot(p[0],p[1])
                if radial>1e-6:mesh.normals[i]=[p[0]/radial*dz/length,p[1]/radial*dz/length,-dr/length]


def panel_cylinder(mesh,z0,z1,r,v0,v1,sides=64):
    for j in range(sides):
        a=j*math.tau/sides;b=(j+1)*math.tau/sides;m=(a+b)/2
        points=[[r*math.cos(q),r*math.sin(q),z] for z,q in ((z0,a),(z0,b),(z1,b),(z1,a))]
        mesh.face(points,[math.cos(m),math.sin(m),0],[255]*4,[(1-j/sides,v1),(1-(j+1)/sides,v1),(1-(j+1)/sides,v0),(1-j/sides,v0)])


def make_models():
    iron=Mesh();paper=Mesh();sign=Mesh();sign_paper=Mesh()
    green=[34,66,55,255];green_dark=[25,51,43,255];gold=[147,132,85,255]
    # Turned plinth, paper enclosure, frieze and domed cast-iron crown.
    lathe(iron,[(0,64),(3,70),(8,73),(13,73),(17,69),(22,69),(25,65),(39,65),(42,68),(46,68),(49,64)],green)
    lathe(iron,[(49,64),(52,66),(55,66),(58,63),(316,63),(319,67),(323,67),(326,63),(356,63),(359,68),(364,72),(370,72)],green_dark)
    panel_cylinder(paper,58,326,63.35,.071,1.)
    panel_cylinder(paper,326,356,63.35,0.,.071)
    for z,r in [(58,66),(190,65.5),(323,68),(357,69)]:
        lathe(iron,[(z-1.5,r-.5),(z-1,r),(z+1,r),(z+1.5,r-.5)],gold if z==357 else green)
    for j in range(8):
        a=j*math.tau/8;n=[math.cos(a),math.sin(a),0];t=[-math.sin(a),math.cos(a),0]
        iron.box([0,0,0],t,n,[0,64.5,192],[3.4,3.5,264],green)
        iron.box([0,0,0],t,n,[0,65,192],[.8,1,260],gold)
    lathe(iron,[(370,72),(373,78),(377,78),(381,73),(384,71),(390,69),(401,64),(414,53),(424,37),(430,20),(432,12),(435,9),(438,10),(441,14),(445,12),(449,6),(452,0)],green)
    lathe(iron,[(380,72.5),(381,73.5),(383,73.5),(384,72)],gold)
    # A separate two-sided public poster box, at its mapped ground support.
    t=[1,0,0];n=[0,1,0]
    sign.box([0,0,0],t,n,[0,0,35],[25,22,70],green_dark)
    sign.box([0,0,0],t,n,[0,0,171],[133,24,206],green)
    for y in [-12.4,12.4]:
        norm=[0,1 if y>0 else -1,0]
        pts=[[-58,y,78],[58,y,78],[58,y,264],[-58,y,264]]
        u0,u1=(.25,0) if y>0 else (0,.25)
        sign_paper.face(pts,norm,[255]*4,[(u0,.525),(u1,.525),(u1,.071),(u0,.071)])
        for x in [-61,61]:sign.box([0,0,0],t,n,[x,y,171],[3,2,192],gold)
        for z in [75,267]:sign.box([0,0,0],t,n,[0,y,z],[125,2,3],gold)
    result=[]
    for name,mesh,material in [('column_iron',iron,'M_ParisMorrisIron'),('column_paper',paper,'M_ParisMorrisPoster'),('sign_iron',sign,'M_ParisMorrisIron'),('sign_paper',sign_paper,'M_ParisMorrisPoster')]:
        item=mesh.item(name,material)
        item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Morris/SM_ParisMorris_')
        result.append(item)
    return result


def surface_query(scene,blob,x,y,radius):
    circle=Point(x,y).buffer(radius);masks={};heights=[]
    for obj in scene['objects']:
        kind=obj['kind']
        if kind not in ('ground','path','sidewalk','road','water','bridge'):continue
        b=obj['mesh_buffer'];verts=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        tris=verts['p'][ix]
        valid=(tris[:,:,0].min(axis=1)<=x+radius)&(tris[:,:,0].max(axis=1)>=x-radius)&(tris[:,:,1].min(axis=1)<=y+radius)&(tris[:,:,1].max(axis=1)>=y-radius)
        for tri in tris[valid].astype('f8'):
            polygon=Polygon(tri[:,:2])
            if polygon.area<1e-5 or not polygon.intersects(circle):continue
            masks.setdefault(kind,[]).append(polygon)
            a,b,c=tri;u=b-a;v=c-a;det=u[0]*v[1]-u[1]*v[0]
            dx=x-a[0];dy=y-a[1];s=(dx*v[1]-dy*v[0])/det;t=(u[0]*dy-u[1]*dx)/det
            if min(s,t,1-s-t)>=-1e-6:heights.append((kind,float(a[2]+s*u[2]+t*v[2])))
    cover={k:unary_union(polys).intersection(circle).area/circle.area for k,polys in masks.items()}
    return cover,heights


def generate():
    config=read(ROOT/'gis/config/ile_de_la_cite.json');geo=Georeference(config);terrain=Terrain(config,geo)
    raw=paths(config)['Raw'];nodes,snapshot=source_nodes(raw,read(raw/'manifest.json'))
    scene=read(DATA/'paris-digital-twin-runtime.json');blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r')
    district=read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
    from shapely.geometry import shape
    buildings=unary_union([shape(f['geometry']) for f in district['layers']['buildings']]);water=unary_union([shape(f['geometry']) for f in district['layers']['water']])
    nearby=[v for v in scene['pick_features'] if v['kind'] in ('street_tree','street_lamp','street_bench','street_bin','street_bicycle_rack') and 'point_cm' in v]
    records=[];rejected=[]
    for n in sorted(nodes,key=lambda n:n['id']):
        tags=n['tags'];kind='column' if tags.get('advertising')=='column' else 'sign' if tags.get('advertising')=='poster_box' and tags.get('support')=='ground' and tags.get('indoor')!='yes' else None
        if not kind:continue
        projected=geo.forward.transform(n['lon'],n['lat']);point=Point(projected)
        if not geo.extent.covers(point):continue
        x,y,_=geo.to_ue(n['lon'],n['lat']);radius=75 if kind=='column' else 68
        cover,heights=surface_query(scene,blob,x,y,radius)
        walkway=max(cover.get('path',0),cover.get('sidewalk',0));avoid=max(cover.get('road',0),cover.get('water',0),cover.get('bridge',0))
        clear_cover,_=surface_query(scene,blob,x,y,radius+100)
        clearance=max(clear_cover.get('path',0),clear_cover.get('sidewalk',0))
        nearest=min([math.dist([x,y],v['point_cm'][:2]) for v in nearby] or [1e9])
        path_heights=[h for k,h in heights if k in ('path','sidewalk')]
        reason=None
        if walkway<.98 or avoid>.01 or not path_heights:reason='footprint is not safely on a mapped walking surface'
        elif clearance<.9:reason='walking surface is too narrow around the prop'
        elif buildings.distance(point)<(radius+25)/100 or water.distance(point)<(radius+25)/100:reason='too close to mapped building or water'
        elif nearest<radius+65:reason='too close to existing street furniture'
        if reason:rejected.append(dict(source_id='osm/node/'+str(n['id']),reason=reason));continue
        z=max(path_heights)
        # A present surface may differ from the DEM by a few centimetres.
        # Anchor on the highest nearby mapped ground or walking-surface mesh.
        z=max([z]+[h for k,h in heights if k=='ground'])-.8
        bearing=tags.get('direction','0').split(';')[0]
        try:yaw=float(bearing)-180 if kind=='sign' else (int(n['id'])%8)*45
        except ValueError:yaw=0
        records.append(dict(source_id='osm/node/'+str(n['id']),kind=kind,position_provenance='mapped_osm_node',appearance_provenance='original_inferred_design',wgs84=[n['lon'],n['lat']],anchor_cm=[round(x,4),round(y,4),round(z,4)],yaw_degrees=yaw,footprint_radius_cm=radius,path_coverage=round(walkway,5),one_metre_clearance_coverage=round(clearance,5),nearest_furniture_cm=round(nearest,2),building_distance_m=round(buildings.distance(point),3),water_distance_m=round(water.distance(point),3),source_tags=tags))
    if not any(r['kind']=='column' for r in records):raise RuntimeError('No valid mapped advertising column positions')
    # Select a clear outdoor eye-height view for an automated visual check.
    ref=next((r for r in records if r['source_id']=='osm/node/9693401739'),records[0]);x,y,z=ref['anchor_cm'];reference=Point(geo.origin[0]+x/100,geo.origin[1]-y/100)
    inspection=None
    for angle in [45,135,90,0,180,270,225,315]:
        a=math.radians(angle);ex=x+850*math.cos(a);ey=y+850*math.sin(a);p=Point(geo.origin[0]+ex/100,geo.origin[1]-ey/100)
        cover,hs=surface_query(scene,blob,ex,ey,35)
        if buildings.distance(p)<.8 or water.distance(p)<.8 or buildings.intersects(LineString([p,reference])):continue
        sight=LineString([(ex,ey),(x,y)])
        if any(sight.distance(Point(v['point_cm'][:2]))<(90 if v['kind']=='street_tree' else 60) for v in nearby):continue
        if max(cover.get('path',0),cover.get('sidewalk',0))<.8 or cover.get('road',0)>.01:continue
        height=max([v for k,v in hs if k in ('path','sidewalk','ground')] or [z]);inspection=dict(source_id=ref['source_id'],eye_cm=[round(ex,3),round(ey,3),round(height+170,3)],target_cm=[x,y,z+210]);break
    if not inspection:raise RuntimeError('No safe outdoor inspection camera')
    texture=ROOT/'unreal/assets/paris-morris/Source/paris-morris-posters-imagegen.png'
    if not texture.is_file():raise RuntimeError('Missing original poster texture')
    return dict(format='paris_morris_props_v1',source_scene_sha256=scene['source_scene_sha256'],source_snapshot=snapshot,source_license='OpenStreetMap contributors, ODbL 1.0',texture_sha256=hashlib.sha256(texture.read_bytes()).hexdigest(),appearance_provenance='Original fictional posters and inferred Paris-style prop geometry; no surveyed appearance claim.',records=records,rejected=rejected,inspection_camera=inspection,objects=make_models())


if __name__=='__main__':
    result=generate();GENERATED.parent.mkdir(parents=True,exist_ok=True)
    GENERATED.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'columns':sum(r['kind']=='column' for r in result['records']),'signs':sum(r['kind']=='sign' for r in result['records']),'rejected':result['rejected'],'triangles':sum(o['triangles'] for o in result['objects'])}))
