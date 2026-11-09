"""Inferred shop displays and terrace parasols on validated walking surfaces."""
import hashlib,math
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
from shapely import prepare
from generate_paris_frontages import Mesh


def make_models(lathe_at,flower):
    result=[];wood=[133,83,45,255];cream=[231,220,191,255];dark=[29,43,39,255]
    def add(name,mesh,role='MarketSolid'):
        item=mesh.item(name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    def box(m,p,s,c):m.box([0,0,0],[1,0,0],[0,1,0],p,s,c)
    # Double-sided A-board with geometric chalk lettering and a cup motif.
    m=Mesh(bevel_cm=.35)
    for y in [-17,17]:
        box(m,[0,y,66],[64,4,82],wood);box(m,[0,y+(2.3 if y>0 else -2.3),66],[56,.7,74],dark)
        for x in [-30,30]:m.tube([x,y*1.45,0],[x,y*.65,111],2.2,wood,8)
    for side in [-1,1]:
        y=side*19.8
        glyphs=[[(0,0),(0,12),(4,6),(8,12),(8,0)],[(0,0),(0,12),(8,12)],[(0,6),(6,6)],[(0,0),(8,0)],[(0,0),(0,12),(8,0),(8,12)],[(0,12),(0,0),(8,0),(8,12)]]
        for glyph,x in [(glyphs[0],-23),(glyphs[1],-10),(glyphs[2],-10),(glyphs[3],-10),(glyphs[4],3),(glyphs[5],16)]:
            for a,b in zip(glyph,glyph[1:]):m.tube([x+a[0],y,85+a[1]],[x+b[0],y,85+b[1]],.48,cream,5)
        for z,w in [(73,20),(66,16),(37,19)]:m.tube([-w,y,z],[w,y,z],.5,cream,5)
        for a,b in [([-9,52],[9,52]),([-9,52],[-7,43]),([9,52],[7,43]),([-7,43],[7,43])]:m.tube([a[0],y,a[1]],[b[0],y,b[1]],.7,cream,6)
    add('market_menu',m)
    m=Mesh(bevel_cm=.25)
    for x in [-35,35]:box(m,[x,-9,54],[5,38,108],wood)
    colors=[[193,58,59,255],[47,105,126,255],[211,176,91,255],[66,106,75,255],[224,211,180,255]]
    for row,z in enumerate([21,52,83]):
        box(m,[0,0,z],[76,44,4],wood);box(m,[0,21,z+6],[76,3,10],wood)
        for j in range(9):
            x=-30+j*7.5;color=colors[(j+row*2)%len(colors)]
            box(m,[x,8,z+13],[6,16,22+(j%3)*2],color);box(m,[x,16.3,z+14],[4,.8,1.8],cream)
    add('market_books',m)
    m=Mesh(bevel_cm=.3)
    for x in [-34,34]:box(m,[x,-8,54],[5,34,108],wood)
    for row,z in enumerate([35,72]):
        box(m,[0,0,z],[76,44,5],wood)
        for y in [-21,21]:box(m,[0,y,z+7],[76,2,12],wood)
        for j in range(18):
            x=-29+(j%6)*11.5;y=-11+(j//6)*11;color=[[224,142,32,255],[177,47,43,255],[194,189,45,255]][(j//6+row)%3]
            lathe_at(m,[(z+4,0),(z+5,3.5),(z+8,4.8),(z+12,3.5),(z+13,0)],x,y,color,10)
            m.tube([x,y,z+13],[x+.8,y,z+15],.45,[76,83,35,255],5)
    add('market_produce',m)
    m=Mesh(bevel_cm=.3);blooms=Mesh()
    for x in [-33,33]:box(m,[x,-7,44],[5,32,88],wood)
    for z in [24,57]:
        box(m,[0,0,z],[74,43,4],wood)
        for j in range(3):
            x=-24+j*24;lathe_at(m,[(z+2,7),(z+19,10),(z+20,10),(z+20,8.8),(z+3,5.8)],x,0,[83,114,102,255],12)
            for k in range(5):
                a=k*math.tau/5;px=x+math.cos(a)*6;py=math.sin(a)*6;h=z+34+(j+k)%4*3
                blooms.tube([x,0,z+7],[px,py,h],.55,[54,89,48,255],5);flower(blooms,[px,py,h],4.3,[[196,61,107,255],[239,189,58,255],[227,218,194,255]][j],k)
    add('market_flowers_frame',m);add('market_flowers_blooms',blooms,'Nature')
    metal=Mesh();bronze=[84,77,64,255]
    lathe_at(metal,[(0,22),(5,22),(7,18)],125,-25,[82,82,77,255],24)
    metal.tube([125,-25,5],[125,-25,258],3,bronze,12);metal.tube([125,-25,252],[0,0,258],2.1,bronze,10)
    for j in range(12):
        a=j*math.tau/12;metal.tube([0,0,257],[109*math.cos(a),109*math.sin(a),224],.7,bronze,6)
    add('market_parasol_metal',metal,'Metal')
    for theme,color in enumerate([[154,49,68,255],[40,111,94,255],[72,115,165,255]]):
        cloth=Mesh()
        for j in range(24):
            a=j*math.tau/24;b=(j+1)*math.tau/24;c=color if j%4<2 else cream
            p=[[0,0,260],[110*math.cos(a),110*math.sin(a),225],[110*math.cos(b),110*math.sin(b),225]]
            u=[p[1][i]-p[0][i] for i in range(3)];v=[p[2][i]-p[0][i] for i in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];length=math.sqrt(sum(x*x for x in n));n=[x/length for x in n];cloth.face(p,n,c)
            cloth.face([p[1],p[2],[p[2][0],p[2][1],216],[p[1][0],p[1][1],216]],[math.cos((a+b)/2),math.sin((a+b)/2),0],c)
        add('market_parasol_'+str(theme),cloth,'Fabric')
    return result


def make_placements(scene,geo,surfaces,buildings,water,records,views):
    businesses=[f for f in scene['pick_features'] if f['kind']=='business']
    doors=unary_union([LineString([f['point_cm'][:2],[f['point_cm'][0]-math.sin(math.radians(f['properties']['facade_yaw_degrees']))*300,f['point_cm'][1]+math.cos(math.radians(f['properties']['facade_yaw_degrees']))*300]]).buffer(78) for f in businesses])
    routes=unary_union([LineString(r['points_cm']).buffer(62) for r in scene['pedestrians']['routes'] if len(r['points_cm'])>1])
    occupied=[]
    for f in scene['pick_features']:
        if f['kind'].startswith('street_') and 'point_cm' in f:occupied.append(Point(f['point_cm'][:2]).buffer(110 if f['kind'] in ('street_bench','street_bicycle_rack') else 60))
    for f in businesses:
        if f['properties'].get('terrace_placed'):occupied.append(Point(f['properties']['terrace_cm'][:2]).buffer(125))
    for r in records:
        if r['kind']=='urn':occupied.append(Point(r['anchor_cm'][:2]).buffer(65))
    from pathlib import Path
    import json
    morris=json.loads((Path(__file__).resolve().parents[2]/'unreal/AIWorld/Content/Data/paris-morris.json').read_text(encoding='utf-8'))
    occupied.extend(Point(r['anchor_cm'][:2]).buffer(r['footprint_radius_cm']+25) for r in morris['records'])
    occupied=unary_union(occupied);camera_keepout=unary_union([Point(c['position_cm'][:2]).buffer(90) for c in scene['photo_cameras']]+[Point(c['eye_cm'][:2]).buffer(90) for c in views[1:]])
    for g in [buildings,water,doors,routes,occupied,camera_keepout]:prepare(g)
    result=[];accepted=[]
    for f in sorted(businesses,key=lambda x:x['id']):
        p=f['point_cm'];props=f['properties'];sid=f['id'];yaw=props['facade_yaw_degrees'];a=math.radians(yaw);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]];seed=int(hashlib.sha256((sid+'street-life').encode()).hexdigest()[:8],16)
        category=props['category'];kind='menu' if category in ('cafe','restaurant','bar','fast_food','bakery','coffee','tea','pastry') else 'produce' if category in ('supermarket','convenience','deli','confectionery','chocolate') else 'books' if category in ('books','books;deli','gift','craft','art','collector','antiques') else 'flowers'
        for side in [-1,1]:
            style='menu' if side==-1 and category in ('restaurant','cafe','bar') else kind
            for along,out in [(side*255,74),(side*295,88),(side*355,62),(side*410,100),(side*205,160)]:
                x=p[0]+t[0]*along+n[0]*out;y=p[1]+t[1]*along+n[1]*out;foot=Point(x,y).buffer(52)
                if any(g.intersects(foot) for g in [buildings,water,doors,routes,occupied,camera_keepout]):continue
                if any(math.dist((x,y),q)<145 for q in accepted):continue
                cover,hs=surfaces.query(x,y,52);wide,_=surfaces.query(x+n[0]*110,y+n[1]*110,75)
                if max(cover.get('path',0),cover.get('sidewalk',0))<.98 or max(wide.get('path',0),wide.get('sidewalk',0))<.9 or max(cover.get(k,0) for k in ('road','water','bridge'))>.001:continue
                heights=[h for k,h in hs if k in ('path','sidewalk')]
                if not heights or abs(max(heights)-p[2])>25:continue
                z=max(heights);models=['market_'+style] if style!='flowers' else ['market_flowers_frame','market_flowers_blooms']
                result.append(dict(kind='street_display',display_type=style,source_id=sid,building_source_id=props['building_source_id'],anchor_cm=[x,y,z],yaw_degrees=yaw,wgs84_placement=list(geo.from_ue(x,y,z)[:2]),footprint_radius_cm=52,path_coverage=max(cover.get('path',0),cover.get('sidewalk',0)),models=models,collision_boxes=[dict(centre_cm=[0,0,56],size_cm=[76,52,112])],placement_provenance='inferred_shop_display_beside_archived_storefront'))
                accepted.append((x,y));break
    # Existing tagged terraces keep their original tables and seats; add shade above.
    for f in sorted(businesses,key=lambda x:x['id']):
        props=f['properties']
        if not props.get('terrace_placed'):continue
        p=props['terrace_cm'];yaw=props['facade_yaw_degrees'];a=math.radians(yaw);n=[-math.sin(a),math.cos(a)];base=[p[0]+math.cos(a)*125-n[0]*25,p[1]+math.sin(a)*125-n[1]*25];foot=Point(base).buffer(24);roof=Point(p[:2]).buffer(112)
        if roof.intersects(buildings) or roof.intersects(water) or foot.intersects(routes) or foot.intersects(doors) or foot.intersects(buildings) or foot.intersects(water):continue
        if foot.intersects(occupied.difference(Point(p[:2]).buffer(126))) or any(math.dist(base,q)<80 for q in accepted):continue
        cover,hs=surfaces.query(*base,24)
        if max(cover.get('path',0),cover.get('sidewalk',0))<.98 or not hs:continue
        ground=max(h for k,h in hs if k in ('path','sidewalk','ground'));clearance=p[2]+216-ground
        if clearance<210:continue
        seed=int(hashlib.sha256(f['id'].encode()).hexdigest()[:8],16)
        result.append(dict(kind='terrace_parasol',source_id=f['id'],building_source_id=props['building_source_id'],anchor_cm=p,yaw_degrees=yaw,wgs84_placement=list(geo.from_ue(*p)[:2]),minimum_clearance_cm=clearance,models=['market_parasol_metal','market_parasol_'+str(seed%3)],collision_boxes=[dict(centre_cm=[125,-25,110],size_cm=[16,16,220])],placement_provenance='inferred_parasol_above_existing_tagged_terrace'))
    return result
