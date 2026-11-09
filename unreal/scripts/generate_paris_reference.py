"""Offline, source-aligned architectural completion for a natural Paris street.

Decorative style is inferred. The archived GIS envelope, roads and heights are
never regenerated. Each attachment retains its source mesh/quad and OSM ID.
"""
import hashlib,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from shapely.geometry import Point,shape
from generate_paris_frontages import Mesh
from paris_district_layout import DTYPE,district_windows

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'unreal/AIWorld/Content/Data'
OUTPUT=ROOT/'unreal/assets/paris-reference/Generated/reference.json'
RECIPE='paris_reference_architecture_v1'


def reference_camera(scene,district):
    from generate_paris_luxury import Surfaces
    road=next(f for f in district['layers']['roads'] if f['properties']['source_id']=='osm/way/123461253')
    line=shape(road['properties']['source_geometry_projected']);ox,oy=district['origin_projected_m']
    # Keep the original upgrade neighborhood, but inspect its flatter upper
    # street. The western riverside DTM currently has an excessive crossfall.
    neighborhood=next(f for f in district['layers']['roads'] if f['properties']['source_id']=='osm/way/4040038')
    region=shape(neighborhood['properties']['source_geometry_projected']).interpolate(.87,normalized=True)
    eye=line.interpolate(.20,normalized=True);target=line.interpolate(.88,normalized=True)
    x,y=(eye.x-ox)*100,(oy-eye.y)*100
    _,heights=Surfaces(scene).query(x,y,25);ground=max(z for k,z in heights if k in ('road','ground','sidewalk'))
    camera=dict(name='Boulevard du Palais / natural street',source_id=road['properties']['source_id'],eye_cm=[x,y,ground+170],target_cm=[(target.x-ox)*100,(oy-target.y)*100,ground+350],eye_height_cm=170,ground_cm=ground)
    return camera,[(region.x-ox)*100,(oy-region.y)*100]


def item(mesh,name,material):
    result=mesh.item(name,material)
    result['asset']='/Game/ParisPhotoreal/Reference/SM_ParisReference_'+name+'_'+result['geometry_sha256'][:12]
    return result


def prototypes():
    stone=Mesh(bevel_cm=.65);iron=Mesh();origin=[0,0,0];t=[1,0,0];n=[0,1,0]
    # One balcony follows the slab already present under an inferred window.
    # Outward offsets are relative to the archived window (9cm off the wall).
    stone.box(origin,t,n,[0,22,-101.5],[176,66,13],[215,207,188,255])
    stone.box(origin,t,n,[0,21,-111],[166,61,6],[196,188,170,255])
    for x in [-59,59]:
        stone.box(origin,t,n,[x,10,-122],[12,34,20],[202,194,175,255])
        stone.box(origin,t,n,[x,1,-133],[10,18,8],[191,183,165,255])
    metal=[42,46,44,255]
    for y,z,width,depth,h in [(54,1,178,3.5,4.5),(54,-89,174,2.8,3),(54,-38,174,2,2)]:
        iron.box(origin,t,n,[0,y,z],[width,depth,h],metal)
    for x in [-86,86]:
        iron.box(origin,t,n,[x,24,1],[3.5,64,4.5],metal)
        iron.box(origin,t,n,[x,24,-89],[2.8,64,3],metal)
        for y in [-5,14,34,54]:iron.tube([x,y,-95],[x,y,1],1.25,metal,6)
    for i in range(13):
        x=-81+i*13.5
        iron.tube([x,54,-95],[x,54,1],.95,metal,6)
    # Restrained wrought-iron scrolls, rather than flat black decal bars.
    for x in [-54,-27,0,27,54]:
        for sign in [-1,1]:
            points=[[x+sign*(6+5*math.cos(a)),54,-64+18*math.sin(a)] for a in np.linspace(-math.pi/2,math.pi/2,12)]
            for a,b in zip(points,points[1:]):iron.tube(a,b,.8,metal,5)
    header=Mesh(bevel_cm=.45)
    for z,w,d,h,y in [(96,125,20,7,4),(103,137,26,6,7),(108,143,30,4,9)]:header.box(origin,t,n,[0,y,z],[w,d,h],[219,211,192,255])
    for x in [-49,49]:
        header.box(origin,t,n,[x,3,87],[10,18,13],[202,194,175,255])
    return [item(stone,'balcony_stone','M_ParisReferenceStone'),item(iron,'balcony_iron','M_ParisCastIron'),item(header,'window_header','M_ParisReferenceStone')]


