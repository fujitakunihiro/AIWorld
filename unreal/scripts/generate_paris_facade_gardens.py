"""Inferred upper-storey decoration aligned to the existing facade quads."""
import hashlib,json,math,random
from pathlib import Path
from collections import defaultdict
import numpy as np
from shapely.geometry import Point,Polygon
from generate_paris_frontages import Mesh
from generate_paris_morris import lathe,DTYPE
from paris_district_layout import district_windows,spread

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data'


def shifted_lathe(mesh,profile,x,y,color,sides=16):
    part=Mesh();lathe(part,profile,color,sides)
    for p in part.positions_cm:p[0]+=x;p[1]+=y
    mesh.extend(part)


def make_models(bloom):
    result=[];dark=[33,56,47,255];gold=[146,119,64,255];soil=[44,34,23,255]
    def add(name,mesh,role):
        item=mesh.item(name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    box=Mesh(bevel_cm=.35)
    box.box([0,0,0],[1,0,0],[0,1,0],[0,24,-14],[94,31,23],dark)
    box.box([0,0,0],[1,0,0],[0,1,0],[0,24,-1],[97,33,3],gold)
    box.box([0,0,0],[1,0,0],[0,1,0],[0,24,1],[88,26,1],soil)
    for x in range(-42,43,14):box.box([0,0,0],[1,0,0],[0,1,0],[x,40,-12],[1,1.4,20],gold)
    for x in [-36,36]:
        box.tube([x,-13,-24],[x,26,-29],1.4,dark,6)
        box.tube([x,26,-29],[x,36,-24],1.4,dark,6)
    add('window_box',box,'Metal')
    palettes=[[[223,48,111,255],[250,164,194,255],[242,224,208,255]],[[170,68,182,255],[225,109,179,255],[245,227,215,255]],[[207,52,67,255],[245,132,149,255],[249,223,191,255]]]
    for variant in range(3):
        mesh=Mesh();rng=random.Random(811+variant)
        for j in range(24):
            x=-41+j*82/23+rng.uniform(-2,2);y=rng.uniform(15,32);z=rng.uniform(6,25)
            mesh.tube([x*.9,24,1],[x,y,z],.35,[42,75,35,255],4)
            for side in [-1,1]:
                mesh.face([[x,y,z-8],[x+side*8,y+2,z-3],[x+side*11,y+5,z-7],[x+side*6,y+6,z-10]],[0,.6,.8],[48,87,43,255])
            if j%3!=2:bloom(mesh,[x,y+3,z+3],rng.uniform(2.8,4.3),palettes[variant][(j//3+j)%3],j*.8,angle=-math.pi*.42)
        # Short, asymmetric cascades of ivy on the front edge.
        for x in [-30,14,35]:
            mesh.tube([x,38,5],[x+3,42,-23],.3,[43,77,35,255],4)
            for z in [-2,-10,-19]:mesh.face([[x-4,40,z],[x,42,z+3],[x+5,40,z],[x,42,z-4]],[0,1,0],[48,87,43,255])
        add('window_flowers_'+str(variant),mesh,'Nature')
    for name,color in [('wine',[118,34,57,255]),('blue',[35,59,94,255]),('ivory',[203,174,121,255])]:
        cloth=Mesh();width=58;top=91;bottom=-82
        def point(u,v):
            x=(u-.5)*width;z=top+(bottom-top)*v+(9*abs(u-.5)*2 if v==1 else 0)
            return [x,10+4*math.sin(u*math.tau*2)+math.sin(v*math.pi)*2,z]
        for ix in range(8):
            for iz in range(12):
                a=ix/8;b=(ix+1)/8;c=iz/12;d=(iz+1)/12
                tint=[155,126,72,255] if ix in (0,7) or iz in (0,11) else color
                cloth.face([point(a,c),point(b,c),point(b,d),point(a,d)],[0,1,0],tint)
        add('banner_'+name,cloth,'Fabric')
    frame=Mesh();glass=Mesh()
    # An embroidered banner rod and a scroll bracket carrying a six-pane lamp.
    frame.tube([-37,13,96],[37,13,96],1.4,gold,10)
    for x in [-25,25]:frame.tube([x,-13,96],[x,13,96],1.3,gold,8)
    for x in [-38,38]:shifted_lathe(frame,[(94,2),(97,2),(100,0)],x,13,gold,10)
    frame.tube([0,2,154],[0,2,187],1.3,dark,8)
    frame.box([0,0,0],[1,0,0],[0,1,0],[0,-5,171],[12,20,48],dark)
    curve=[[0,4+52*j/15,184+12*math.sin(j*math.pi/15)] for j in range(16)]
    for a,b in zip(curve,curve[1:]):frame.tube(a,b,1.05,dark,8)
    frame.tube([0,56,184],[0,56,161],1.,gold,8)
    shifted_lathe(frame,[(100,10),(104,14),(108,14),(109,10)],0,56,dark,24)
    shifted_lathe(frame,[(151,15),(154,19),(157,19),(163,4),(167,0)],0,56,dark,24)
    for j in range(6):
        a=j*math.tau/6;b=(j+1)*math.tau/6;m=(a+b)/2
        points=[[r*math.cos(q),56+r*math.sin(q),z] for z,r,q in [(109,10,a),(109,10,b),(151,15,b),(151,15,a)]]
        length=math.sqrt(1+.12*.12);glass.face(points,[math.cos(m)/length,math.sin(m)/length,-.12/length],[250,217,151,255])
        frame.tube(points[0],points[3],.8,gold,6)
    add('facade_metal',frame,'Metal');add('facade_lantern',glass,'Bulb')
    return result


def source_planters(scene):
    blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');found=[]
    for o in scene['objects']:
        if o['kind']!='facade_planter':continue
        b=o['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count'])
        for k in range(0,len(ix),6):
            ids=np.unique(ix[k:k+6])
            if len(ids)!=4 or np.mean(v['n'][ids,2])<.9:continue
            pts=v['p'][ids];p=pts.mean(axis=0)
            if 300<Polygon(pts[:,:2]).convex_hull.area<5000:found.append(p)
    return found


def make_placements(scene,geo,surfaces,return_candidates=False):
    data=json.loads((DATA/'paris-photo-frontages-source.json').read_text(encoding='utf-8'))
    if data['source_scene_sha256']!=scene['source_scene_sha256']:raise RuntimeError('Facade decoration input is stale')
    core={(w['source_mesh_id'],w['source_quad_index']) for w in data['windows']}
    commercial={f['properties']['building_source_id'] for f in scene['pick_features'] if f['kind']=='business'}
    all_windows,allowed=district_windows(scene['source_scene_sha256']);data=dict(data,windows=all_windows)
    existing=source_planters(scene);windows=[];records=[];rejected=[];ground_cache={}
    for w in data['windows']:
        if w['source_id'] not in allowed:continue
        p=w['centre_cm'];n=w['normal'];x=p[0]+n[0]*65;y=p[1]+n[1]*65
        key=(round(x),round(y))
        if key not in ground_cache:
            _,heights=surfaces.query(x,y,15);ground_cache[key]=[h for k,h in heights if k in ('ground','path','sidewalk')]
        floors=ground_cache[key]
        if not floors:continue
        ground=max(floors);sill=p[2]-w['height_cm']/2
        # First and second upper storeys; keep church and landmark sources out.
        if not 300<=sill-ground<=1100:continue
        windows.append(dict(**w,ground_cm=ground,sill_cm=sill))
    core_windows=[w for w in windows if (w['source_mesh_id'],w['source_quad_index']) in core and w['source_id'] in commercial]
    extras=[w for w in windows if w not in core_windows]
    core_windows.sort(key=lambda w:(math.dist(w['centre_cm'][:2],scene['quality_centre_ue_cm'][:2]),w['source_id'],w['source_quad_index']))
    ordered=core_windows+spread(extras,lambda w:w['centre_cm'],lambda w:(w['source_id'],w['source_quad_index']))
    selected=[];per_building=defaultdict(int)
    for phase in (0,1):
        if phase:
            # Keep every v4 box, then visit buildings that previously had none.
            remaining=defaultdict(list)
            for w in windows:
                if w['source_id'] not in per_building:remaining[w['source_id']].append(w)
            ranked=[]
            for sid,values in sorted(remaining.items()):
                values.sort(key=lambda w:hashlib.sha256((sid+str(w['source_quad_index'])).encode()).hexdigest())
                ranked.extend(dict(w,selection_round=i) for i,w in enumerate(values))
            ordered=spread(ranked,lambda w:w['centre_cm'],lambda w:(w['selection_round'],w['source_id']))
        for w in ordered:
            if len(selected)>=(1200 if not phase else 2400):break
            p=w['centre_cm'];n=w['normal'];sid=w['source_id'];digest=int(hashlib.sha256((sid+str(w['source_quad_index'])).encode()).hexdigest()[:8],16)
            if digest%4==0:continue
            is_core=(w['source_mesh_id'],w['source_quad_index']) in core and sid in commercial
            if (phase or not is_core) and per_building[sid]>=(8 if phase else 18):continue
            if any(math.dist([p[0],p[1],w['sill_cm']],r['anchor_cm'])<130 for r in selected):continue
            anchor=[p[0],p[1],w['sill_cm']];old=any(math.dist(q[:2],anchor[:2])<60 and abs(q[2]-anchor[2])<35 for q in existing)
            yaw=math.degrees(math.atan2(-n[0],n[1]));ll=geo.from_ue(*anchor)
            r=dict(source_id=sid,building_source_id=sid,source_window_mesh=w['source_mesh_id'],source_window_quad=w['source_quad_index'],placement_provenance='inferred_flower_box_at_existing_inferred_upper_window',kind='window',anchor_cm=anchor,yaw_degrees=yaw,wgs84_placement=list(ll[:2]),source_window_centre_cm=p,source_window_normal=n,source_window_height_cm=w['height_cm'],source_window_width_cm=w['width_cm'],uses_existing_planter=old,minimum_clearance_cm=w['sill_cm']-w['ground_cm']-29,models=([] if old else ['window_box'])+['window_flowers_'+str(digest%3),'proxy_window_'+str(digest%3)])
            records.append(r);selected.append(r);per_building[sid]+=1
    # Find blank wall gaps between adjacent windows on a common facade row.
    groups=defaultdict(list)
    for w in windows:
        n=w['normal'];groups[(w['source_id'],round(n[0],2),round(n[1],2),round(w['centre_cm'][2]/25))].append(w)
    sites=[];by_source=defaultdict(list)
    for w in data['windows']:by_source[w['source_id']].append(w)
    for key,ws in sorted(groups.items()):
        n=ws[0]['normal'];t=[n[1],-n[0],0];ws=sorted(ws,key=lambda w:sum(w['centre_cm'][i]*t[i] for i in range(3)))
        for a,b in zip(ws,ws[1:]):
            delta=np.array(b['centre_cm'])-np.array(a['centre_cm']);distance=abs(sum(delta[i]*t[i] for i in range(3)))
            if not 190<distance<420 or abs(sum(delta[i]*n[i] for i in range(3)))>12 or abs(delta[2])>20:continue
            p=[(a['centre_cm'][i]+b['centre_cm'][i])/2 for i in range(3)];ground=max(a['ground_cm'],b['ground_cm'])
            if not 400<p[2]-ground<850:continue
            blocked=False
            for other in by_source[a['source_id']]:
                if other['source_id']!=a['source_id'] or sum(other['normal'][i]*n[i] for i in range(3))<.995:continue
                delta=[p[i]-other['centre_cm'][i] for i in range(3)]
                if abs(sum(delta[i]*n[i] for i in range(3)))>15:continue
                if abs(sum(delta[i]*t[i] for i in range(3)))<other['width_cm']/2+40 and p[2]-82<other['centre_cm'][2]+other['height_cm']/2+8 and p[2]+190>other['centre_cm'][2]-other['height_cm']/2-8:
                    blocked=True;break
            if blocked:continue
            if any(math.dist(p[:2],s['anchor_cm'][:2])<450 for s in sites):continue
            sid=a['source_id'];seed=int(hashlib.sha256((sid+str(a['source_quad_index'])).encode()).hexdigest()[:8],16);yaw=math.degrees(math.atan2(-n[0],n[1]));ll=geo.from_ue(*p)
            r=dict(source_id=sid,building_source_id=sid,kind='facade_banner',placement_provenance='inferred_banner_and_lantern_in_blank_gap_between_existing_windows',anchor_cm=p,yaw_degrees=yaw,wgs84_placement=list(ll[:2]),adjacent_window_quads=[a['source_quad_index'],b['source_quad_index']],source_window_mesh=a['source_mesh_id'],window_gap_cm=distance-(a['width_cm']+b['width_cm'])/2,minimum_clearance_cm=p[2]-ground-82,models=['banner_'+['wine','blue','ivory'][seed%3],'facade_metal','facade_lantern'])
            sites.append(r)
    sites=spread(sites,lambda r:r['anchor_cm'],lambda r:(r['source_id'],r['anchor_cm'][2]))[:150];records.extend(sites)
    return (records,rejected,windows) if return_candidates else (records,rejected)
