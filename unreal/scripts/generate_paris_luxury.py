"""Original inferred Paris street decoration, attached to archived storefronts."""
import hashlib,json,math,random,sys
from pathlib import Path
import numpy as np
from shapely.geometry import Point,Polygon,LineString,shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data'
sys.path[:0]=[str(ROOT/'unreal/scripts'),str(ROOT/'gis')]
from generate_paris_frontages import Mesh
from generate_paris_morris import lathe,DTYPE
from paris_twin.coordinates import Georeference
from paris_twin.io import read
from generate_paris_facade_gardens import make_models as facade_models,make_placements as facade_placements
from generate_paris_district_decor import make_models as district_models,make_placements as district_placements
from paris_district_layout import spread,coverage_report,inspection_views
from generate_paris_street_garlands import make_models as garland_models,make_placements as garland_placements,inspection_camera as garland_camera
from generate_paris_window_lights import make_models as window_light_models,make_placements as window_light_placements
from generate_paris_window_relief import make_models as window_relief_models,make_placements as window_relief_placements
from generate_paris_party import make_models as party_models,make_placements as party_placements
from generate_paris_street_props import make_models as street_prop_models,make_placements as street_prop_placements
from generate_paris_extra_objects import make_models as extra_object_models,make_placements as extra_object_placements,inspection_camera as extra_object_camera

DECORATION_RECIPE='paris_street_accents_v10'
BULBS_PER_STOREFRONT=12


