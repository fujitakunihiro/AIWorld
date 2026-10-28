"""Convert the reviewed ferry and plan a safe route in existing Seine data."""
import hashlib
import json
import math
from pathlib import Path
import struct
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from inspect_notredame import accessor, image_size
from prepare_paris_vehicles import split_conflicting_edges

ROOT=Path(__file__).resolve().parents[2]
CONTENT=ROOT/'unreal/AIWorld/Content'
FOLDER=ROOT/'unreal/assets/paris-cruise'
OUT=FOLDER/'Generated'
RECIPE='paris_seine_cruise_v1'
WATERLINE_M=1.18 # Estimated draft; source is a visual model, not hydrostatic data.
MARGIN_CM=150.


def parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='LineString':return [geometry]
    return [item for g in getattr(geometry,'geoms',[]) for item in parts(g)]


def bridge_obstacles(data,bridges,blob):
    polygons=[];covered=set()
    for b in bridges['profiles']:
        covered.update(b['source_mesh_ids']);centre=np.asarray(b['centre_cm'][:2]);axis=np.asarray(b['direction']);side=np.array([-axis[1],axis[0]])
        length=b['length_cm']/2;width=b['width_cm']/2
        polygons.append(Polygon([centre+axis*x+side*y for x,y in [(-length,-width),(length,-width),(length,width),(-length,width)]]))
    # Incomplete boundary fragments are still obstacles, never navigable gaps.
    dtype=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])
    for o in data['objects']:
        if o['kind']!='bridge' or o['id'] in covered:continue
        spec=o['mesh_buffer'];vertices=np.frombuffer(blob,dtype=dtype,count=spec['vertex_count'],offset=spec['offset'])['p'][:,:2]
        hull=shapely.MultiPoint(vertices).convex_hull
        if not hull.is_empty:polygons.append(hull)
    return unary_union(polygons)


def plan_route(data,water,bridges,boat_radius,blob):
    feature=next(f for f in data['pick_features'] if f['id']==water['source_id'])
    river=unary_union([shapely.make_valid(Polygon(p[0],p[1:])) for p in feature['polygons_cm']])
    radius=boat_radius+MARGIN_CM
    obstacles=bridge_obstacles(data,bridges,blob)
    navigable=river.buffer(-radius).difference(obstacles.buffer(radius))
    target=np.asarray(water['preview_camera']['position_cm'][:2]);candidates=[]
    x0,y0,x1,y1=navigable.bounds
    for x in np.arange(math.floor(x0/1800)*1800,x1+1,1800):
        for y in np.arange(math.floor(y0/1800)*1800,y1+1,1800):
            point=Point(x,y)
            if not navigable.covers(point) or point.distance(Point(target))>22000:continue
            for angle in np.linspace(0,np.pi,24,endpoint=False):
                direction=np.array([np.cos(angle),np.sin(angle)]);mid=np.array([x,y]);line=LineString([mid-direction*110000,mid+direction*110000])
                for segment in parts(line.intersection(navigable)):
                    if segment.length<8000:continue
                    # Leave a physical turning circle at each end.
                    a=np.array(segment.interpolate(200).coords[0]);b=np.array(segment.interpolate(segment.length-200).coords[0]);line_ab=LineString([a,b])
                    midpoint=(a+b)*.5;distance=np.linalg.norm(midpoint-target)
                    score=line_ab.length-.8*distance
                    candidates.append((score,line_ab.length,a,b))
    if not candidates:raise ValueError('No clear 80m river reach for the full ship radius')
    _,length,a,b=max(candidates,key=lambda c:(round(c[0],5),round(c[1],5),tuple(c[2]),tuple(c[3])))
    line=LineString([a,b]);swept=line.buffer(radius,quad_segs=24)
    if not river.buffer(.05).covers(swept) or swept.intersects(obstacles):raise ValueError('Cruise swept circle intersects a riverbank or bridge')
    return dict(start_cm=a.tolist(),end_cm=b.tolist(),length_cm=float(length),clearance_radius_cm=float(radius),water_source_id=feature['id'],
        inferred=True,bridge_policy='Turn before all mapped bridge footprints; no bridge clearance is claimed',
        provenance='Straight inferred sightseeing reach selected inside the OSM Seine polygon and outside mapped bridge footprints, using a rotation-safe vessel envelope')


