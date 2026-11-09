"""Reproducible, source-bound everyday Paris street dressing; no GIS mutation."""
import hashlib,json,math,random
from collections import defaultdict
from pathlib import Path
import numpy as np
from shapely.geometry import Point,Polygon,LineString,shape
from shapely.ops import unary_union,triangulate
from generate_paris_frontages import Mesh
from generate_paris_luxury import Surfaces,lathe_at,flower
from generate_paris_street_props import make_models as shop_models
from paris_district_layout import DTYPE,district_windows

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data'
OUTPUT=ROOT/'unreal/assets/paris-lane/Generated/lane.json'
RECIPE='paris_everyday_lane_v1'


def model(mesh,name,material='M_ParisLuxuryMarketSolid'):
    m=mesh.item('lane_'+name,material);m['asset']='/Game/ParisPhotoreal/Reference/SM_ParisReference_'+m['id']+'_'+m['geometry_sha256'][:12];return m


def models():
    out=[];iron=[31,39,36,255];rubber=[29,31,30,255];silver=[153,157,154,255]
    for variant,color in enumerate([[36,61,77,255],[130,42,43,255],[112,121,116,255],[30,43,38,255]]):
        m=Mesh(bevel_cm=.15)
        for x in [-53,53]:
            for radius,thick,c in [(34,2.25,rubber),(31.5,.85,silver)]:
                for k in range(40):
                    a=k*math.tau/40;b=(k+1)*math.tau/40;m.tube([x+radius*math.cos(a),0,35+radius*math.sin(a)],[x+radius*math.cos(b),0,35+radius*math.sin(b)],thick,c,6)
            for k in range(16):
                a=k*math.tau/16;m.tube([x,0,35],[x+31*math.cos(a),0,35+31*math.sin(a)],.24,silver,4)
        edges=[([-53,0,35],[-7,0,32]),([-7,0,32],[-28,0,78]),([-28,0,78],[-53,0,35]),([-28,0,78],[32,0,78]),([32,0,78],[-7,0,32]),([32,0,78],[53,0,35]),([-28,0,78],[-31,0,92]),([32,0,78],[26,0,103])]
        if variant%2:edges[3]=([-24,0,69],[32,0,78])
        for a,b in edges:m.tube(a,b,1.5,color,8)
        m.box([0,0,0],[1,0,0],[0,1,0],[-31,0,94],[24,15,4.5],rubber)
        m.tube([26,0,101],[23,-26,103],1.1,silver,8);m.tube([26,0,101],[23,26,103],1.1,silver,8)
        for y in [-26,26]:m.tube([23,y,103],[10,y,101],1.5,rubber,8)
        m.tube([-7,-9,32],[-7,9,32],1.0,iron,6)
        for y,z in [(-12,21),(12,43)]:m.box([0,0,0],[1,0,0],[0,1,0],[-7,y,z],[14,7,3],iron)
        # Rear carrier, fenders and a small rear reflector.
        for y in [-9,9]:m.tube([-73,y,73],[-32,y,73],.8,iron,6);m.tube([-64,y,73],[-53,y,35],.65,iron,6)
        for x in [-70,-58,-46,-34]:m.tube([x,-9,73],[x,9,73],.6,iron,6)
        m.box([0,0,0],[1,0,0],[0,1,0],[-79,0,68],[3,8,5],[159,33,31,255])
        if variant in (0,3):
            for z,w in [(80,20),(100,27)]:
                for y in [-18,18]:m.tube([48-w/2,y,z],[48+w/2,y,z],.45,iron,5)
                for x in [48-w/2,48+w/2]:m.tube([x,-18,z],[x,18,z],.45,iron,5)
            for x in [36,42,48,54,60]:
                for y in [-18,18]:m.tube([x,y,80],[x,y,100],.32,iron,4)
        # Different parked lean, applied to both geometry and normals.
        angle=math.radians([-5,4,-3,6][variant]);c,s=math.cos(angle),math.sin(angle)
        for p in m.positions_cm:y,z=p[1:];p[1:]=[c*y-s*z,s*y+c*z]
        for n in m.normals:y,z=n[1:];n[1:]=[c*y-s*z,s*y+c*z]
        out.append(model(m,'bicycle_'+str(variant)))
    m=Mesh();pts=[[-38,0,0],[-38,0,66]]
    pts += [[38*math.cos(a),0,66+38*math.sin(a)] for a in np.linspace(math.pi,0,16)]
    pts += [[38,0,0]]
    for a,b in zip(pts,pts[1:]):
        if math.dist(a,b)>.01:m.tube(a,b,2.4,iron,8)
    for x in [-38,38]:m.box([0,0,0],[1,0,0],[0,1,0],[x,0,1.5],[12,16,3],iron)
    out.append(model(m,'rack'))
    m=Mesh(bevel_cm=.4)
    for side in [-1,1]:
        for i in range(6):
            x=-30+i*12
            m.box([0,0,0],[1,0,0],[0,1,0],[x,side*35,35],[11,4,64],[157+(i%3)*8,129+(i%3)*5,91,255])
            m.box([0,0,0],[1,0,0],[0,1,0],[side*35,x,35],[4,11,64],[149+(i%3)*7,123+(i%3)*5,88,255])
        for z in [9,59]:m.box([0,0,0],[1,0,0],[0,1,0],[0,side*37,z],[75,3,4],iron);m.box([0,0,0],[1,0,0],[0,1,0],[side*37,0,z],[3,75,4],iron)
    m.box([0,0,0],[1,0,0],[0,1,0],[0,0,63],[68,68,4],[53,43,30,255]);out.append(model(m,'planter','M_ParisLaneWood'))
    leaves=Mesh();rng=random.Random(413)
    # A dark inner mass avoids the hollow, checkered look of a leaf shell.
    for ring in range(10):
        for k in range(20):
            def point(i,j):
                v=-math.pi/2+(i+.03)*math.pi/10;u=j*math.tau/20;rad=1+.045*math.sin(u*5+v*4);return [33*math.cos(v)*math.cos(u)*rad,33*math.cos(v)*math.sin(u)*rad,99+27*math.sin(v)]
            pts=[point(ring,k),point(ring,k+1),point(ring+1,k+1),point(ring+1,k)];centre=np.mean(pts,axis=0)-[0,0,99];normal=centre/np.linalg.norm(centre);leaves.face(pts,normal.tolist(),[31,64,29,255])
    for i in range(1100):
        z=rng.uniform(-1,1);a=rng.random()*math.tau;r=math.sqrt(1-z*z);normal=[r*math.cos(a),r*math.sin(a),z];depth=rng.uniform(.79,1);p=[normal[0]*42*depth,normal[1]*42*depth,99+normal[2]*34*depth];u=[-math.sin(a),math.cos(a),0];v=[-z*math.cos(a),-z*math.sin(a),r]
        leaves.face([[p[k]+u[k]*x+v[k]*y for k in range(3)] for x,y in [(-2,0),(0,5),(2,0),(0,-5)]],normal,[[49,96,43,255],[73,117,47,255],[91,132,54,255]][i%3])
    out.append(model(leaves,'shrub','M_ParisLuxuryNature'))
    for theme,color in [('blue',[21,58,93,255]),('sage',[55,74,65,255]),('wine',[99,41,47,255])]:
        m=Mesh(bevel_cm=.4)
        # A shop bay uses archived facade orientation and local ground height.
        for x in [-164,72,164]:m.box([0,0,0],[1,0,0],[0,1,0],[x,24,136],[10,19,272],color)
        for z,h in [(22,44),(244,12),(270,20)]:m.box([0,0,0],[1,0,0],[0,1,0],[0,24,z],[338,18,h],color)
        for x in [-156,64]:m.box([0,0,0],[1,0,0],[0,1,0],[x,30,137],[3,3,196],[183,172,143,255])
        m.box([0,0,0],[1,0,0],[0,1,0],[112,32,128],[4,5,30],[169,142,77,255])
        for y,z in [(5,291),(135,258)]:m.tube([-174,y,z],[174,y,z],1.2,iron,8)
        for x in [-173,173]:m.tube([x,5,291],[x,135,258],1.1,iron,8)
        out.append(model(m,'shop_'+theme))
        cloth=Mesh()
        cloth.face([[-178,5,292],[178,5,292],[178,135,259],[-178,135,259]],[0,.246,.9693],color)
        # Correct a normalized pitched cloth normal, including the valance.
        length=math.hypot(.246,.9693)
        cloth.normals=[[0,.246/length,.9693/length] for _ in cloth.normals]
        cloth.face([[-178,5,289],[-178,135,256],[178,135,256],[178,5,289]],[0,-.246/length,-.9693/length],color)
        cloth.face([[-178,135,259],[178,135,259],[178,135,239],[-178,135,239]],[0,1,0],color)
        for side in [-1,1]:cloth.face([[side*178,5,292],[side*178,135,259],[side*178,135,244]],[side,0,0],color)
        out.append(model(cloth,'awning_'+theme,'M_ParisLuxuryFabric'))
    glass=Mesh()
    for left,right in [(-157,64),(79,157)]:glass.face([[left,31,45],[right,31,45],[right,31,235],[left,31,235]],[0,1,0],[81,98,110,255],[(0,0),(1,0),(1,1),(0,1)])
    out.append(model(glass,'shop_glass','M_ParisStreetWindowGlass'))
    menu=next(m for m in shop_models(lathe_at,flower) if m['id']=='market_menu');menu['id']='lane_menu';menu['asset']='/Game/ParisPhotoreal/Reference/SM_ParisReference_lane_menu_'+menu['geometry_sha256'][:12];out.append(menu)
    return out


