"""Additional inferred street accents with reproducible source-bound placement."""
import hashlib,math,random,json
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from shapely import prepare
from generate_paris_frontages import Mesh


def make_models(lathe_at,flower):
    result=[];wood=[140,91,54,255];ivory=[230,222,199,255];iron=[57,67,64,255]
    def add(name,m,role='MarketSolid'):
        item=m.item('market_extra_'+name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    def box(m,p,s,c):m.box([0,0,0],[1,0,0],[0,1,0],p,s,c)
    m=Mesh(bevel_cm=.35)
    for x in [-36,36]:box(m,[x,0,45],[5,42,90],wood)
    for z in [25,58]:
        box(m,[0,0,z],[80,46,4],wood)
        for y in [-22,22]:box(m,[0,y,z+6],[80,3,10],wood)
        for i in range(9):
            temp=Mesh();lathe_at(temp,[(0,0),(2,2.6),(6,3.4),(28,3.4),(32,2.6),(34,0)],0,0,[216,159,84,255],12)
            a=.48;cs=math.cos(a);sn=math.sin(a)
            for p in temp.positions_cm:x,y,h=p;p[:]=[-31+i*7+cs*x+sn*h,y,z+3-sn*x+cs*h]
            for n in temp.normals:x,y,h=n;n[:]=[cs*x+sn*h,y,-sn*x+cs*h]
            m.extend(temp)
    add('bread',m)
    m=Mesh();lathe_at(m,[(0,26),(7,28),(24,31),(55,31),(74,28),(80,26),(80,0)],0,0,wood,32)
    for z in [9,22,59,72]:lathe_at(m,[(z,29 if z in (9,72) else 31.5),(z+3,29 if z in (9,72) else 31.5)],0,0,iron,32)
    for x,y in [(-13,-9),(0,-9),(13,-9),(-7,8),(7,8)]:
        lathe_at(m,[(80,4),(98,4),(101,1.7),(111,1.7),(112,0)],x,y,[44,77,48,255],12)
        lathe_at(m,[(86,4.1),(94,4.1)],x,y,ivory,12);lathe_at(m,[(109,1.9),(112,1.9),(112,0)],x,y,[135,43,50,255],12)
    add('wine',m)
    m=Mesh(bevel_cm=.3)
    for x in [-35,35]:
        for y in [-19,19]:m.tube([x,y,7],[x,y,92],1.8,iron,8);lathe_at(m,[(0,5),(8,5),(8,0)],x,y,[35,36,34,255],12)
    for z in [25,68]:box(m,[0,0,z],[80,46,4],[43,100,108,255])
    m.tube([-35,-19,90],[35,-19,90],1.8,iron,8)
    for x in [-22,-5,12]:lathe_at(m,[(70,3.3),(82,4.3),(83,4.3),(83,3.3),(71,2.6)],x,6,ivory,14)
    for z in [70,72,74,76]:lathe_at(m,[(z,9),(z+1.3,9),(z+1.3,0)],21,-8,ivory,16)
    lathe_at(m,[(28,9),(31,10),(48,8),(52,3),(56,3),(56,0)],-14,0,[165,132,75,255],16)
    box(m,[18,0,38],[20,23,18],[195,174,133,255]);add('cart',m)
    m=Mesh();blooms=Mesh()
    for x in [-49,49]:
        for r,c in [(32,[35,37,36,255]),(29,[180,178,156,255])]:
            for j in range(32):
                a=j*math.tau/32;b=(j+1)*math.tau/32;m.tube([x+r*math.cos(a),0,34+r*math.sin(a)],[x+r*math.cos(b),0,34+r*math.sin(b)],2.4 if r==32 else .9,c,6)
        for j in range(12):
            a=j*math.tau/12;m.tube([x,0,34],[x+28*math.cos(a),0,34+28*math.sin(a)],.45,[168,168,157,255],5)
    color=[111,48,58,255]
    for a,b in [([-49,0,34],[-12,0,31]),([-12,0,31],[-30,0,72]),([-30,0,72],[-49,0,34]),([-30,0,72],[30,0,73]),([30,0,73],[-12,0,31]),([30,0,73],[49,0,34]),([-30,0,72],[-32,0,83]),([30,0,73],[25,0,92]),([25,0,92],[19,12,96])]:m.tube(a,b,1.8,color,8)
    m.box([0,0,0],[1,0,0],[0,1,0],[-32,0,85],[23,15,5],[48,41,34,255])
    lathe_at(m,[(67,13),(87,19),(89,19),(89,17),(70,10)],52,0,[167,122,69,255],18)
    for j in range(14):
        a=j*math.tau/14;x=52+math.cos(a)*12;y=math.sin(a)*12;z=91+(j%3)*4;blooms.tube([52,0,75],[x,y,z],.5,[54,86,45,255],5);flower(blooms,[x,y,z],4.4,[[221,111,151,255],[238,213,97,255],[228,223,202,255]][j%3],a)
    add('bicycle',m);add('bicycle_blooms',blooms,'Nature')
    base=Mesh(bevel_cm=.5);rings=Mesh()
    for z,w,h in [(6,84,12),(15,72,8),(48,59,58),(82,76,10)]:box(base,[0,0,z],[w,w,h],ivory)
    lathe_at(rings,[(87,14),(95,12),(109,8),(123,7),(130,0)],0,0,[153,117,53,255],24)
    for tilt in [0,.83,-.83]:
        for j in range(64):
            def p(a):return [62*math.cos(a),62*math.sin(a)*math.sin(tilt),173+62*math.sin(a)*math.cos(tilt)]
            rings.tube(p(j*math.tau/64),p((j+1)*math.tau/64),1.2,[172,136,61,255],8)
    lathe_at(rings,[(148,0),(153,17),(173,25),(193,17),(198,0)],0,0,[110,138,129,255],24)
    rings.tube([0,0,118],[0,0,236],1.4,[172,136,61,255],10)
    add('orrery_base',base,'Stone');add('orrery_rings',rings,'Metal')
    m=Mesh();leaves=Mesh();lathe_at(m,[(0,17),(6,19),(38,26),(43,28),(45,28),(45,24),(7,13)],0,0,[153,78,49,255],24)
    lathe_at(m,[(42,24),(42,0)],0,0,[57,44,31,255],24);m.tube([0,0,42],[0,0,115],2,[99,74,40,255],10)
    rng=random.Random(173)
    for j in range(240):
        z=rng.uniform(-1,1);a=rng.random()*math.tau;r=math.sqrt(1-z*z);n=[r*math.cos(a),r*math.sin(a),z];p=[n[0]*33,n[1]*33,119+n[2]*37];u=[-math.sin(a),math.cos(a),0];v=[-z*math.cos(a),-z*math.sin(a),r]
        points=[[p[i]+u[i]*x+v[i]*y for i in range(3)] for x,y in [(-2,0),(0,4.5),(2,0),(0,-4.5)]];leaves.face(points,n,[[62,100,47,255],[81,119,55,255],[99,127,62,255]][j%3])
    add('topiary_pot',m);add('topiary_leaves',leaves,'Nature')
    gold=Mesh();flowers=Mesh();ribbon=Mesh()
    for side in [-1,1]:
        cx=side*61;gold.tube([0,0,365],[cx,60,350],1.,[244,196,94,255],6);gold.tube([cx,60,350],[cx,60,339],.8,[244,196,94,255],6)
        for j in range(32):
            a=j*math.tau/32;b=(j+1)*math.tau/32;gold.tube([cx+24*math.cos(a),60,315+24*math.sin(a)],[cx+24*math.cos(b),60,315+24*math.sin(b)],1.3,[244,196,94,255],7)
        for j in range(12):
            a=j*math.tau/12;temp=Mesh();flower(temp,[0,0,0],6.5,[[235,76,148,255],[112,159,226,255],[249,211,93,255]][j%3],a)
            for p in temp.positions_cm:x,y,z=p;p[:]=[cx+23*math.cos(a)+x,63+z,315+23*math.sin(a)-y]
            for n in temp.normals:x,y,z=n;n[:]=[x,z,-y]
            flowers.extend(temp)
        color=[191,38,82,255] if side<0 else [51,100,191,255]
        ribbon.face([[cx,65,288],[cx-19,65,298],[cx-17,65,278]],[0,1,0],color)
        ribbon.face([[cx,65,288],[cx+19,65,298],[cx+17,65,278]],[0,1,0],color)
        for sign in [-1,1]:ribbon.face([[cx+sign*2,65,285],[cx+sign*10,65,284],[cx+sign*15,65,260],[cx+sign*6,65,263]],[0,1,0],color)
    add('hanging_gold',gold,'PartyGold');add('hanging_blooms',flowers,'Nature');add('hanging_ribbons',ribbon,'Fabric')
    return result


def inspection_camera(scene,surfaces,buildings,water,records):
    extras=[r for r in records if r['kind']=='street_accent'];priority={'orrery':0,'bicycle':1,'bread':2,'cart':3,'wine':4,'topiary':5}
    candidates=sorted([r for r in extras if max(abs(x) for x in r['anchor_cm'][:2])<28000],key=lambda r:(priority[r['accent_type']],r['source_id'],r['anchor_cm']))[:80]
    hangers=[r for r in records if r['kind']=='street_hanging_accent']
    keep=[]
    for r in records:
        if 'collision_boxes' in r:keep.append(Point(r['anchor_cm'][:2]).buffer(r.get('footprint_radius_cm',70)+65))
        if r['kind']=='urn':keep.append(Point(r['anchor_cm'][:2]).buffer(110))
    for f in scene['pick_features']:
        if f['kind'].startswith('street_'):keep.append(Point(f['point_cm'][:2]).buffer(150 if f['kind']=='street_tree' else 130))
    occupied=unary_union(keep);prepare(occupied);views=[]
    for r in candidates:
        p=r['anchor_cm'];base=math.radians(r['yaw_degrees'])+math.pi/2
        for distance,offset in [(750,0),(850,.6),(850,-.6),(1100,0),(950,1.2),(950,-1.2)]:
            a=base+offset;x=p[0]+math.cos(a)*distance;y=p[1]+math.sin(a)*distance;point=Point(x,y)
            if point.distance(buildings)<70 or point.distance(water)<70 or occupied.intersects(point) or LineString([point.coords[0],p[:2]]).intersects(buildings):continue
            cover,hs=surfaces.query(x,y,40)
            if max(cover.get('path',0),cover.get('sidewalk',0))<.9 or max(cover.get(k,0) for k in ('water','road','bridge'))>.001:continue
            heights=[h for k,h in hs if k in ('path','sidewalk')]
            if not heights:continue
            eye=[x,y,max(heights)+170];target=[p[0],p[1],p[2]+120];heading=math.atan2(p[1]-y,p[0]-x);seen=[]
            for other in extras:
                q=other['anchor_cm'];d=math.dist(q[:2],eye[:2]);delta=abs((math.atan2(q[1]-y,q[0]-x)-heading+math.pi)%(2*math.pi)-math.pi)
                if d<2200 and delta<math.pi/6 and not LineString([eye[:2],q[:2]]).intersects(buildings):seen.append(other['accent_type'])
            lit=0
            for other in hangers:
                q=other['anchor_cm'];d=math.dist(q[:2],eye[:2]);delta=abs((math.atan2(q[1]-y,q[0]-x)-heading+math.pi)%(2*math.pi)-math.pi)
                if 500<d<2500 and delta<math.pi/6 and not LineString([eye[:2],q[:2]]).intersects(buildings):lit+=1
            score=len(seen)*50+len(set(seen))*140+lit*170+(400 if r['accent_type']=='orrery' else 0)+(120 if 'bicycle' in seen else 0)-distance*.015
            views.append((score,dict(source_id=r['source_id'],name='Street objects',eye_cm=eye,target_cm=target,visible_accent_types=sorted(set(seen)))))
    if not views:raise RuntimeError('No unobstructed walking-surface camera for new street objects')
    return max(views,key=lambda item:item[0])[1]


SPECS={
    'bread':(50,[80,48,108],['bread']), 'wine':(46,[64,64,114],['wine']),
    'cart':(50,[80,46,94],['cart']), 'bicycle':(96,[168,52,108],['bicycle','bicycle_blooms']),
    'orrery':(100,[140,140,240],['orrery_base','orrery_rings']),
    'topiary':(43,[60,60,158],['topiary_pot','topiary_leaves'])}


def make_placements(scene,geo,surfaces,buildings,water,records,views):
    businesses=[f for f in scene['pick_features'] if f['kind']=='business'];fixtures=[f for f in scene['pick_features'] if f['kind'].startswith('street_')]
    doors=unary_union([LineString([f['point_cm'][:2],[f['point_cm'][0]-math.sin(math.radians(f['properties']['facade_yaw_degrees']))*300,f['point_cm'][1]+math.cos(math.radians(f['properties']['facade_yaw_degrees']))*300]]).buffer(78) for f in businesses])
    routes=unary_union([LineString(r['points_cm']).buffer(62) for r in scene['pedestrians']['routes'] if len(r['points_cm'])>1]);occupied=[]
    for f in fixtures:occupied.append(Point(f['point_cm'][:2]).buffer(110 if f['kind'] in ('street_bench','street_bicycle_rack') else 60))
    for f in businesses:
        if f['properties'].get('terrace_placed'):occupied.append(Point(f['properties']['terrace_cm'][:2]).buffer(125))
    for r in records:
        if r['kind']=='urn':occupied.append(Point(r['anchor_cm'][:2]).buffer(58))
        for b in r.get('collision_boxes',[]):
            a=math.radians(r['yaw_degrees']);x,y,_=b['centre_cm'];p=r['anchor_cm'];occupied.append(Point(p[0]+math.cos(a)*x-math.sin(a)*y,p[1]+math.sin(a)*x+math.cos(a)*y).buffer(math.hypot(*b['size_cm'][:2])/2+18))
    morris=json.loads((Path(__file__).resolve().parents[2]/'unreal/AIWorld/Content/Data/paris-morris.json').read_text(encoding='utf-8'));occupied.extend(Point(r['anchor_cm'][:2]).buffer(r['footprint_radius_cm']+25) for r in morris['records'])
    occupied=unary_union(occupied);camera_keepout=unary_union([Point(v['eye_cm'][:2]).buffer(100) for v in views[1:]]+[Point(v['position_cm'][:2]).buffer(100) for v in scene['photo_cameras']])
    for g in [buildings,water,doors,routes,occupied,camera_keepout]:prepare(g)
    result=[];accepted=[];art=0
    def place(f,style,candidates,yaw):
        radius,size,models=SPECS[style];p=f['point_cm'];a=math.radians(yaw);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
        for along,out in candidates:
            x=p[0]+t[0]*along+n[0]*out;y=p[1]+t[1]*along+n[1]*out;foot=Point(x,y).buffer(radius)
            if any(g.intersects(foot) for g in [buildings,water,doors,routes,occupied,camera_keepout]):continue
            if any(math.dist((x,y),(xx,yy))<radius+rr+28 for xx,yy,rr in accepted):continue
            cover,hs=surfaces.query(x,y,radius);wide,_=surfaces.query(x+n[0]*(radius+85),y+n[1]*(radius+85),75)
            if max(cover.get('path',0),cover.get('sidewalk',0))<.98 or max(wide.get('path',0),wide.get('sidewalk',0))<.85 or max(cover.get(k,0) for k in ('road','water','bridge'))>.001:continue
            heights=[h for k,h in hs if k in ('path','sidewalk')]
            if not heights or abs(max(heights)-p[2])>30:continue
            z=max(heights);sid=f['id'];result.append(dict(kind='street_accent',accent_type=style,source_id=sid,source_anchor_kind=f['kind'],building_source_id=f['properties'].get('building_source_id'),anchor_cm=[x,y,z],yaw_degrees=yaw,wgs84_placement=list(geo.from_ue(x,y,z)[:2]),footprint_radius_cm=radius,path_coverage=max(cover.get('path',0),cover.get('sidewalk',0)),models=['market_extra_'+m for m in models],collision_boxes=[dict(centre_cm=[0,0,size[2]/2],size_cm=size)],placement_provenance='inferred_additional_street_object_not_surveyed_furniture'))
            accepted.append((x,y,radius));return True
        return False
    for f in sorted(businesses,key=lambda f:f['id']):
        category=f['properties']['category'];seed=int(hashlib.sha256((f['id']+'extra-objects').encode()).hexdigest()[:8],16)
        style='bread' if category in ('bakery','pastry','fast_food') else 'wine' if category in ('bar','wine') else 'cart' if category in ('cafe','coffee','tea') else ('wine' if seed%2 else 'cart') if category=='restaurant' else 'topiary'
        for side in [-1,1]:
            place(f,style,[(side*460,70),(side*520,95),(side*610,65),(side*700,85),(side*330,210)],f['properties']['facade_yaw_degrees'])
        if len(result)>=340:break
    for f in sorted([f for f in fixtures if f['kind'] in ('street_bench','street_bicycle_rack')],key=lambda f:f['id']):
        seed=int(hashlib.sha256((f['id']+'square').encode()).hexdigest()[:8],16);style='bicycle' if f['kind']=='street_bicycle_rack' else 'orrery' if art<12 and seed%5==0 else 'topiary'
        if place(f,style,[(s*d,o) for d,o in [(245,90),(295,60),(220,-110),(350,80)] for s in [-1,1]],f['properties']['yaw_degrees']):art+=style=='orrery'
        if len(result)>=400:break
    for pole in [r for r in records if r['kind']=='pole']:
        p=pole['anchor_cm'];a=math.radians(pole['yaw_degrees']);cs=math.cos(a);sn=math.sin(a);floor=[];safe=True
        for side in [-1,1]:
            x=p[0]+cs*side*61-sn*60;y=p[1]+sn*side*61+cs*60;foot=Point(x,y).buffer(37)
            if buildings.intersects(foot) or water.intersects(foot):safe=False;break
            cover,hs=surfaces.query(x,y,37)
            if max(cover.get('path',0),cover.get('sidewalk',0))<.98 or max(cover.get(k,0) for k in ('road','water','bridge'))>.001:safe=False;break
            floor.extend(h for k,h in hs if k in ('ground','path','sidewalk'))
        if not safe or not floor or p[2]+260-max(floor)<210:continue
        result.append(dict(kind='street_hanging_accent',accent_type='hanging_bouquet',source_id=pole['source_id'],source_anchor_kind='street_lamp',building_source_id=None,anchor_cm=p,yaw_degrees=pole['yaw_degrees'],wgs84_placement=list(geo.from_ue(*p)[:2]),minimum_clearance_cm=p[2]+260-max(floor),models=['market_extra_hanging_gold','market_extra_hanging_blooms','market_extra_hanging_ribbons'],collision_boxes=[],placement_provenance='inferred_extra_floral_wreaths_on_existing_mapped_lamp'))
    return result
