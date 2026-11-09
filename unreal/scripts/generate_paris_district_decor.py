"""Shared street-pole decoration, distant substitutes and public-space urns."""
import hashlib,math,random
from collections import defaultdict
from shapely.geometry import Point
from generate_paris_frontages import Mesh
from paris_district_layout import spread,cell

PALETTES={'wine':[118,34,57,255],'blue':[35,59,94,255],'ivory':[203,174,121,255]}


def make_models(greenery,lathe_at):
    objects=[];dark=[32,56,45,255];gold=[145,117,65,255]
    def add(name,mesh,role):
        item=mesh.item(name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');objects.append(item)
    metal=Mesh();bulbs=Mesh()
    for z in [272,365]:metal.tube([0,0,z],[0,55,z],1.2,dark,8)
    metal.tube([-26,55,365],[26,55,365],1.1,gold,8)
    lathe_at(metal,[(221,8),(223,16),(228,23),(237,25),(239,25),(240,23)],0,60,dark,24)
    lathe_at(metal,[(237,25.5),(239,26),(241,25)],0,60,gold,24)
    for a in [0,math.tau/3,math.tau*2/3]:metal.tube([0,55,272],[24*math.cos(a),60+24*math.sin(a),238],.5,gold,6)
    for x in [-18,0,18]:
        metal.tube([x,55,365],[x,55,373],.45,gold,6)
        lathe_at(bulbs,[(370,0),(371,2.5),(374,3),(377,1.7),(378,0)],x,55,[247,218,159,255],12)
    add('pole_metal',metal,'Metal');add('pole_bulbs',bulbs,'Bulb')
    for variant in range(3):
        mesh=Mesh();greenery(mesh,42+variant,hanging=True)
        for p in mesh.positions_cm:p[:]=[p[0]*.55,60+p[1]*.55,240+(p[2]-72)*.55]
        add('pole_flowers_'+str(variant),mesh,'Nature')
    for theme,color in PALETTES.items():
        fabric=Mesh()
        for j in range(8):
            for k in range(10):
                def p(u,v):return [(u-.5)*44,55+3*math.sin(u*math.tau*2),360-v*90+(v*8*abs(u-.5)*2)]
                u=j/8;v=k/10;u1=(j+1)/8;v1=(k+1)/10
                fabric.face([p(u,v),p(u1,v),p(u1,v1),p(u,v1)],[0,1,0],gold if j in (0,7) or k in (0,9) else color)
        add('pole_banner_'+theme,fabric,'Fabric')
    # These tiny substitutes are masked out near the camera. They retain the
    # colour and glow of the decoration when detailed meshes are culled.
    themes={'red':[121,38,47,0],'green':[32,65,51,0],'cream':[185,155,104,0]}
    for theme,color in themes.items():
        mesh=Mesh()
        for j in range(8):
            x0=-173.5+j*347/8;x1=-173.5+(j+1)*347/8;c=color if j%2==0 else [225,215,187,0]
            mesh.face([[x0,4,294],[x1,4,294],[x1,116,264],[x0,116,264]],[0,0,1],c)
            mesh.face([[x0,117,264],[x1,117,264],[x1,117,240],[x0,117,240]],[0,1,0],c)
        for x in [-110,0,110]:mesh.face([[x-4,122,281],[x+4,122,281],[x+4,122,273],[x-4,122,273]],[0,1,0],[247,218,159,255])
        add('proxy_shop_'+theme,mesh,'ProxyShop')
    for variant,color in enumerate([[221,65,131,0],[184,87,190,0],[228,84,103,0]]):
        mesh=Mesh();mesh.face([[-47,43,-20],[47,43,-20],[47,43,5],[-47,43,5]],[0,1,0],[36,64,44,0])
        mesh.face([[-43,44,3],[43,44,3],[43,44,25],[-43,44,25]],[0,1,0],color)
        add('proxy_window_'+str(variant),mesh,'ProxyWindow')
    for theme,color in PALETTES.items():
        mesh=Mesh();mesh.face([[-22,60,270],[22,60,270],[22,60,360],[-22,60,360]],[0,1,0],color[:3]+[0])
        mesh.face([[-22,88,240],[22,88,240],[22,88,260],[-22,88,260]],[0,1,0],[224,75,139,0])
        for x in [-18,0,18]:mesh.face([[x-4,59,370],[x+4,59,370],[x+4,59,378],[x-4,59,378]],[0,1,0],[247,218,159,255])
        add('proxy_pole_'+theme,mesh,'ProxyPole')
    return objects


def make_placements(scene,geo,surfaces,buildings,water,routes,doors,occupied,urns):
    records=[];rejected=[]
    lamps=spread([f for f in scene['pick_features'] if f['kind']=='street_lamp'],lambda f:f['point_cm'],lambda f:f['id'])
    for f in lamps:
        p=f['point_cm'];props=f['properties'];chosen=None
        # The normal points into a verified walking surface, away from traffic.
        for turn in range(8):
            yaw=props.get('yaw_degrees',0)+turn*45;a=math.radians(yaw);n=[-math.sin(a),math.cos(a)];x=p[0]+n[0]*60;y=p[1]+n[1]*60;foot=Point(x,y).buffer(34)
            if foot.intersects(buildings) or foot.intersects(water):continue
            cover,hs=surfaces.query(x,y,34)
            if max(cover.get('path',0),cover.get('sidewalk',0))<.98 or max(cover.get(k,0) for k in ('road','water','bridge'))>.001:continue
            height=max([h for k,h in hs if k in ('ground','path','sidewalk')] or [p[2]])
            clearance=p[2]+221-height
            if clearance<205:continue
            chosen=(yaw,clearance,max(cover.get('path',0),cover.get('sidewalk',0)));break
        if chosen is None:rejected.append(dict(source_id=f['id'],reason='No safe walking surface and 205cm headroom for pole decoration'));continue
        seed=int(hashlib.sha256(f['id'].encode()).hexdigest()[:8],16);theme=list(PALETTES)[seed%3];yaw,clearance,coverage=chosen
        records.append(dict(kind='pole',source_id=f['id'],building_source_id=None,source_wgs84=props['wgs84_centre'],placement_provenance='inferred_banner_and_flowers_on_mapped_lamp_position',anchor_cm=p,yaw_degrees=yaw,minimum_clearance_cm=round(clearance,4),path_coverage=round(coverage,5),models=['pole_metal','pole_bulbs','pole_flowers_'+str(seed%3),'pole_banner_'+theme,'proxy_pole_'+theme]))
    # Add public-space flowers where shops do not supply a planter. Existing
    # mapped benches provide an anchor; no unverified pavement grid is filled.
    counts=defaultdict(int)
    for r in urns:counts[cell(r['anchor_cm'])]+=1
    benches=spread([f for f in scene['pick_features'] if f['kind']=='street_bench'],lambda f:f['point_cm'],lambda f:f['id']);added=0
    for f in benches:
        if added>=40:break
        p=f['point_cm'];props=f['properties']
        if counts[cell(p)]>=4:continue
        a=math.radians(props.get('yaw_degrees',0));t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
        for side in [-1,1]:
            x=p[0]+t[0]*side*175+n[0]*25;y=p[1]+t[1]*side*175+n[1]*25;point=Point(x,y);foot=point.buffer(43)
            if any(foot.intersects(g) for g in [buildings,water,routes,doors,occupied]):continue
            if any(point.distance(Point(r['anchor_cm'][:2]))<155 for r in urns):continue
            cover,hs=surfaces.query(x,y,43);wide,_=surfaces.query(x+n[0]*85,y+n[1]*85,85)
            coverage=max(cover.get('path',0),cover.get('sidewalk',0));clearance=max(wide.get('path',0),wide.get('sidewalk',0))
            if coverage<.98 or clearance<.85 or max(cover.get(k,0) for k in ('water','road','bridge'))>.001:continue
            heights=[h for k,h in hs if k in ('path','sidewalk')]
            if not heights:continue
            z=max(heights)-.5;seed=int(hashlib.sha256(f['id'].encode()).hexdigest()[:8],16);ll=geo.from_ue(x,y,z)
            r=dict(kind='urn',source_id=f['id'],building_source_id=None,source_wgs84=props['wgs84_centre'],anchor_source_kind='street_bench',placement_provenance='inferred_public_flower_urn_beside_mapped_bench',anchor_cm=[x,y,z],yaw_degrees=props.get('yaw_degrees',0),wgs84_placement=list(ll[:2]),footprint_radius_cm=43,path_coverage=coverage,clearance_coverage=clearance,models=['urn_stone','urn_metal','urn_flowers_'+str(seed%3)])
            records.append(r);urns.append(r);counts[cell(p)]+=1;added+=1;break
    return records,rejected
