"""Inferred festive spans anchored to real opposing building footprints."""
import hashlib,math
from collections import defaultdict
import numpy as np
from shapely.geometry import Point,LineString,shape
from shapely.ops import transform
from shapely.strtree import STRtree
from generate_paris_frontages import Mesh
from paris_district_layout import district_windows,spread

SPAN_LIMIT=96
SPAN_LOWEST_CM=480
COLORS=[[151,37,67,255],[38,82,135,255],[231,202,139,255],[54,121,100,255]]


def make_models(lathe_at):
    result=[];wire=Mesh();bulbs=Mesh()
    def add(name,mesh,role):
        item=mesh.item(name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    def height(x,lower=False):return (560 if lower else 620)-(35 if lower else 55)*(1-(x/500)**2)
    for lower in [False,True]:
        y=0
        for j in range(48):
            x=-500+j*1000/48;xx=-500+(j+1)*1000/48
            wire.tube([x,y,height(x,lower)],[xx,y,height(xx,lower)],.48,[120,98,58,255],6)
        for x in [-500,500]:wire.box([0,0,0],[1,0,0],[0,1,0],[x,y,height(x,lower)],[3,16,18],[133,105,61,255])
    add('street_festoon_wire',wire,'Metal')
    for theme in range(2):
        flags=Mesh();proxy=Mesh()
        for j in range(14):
            x=-460+j*920/13;z=height(x)-2;c=COLORS[(j+theme*2)%4]
            for k in range(4):
                u=k/4;v=(k+1)/4
                def p(q,bottom=False):return [x+(q-.5)*46,3*math.sin(q*math.tau+j),z-(12+59*(1-abs(q-.5)*2) if bottom else 0)]
                flags.face([p(u),p(v),p(v,True),p(u,True)],[0,1,0],c)
            flags.tube([x-23,0,z],[x+23,0,z],.35,[198,163,91,255],5)
            proxy.face([[x-23,0,z],[x+23,0,z],[x,0,z-71]],[0,1,0],c[:3]+[0])
        for j in range(17):
            x=-470+j*940/16;z=height(x,True)-9
            proxy.face([[x-10,0,z-10],[x+10,0,z-10],[x+10,0,z+10],[x-10,0,z+10]],[0,1,0],[255,215,151,255])
        add('street_festoon_flags_'+str(theme),flags,'Fabric');add('proxy_street_'+str(theme),proxy,'ProxyStreet')
    for j in range(17):
        x=-470+j*940/16;z=height(x,True)
        lathe_at(bulbs,[(z-20,0),(z-19,3.5),(z-15,6),(z-8,6),(z-4,3),(z-2,2)],x,0,[255,219,163,255],16)
    add('street_festoon_bulbs',bulbs,'FestiveGlow')
    return result


def make_placements(scene,district,geo,surfaces,buildings,water,records):
    local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
    windows,allowed=district_windows(scene['source_scene_sha256']);features=[];polys=[]
    for f in district['layers']['buildings']:
        if f['properties']['source_id'] in allowed and (f['properties'].get('height_gutter_min_m') or f['properties'].get('height_m',0))>=8:
            features.append(f);polys.append(local(shape(f['geometry'])))
    tree=STRtree(polys);by_source=defaultdict(list)
    for w in windows:by_source[w['source_id']].append(w)
    candidates=[];rejected=[]
    for f in sorted(district['layers']['roads'],key=lambda f:f['properties']['source_id']):
        props=f['properties'];tags=props.get('tags',{})
        if props.get('bridge') or props.get('tunnel') or props.get('layer',0)!=0 or tags.get('highway') not in ('pedestrian','living_street','residential','service','footway'):continue
        if tags.get('access') in ('private','no'):continue
        line=local(shape(f['geometry']))
        if line.geom_type!='LineString' or line.length<1400:continue
        seed=int(hashlib.sha256(props['source_id'].encode()).hexdigest()[:8],16)
        for station in np.arange(600+seed%700,line.length-400,2300):
            centre=line.interpolate(station);a=line.interpolate(max(0,station-100));b=line.interpolate(min(line.length,station+100));dx=b.x-a.x;dy=b.y-a.y;length=math.hypot(dx,dy)
            if length<1:continue
            across=np.array([-dy/length,dx/length]);ends=[];sources=[]
            for side in [-1,1]:
                ray=LineString([centre.coords[0],(centre.x+across[0]*side*2200,centre.y+across[1]*side*2200)]);hits=[]
                for index in tree.query(ray):
                    if polys[index].contains(centre):continue
                    hit=ray.intersection(polys[index].boundary)
                    if hit.is_empty:continue
                    points=[hit] if hit.geom_type=='Point' else [p for p in getattr(hit,'geoms',[]) if p.geom_type=='Point']
                    for p in points:
                        distance=p.distance(centre)
                        if distance>80:hits.append((distance,p,features[index]['properties']['source_id']))
                if not hits:break
                _,point,sid=min(hits,key=lambda h:(h[0],h[2]));ends.append(point);sources.append(sid)
            if len(ends)!=2 or sources[0]==sources[1]:continue
            span=LineString([p.coords[0] for p in ends]);width=span.length
            if not 600<=width<=1500 or span.intersects(water) or span.intersection(buildings).length>2:continue
            floors=[];safe=True
            for sample in np.linspace(.02,.98,11):
                p=span.interpolate(sample,normalized=True);cover,hs=surfaces.query(p.x,p.y,12)
                if max(cover.get('water',0),cover.get('bridge',0))>.001:safe=False;break
                h=[z for kind,z in hs if kind in ('ground','road','path','sidewalk')]
                if not h:safe=False;break
                floors.extend(h)
            if not safe:continue
            base=max(floors);blocked=False;wall_heights=[];wall_floors=[]
            for end,sid in zip(ends,sources):
                building=next(f for f in features if f['properties']['source_id']==sid)['properties']
                wall_height=building.get('height_gutter_min_m') or building.get('height_m',0)
                q=LineString([end.coords[0],centre.coords[0]]).interpolate(25);_,hs=surfaces.query(q.x,q.y,5)
                ground=max([z for kind,z in hs if kind in ('ground','road','path','sidewalk')] or [base])
                if base+620>ground+wall_height*100-50:blocked=True;break
                wall_heights.append(wall_height);wall_floors.append(ground)
                for w in by_source[sid]:
                    p=w['centre_cm'];n=w['normal'];t=[n[1],-n[0]];delta=[end.x-p[0],end.y-p[1]]
                    if abs(sum(delta[i]*n[i] for i in range(2)))>22:continue
                    if abs(sum(delta[i]*t[i] for i in range(2)))>w['width_cm']/2+16:continue
                    if any(p[2]-w['height_cm']/2-16<base+h<p[2]+w['height_cm']/2+16 for h in (560,620)):blocked=True;break
                if blocked:break
            if blocked:continue
            midpoint=span.interpolate(.5,normalized=True);angle=math.degrees(math.atan2(ends[1].y-ends[0].y,ends[1].x-ends[0].x));variant=seed%2;ll=geo.from_ue(midpoint.x,midpoint.y,base)
            candidates.append(dict(kind='street_garland',source_id=props['source_id'],building_source_id=None,anchor_building_source_ids=sources,anchor_wall_height_m=wall_heights,anchor_wall_ground_cm=wall_floors,source_wgs84=props['wgs84_centre'],wgs84_placement=list(ll[:2]),placement_provenance='inferred_festival_garland_between_opposing_mapped_building_footprints',anchor_cm=[midpoint.x,midpoint.y,base],yaw_degrees=angle,scale_xyz=[width/1000,1,1],span_cm=width,anchor_ends_cm=[[p.x,p.y,base+620] for p in ends],maximum_ground_cm=base,minimum_clearance_cm=SPAN_LOWEST_CM,flags=14,bulbs=17,models=['street_festoon_wire','street_festoon_flags_'+str(variant),'street_festoon_bulbs','proxy_street_'+str(variant)]))
    selected=[]
    for r in spread(candidates,lambda r:r['anchor_cm'],lambda r:(r['source_id'],r['anchor_cm'][0],r['anchor_cm'][1])):
        if len(selected)>=SPAN_LIMIT:break
        if any(math.dist(r['anchor_cm'][:2],other['anchor_cm'][:2])<1800 for other in selected):continue
        selected.append(r)
    return selected,rejected


def inspection_camera(garlands,scene,surfaces,buildings,water,occupied,records):
    trees=[Point(f['point_cm'][:2]) for f in scene['pick_features'] if f['kind']=='street_tree']
    tree=STRtree(trees);choices=[]
    for r in garlands:
        p=r['anchor_cm'];angle=math.radians(r['yaw_degrees']);t=np.array([math.cos(angle),math.sin(angle)]);n=np.array([-t[1],t[0]])
        for distance in [1600,2200,2800]:
            for along in [-1,1]:
                for side in [-1,1]:
                    eye=np.array(p[:2])+n*distance*along+t*side*(r['span_cm']/2-140);point=Point(eye);target=[p[0],p[1],p[2]+400];ray=LineString([eye,target[:2]])
                    if point.distance(buildings)<50 or point.distance(water)<50 or point.distance(occupied)<40 or ray.intersection(buildings).length>1:continue
                    if any(trees[i].distance(point)<220 or trees[i].distance(ray)<120 for i in tree.query(ray.buffer(220))):continue
                    cover,hs=surfaces.query(*eye,35)
                    if max(cover.get('path',0),cover.get('sidewalk',0))<.9 or cover.get('road',0)>.01:continue
                    floors=[z for kind,z in hs if kind in ('ground','path','sidewalk')]
                    if not floors:continue
                    shops=sum(v['kind']=='canopy' and math.dist(v['anchor_cm'][:2],p[:2])<2500 for v in records)
                    nearby=sum(math.dist(v['anchor_cm'][:2],p[:2])<5000 for v in garlands)
                    score=shops*5+nearby*3-distance/2000
                    choices.append((score,dict(name='Festival street',source_id=r['source_id'],eye_cm=[float(eye[0]),float(eye[1]),max(floors)+170],target_cm=target)))
    return max(choices,key=lambda pair:pair[0])[1] if choices else None