def parts(g):
    if g.geom_type=='Polygon':yield g
    elif hasattr(g,'geoms'):
        for child in g.geoms:yield from parts(child)


def paving(scene,area,surfaces):
    blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');mesh=Mesh();sources=[];height_cache={}
    road=next(o for o in scene['objects'] if o['kind']=='road');b=road['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
    for index,ids in enumerate(ix):
        p=v['p'][ids].astype(float);poly=Polygon(p[:,:2])
        if not poly.intersects(area):continue
        clipped=poly.intersection(area)
        for part in parts(clipped):
            for tri in triangulate(part):
                if tri.area<.1 or not part.covers(tri):continue
                pts=[]
                for x,y in list(tri.exterior.coords)[:3]:
                    key=(round(x,3),round(y,3))
                    if key not in height_cache:
                        hs=surfaces.query(x,y,2)[1];zs=[z for k,z in hs if k in ('road','path','sidewalk','ground')]
                        if not zs:
                            u=p[1]-p[0];w=p[2]-p[0];d=u[0]*w[1]-u[1]*w[0];s=((x-p[0,0])*w[1]-(y-p[0,1])*w[0])/d;t=(u[0]*(y-p[0,1])-u[1]*(x-p[0,0]))/d;zs=[float(p[0,2]+s*u[2]+t*w[2])]
                        height_cache[key]=max(zs)+.7
                    pts.append([x,y,height_cache[key]])
                normal=np.cross(np.array(pts[1])-pts[0],np.array(pts[2])-pts[0]);normal=normal/np.linalg.norm(normal)
                if normal[2]<0:normal=-normal
                mesh.face(pts,normal.tolist(),[205,205,199,255]);sources.append(index)
    m=model(mesh,'paving','M_ParisLanePaving');return m,dict(source_mesh_id=road['id'],source_triangle_indices=sorted(set(sources)),area_m2=area.area/10000,visual_offset_cm=.7)


def generate():
    scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'));district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'));base=json.loads((DATA/'paris-reference.json').read_text(encoding='utf-8'))
    assert base['source_scene_sha256']==scene['source_scene_sha256']
    road=next(f for f in district['layers']['roads'] if f['properties']['source_id']=='osm/way/40067719');ox,oy=district['origin_projected_m']
    def local(g):
        from shapely.ops import transform
        return transform(lambda x,y,z=None:((np.asarray(x)-ox)*100,(oy-np.asarray(y))*100),g)
    line=local(shape(road['properties']['source_geometry_projected']));area=local(shape(road['geometry']));area=area if area.area>0 else line.buffer(road['properties']['width_m']*50,cap_style=2,join_style=2);buildings=unary_union([local(shape(f['geometry'])) for f in district['layers']['buildings']]);water=unary_union([local(shape(f['geometry'])) for f in district['layers']['water']]);area=area.difference(buildings.buffer(2)).difference(water)
    surfaces=Surfaces(scene);position=line.interpolate(.86,normalized=True);target=line.interpolate(.06,normalized=True);d=np.array(target.coords[0])-position.coords[0];d=d/np.linalg.norm(d);right=np.array([-d[1],d[0]]);eye=np.array(position.coords[0])+right*60
    ground=max(z for k,z in surfaces.query(*eye,20)[1] if k in ('path','road','ground'))
    base['camera']=dict(name='Rue de la Bucherie / everyday Paris',source_id=road['properties']['source_id'],eye_cm=[*eye,ground+170],target_cm=[*target.coords[0],ground+285],ground_cm=ground,eye_height_cm=170,focal_length_mm=38)
    base['recipe']=RECIPE;base['appearance_provenance']='Inferred everyday Paris street finish, storefronts and parked occupancy; mapped street/buildings unchanged; not a surveyed reconstruction of the supplied photograph'
    new=models();pave,pave_source=paving(scene,area,surfaces);new.append(pave);base['objects']+=new
    additions=[dict(kind='lane_paving',source_id=road['properties']['source_id'],anchor_cm=[0,0,0],yaw_degrees=0,scale_xyz=[1,1,1],models=['lane_paving'])];occupied=[]
    businesses=[f for f in scene['pick_features'] if f['kind']=='business'];doors=unary_union([Point(f['point_cm'][:2]).buffer(105) for f in businesses]);centre_keep=line.buffer(105)
    for f in scene['pick_features']:
        if f['kind'].startswith('street_'):occupied.append(Point(f['point_cm'][:2]).buffer(65))
    fixed=unary_union(occupied);accepted=[]
    routes=unary_union([LineString([p[:2] for p in r['points_cm']]) for r in scene['pedestrians']['routes'] if len(r['points_cm'])>1]).buffer(55)
    parking_domain=area.buffer(180).difference(buildings.buffer(30)).difference(water)
    yaw=math.degrees(math.atan2(d[1],d[0]));eye_s=line.project(position);row_count=0
    from shapely.affinity import rotate,translate
    def parking_slot(i,offset):
        s=eye_s-340-i*106
        if s<500:return None
        q=np.array(line.interpolate(s).coords[0])+right*offset;angle=yaw+58;foot=translate(rotate(Polygon([[-96,-36],[96,-36],[96,36],[-96,36]]),angle,origin=(0,0)),*q)
        if not parking_domain.covers(foot) or any(foot.intersects(g) for g in [centre_keep,doors,fixed,routes]):return None
        return q,angle,foot
    row_offset=max([250,290,330,370,410,450],key=lambda off:(sum(parking_slot(i,off) is not None for i in range(16)),-off))
    for i in range(16):
        slot=parking_slot(i,row_offset)
        if slot is None:continue
        q,angle,foot=slot
        hs=surfaces.query(*q,15)[1];z=max(z for k,z in hs if k in ('road','path','ground','sidewalk'))+1
        additions.append(dict(kind='lane_bicycle',source_id=road['properties']['source_id'],anchor_cm=[*q,z],yaw_degrees=angle,scale_xyz=[1,1,1],models=['lane_bicycle_'+str(i%4)],collision_boxes=[dict(centre_cm=[0,0,52],size_cm=[184,55,104])],placement_provenance='inferred parked bicycle, no observed occupancy',footprint_cm=list(foot.exterior.coords)))
        rack=q+d*12;additions.append(dict(kind='lane_rack',source_id=road['properties']['source_id'],anchor_cm=[*rack,z],yaw_degrees=yaw+90,scale_xyz=[1,1,1],models=['lane_rack']))
        accepted.append(foot.buffer(8));row_count+=1
    # Planters use the outside of the parked row, with a continuous 2.1m route.
    for s,side in [(eye_s-170,1),(eye_s-2250,1),(eye_s-3600,1),(eye_s-900,-1)]:
        if s<400:continue
        q=np.array(line.interpolate(s).coords[0])+right*side*(row_offset+20);foot=Point(q).buffer(53)
        if foot.intersects(buildings) or foot.intersects(water) or foot.intersects(doors) or foot.intersects(fixed) or foot.intersects(centre_keep) or foot.intersects(routes) or any(foot.intersects(p) for p in accepted):continue
        hs=surfaces.query(*q,40)[1];zs=[z for k,z in hs if k in ('path','road','ground','sidewalk')]
        if not zs:continue
        additions.append(dict(kind='lane_planter',source_id=road['properties']['source_id'],anchor_cm=[*q,max(zs)],yaw_degrees=yaw,scale_xyz=[1,1,1],models=['lane_planter','lane_shrub'],collision_boxes=[dict(centre_cm=[0,0,35],size_cm=[76,76,70])],placement_provenance='inferred wooden planter outside preserved walking ribbon',footprint_cm=list(foot.exterior.coords)));accepted.append(foot)
    shop_count=0
    for f in sorted(businesses,key=lambda f:f['id']):
        p=np.array(f['point_cm']);pt=Point(p[:2])
        if pt.distance(line)>1150 or line.project(pt)<200 or line.project(pt)>line.length-200:continue
        a=math.radians(f['properties']['facade_yaw_degrees']);t=np.array([math.cos(a),math.sin(a)]);n=np.array([-t[1],t[0]])
        front=pt.distance(line);probe=Point(p[:2]+n*120)
        if probe.distance(line)>front+30:continue
        width=285
        if any(math.dist(p[:2],q)<315 for q in [r['anchor_cm'][:2] for r in additions if r['kind']=='lane_shop']):continue
        # A ground-based bay masks the old flat frontage; width stays modest.
        hs=surfaces.query(*(p[:2]+n*55),15)[1];zs=[z for k,z in hs if k in ('path','sidewalk','road','ground')]
        if not zs:continue
        p[2]=max(zs);theme=['blue','sage','blue','blue','wine'][shop_count%5]
        additions.append(dict(kind='lane_shop',source_id=f['id'],building_source_id=f['properties']['building_source_id'],anchor_cm=p.tolist(),yaw_degrees=f['properties']['facade_yaw_degrees'],scale_xyz=[width/340,1,1],models=['lane_shop_'+theme,'lane_awning_'+theme,'lane_shop_glass'],placement_provenance='inferred bay and awning at archived shop facade; not current business-design verification'))
        shop_count+=1
    visible_shops=[r for r in additions if r['kind']=='lane_shop' and np.dot(np.array(r['anchor_cm'][:2])-eye,d)>150 and abs(np.dot(np.array(r['anchor_cm'][:2])-eye,right))<np.dot(np.array(r['anchor_cm'][:2])-eye,d)*.5+150]
    if visible_shops:
        closest=min(visible_shops,key=lambda r:math.dist(r['anchor_cm'][:2],eye));closest['models']=['lane_shop_blue','lane_awning_blue','lane_shop_glass']
    base['records']+=additions;base['lane']=dict(source_street_id=road['properties']['source_id'],street_name=road['properties']['name'],mapped_surface=road['properties']['tags'].get('surface'),fan_layout_inferred=True,paving_source=pave_source,bicycles=row_count,racks=row_count,planters=sum(r['kind']=='lane_planter' for r in additions),storefronts=shop_count,walking_ribbon_width_cm=210,centreline_cm=list(line.coords),street_axis=d.tolist(),parking_offset_cm=row_offset,pedestrian_routes_kept_clear=True,sidewalk_occupancy_inferred=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);temp=OUTPUT.with_suffix('.tmp');temp.write_text(json.dumps(base,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8');temp.replace(OUTPUT)
    print(json.dumps(dict(lane=base['lane'],new_models=len(new),sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()),ensure_ascii=False));return base


if __name__=='__main__':generate()
