"""OSM-aligned bridge reconstruction; documented dimensions, inferred detail.

Original GIS buffers are read only. Thin disconnected lane slabs are replaced
in the detailed renderer by a continuous deck with an independent walking mesh.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from generate_paris_roads import Surface, digest

ROOT=Path(__file__).resolve().parents[2]
CONTENT=ROOT/'unreal/AIWorld/Content'
RECIPE='paris_bridge_structure_v1'
REF='https://www.afgc.asso.fr/history-heritage/'
SPECS={
 'Petit-Pont - Cardinal Lustiger':dict(key='petit',width=20,road=12,spans=[32],types=['stone'],reference=REF+'petit-pont-a-paris/'),
 'Pont Saint-Michel':dict(key='michel',width=30,road=18,spans=[17,17,17],types=['stone']*3,reference=REF+'pont-saint-michel-a-paris/',medallions=True),
 'Pont au Change':dict(key='change',width=30,road=18,spans=[31,31,31],types=['stone']*3,reference=REF+'pont-au-change-a-paris/',medallions=True),
 "Pont de l'Archevêché":dict(key='archeveche',width=11,road=7,spans=[15,17,15],types=['stone']*3,reference=REF+'pont-de-larcheveche-a-paris/'),
 'Pont au Double':dict(key='double',width=20,road=0,spans=[31],types=['copper'],reference=REF+'pont-au-double-a-paris/'),
 "Pont d'Arcole":dict(key='arcole',width=20,road=12,spans=[80],types=['iron'],reference=REF+'pont-darcole-a-paris/'),
 'Pont Notre-Dame':dict(key='notredame',width=20,road=12,spans=[18,60,18],types=['stone','iron','stone'],reference=REF+'pont-notre-dame-a-paris/'),
}
DTYPE=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])


class Mesh:
    def __init__(self,profile):self.profile=profile;self.p=[];self.n=[];self.uv=[];self.c=[];self.ix=[]

    def world(self,p):
        b=self.profile;d=np.array(b['direction']);side=np.array([-d[1],d[0]])
        q=np.array(b['centre_cm'][:2])+d*p[0]+side*p[1]
        return [float(q[0]),float(q[1]),float(p[2])]

    def face(self,points,wanted,color=(1,1,1,1)):
        p=np.asarray(points,dtype='f8');normal=np.cross(p[2]-p[0],p[1]-p[0])
        if np.linalg.norm(normal)<1.e-8:return
        if np.dot(normal,wanted)<0:p=p[::-1];normal=-normal
        normal/=np.linalg.norm(normal);d=self.profile['direction'];nx=normal[0]*d[0]-normal[1]*d[1];ny=normal[0]*d[1]+normal[1]*d[0]
        start=len(self.p);self.p.extend([np.round(self.world(q),5).tolist() for q in p]);self.n.extend([[nx,ny,float(normal[2])]]*len(p))
        self.uv.extend([[float((q[1] if abs(normal[0])>abs(normal[1]) and abs(normal[2])<.5 else q[0])/300),float((q[1] if abs(normal[2])>.5 else q[2])/300)] for q in p]);self.c.extend([list(color)]*len(p))
        for j in range(1,len(p)-1):self.ix.extend([start,start+j,start+j+1])

    def box(self,x0,x1,y0,y1,z0,z1,color=(1,1,1,1)):
        a=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)];b=[(x,y,z1) for x,y,_ in a]
        self.face(a,(0,0,-1),color);self.face(b,(0,0,1),color)
        for i,n in enumerate(((0,-1,0),(1,0,0),(0,1,0),(-1,0,0))):
            j=(i+1)%4;self.face([a[i],a[j],b[j],b[i]],n,color)

    def bar(self,a,b,r,sides=8,color=(1,1,1,1)):
        a,b=np.array(a),np.array(b);direction=b-a;length=np.linalg.norm(direction)
        if length<1.e-5:return
        direction/=length;ref=np.array([0.,0.,1.]) if abs(direction[2])<.8 else np.array([0.,1.,0.]);u=np.cross(direction,ref);u/=np.linalg.norm(u);v=np.cross(direction,u)
        ring=[(u*math.cos(i*math.tau/sides)+v*math.sin(i*math.tau/sides))*r for i in range(sides)]
        for i in range(sides):j=(i+1)%sides;self.face([a+ring[i],a+ring[j],b+ring[j],b+ring[i]],ring[i]+ring[j],color)
        self.face([a+q for q in ring],-direction,color);self.face([b+q for q in ring],direction,color)

    def item(self,key,material,collision=False):
        body=dict(positions_cm=self.p,normals=self.n,uv0=self.uv,vertex_colors=self.c,indices=self.ix);sha=digest(body)
        return dict(id=self.profile['id']+'_'+key,bridge_id=self.profile['id'],asset='/Game/ParisPhotoreal/Bridges/SM_ParisBridge_'+self.profile['id']+'_'+key+'_'+sha[:12],
            material=material,geometry_sha256=sha,triangles=len(self.ix)//3,collision_only=collision,**body)


def height(b,x,y=0.):
    t=max(0.,min(1.,(x+b['length_cm']/2)/b['length_cm']))
    z=b['endpoint_z_cm'][0]*(1-t)+b['endpoint_z_cm'][1]*t+4*b['crown_cm']*t*(1-t)
    if b['road_width_cm']>0 and abs(y)>b['road_width_cm']/2:z+=14.
    return z


def source_surface(obj,blob):
    b=obj['mesh_buffer'];verts=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
    triangles=verts['p'][ix].astype('f8');top=triangles[np.mean(verts['n'][ix][:,:,2],axis=1)>.5]
    polygons=[Polygon(t[:,:2]) for t in top if Polygon(t[:,:2]).area>.1]
    return triangles,unary_union(polygons)


class Landings:
    """Highest archived walkable surface at bridge approaches, in UE cm."""
    def __init__(self,data,blob):
        triangles=[]
        for obj in data['objects']:
            if obj['kind'] not in ('ground','road','path','sidewalk'):continue
            b=obj['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
            triangles.extend(v['p'][ix])
        t=np.asarray(triangles,dtype='f8');self.a=t[:,0];self.u=t[:,1]-self.a;self.v=t[:,2]-self.a
        den=self.u[:,0]*self.v[:,1]-self.u[:,1]*self.v[:,0];self.valid=np.abs(den)>1.e-7;self.den=np.where(self.valid,den,1.)

    def height(self,point):
        a,u,v=self.a,self.u,self.v;s=((point[0]-a[:,0])*v[:,1]-(point[1]-a[:,1])*v[:,0])/self.den;t=(u[:,0]*(point[1]-a[:,1])-u[:,1]*(point[0]-a[:,0]))/self.den
        mask=self.valid&(s>=-1.e-5)&(t>=-1.e-5)&(s+t<=1.00001)
        return float((a[:,2]+s*u[:,2]+t*v[:,2])[mask].max()) if mask.any() else None


def generate(write=True):
    data=json.loads((CONTENT/'Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    blob=np.memmap(CONTENT/'Data/paris-digital-twin-meshes.bin',dtype='u1',mode='r');sources=[o for o in data['objects'] if o['kind']=='bridge'];geometry={o['id']:source_surface(o,blob)[1] for o in sources}
    landings=Landings(data,blob)
    groups={name:[] for name in SPECS};unassigned=[]
    for o in sources:
        name=next((n for n in o['properties']['names'] if n in SPECS),None)
        if name:groups[name].append(o)
        else:unassigned.append(o)
    for o in unassigned:
        if o['properties']['clipped_at_context_boundary']:continue
        candidates=[(min(geometry[o['id']].distance(geometry[v['id']]) for v in g),name) for name,g in groups.items() if g]
        distance,name=min(candidates)
        if distance<1800:groups[name].append(o)
    river=json.loads((CONTENT/'Data/paris-water.json').read_text(encoding='utf-8'));water=river['water_level_cm']
    profiles=[];objects=[]
    picks={f['id']:f for f in data['pick_features']};origin=data['georeference']['projected_origin_m'];origin_z=data['georeference']['origin_elevation_ngf_m']
    for name,spec in SPECS.items():
        group=groups[name]
        if not group:continue
        ids=sorted({i for o in group for i in o['properties']['source_ids']})
        lines=[picks[i] for i in ids if i in picks and picks[i]['properties'].get('name')==name]
        # The widest named route is normally the carriageway, rather than an
        # independently mapped footway/bicycle strip.
        main=max(lines,key=lambda f:(f['properties']['width_m'],sum(math.dist(a,b) for a,b in zip(f['polylines_cm'][0],f['polylines_cm'][0][1:]))))
        line=np.array(main['polylines_cm'][0]);direction=line[-1,:2]-line[0,:2];direction/=np.linalg.norm(direction);side=np.array([-direction[1],direction[0]])
        centre=(line[0,:2]+line[-1,:2])/2
        coords=np.array([p for o in group for p in geometry[o['id']].convex_hull.exterior.coords]);along=(coords-centre)@direction;across=(coords-centre)@side
        lo,hi=float(along.min()),float(along.max())
        main_length=float(np.linalg.norm(line[-1,:2]-line[0,:2]))
        # Do not stretch the span over the T-shaped road junction at Arcole.
        if hi-lo>main_length+400:lo,hi=-main_length/2,main_length/2
        centre+=direction*(lo+hi)/2
        width=spec['width']*100
        # Approach-road junctions flare out beyond the bridge itself. They
        # must not turn an 11m bridge into a 24m rectangle. Fit the centre to
        # the middle portion of mapped strips and use documented full width.
        middle=across[np.abs(along-(lo+hi)/2)<(hi-lo)*.30]
        if len(middle):centre+=side*float((middle.min()+middle.max())/2)
        primary=next(o for o in group if main['id'] in o['properties']['source_ids']);pr=primary['properties'];ends=np.array(pr['endpoint_xy_projected_m']);ends=(ends-np.array(origin))*np.array([100,-100]);z=(np.array(pr['endpoint_ngf_m'])-origin_z)*100
        if np.dot(ends[1]-ends[0],direction)<0:z=z[::-1]
        original_z=z.copy();approaches=[];landing_offsets=[]
        for i,sign in enumerate((-1,1)):
            bank=None;offset=0.
            for offset in (1.,45.,90.,180.):
                bank=landings.height(centre+direction*sign*((hi-lo)/2+offset))
                if bank is not None:break
            approaches.append(bank);landing_offsets.append(offset)
            if bank is not None:z[i]=bank
        b=dict(id=spec['key'],name=name,source_ids=ids,source_mesh_ids=sorted(o['id'] for o in group),primary_source_id=main['id'],centre_cm=[*np.round(centre,5),0.],direction=np.round(direction,12).tolist(),length_cm=round(hi-lo,5),width_cm=round(width,5),
            endpoint_z_cm=np.round(z,5).tolist(),archived_endpoint_z_cm=np.round(original_z,5).tolist(),landing_samples_cm=approaches,landing_sample_distance_cm=landing_offsets,landing_source='Estimated from the highest archived road/path/terrain triangle immediately beyond each mapped bridge end; not surveyed deck elevations',crown_cm=35.,road_width_cm=min(spec['road']*100,width-260) if spec['road'] else 0.,reference_width_m=spec['width'],span_reference_m=spec['spans'],reference_url=spec['reference'],
            provenance='Mapped OSM position and direction; endpoint elevations estimated from archived IGN terrain; architectural proportions and surface ageing inferred from engineering references; not a measured L4/L5 bridge',water_level_cm=water)
        profiles.append(b);parts={k:Mesh(b) for k in ('stone','cutstone','iron','copper','asphalt','paving','collision')};L=b['length_cm'];W=b['width_cm'];road=b['road_width_cm']/2
        count=max(16,math.ceil(L/120));xs=np.linspace(-L/2,L/2,count+1)
        # Closed continuous deck, including the gaps between OSM lane buffers.
        ys=sorted(set([-W/2,-road,road,W/2])) if road else [-W/2,W/2]
        for a,c in zip(xs,xs[1:]):
            for y0,y1 in zip(ys,ys[1:]):
                mid=(y0+y1)/2;walk=not road or abs(mid)>road;mesh=parts['paving' if walk else 'asphalt']
                aa,cc=height(b,a,mid),height(b,c,mid);quad=[(a,y0,aa),(c,y0,cc),(c,y1,cc),(a,y1,aa)]
                mesh.face(quad,(0,0,1));parts['collision'].face(quad,(0,0,1))
                if road and walk:
                    kerb=-road if mid<0 else road;low0,low1=height(b,a,0),height(b,c,0)
                    parts['cutstone'].face([(a,kerb,low0),(c,kerb,low1),(c,kerb,cc),(a,kerb,aa)],(0,1 if mid<0 else -1,0))
            # Underside closes the slab; every arch below it is real geometry.
            za,zc=height(b,a,0)-45,height(b,c,0)-45
            parts['stone'].face([(a,-W/2,za),(a,W/2,za),(c,W/2,zc),(c,-W/2,zc)],(0,0,-1))
            for sign in (-1,1):parts['cutstone'].face([(a,sign*W/2,za),(c,sign*W/2,zc),(c,sign*W/2,height(b,c,sign*W/2)),(a,sign*W/2,height(b,a,sign*W/2))],(0,sign,0))
        # Documented span ratios, fitted to the existing mapped deck length.
        pier=240. if len(spec['spans'])>1 else 0.;abut=130. if spec['key']!='petit' else 220.
        available=L-2*abut-(len(spec['spans'])-1)*pier;scale=available/sum(spec['spans']);start=-L/2+abut;arches=[]
        for span,kind in zip(spec['spans'],spec['types']):
            length=span*scale;arches.append((start,start+length,kind));start+=length+pier
        b['arches']=[dict(start_cm=a,end_cm=c,type=k) for a,c,k in arches]
        knots=sorted(set([-L/2,L/2]+[x for a,c,_ in arches for x in (a,c)]))
        for a,c in zip(knots,knots[1:]):
            if any(a>=u-.01 and c<=v+.01 for u,v,_ in arches):continue
            top=min(height(b,a,0),height(b,c,0))-40
            parts['stone'].box(a,c,-W/2,W/2,water-100,top)
            if a>-L/2+.1 and c<L/2-.1:
                mid=(a+c)/2
                for sign in (-1,1):
                    # Pointed cutwaters project from the actual load-bearing pier.
                    plan=[(a,sign*W/2),(c,sign*W/2),(mid,sign*(W/2+160))]
                    bottom=[(x,y,water-80) for x,y in plan];cap=[(x,y,top-180 if i<2 else top-230) for i,(x,y) in enumerate(plan)]
                    parts['stone'].face(cap,(0,0,1))
                    for j in range(3):q=(j+1)%3;parts['stone'].face([bottom[j],bottom[q],cap[q],cap[j]],(plan[j][0]-mid,plan[j][1],0))
                if spec.get('medallions'):
                    for sign in (-1,1):
                        yc=sign*(W/2+8);zc=height(b,mid,0)-128
                        circle=[(mid+66*math.cos(t),yc,zc+66*math.sin(t)) for t in np.linspace(0,math.tau,65)]
                        for p,q in zip(circle,circle[1:]):parts['cutstone'].bar(p,q,5,6)
                        for p,q in [((mid-24,yc,zc-38),(mid-24,yc,zc+38)),((mid+24,yc,zc-38),(mid+24,yc,zc+38)),((mid-24,yc,zc+38),(mid+24,yc,zc-38))]:parts['cutstone'].bar(p,q,7,4)
        for index,(a,c,kind) in enumerate(arches):
            mid=(a+c)/2;half=(c-a)/2;crown=height(b,mid,0)-100
            rise=min((c-a)*(.10 if spec['key']=='petit' else .20),crown-water-65);spring=crown-rise
            def underside(x):return spring+rise*math.sqrt(max(0.,1-((x-mid)/half)**2))
            steps=max(72,math.ceil((c-a)/38));samples=np.linspace(a,c,steps+1)
            if kind=='stone':
                for j,(x0,x1) in enumerate(zip(samples,samples[1:])):
                    z0,z1=underside(x0),underside(x1);top0,top1=height(b,x0,0)-44,height(b,x1,0)-44
                    for sign in (-1,1):
                        parts['stone'].face([(x0,sign*W/2,z0),(x1,sign*W/2,z1),(x1,sign*W/2,top1),(x0,sign*W/2,top0)],(0,sign,0))
                    parts['stone'].face([(x0,-W/2,z0),(x1,-W/2,z1),(x1,W/2,z1),(x0,W/2,z0)],(z1-z0,0,-(x1-x0)))
                # Individual radial voussoirs with small real gaps and bevels.
                blocks=max(27,math.ceil((c-a)/58))
                for j in range(blocks):
                    t0=math.pi*j/blocks+.002;t1=math.pi*(j+1)/blocks-.002;tm=(t0+t1)/2
                    inner=[(mid+half*math.cos(t),spring+rise*math.sin(t)) for t in (t0,t1)]
                    outer=[(mid+(half+72)*math.cos(t),spring+(rise+72)*math.sin(t)) for t in (t0,t1)]
                    tint=.91+.10*((j*37+index*23)%101)/100
                    for sign in (-1,1):
                        y=sign*(W/2+5);quad=[(inner[0][0],y,inner[0][1]),(inner[1][0],y,inner[1][1]),(outer[1][0],y,outer[1][1]),(outer[0][0],y,outer[0][1])]
                        parts['cutstone'].face(quad,(0,sign,0),(tint,tint*.99,tint*.96,1))
                        for k in range(4):q=(k+1)%4;parts['cutstone'].face([quad[k],quad[q],(quad[q][0],y-sign*6,quad[q][2]),(quad[k][0],y-sign*6,quad[k][2])],(math.cos(tm),0,math.sin(tm)))
            else:
                iron=parts[kind];rib_count=14 if spec['key']=='arcole' else 9
                for y in np.linspace(-W/2+22,W/2-22,rib_count):
                    for x0,x1 in zip(samples,samples[1:]):
                        z0,z1=underside(x0),underside(x1)
                        iron.face([(x0,y-13,z0),(x1,y-13,z1),(x1,y-13,z1+55),(x0,y-13,z0+55)],(0,-1,0));iron.face([(x0,y+13,z0),(x1,y+13,z1),(x1,y+13,z1+55),(x0,y+13,z0+55)],(0,1,0))
                        for zoff in (0,55):iron.face([(x0,y-24,z0+zoff),(x1,y-24,z1+zoff),(x1,y+24,z1+zoff),(x0,y+24,z0+zoff)],(0,0,-1 if zoff==0 else 1))
                for x in np.arange(a+90,c-60,230):
                    z=underside(x)+55;top=height(b,x,0)-45
                    for y in (-W/2+26,W/2-26):
                        iron.bar((x,y,z),(x,y,top),7,4)
                        for zz in (z+15,top-15):
                            for sign in (-1,1):iron.bar((x,y+sign*7,zz),(x,y+sign*9,zz),2.2,8)
                    iron.bar((x,-W/2+25,z),(x,W/2-25,z),10,4)
                # Side girders show real rivet heads rather than flat paint.
                for x in np.arange(a+50,c-30,95):
                    z=underside(x)+26
                    for sign in (-1,1):iron.bar((x,sign*(W/2-9),z),(x,sign*(W/2-7),z),2.4,8)
        metal=any(k!='stone' for k in spec['types']);rail=parts['copper' if spec['key']=='double' else 'iron'];sidewalk=14 if road else 0
        for sign in (-1,1):
            yc=sign*(W/2-26)
            for x0,x1 in zip(xs,xs[1:]):
                z0,z1=height(b,x0,yc),height(b,x1,yc)
                # Invisible simple barrier retains safe traversal in low quality.
                barrier=yc if metal else yc-sign*23
                parts['collision'].face([(x0,barrier,z0),(x1,barrier,z1),(x1,barrier,z1+106),(x0,barrier,z0+106)],(0,-sign,0))
                if not metal:
                    for side in (-1,1):parts['stone'].face([(x0,yc+side*23,z0),(x1,yc+side*23,z1),(x1,yc+side*23,z1+91),(x0,yc+side*23,z0+91)],(0,side,0))
                    parts['cutstone'].face([(x0,yc-29,z0+99),(x1,yc-29,z1+99),(x1,yc+29,z1+99),(x0,yc+29,z0+99)],(0,0,1))
                    for off in (16,82,93):parts['cutstone'].bar((x0,yc-sign*25,z0+off),(x1,yc-sign*25,z1+off),3.8,4)
                else:
                    for zoff,r in ((11,2.6),(51,2.0),(106,3.0)) :rail.bar((x0,yc,z0+zoff),(x1,yc,z1+zoff),r,8)
            if metal:
                for x in np.arange(-L/2+10,L/2,145):
                    z=height(b,x,yc);rail.bar((x,yc,z),(x,yc,z+113),4.,8)
                    for dx in (27,54,81,108):rail.bar((min(x+dx,L/2),yc,height(b,min(x+dx,L/2),yc)+13),(min(x+dx,L/2),yc,height(b,min(x+dx,L/2),yc)+101),1.2,6)
                    if spec['key']=='double':
                        ring=[(x+72+29*math.cos(t),yc,z+57+32*math.sin(t)) for t in np.linspace(0,math.tau,25)]
                        for p,q in zip(ring,ring[1:]):rail.bar(p,q,1.,6)
            for x in (-L/2+30,L/2-30):
                z=height(b,x,yc);parts['cutstone'].box(x-42,x+42,yc-42,yc+42,z-8,z+119);parts['cutstone'].box(x-47,x+47,yc-47,yc+47,z+119,z+130)
        materials=dict(stone='M_ParisBridgeMasonry',cutstone='M_ParisBridgeCutStone',iron='M_ParisBridgeIron',copper='M_ParisBridgeCopper',asphalt='M_ParisAsphaltPhotographic',paving='M_ParisBridgePaving',collision='M_Vertex')
        for key,mesh in parts.items():
            if mesh.ix:objects.append(mesh.item(key,'/Game/Materials/'+materials[key],key=='collision'))
    preview=next(b for b in profiles if b['id']=='michel');d=np.array(preview['direction']);s=np.array([-d[1],d[0]]);c=np.array(preview['centre_cm'][:2]);L=preview['length_cm'];eye=c-d*L*.72+s*(preview['width_cm']/2+L*.38)
    ground=landings.height(eye);eye_z=height(preview,-L*.45,0)+190
    if ground is not None:eye_z=max(eye_z,ground+170)
    camera=dict(position_cm=[*eye,eye_z],target_cm=[*c,height(preview,0,0)-155],focal_length_mm=28,bridge_id='michel',ground_z_cm=ground,
        height_source='Archived walkable triangles +170cm; independent of startup collision readiness')
    with open(CONTENT/'Data/paris-digital-twin-meshes.bin','rb') as stream:blob_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    result=dict(format='paris_bridge_display_v1',recipe=RECIPE,source_scene_sha256=data['source_scene_sha256'],source_geometry_sha256=blob_sha,
        appearance_provenance='Original inferred reconstruction using actual OSM axes, engineering references, and estimated archived terrain elevations; not a surveyed bridge model',profiles=profiles,objects=objects,preview_camera=camera,
        skipped_boundary_fragments=[o['id'] for o in sources if o['properties']['clipped_at_context_boundary']])
    if write:
        out=CONTENT/'Data/paris-bridges-source.json';out.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps(dict(bridges=len(profiles),parts=len(objects),triangles=sum(x['triangles'] for x in objects),source_meshes=sum(len(b['source_mesh_ids']) for b in profiles))))
    return result


if __name__=='__main__':generate()