def prepare():
    meta=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'));raw=(FOLDER/'Raw'/meta['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('Unverified ferry source')
    if struct.unpack_from('<4sII',raw)!=(b'glTF',2,len(raw)):raise ValueError('Invalid source GLB')
    size,kind=struct.unpack_from('<II',raw,12);gltf=json.loads(raw[20:20+size]);start=20+size;binary_size,binary_kind=struct.unpack_from('<II',raw,start)
    if kind!=0x4e4f534a or binary_kind!=0x004e4942:raise ValueError('Invalid GLB chunks')
    blob=raw[start+8:start+8+binary_size]
    if any(any(k in n for k in ('matrix','scale','rotation','translation')) for n in gltf['nodes']):raise ValueError('Unexpected source node transform; review geometry conversion')
    OUT.mkdir(parents=True,exist_ok=True);textures=[]
    for i,image in enumerate(gltf['images']):
        view=gltf['bufferViews'][image['bufferView']];chunk=blob[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
        if image['mimeType']!='image/png':raise ValueError('Unexpected source texture')
        name=f'source_{i:02}.png';(OUT/name).write_bytes(chunk);textures.append(dict(file=name,sha256=hashlib.sha256(chunk).hexdigest(),resolution=image_size(chunk),name=image.get('name','')))
    groups={i:[] for i in range(len(gltf['materials']))};orientation=np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    for node in gltf['nodes']:
        if 'mesh' not in node:continue
        for primitive in gltf['meshes'][node['mesh']]['primitives']:
            if primitive.get('mode',4)!=4:raise ValueError('Unexpected source primitive')
            attrs=primitive['attributes'];mid=primitive['material'];p=accessor(gltf,blob,attrs['POSITION']).astype(float);n=accessor(gltf,blob,attrs['NORMAL']).astype(float);uv=accessor(gltf,blob,attrs['TEXCOORD_0']).astype(float)
            transform=gltf['materials'][mid]['pbrMetallicRoughness']['baseColorTexture'].get('extensions',{}).get('KHR_texture_transform',{})
            uv=uv*np.asarray(transform.get('scale',[1,1]))+np.asarray(transform.get('offset',[0,0]))
            positions=(p@orientation.T*100).astype('<f4');positions[:,2]-=WATERLINE_M*100
            normals=(n@orientation.T).astype('<f4');normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1.e-20)
            triangles=accessor(gltf,blob,primitive['indices']).reshape(-1,3).astype('<u4')
            cross=np.cross(positions[triangles[:,1]]-positions[triangles[:,0]],positions[triangles[:,2]]-positions[triangles[:,0]])
            valid=np.linalg.norm(cross,axis=1)>1.e-6;triangles=triangles[valid];cross=cross[valid]
            reverse=np.einsum('ij,ij->i',cross,normals[triangles].sum(axis=1))>0;triangles[reverse]=triangles[reverse][:,[0,2,1]]
            groups[mid].append((positions,normals,uv.astype('<f4'),triangles))
    parts_out=[];total=0
    for part_id,material_ids in [('body',[i for i in groups if i!=6]),('glass',[6])]:
        result=dict(id=part_id,primitives=[])
        for mid in material_ids:
            values=groups[mid]
            if not values:continue
            offset=0;pos=[];norm=[];tex=[];tris=[]
            for p,n,u,t in values:pos.append(p);norm.append(n);tex.append(u);tris.append(t+offset);offset+=len(p)
            p=np.concatenate(pos);n=np.concatenate(norm);u=np.concatenate(tex);t=np.concatenate(tris).astype('<u4')
            p,n,u,t,split=split_conflicting_edges(p,n,u,t)
            data=struct.pack('<8sII',b'NDSCAN01',len(p),len(t))+p.astype('<f4').tobytes()+n.astype('<f4').tobytes()+u.astype('<f4').tobytes()+t.tobytes()
            name=f'{part_id}_{mid:02}.bin';(OUT/name).write_bytes(data)
            result['primitives'].append(dict(material=mid,file=name,sha256=hashlib.sha256(data).hexdigest(),triangles=len(t),vertices=len(p),split_nonmanifold_faces=split))
            total+=len(t)
        digest=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
        result['asset']=f'/Game/ParisPhotoreal/Cruise/SM_ParisCruise_{part_id}_{digest[:12]}'
        parts_out.append(result)
    water=json.loads((CONTENT/'Data/paris-water.json').read_text(encoding='utf-8'));bridges=json.loads((CONTENT/'Data/paris-bridges.json').read_text(encoding='utf-8'));scene=json.loads((CONTENT/'Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    if scene['source_scene_sha256']!=water['source_scene_sha256'] or scene['source_scene_sha256']!=bridges['source_scene_sha256']:raise ValueError('World, water and bridge data do not share a source')
    radius=100*math.hypot(meta['source_dimensions_m'][0]/2,meta['source_dimensions_m'][1]/2)
    route=plan_route(scene,water,bridges,radius,(CONTENT/'Data/paris-digital-twin-meshes.bin').read_bytes())
    mats=[]
    for i,m in enumerate(gltf['materials']):
        pbr=m['pbrMetallicRoughness'];texture_id=pbr['baseColorTexture']['index'];image_id=gltf['textures'][texture_id]['source']
        mats.append(dict(id=i,name=m.get('name',''),texture=image_id,base_color=pbr.get('baseColorFactor',[1,1,1,1]),metallic=pbr.get('metallicFactor',1.),roughness=pbr.get('roughnessFactor',1.)))
    result=dict(recipe=RECIPE,source=meta,source_scene_sha256=scene['source_scene_sha256'],source_geometry_sha256=bridges['source_geometry_sha256'],water_level_cm=water['water_level_cm'],water_bounds_cm=water['world_bounds_cm'],waterline_source_m=WATERLINE_M,model_radius_cm=radius,route=route,materials=mats,textures=textures,parts=parts_out,source_triangles=total)
    (OUT/'source.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(triangles=total,dimensions_m=meta['source_dimensions_m'],water_level_cm=water['water_level_cm'],route=route),indent=2));print('PARIS_CRUISE_INPUTS_READY')
    return result


if __name__=='__main__':prepare()