class Surfaces:
    def __init__(self,scene):
        blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');self.polys=[];self.tris=[];self.kinds=[]
        for o in scene['objects']:
            if o['kind'] not in ('ground','path','sidewalk','road','water','bridge'):continue
            b=o['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
            ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
            for tri in v['p'][ix].astype('f8'):
                p=Polygon(tri[:,:2])
                if p.area>.001:self.polys.append(p);self.tris.append(tri);self.kinds.append(o['kind'])
        self.tree=STRtree(self.polys)

    def query(self,x,y,radius=40):
        circle=Point(x,y).buffer(radius);cover={};heights=[]
        for i in self.tree.query(circle):
            p=self.polys[i];k=self.kinds[i]
            if not p.intersects(circle):continue
            cover.setdefault(k,[]).append(p)
            a,b,c=self.tris[i];u=b-a;v=c-a;d=u[0]*v[1]-u[1]*v[0];dx=x-a[0];dy=y-a[1]
            s=(dx*v[1]-dy*v[0])/d;t=(u[0]*dy-u[1]*dx)/d
            if min(s,t,1-s-t)>=-1e-6:heights.append((k,float(a[2]+s*u[2]+t*v[2])))
        return {k:unary_union(ps).intersection(circle).area/circle.area for k,ps in cover.items()},heights


def flower(mesh,p,r,color,phase=0):
    # Rounded, shallowly cupped petals with smooth vertex normals.
    x,y,z=p
    for j in range(6):
        a=phase+j*math.tau/6;u=(math.cos(a),math.sin(a));v=(-u[1],u[0])
        def q(d,w,h):return [x+u[0]*d+v[0]*w,y+u[1]*d+v[1]*w,z+h]
        rim=[]
        for k in range(10):
            theta=k*math.tau/10;d=r*(.59+.50*math.cos(theta));w=r*.39*math.sin(theta)
            rim.append(q(d,w,r*(.07+.06*d/r)))
        centre=q(r*.59,0,r*.23)
        for k in range(10):
            start=len(mesh.positions_cm);mesh.face([centre,rim[k],rim[(k+1)%10]],[0,0,1],color)
            for i in range(start,len(mesh.positions_cm)):
                pp=mesh.positions_cm[i];dx=pp[0]-x;dy=pp[1]-y;w=(dx*v[0]+dy*v[1])/r;d=(dx*u[0]+dy*u[1])/r-.59
                n=[u[0]*d*.28+v[0]*w*.65,u[1]*d*.28+v[1]*w*.65,1];length=math.sqrt(sum(s*s for s in n));mesh.normals[i]=[s/length for s in n]
    lathe_at(mesh,[(z-.2,r*.16),(z+.7,r*.21),(z+1.1,0)],x,y,[190,152,55,255],8)


def lathe_at(mesh,profile,x,y,color,sides=20):
    temp=Mesh();lathe(temp,profile,color,sides)
    for p in temp.positions_cm:p[0]+=x;p[1]+=y
    mesh.extend(temp)


def facing_flower(mesh,p,r,color,phase=0,angle=-math.pi/2):
    temp=Mesh();flower(temp,[0,0,0],r,color,phase);cs=math.cos(angle);sn=math.sin(angle)
    for q in temp.positions_cm:
        x,y,z=q;q[:]=[p[0]+x,p[1]+y*cs-z*sn,p[2]+y*sn+z*cs]
    for q in temp.normals:
        x,y,z=q;q[:]=[x,y*cs-z*sn,y*sn+z*cs]
    mesh.extend(temp)


def greenery(mesh,seed,small=False,hanging=False):
    rng=random.Random(seed);scale=.16 if small else 1;origin=[0,0,86 if small else 72]
    for i in range(42 if not small else 12):
        a=rng.random()*math.tau;d=rng.uniform(5,34)*scale
        x=math.cos(a)*d;y=math.sin(a)*d;z=origin[2]+rng.uniform(0,25)*scale
        if not small:mesh.tube([x*.4,y*.4,68],[x,y,z],.5,[43,77,35,255],5)
        for j in range(2 if not small else 3):
            aa=a+j*2.1;length=rng.uniform(9,15)*scale;width=length*.24
            c=[x+math.cos(aa)*length*.45,y+math.sin(aa)*length*.45,z-2*scale]
            u=[math.cos(aa),math.sin(aa)];v=[-u[1],u[0]]
            leaf_color=[[40,65,36,255],[50,82,43,255],[60,94,45,255]][(i+j)%3]
            # An elliptical leaf with a shallow raised midrib, instead of a
            # single large diamond. Six triangles preserve its curved outline.
            centre=[x+u[0]*length*.5,y+u[1]*length*.5,z+.7*scale]
            rim=[]
            for k in range(6):
                theta=k*math.tau/6;along=length*(.5+.5*math.cos(theta));across=width*math.sin(theta)
                rim.append([x+u[0]*along+v[0]*across,y+u[1]*along+v[1]*across,z-along*.18])
            for k in range(6):mesh.face([centre,rim[k],rim[(k+1)%6]],[0,0,1],leaf_color)
        if i%3!=2:
            palettes=[[[211,29,83,255],[244,91,148,255],[247,221,214,255]],[[192,32,54,255],[247,227,205,255],[160,64,177,255]],[[235,83,109,255],[181,105,204,255],[246,153,192,255]]]
            # The colour index is independent of the skipped shoots, so every
            # palette includes its accent colour rather than losing one hue.
            bloom=facing_flower if hanging else flower
            kwargs={'angle':-math.pi*.36} if hanging else {}
            bloom(mesh,[x,y,z+7*scale],rng.uniform(5.5,7.5)*scale,palettes[seed%3][(i//3+i)%3],a,**kwargs)


def translate(mesh,offset,scale=1,origin=(0,0,0)):
    for p in mesh.positions_cm:
        for i in range(3):p[i]=(p[i]-origin[i])*scale+offset[i]


def shop_blossoms():
    """Front-facing flowers hang from the existing canopy above safe paths."""
    basket=Mesh();wire=Mesh();bulbs=Mesh();flowers=[]
    bronze=[138,111,67,255];dark=[36,49,40,255]
    for side in [-1,1]:
        x=side*140;y=138
        lathe_at(basket,[(221,8),(222,15),(226,22),(234,25),(237,25),(238,23)],x,y,[62,64,43,255],24)
        lathe_at(basket,[(235,25.3),(236.2,26),(238.2,26),(239,24.8)],x,y,bronze,24)
        lathe_at(basket,[(237,23.2),(237,0)],x,y,[49,35,23,255],24)
        for a in [0,math.tau/3,math.tau*2/3]:
            end=[x+24*math.cos(a),y+24*math.sin(a),235]
            basket.tube([x,118,263],end,.55,bronze,6)
    for variant in range(3):
        mesh=Mesh();rng=random.Random(490+variant)
        for side in [-1,1]:
            temp=Mesh();greenery(temp,42+variant,hanging=True)
            translate(temp,[side*140,138,237],.60,(0,0,72));mesh.extend(temp)
            # Short trailing ivy stays safely above the walking envelope.
            for k in range(3):
                a=k*math.tau/3;px=side*140+23*math.cos(a);py=138+23*math.sin(a)
                mesh.tube([px,py,237],[px+3*math.cos(a),py+3*math.sin(a),223],.45,[45,78,40,255],5)
                for z in [235,231,227]:
                    mesh.face([[px,py,z+3],[px+5,py+2,z],[px,py+4,z-4],[px-5,py+2,z]],[0,.6,.8],[53,93,44,255])
        # A supported floral band above the front edge of the canopy.
        for j in range(15):
            x=-157+j*314/14
            for k in range(2):
                xx=x+(k-.5)*7+rng.uniform(-4,4);z=278+(j%3)*2+rng.uniform(-3.5,3.5)
                mesh.face([[xx-8,120,z],[xx,121,z+4],[xx+8,120,z],[xx,122,z-5]],[0,1,0],[45,79,40,255])
                color=[[218,37,90,255],[246,110,161,255],[246,220,211,255],[172,74,178,255]][(j+k+variant)%4]
                facing_flower(mesh,[xx,124+rng.uniform(-2,2),z+3],rng.uniform(4.2,6.3),color,j*.4,angle=-math.pi/2+rng.uniform(-.18,.18))
        flowers.append(mesh)
    # Festoon poles, a gently sagging wire and twelve small warm bulbs.
    for x in [-171,171]:wire.tube([x,118,264],[x,118,291],.8,bronze,8)
    def height(x):return 274+14*(x/171)**2
    for j in range(24):
        x0=-171+j*342/24;x1=-171+(j+1)*342/24
        wire.tube([x0,120,height(x0)],[x1,120,height(x1)],.25,dark,5)
    # A separate rail supports the flowers without draping across the signs.
    wire.tube([-171,114,278],[171,114,278],.6,bronze,6)
    for j in range(BULBS_PER_STOREFRONT):
        x=-158+j*316/(BULBS_PER_STOREFRONT-1);z=height(x)
        wire.tube([x,120,z],[x,120,z-3],.45,dark,6)
        lathe_at(wire,[(z-4,1.8),(z-2.5,1.8)],x,120,bronze,10)
        lathe_at(bulbs,[(z-9,0),(z-8.5,1.9),(z-6.5,3),(z-4.5,2.6),(z-3.5,1.4)],x,120,[247,218,159,255],12)
    return basket,flowers,wire,bulbs


def models():
    stone=Mesh(bevel_cm=.25);metal=Mesh();objects=[]
    ivory=[204,195,173,255];bronze=[151,124,70,255]
    stone.box([0,0,0],[1,0,0],[0,1,0],[0,0,6],[43,43,12],ivory)
    lathe(stone,[(12,23),(17,24),(21,18),(33,13),(38,15),(44,24),(53,31),(62,34),(66,37),(70,37),(73,34)],ivory,32)
    # Fine fluting and shell-like raised ribs on the bowl.
    for j in range(16):
        a=j*math.tau/16
        for (z0,r0),(z1,r1) in zip([(40,19),(49,28),(59,33)],[(49,28),(59,33),(65,35)]):
            stone.tube([r0*math.cos(a),r0*math.sin(a),z0],[r1*math.cos(a),r1*math.sin(a),z1],1.2,ivory,6)
    lathe(metal,[(66,37.2),(67,37.8),(68,37.8),(69,37.2)],bronze,32)
    lathe(metal,[(71,33),(72,33),(72,0)],[58,45,31,255],24)
    for side in [-1,1]:
        pts=[[side*(33+9*math.sin(j*math.pi/12)),0,54+11*math.cos(j*math.pi/12)] for j in range(13)]
        for a,b in zip(pts,pts[1:]):metal.tube(a,b,1.25,bronze,6)
    def add(name,mesh,material):
        item=mesh.item(name,'M_ParisLuxury'+material);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');objects.append(item)
    add('urn_stone',stone,'Stone');add('urn_metal',metal,'Metal')
    for variant in range(3):
        nature=Mesh();greenery(nature,42+variant);add('urn_flowers_'+str(variant),nature,'Nature')
    for theme,color in [('red',[121,38,47,255]),('green',[32,65,51,255]),('cream',[185,155,104,255])]:
        fabric=Mesh()
        for j in range(14):
            x0=-173.5+j*347/14;x1=-173.5+(j+1)*347/14;c=color if j%2==0 else [225,215,187,255]
            fabric.face([[x0,4,293],[x1,4,293],[x1,114.9,264],[x0,114.9,264]],[0,.253,.967],c)
            for k in range(5):
                xx0=x0+(x1-x0)*k/5;xx1=x0+(x1-x0)*(k+1)/5
                b0=244-7*math.sin(k*math.pi/5);b1=244-7*math.sin((k+1)*math.pi/5)
                fabric.face([[xx0,115.6,264],[xx1,115.6,264],[xx1,115.6,b1],[xx0,115.6,b0]],[0,1,0],c)
        add('canopy_'+theme,fabric,'Fabric')
    trims=Mesh()
    for x in [-174,174]:
        trims.tube([x,4,293.5],[x,115,264.5],.85,bronze,8)
        points=[[x,8+100*j/12,281-28*math.sin(j*math.pi/24)] for j in range(13)]
        for a,b in zip(points,points[1:]):trims.tube(a,b,.8,[39,57,49,255],6)
    trims.tube([-174,116,264.5],[174,116,264.5],.85,bronze,8)
    add('canopy_metal',trims,'Metal')
    top=Mesh();rim=Mesh();nature=Mesh();cushions=Mesh(bevel_cm=.7)
    lathe(top,[(76.15,37.5),(78.5,37.5),(79,36.8),(79,0)],[226,220,205,255],32)
    lathe(rim,[(77.8,37.8),(78.4,37.9),(78.8,37.5)],bronze,32)
    for x in [-14,14]:
        lathe_at(top,[(79,x*0+7),(79.8,7),(80,0)],x,-7,[238,230,210,255],16)
        lathe_at(top,[(80,3.8),(86,4.5),(86.3,4.4),(86.3,3.4),(85.5,3.3),(81,2.8)],x,-7,[238,230,210,255],16)
        lathe_at(top,[(85,3.4),(85,0)],x,-7,[67,39,24,255],16)
    lathe(rim,[(79,3.4),(80,4),(85,2.8),(88,2.3)],bronze,16)
    greenery(nature,73,small=True)
    for side in [-1,1]:cushions.box([0,0,0],[1,0,0],[0,1,0],[side*72,0,50],[39,39,3.7],[111,44,43,255])
    add('table_stone',top,'Marble');add('table_metal',rim,'Metal');add('table_nature',nature,'Nature');add('table_cushions',cushions,'Fabric')
    basket,flower_models,wire,bulbs=shop_blossoms()
    add('floral_basket',basket,'Metal')
    for i,mesh in enumerate(flower_models):add('floral_flowers_'+str(i),mesh,'Nature')
    add('festoon_wire',wire,'Metal');add('festoon_bulbs',bulbs,'Bulb')
    objects.extend(facade_models(facing_flower))
    objects.extend(district_models(greenery,lathe_at))
    objects.extend(garland_models(lathe_at))
    objects.extend(window_light_models())
    objects.extend(window_relief_models())
    objects.extend(party_models(lathe_at))
    objects.extend(street_prop_models(lathe_at,flower))
    objects.extend(extra_object_models(lathe_at,flower))
    return objects


def generate():
    scene=read(DATA/'paris-digital-twin-runtime.json');geo=Georeference(read(ROOT/'gis/config/ile_de_la_cite.json'));surfaces=Surfaces(scene)
    district=read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
    def local(g):
        from shapely.ops import transform
        return transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
    buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
    water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
    businesses=[f for f in scene['pick_features'] if f['kind']=='business'];centre=scene['quality_centre_ue_cm']
    doors=unary_union([LineString([f['point_cm'][:2],[f['point_cm'][0]-math.sin(math.radians(f['properties']['facade_yaw_degrees']))*300,f['point_cm'][1]+math.cos(math.radians(f['properties']['facade_yaw_degrees']))*300]]).buffer(68) for f in businesses])
    routes=unary_union([LineString(r['points_cm']).buffer(50) for r in scene['pedestrians']['routes'] if len(r['points_cm'])>1])
    furniture=[]
    for f in scene['pick_features']:
        if f['kind'].startswith('street_') and 'point_cm' in f:furniture.append(Point(f['point_cm'][:2]).buffer(110 if f['kind'] in ('street_bench','street_bicycle_rack') else 55))
    for f in businesses:
        if f['properties'].get('terrace_placed'):furniture.append(Point(f['properties']['terrace_cm'][:2]).buffer(120))
    morris=read(DATA/'paris-morris.json')
    furniture.extend(Point(r['anchor_cm'][:2]).buffer(r['footprint_radius_cm']+20) for r in morris['records'])
    occupied=unary_union(furniture);records=[];rejected=[];urns=[];themes={}
    for b in scene['instance_batches']:
        if b['model'].startswith('awning_'):
            for i in b['instances']:themes[i['source_id']]=b['model'].split('_',1)[1]
    ordered=sorted(businesses,key=lambda f:(math.dist(f['point_cm'][:2],centre[:2]),f['id']))
    selected=ordered[:80]+spread(ordered[80:],lambda f:f['point_cm'],lambda f:f['id'])
    for index,f in enumerate(selected):
        sid=f['id'];p=f['point_cm'];props=f['properties'];yaw=props['facade_yaw_degrees'];a=math.radians(yaw);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
        common=dict(source_id=sid,building_source_id=props['building_source_id'],source_wgs84=props['wgs84_centre'],placement_provenance='inferred_decoration_at_existing_inferred_storefront',yaw_degrees=yaw)
        variant=int(hashlib.sha256(sid.encode()).hexdigest()[:8],16)%3
        floors=[];walking=True;walk_coverage=[]
        for side in [-1,1]:
            cx=p[0]+t[0]*side*140+n[0]*138;cy=p[1]+t[1]*side*140+n[1]*138
            cover,_=surfaces.query(cx,cy,34)
            walk_coverage.append(max(cover.get('path',0),cover.get('sidewalk',0)))
            walking &= max(cover.get('path',0),cover.get('sidewalk',0))>=.98 and max(cover.get(k,0) for k in ('road','water','bridge'))<.001
            for dx,dy in [(0,0),(34,0),(-34,0),(0,34),(0,-34)]:
                x=p[0]+t[0]*(side*140+dx)+n[0]*(138+dy);y=p[1]+t[1]*(side*140+dx)+n[1]*(138+dy)
                _,hs=surfaces.query(x,y,2)
                floors.extend(h for k,h in hs if k in ('ground','path','sidewalk','road','bridge'))
        clearance=p[2]+221-max(floors or [p[2]])
        hanging=clearance>=205 and walking
        parts=['canopy_'+themes[sid],'canopy_metal','festoon_wire','festoon_bulbs','proxy_shop_'+themes[sid]]
        if hanging:parts+=['floral_basket','floral_flowers_'+str(variant)]
        records.append(dict(**common,kind='canopy',anchor_cm=p,hanging_baskets=2 if hanging else 0,bulbs=BULBS_PER_STOREFRONT,minimum_hanging_clearance_cm=round(clearance,4) if hanging else None,hanging_walk_coverage=round(min(walk_coverage),5),hanging_not_placed_reason=None if hanging else 'Insufficient 205cm headroom or no safe mapped walking surface under baskets',models=parts))
        # Existing positive outdoor_seating sites receive tabletop details only.
        if props.get('terrace_placed'):records.append(dict(**common,kind='table',anchor_cm=props['terrace_cm'],models=['table_stone','table_metal','table_nature','table_cushions']))
        for side in [-1,1]:
            if len(urns)>=(64 if index<80 else 240):break
            placed=False
            for along,out in [(side*132,62),(side*145,85),(side*218,62),(side*245,95),(side*205,115)]:
                x=p[0]+t[0]*along+n[0]*out;y=p[1]+t[1]*along+n[1]*out;point=Point(x,y);foot=point.buffer(40)
                if foot.intersects(buildings) or foot.intersects(water) or foot.intersects(doors) or foot.intersects(routes) or foot.intersects(occupied):continue
                if any(foot.distance(Point(r['anchor_cm'][:2]))<115 for r in urns):continue
                cover,heights=surfaces.query(x,y,43);wide,_=surfaces.query(x+n[0]*85,y+n[1]*85,85)
                coverage=max(cover.get('path',0),cover.get('sidewalk',0));clear=max(wide.get('path',0),wide.get('sidewalk',0))
                if coverage<.98 or clear<.85 or max(cover.get(k,0) for k in ('water','road','bridge'))>.001:continue
                hs=[h for k,h in heights if k in ('path','sidewalk')]
                if not hs:continue
                z=max(hs)-.5
                if abs(z-p[2])>24:continue
                seed=int(hashlib.sha256((sid+str(side)).encode()).hexdigest()[:8],16);ll=geo.from_ue(x,y,z)
                r=dict(**common,kind='urn',anchor_cm=[round(x,4),round(y,4),round(z,4)],wgs84_placement=list(ll[:2]),footprint_radius_cm=43,path_coverage=round(coverage,5),clearance_coverage=round(clear,5),models=['urn_stone','urn_metal','urn_flowers_'+str(seed%3)])
                records.append(r);urns.append(r);placed=True;break
            if not placed:rejected.append(dict(source_id=sid,side=side,reason='No clear mapped walking surface beside storefront; keep entrance, route, road and existing furniture clear'))
    selected_ids={f['id'] for f in selected}
    for f in businesses:
        props=f['properties']
        if f['id'] not in selected_ids and props.get('terrace_placed'):
            records.append(dict(source_id=f['id'],building_source_id=props['building_source_id'],source_wgs84=props['wgs84_centre'],placement_provenance='inferred_tabletop_detail_at_existing_terrace',yaw_degrees=props['facade_yaw_degrees'],kind='table',anchor_cm=props['terrace_cm'],models=['table_stone','table_metal','table_nature','table_cushions']))
    # Make the existing real, tagged cafe terrace the main inspection view.
    cameras=[]
    for f in selected[:80]:
        if not f['properties'].get('terrace_placed'):continue
        p=f['point_cm'];a=math.radians(f['properties']['facade_yaw_degrees']);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
        for distance,side in [(640,460),(730,-420),(580,240),(850,0)]:
            x=p[0]+n[0]*distance+t[0]*side;y=p[1]+n[1]*distance+t[1]*side;point=Point(x,y);target=[p[0]+n[0]*80,p[1]+n[1]*80,p[2]+170]
            if point.distance(buildings)<45 or point.distance(water)<45 or LineString([(x,y),target[:2]]).intersects(buildings):continue
            cover,heights=surfaces.query(x,y,35)
            if max(cover.get('path',0),cover.get('sidewalk',0))<.85 or cover.get('road',0)>.01:continue
            z=max([h for k,h in heights if k in ('path','sidewalk','ground')] or [p[2]])+170
            count=sum(r['source_id']==f['id'] for r in urns)
            cameras.append((math.dist(p[:2],centre[:2])-count*500,dict(source_id=f['id'],eye_cm=[x,y,z],target_cm=target)));break
    if not cameras or not urns:raise RuntimeError('No safe decorated street or inspection camera')
    public,public_rejected=district_placements(scene,geo,surfaces,buildings,water,routes,doors,occupied,urns)
    records.extend(public);rejected.extend(public_rejected)
    upper,upper_rejected,window_candidates=facade_placements(scene,geo,surfaces,return_candidates=True);records.extend(upper);rejected.extend(upper_rejected)
    close=min(cameras,key=lambda c:c[0])[1];wide=[]
    ref=next(f for f in selected if f['id']==close['source_id']);p=ref['point_cm'];a=math.radians(ref['properties']['facade_yaw_degrees']);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
    wide_offsets=[(1250,220),(1100,460),(1400,-350),(1000,-450),(950,300)]
    wide_offsets += [(distance,side) for distance in [600,500,400,700,800,300] for side in [900,-900,1150,-1150,1400,-1400]]
    tree_points=[Point(f['point_cm'][:2]) for f in scene['pick_features'] if f['kind']=='street_tree' and 'point_cm' in f]
    tree_centres=unary_union(tree_points)
    for distance,side in wide_offsets:
        x=p[0]+n[0]*distance+t[0]*side;y=p[1]+n[1]*distance+t[1]*side;point=Point(x,y);target=[p[0]+n[0]*70,p[1]+n[1]*70,p[2]+470]
        if point.distance(buildings)<50 or point.distance(water)<50 or point.distance(occupied)<40 or LineString([(x,y),target[:2]]).intersects(buildings):continue
        if point.distance(tree_centres)<350 or LineString([(x,y),target[:2]]).distance(tree_centres)<200:continue
        cover,hs=surfaces.query(x,y,35)
        if max(cover.get('path',0),cover.get('sidewalk',0))<.9 or cover.get('road',0)>.01:continue
        z=max([h for k,h in hs if k in ('path','sidewalk','ground')] or [p[2]])+170
        wide.append(dict(source_id=ref['id'],eye_cm=[x,y,z],target_cm=target));break
    facade_views=[]
    for r in [r for r in upper if r['kind']=='facade_banner']:
        if math.dist(r['anchor_cm'][:2],centre[:2])>15000:continue
        p=r['anchor_cm'];a=math.radians(r['yaw_degrees']);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
        for distance in [1200,1000,1400,1600,850,1800,700]:
            for side in [0,200,-200,400,-400]:
                x=p[0]+n[0]*distance+t[0]*side;y=p[1]+n[1]*distance+t[1]*side;point=Point(x,y);target=[p[0]+n[0]*70,p[1]+n[1]*70,p[2]]
                ray=LineString([(x,y),target[:2]])
                if point.distance(buildings)<50 or point.distance(water)<50 or point.distance(occupied)<40 or ray.intersects(buildings):continue
                if point.distance(tree_centres)<350 or ray.distance(tree_centres)<200:continue
                cover,hs=surfaces.query(x,y,35)
                if max(cover.get('path',0),cover.get('sidewalk',0))<.9 or cover.get('road',0)>.01:continue
                z=max([h for k,h in hs if k in ('path','sidewalk','ground')] or [p[2]-500])+170
                window_count=sum(w['kind']=='window' and w['source_id']==r['source_id'] for w in upper)
                score=abs(side)/distance*6000+abs(distance-1200)*.15+math.dist(p[:2],scene['quality_centre_ue_cm'][:2])*.05-window_count*18
                facade_views.append((score,dict(source_id=r['source_id'],eye_cm=[x,y,z],target_cm=target)))
    if facade_views:wide=[min(facade_views,key=lambda c:c[0])[1]]
    if not wide:
        photo=next(c for c in scene['photo_cameras'] if c['name']=='Camera_Paris_Street')
        eye=photo['position_cm'];candidates=[]
        for r in upper:
            if r['kind']!='window':continue
            p=r['source_window_centre_cm'];n=r['source_window_normal'];target=[p[i]+n[i]*65 for i in range(3)]
            if sum((eye[i]-p[i])*n[i] for i in range(2))<200:continue
            if LineString([eye[:2],target[:2]]).intersects(buildings):continue
            if Point(eye[:2]).distance(tree_centres)<300 or LineString([eye[:2],target[:2]]).distance(tree_centres)<200:continue
            candidates.append((math.dist(eye[:2],p[:2]),target,r['source_id']))
        if candidates:
            _,target,sid=min(candidates);wide.append(dict(source_id=sid,eye_cm=eye,target_cm=target))
    views=inspection_views(scene,selected,surfaces,buildings,water,occupied,tree_centres,upper,records)
    garlands,garland_rejected=garland_placements(scene,district,geo,surfaces,buildings,water,records)
    records.extend(garlands);rejected.extend(garland_rejected)
    festive=garland_camera(garlands,scene,surfaces,buildings,water,occupied,records)
    if festive:views[3]=festive
    records.extend(window_light_placements(window_candidates,geo))
    records.extend(window_relief_placements(window_candidates,geo))
    party,party_rejected=party_placements(records,buildings,water);records.extend(party);rejected.extend(party_rejected)
    records.extend(street_prop_placements(scene,geo,surfaces,buildings,water,records,views))
    records.extend(extra_object_placements(scene,geo,surfaces,buildings,water,records,views))
    return dict(extra_objects_camera=extra_object_camera(scene,surfaces,buildings,water,records),format='paris_luxury_street_v1',decoration_recipe=DECORATION_RECIPE,source_scene_sha256=scene['source_scene_sha256'],appearance_provenance='Optional fictional multicolour festival canopy, lanterns, stars and neon trims; original inferred overhead street pennants and light spans, district-wide window flowers, cloth banners, lanterns, public and storefront urns, mapped lamp baskets, warm festoon bulbs, striped canopies and cafe accessories; no surveyed decoration or real festival claim.',records=records,rejected=rejected,inspection_camera=wide[0] if wide else close,inspection_close_camera=close,inspection_district_camera=views[0],district_views=views,coverage=coverage_report(scene,records),objects=models())


if __name__=='__main__':
    data=generate();out=ROOT/'unreal/assets/paris-luxury/Generated/luxury.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    from collections import Counter
    print(json.dumps(dict(counts=dict(Counter(r['kind'] for r in data['records'])),models=len(data['objects']),triangles=sum(o['triangles'] for o in data['objects']),camera=data['inspection_camera']['source_id'])))