def add_entries(result,scene,district):
    """Replace flat ground-floor door fronts with panels at the same source pose."""
    stone=Mesh(bevel_cm=.6);wood=Mesh(bevel_cm=.25);iron=Mesh();o=[0,0,0];t=[1,0,0];n=[0,1,0];paint=[44,58,54,255];c=[218,210,192,255]
    for x in [-74,74]:stone.box(o,t,n,[x,-4,5],[16,32,270],c)
    for z,w,d,h,y in [(135,178,32,18,0),(152,172,28,16,0),(166,186,40,14,4),(176,192,46,6,7)]:stone.box(o,t,n,[0,y,z],[w,d,h],c)
    wood.box(o,t,n,[0,2,0],[130,5,258],paint)
    for x in [-62,0,62]:wood.box(o,t,n,[x,6,0],[5,5,258],paint)
    for side in [-1,1]:
        for z,h in [(-97,40),(-37,46),(74,90)]:
            x=side*32.5;wood.box(o,t,n,[x,5,z],[48,2.4,h],[35,47,43,255])
            for dx in [-1,1]:wood.box(o,t,n,[x+dx*24,7,z],[3.5,3,h+4],paint)
            for dz in [-1,1]:wood.box(o,t,n,[x,7,z+dz*h/2],[51,3,3.5],paint)
        iron.box(o,t,n,[side*10,10,-25],[5,2,24],[48,50,46,255]);iron.tube([side*10,12,-33],[side*10,16,-33],.8,[48,50,46,255]);iron.tube([side*10,16,-33],[side*10,16,-17],.8,[48,50,46,255])
    result['objects'] += [item(stone,'door_stone','M_ParisReferenceStone'),item(wood,'door_joinery','M_ParisWindowPaintedWood'),item(iron,'door_handles','M_ParisCastIron')]
    ids=set(result['building_ids']);buildings={f['properties']['source_id']:shape(f['geometry']) for f in district['layers']['buildings'] if f['properties']['source_id'] in ids};ox,oy=district['origin_projected_m'];eye=result['upgrade_center_cm'];blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');seen=set();count=0
    core=json.loads((DATA/'paris-photo-frontages-source.json').read_text(encoding='utf-8'));existing={(r['source_mesh_id'],r['source_quad_index']) for r in core['entrances']}
    for obj in scene['objects']:
        if obj['kind']!='facade_wood':continue
        b=obj['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']);possible=[sid for sid in obj['properties']['source_ids'] if sid in ids]
        for k in range(0,len(ix),6):
            if (obj['id'],k//6) in existing:continue
            q=np.unique(ix[k:k+6])
            if len(q)!=4:continue
            pts=v['p'][q].astype(float);n=v['n'][q[0]].astype(float)
            if abs(n[2])>.001 or math.hypot(*n[:2])<.99:continue
            p=pts.mean(axis=0);t=np.array([n[1],-n[0],0]);w=float(np.ptp((pts-p)@t));h=float(np.ptp(pts[:,2]))
            if not(129<w<131 and 257<h<259) or math.dist(p[:2],eye[:2])>=result['radius_m']*100:continue
            key=tuple(round(v,2) for v in list(p)+list(n))
            if key in seen:continue
            wall=Point(ox+(p[0]-n[0]*30.75)/100,oy-(p[1]-n[1]*30.75)/100);candidates=[(buildings[sid].boundary.distance(wall),sid) for sid in possible]
            if not candidates:continue
            distance,sid=min(candidates)
            if distance>.06:continue
            seen.add(key);count+=1;result['records'].append(dict(kind='entrance_architecture',anchor_cm=p.tolist(),yaw_degrees=math.degrees(math.atan2(-n[0],n[1])),scale_xyz=[w/130,1,h/258],models=['door_stone','door_joinery','door_handles'],source_id=sid,source_mesh_id=obj['id'],source_quad_index=k//6,boundary_error_m=distance))
    result['counts']['entrances']=count


def generate(output=OUTPUT,camera_region=None,radius_cm=18000):
    scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'))
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    windows,allowed=district_windows(scene['source_scene_sha256'])
    buildings={f['properties']['source_id']:shape(f['geometry']) for f in district['layers']['buildings'] if f['properties']['source_id'] in allowed}
    ox,oy=district['origin_projected_m']
    camera,region=camera_region or reference_camera(scene,district);x,y=region
    # Upgrade a continuous 360m neighborhood around the inspection street.
    selected=[w for w in windows if math.dist(w['centre_cm'][:2],[x,y])<radius_cm]
    records=[];attachments=[];columns=defaultdict(list)
    for w in selected:
        p=w['centre_cm'];n=w['normal'];columns[(w['source_id'],round(p[0]),round(p[1]),round(n[0],3),round(n[1],3))].append(w)
    balcony_keys=set()
    for column in columns.values():
        column.sort(key=lambda w:w['centre_cm'][2])
        if len(column)>=3:
            for w in [column[1],column[-1]]:balcony_keys.add((w['source_mesh_id'],w['source_quad_index']))
    for w in selected:
        n=w['normal'];models=['window_header']
        if (w['source_mesh_id'],w['source_quad_index']) in balcony_keys:models+=['balcony_stone','balcony_iron']
        records.append(dict(kind='window_architecture',anchor_cm=w['centre_cm'],yaw_degrees=math.degrees(math.atan2(-n[0],n[1])),scale_xyz=[w['width_cm']/90,1,w['height_cm']/165],models=models,source_id=w['source_id'],source_mesh_id=w['source_mesh_id'],source_quad_index=w['source_quad_index']))
    # Trace existing cornice front faces; do not choose an invented eave height.
    blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');tiles={};seen=set()
    for obj in scene['objects']:
        if obj['kind']!='facade_trim':continue
        b=obj['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count'])
        possible=[sid for sid in obj['properties']['source_ids'] if sid in buildings]
        for k in range(0,len(ix),6):
            ids=np.unique(ix[k:k+6])
            if len(ids)!=4:continue
            pts=v['p'][ids].astype(float);n=v['n'][ids[0]].astype(float)
            if abs(n[2])>.001 or math.hypot(*n[:2])<.99:continue
            p=pts.mean(axis=0)
            if math.dist(p[:2],[x,y])>=radius_cm:continue
            t=np.array([n[1],-n[0],0]);width=float(np.ptp((pts-p)@t));height=float(np.ptp(pts[:,2]))
            if not(width>150 and 20<height<23):continue
            key=tuple(round(q,2) for q in list(p)+list(n))
            if key in seen:continue
            wall=Point(ox+(p[0]-n[0]*24)/100,oy-(p[1]-n[1]*24)/100)
            candidates=[(buildings[sid].boundary.distance(wall),sid) for sid in possible]
            if not candidates:continue
            distance,sid=min(candidates)
            if distance>.06:continue
            seen.add(key);tile=(math.floor(p[0]/10000),math.floor(p[1]/10000));anchor=np.array([tile[0]*10000,tile[1]*10000,0]);mesh=tiles.setdefault(tile,Mesh(bevel_cm=0 if radius_cm>18000 else .4))
            for z,depth,h,yoff in [(-16,20,9,0),(-7,30,8,3),(1,43,8,6),(9,57,7,9),(15,65,5,12)]:
                mesh.box(p-anchor,t,n,[0,yoff,z],[width,depth,h],[218,210,192,255])
            # Shadow-casting small brackets under the eaves.
            count=max(1,int(width/85))
            for i in range(count):
                xx=(i+.5)*width/count-width/2
                mesh.box(p-anchor,t,n,[xx,1,-28],[10,34,21],[202,194,177,255])
            attachments.append(dict(kind='eave_cornice',source_id=sid,source_mesh_id=obj['id'],source_quad_index=k//6,centre_cm=p.tolist(),normal=n.tolist(),width_cm=width,height_cm=height,boundary_error_m=distance))
    objects=prototypes()
    for tile,mesh in sorted(tiles.items()):
        name='cornice_'+str(tile[0]).replace('-','m')+'_'+str(tile[1]).replace('-','m');objects.append(item(mesh,name,'M_ParisReferenceStone'))
        records.append(dict(kind='cornice_tile',anchor_cm=[tile[0]*10000,tile[1]*10000,0],yaw_degrees=0,scale_xyz=[1,1,1],models=[name]))
    result=dict(format='paris_reference_v1',recipe=RECIPE,source_scene_sha256=scene['source_scene_sha256'],georeference=scene['georeference'],appearance_provenance='Inferred Haussmann-style details attached to existing inferred facade quads; not surveyed L4/L5 exteriors',camera=camera,objects=objects,records=records,cornices=attachments,building_ids=sorted({w['source_id'] for w in selected}),counts=dict(windows=len(selected),balconies=len(balcony_keys),cornices=len(attachments),buildings=len({w['source_id'] for w in selected})),radius_m=radius_cm/100,upgrade_center_cm=region)
    add_entries(result,scene,district)
    from paris_reference_roofs import add_roofs
    add_roofs(result,scene,district)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(result,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8');temp.replace(output)
    print(json.dumps(dict(counts=result['counts'],models=len(objects),triangles=sum(o['triangles'] for o in objects),camera=camera,sha256=hashlib.sha256(output.read_bytes()).hexdigest()),ensure_ascii=False))
    return result


if __name__=='__main__':generate()
