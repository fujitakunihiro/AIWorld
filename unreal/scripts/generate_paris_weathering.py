"""Deterministic inferred wall weathering anchored to existing facade windows."""
import hashlib,json,math,sys
from pathlib import Path
from shapely.geometry import Point,shape
ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/'unreal/AIWorld/Content/Data'
sys.path[:0]=[str(ROOT/'unreal/scripts'),str(ROOT/'gis')]
from generate_paris_frontages import Mesh
from paris_twin.coordinates import Georeference
from paris_twin.terrain import Terrain


def generate():
    scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    facade=json.loads((DATA/'paris-photo-frontages-source.json').read_text(encoding='utf-8'))
    if facade['source_scene_sha256']!=scene['source_scene_sha256']:raise RuntimeError('Facade data belongs to a different scene')
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    config=json.loads((ROOT/'gis/config/ile_de_la_cite.json').read_text(encoding='utf-8'))
    geo=Georeference(config);terrain=Terrain(config,geo);ox,oy=district['origin_projected_m']
    buildings={f['properties']['source_id']:f['properties'] for f in district['layers']['buildings']}
    windows=Mesh(); bases=Mesh(); records=[];lowest={};inspection=[]
    for w in facade['windows']:
        p=w['centre_cm'];n=w['normal'];t=[n[1],-n[0],0];sid=w['source_id'];key=(sid,round(p[0],1),round(p[1],1))
        if key not in lowest or p[2]<lowest[key]['centre_cm'][2]:lowest[key]=w
        digest=hashlib.sha256((sid+':'+str(w['source_quad_index'])+':'+w['source_mesh_id']).encode()).digest()
        if digest[0]%5==0:continue
        width=w['width_cm']*(.82+.2*digest[1]/255);height=40+35*digest[2]/255
        top=p[2]-w['height_cm']/2-17;bottom=top-height
        def point(x,z):return [p[i]+t[i]*x-n[i]*8.35+(z-p[2] if i==2 else 0) for i in range(3)]
        windows.face([point(-width/2,top),point(width/2,top),point(width/2,bottom),point(-width/2,bottom)],n,[digest[3],180,150,255],[(0,0),(1,0),(1,1),(0,1)])
        records.append(dict(kind='window_streak',source_id=sid,source_mesh_id=w['source_mesh_id'],source_quad_index=w['source_quad_index'],top_cm=round(top,3),length_cm=round(height,3)))
    entrances=facade.get('entrances',[])
    for w in lowest.values():
        p=w['centre_cm'];n=w['normal'];t=[n[1],-n[0],0];sid=w['source_id'];props=buildings.get(sid)
        if not props:continue
        projected=Point(ox+(p[0]-n[0]*9)/100,oy-(p[1]-n[1]*9)/100)
        parts=[(shape(part['geometry']).distance(projected),part) for part in props['height_parts']]
        if not parts:continue
        part=min(parts,key=lambda item:item[0])[1]
        ground=(max(part.get('ground_ngf_m',terrain.ngf((projected.x,projected.y)))-terrain.origin_ngf,terrain.local((projected.x,projected.y))))*100
        if not 50 < p[2]-w['height_cm']/2-ground < 700:continue
        if any(e['source_id']==sid and math.dist(e['centre_cm'][:2],p[:2])<145 for e in entrances):continue
        digest=hashlib.sha256((sid+':base:'+str(round(p[0],1))+':'+str(round(p[1],1))).encode()).digest()
        width=w['width_cm']*1.32;height=32+digest[0]%19
        def point(x,z):return [p[i]+t[i]*x-n[i]*8.35+(z-p[2] if i==2 else 0) for i in range(3)]
        if any(r['kind']=='window_streak' and r['source_mesh_id']==w['source_mesh_id'] and r['source_quad_index']==w['source_quad_index'] for r in records):
            eye=[p[0]+n[0]*420,p[1]+n[1]*420,ground+170]
            target=[p[0]-n[0]*8.35,p[1]-n[1]*8.35,p[2]-w['height_cm']/2-38]
            inspection.append(dict(eye_cm=eye,target_cm=target,source_id=sid,window_centre_cm=p))
        bases.face([point(-width/2,ground+height),point(width/2,ground+height),point(width/2,ground+3),point(-width/2,ground+3)],n,[digest[1],150,120,255],[(0,0),(1,0),(1,1),(0,1)])
        records.append(dict(kind='wall_base',source_id=sid,ground_cm=round(ground,3),width_cm=round(width,3)))
    def result(mesh,name):
        item=mesh.item(name,'M_ParisWeathering'+name.title()); item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Weathering/SM_ParisWeathering_');return item
    foots=[shape(f['geometry']) for f in district['layers']['buildings']]
    valid=[i for i in inspection if not any(g.buffer(.4).covers(Point(ox+i['eye_cm'][0]/100,oy-i['eye_cm'][1]/100)) for g in foots)]
    if not valid:raise RuntimeError('No safe outdoor weathering inspection point')
    inspected=min(valid,key=lambda i:math.dist(i['eye_cm'][:2],facade['anchor_cm'][:2]))
    result=dict(inspection_camera=inspected,format='paris_local_weathering_v1',source_scene_sha256=scene['source_scene_sha256'],provenance='Procedurally inferred streaks below existing inferred windows and grime close to terrain-supported wall bases; not a survey of stains.',records=records,objects=[result(windows,'streak'),result(bases,'base')])
    from generate_paris_district_grime import extend
    extra,objects=extend(scene,district,geo,terrain,facade['windows']);result['records'].extend(extra);result['objects'].extend(objects);result['format']='paris_local_weathering_v2';result['recipe']='district_wall_and_road_grime_v2'
    if not windows.indices or not bases.indices:raise RuntimeError('No anchored weathering geometry')
    return result

if __name__=='__main__':
    result=generate();out=ROOT/'unreal/assets/paris-weathering/Generated';out.mkdir(parents=True,exist_ok=True)
    (out/'weathering.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({'streaks':sum(r['kind']=='window_streak' for r in result['records']),'bases':sum(r['kind']=='wall_base' for r in result['records']),'triangles':sum(o['triangles'] for o in result['objects'])}))
