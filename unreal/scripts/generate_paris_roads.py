"""Rendering-only street finish derived from the existing GIS triangles.

No road is moved or widened. Kerbs occupy the existing sidewalk side of the
road edge; drainage covers are inferred details, not surveyed street assets.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from generate_paris_water import png

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT/'unreal/AIWorld/Content'
OUT = ROOT/'unreal/textures/paris-roads'
DTYPE = np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])
RECIPE = 'paris_road_finish_v1'


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class Surface:
    def __init__(self, obj, blob):
        b=obj['mesh_buffer']
        v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        self.triangles=v['p'][ix].astype('f8')
        self.polygons=[Polygon(t[:,:2]) for t in self.triangles]
        self.tree=STRtree(self.polygons)
        self.geometry=shapely.make_valid(unary_union(self.polygons))
        shapely.prepare(self.geometry)

    def height(self, xy):
        p=Point(xy)
        hits=self.tree.query(p,predicate='intersects')
        i=int(hits[0]) if len(hits) else int(self.tree.nearest(p))
        a,b,c=self.triangles[i]
        u,v=b-a,c-a
        den=u[0]*v[1]-u[1]*v[0]
        if abs(den)<1.e-8:raise ValueError('Degenerate source surface')
        s=((xy[0]-a[0])*v[1]-(xy[1]-a[1])*v[0])/den
        t=(u[0]*(xy[1]-a[1])-u[1]*(xy[0]-a[0]))/den
        return float(a[2]+s*u[2]+t*v[2])


class Mesh:
    def __init__(self):self.p=[];self.n=[];self.c=[];self.ix=[]

    def face(self, points, color):
        points=np.asarray(points,dtype='f8')
        n=np.cross(points[2]-points[0],points[1]-points[0])
        if np.linalg.norm(n)<1.e-8:return
        n/=np.linalg.norm(n);start=len(self.p)
        self.p.extend(np.round(points,5).tolist());self.n.extend([n.tolist()]*len(points));self.c.extend([color]*len(points))
        for j in range(1,len(points)-1):self.ix.extend([start,start+j,start+j+1])

    def box(self, centre, along, width, length, height, color):
        d=np.array(along);side=np.array([-d[1],d[0]])
        xy=[np.array(centre[:2])+d*x+side*y for x,y in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]]
        low=[[p[0],p[1],centre[2]] for p in xy];top=[[p[0],p[1],centre[2]+height] for p in xy]
        self.face(top[::-1],color)
        for i in range(4):j=(i+1)%4;self.face([low[i],low[j],top[j],top[i]],color)

    def item(self, name, material):
        body=dict(positions_cm=self.p,normals=self.n,vertex_colors=self.c,indices=self.ix)
        sha=digest(body)
        return dict(id=name,asset='/Game/ParisPhotoreal/Roads/SM_ParisRoad_'+name+'_'+sha[:12],material=material,
                    geometry_sha256=sha,triangles=len(self.ix)//3,**body)


def curves(g):
    if g.is_empty:return []
    if g.geom_type in ('LineString','LinearRing'):return [g]
    return [r for p in g.geoms for r in curves(p)]


def generate(write=True):
    data=json.loads((CONTENT/'Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    blob=np.memmap(CONTENT/'Data/paris-digital-twin-meshes.bin',dtype='u1',mode='r')
    surfaces={k:Surface(next(o for o in data['objects'] if o['kind']==k),blob) for k in ('road','sidewalk')}
    road,walk=surfaces['road'],surfaces['sidewalk'];q=np.array(data['quality_centre_ue_cm'][:2])
    zone=Point(q).buffer(14500)
    # Float32 archive vertices can differ by millimetres along shared edges.
    # A 1cm tolerance locates the same boundary without changing either mesh.
    shared=road.geometry.boundary.intersection(walk.geometry.buffer(1)).intersection(zone)
    segments=[]
    for line in sorted(curves(shared),key=lambda l:l.normalize().wkb_hex):
        coords=list(line.simplify(.05).coords)
        for a,b in zip(coords,coords[1:]):
            a,b=np.array(a),np.array(b);length=np.linalg.norm(b-a)
            if length<8:continue
            n=math.ceil(length/100)
            for i in range(n):segments.append((a+(b-a)*i/n,a+(b-a)*(i+1)/n))
    batches={};kerbs=drains=0;last_drains=[];placements=[]
    def batch(kind,p):
        key=f'{kind}_{math.floor(p[0]/6000)}_{math.floor(p[1]/6000)}'.replace('-','n')
        return batches.setdefault(key,Mesh())
    for a,b in segments:
        direction=(b-a)/np.linalg.norm(b-a);mid=(a+b)/2;side=np.array([-direction[1],direction[0]])
        if not walk.geometry.covers(Point(mid+side*12)):side=-side
        # All 20cm of visible stone must fit in the original walking surface.
        strip=Polygon([a+side,b+side,b+side*21,a+side*21])
        if not walk.geometry.buffer(.3).covers(strip):continue
        za,zb=walk.height(a+side*12)+.7,walk.height(b+side*12)+.7
        ba,bb=road.height(a)+.2,road.height(b)+.2
        if min(za-ba,zb-bb)<2 or max(za-ba,zb-bb)>35:continue
        # Half-centimetre joints and a 2cm chamfer catch genuine light/shadow.
        a=a+direction*.3;b=b-direction*.3
        mesh=batch('kerb',mid);tint=.8+.12*((int(mid[0]*13+mid[1]*7)&255)/255)
        color=[round(tint*.91,4),round(tint*.90,4),round(tint*.86,4),1]
        at=lambda p,s,z:[float(p[0]+side[0]*s),float(p[1]+side[1]*s),float(z)]
        section=lambda p,z,bottom:[at(p,1,bottom),at(p,1,z-2),at(p,3,z),at(p,19,z),at(p,21,z-2),at(p,21,bottom)]
        aa,ab=section(a,za,ba),section(b,zb,bb)
        # Orient every face to the intended outward normal (UE clockwise).
        def outward(points,wanted):
            pts=np.asarray(points);normal=np.cross(pts[2]-pts[0],pts[1]-pts[0])
            mesh.face(points if np.dot(normal,wanted)>0 else list(reversed(points)),color)
        outward(aa,np.r_[-direction,0]);outward(ab,np.r_[direction,0])
        for i in range(5):
            wanted=np.r_[-side,0] if i==0 else np.array([0,0,1]) if i in (1,2,3) else np.r_[side,0]
            outward([aa[i],ab[i],ab[i+1],aa[i+1]],wanted)
        kerbs+=1
        # Sparse inferred drains, entirely inside existing asphalt coverage.
        centre=mid-side*23;foot=Polygon([centre-direction*29-side*16,centre+direction*29-side*16,centre+direction*29+side*16,centre-direction*29+side*16])
        if not road.geometry.covers(foot) or any(np.linalg.norm(centre-p)<1800 for p in last_drains):continue
        z=road.height(centre)+.3;iron=batch('iron',mid);base=[float(centre[0]),float(centre[1]),z]
        iron.box(base,direction,30,56,.2,[.055,.06,.057,1])
        for offset in (-14,14):iron.box([*(centre+side*offset),z+.2],direction,2,56,.65,[.22,.23,.22,1])
        for offset in (-27,27):iron.box([*(centre+direction*offset),z+.2],side,2,28,.65,[.22,.23,.22,1])
        for offset in np.linspace(-23,23,12):iron.box([*(centre+direction*offset),z+.2],side,1.4,26,.55,[.19,.20,.19,1])
        placements.append(dict(kind='inferred_drain',xy_cm=centre.tolist(),footprint_cm=[list(p) for p in foot.exterior.coords],height_cm=z,source_surface_id='roads'))
        last_drains.append(centre);drains+=1
    objects=[mesh.item(name,'/Game/Materials/M_ParisRoadKerb' if name.startswith('kerb') else '/Game/Materials/M_ParisRoadIron') for name,mesh in sorted(batches.items())]

    # A continuous view along a real road, within the existing quality district.
    cameras=[]
    for f in data['pick_features']:
        if f['kind']!='road' or f['properties'].get('tunnel') or f['properties'].get('bridge') or f['properties'].get('width_m',0)<5:continue
        for line in f.get('polylines_cm',[]):
            line=LineString([p[:2] for p in line]);length=line.length
            if length<2800:continue
            for t in (.25,.5,.75):
                p=line.interpolate(t,normalized=True);xy=np.array(p.coords[0]);distance=np.linalg.norm(xy-q)
                if distance>13000 or road.geometry.boundary.distance(p)<160:continue
                for sign in (-1,1):
                    aim=line.interpolate(np.clip(t*length+sign*2300,0,length));target=np.array(aim.coords[0]);d=target-xy
                    if np.linalg.norm(d)<1800:continue
                    ray=LineString([xy,target]);score=ray.intersection(road.geometry).length
                    if score<2200:continue
                    cameras.append((distance+abs(road.geometry.boundary.distance(p)-350)*8,xy,target,f['id']))
    if not cameras:raise ValueError('No source-aligned road comparison camera')
    _,position,target,source_id=min(cameras,key=lambda c:(c[0],c[3]))
    camera=dict(position_cm=[*position,road.height(position)+170],target_cm=[*target,road.height(target)+65],focal_length_mm=30,source_id=source_id)
    # 320m detail atlas: packed signed distance has sub-cm quantization. Pixel
    # interpolation resolves broad 20-80cm gutter dirt; no geometry displacement.
    size=2048;bounds=[*(q-16000),*(q+16000)];OUT.mkdir(parents=True,exist_ok=True)
    lines=[]
    for line in curves(road.geometry.boundary):
        coords=list(line.coords);lines.extend(LineString([a,b]) for a,b in zip(coords,coords[1:]))
    edges=STRtree(lines);pixels=np.full((size,size,4),255,dtype='u1')
    directions=np.array([np.subtract(l.coords[-1],l.coords[0]) for l in lines])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    directions*=np.where(directions[:,0:1]<0,-1,1)
    xs=bounds[0]+(np.arange(size)+.5)*32000/size
    for start in range(0,size,64):
        ys=bounds[1]+(np.arange(start,min(start+64,size))+.5)*32000/size
        x,y=np.meshgrid(xs,ys);points=shapely.points(x.ravel(),y.ravel())
        index,dist=edges.query_nearest(points,return_distance=True,all_matches=False)
        distance=np.empty(len(points));distance[index[0]]=dist
        signed=np.where(shapely.contains_xy(road.geometry,x.ravel(),y.ravel()),distance,-distance)
        value=np.rint(np.clip((signed+3200)/6400,0,1)*65535).astype('u2').reshape(x.shape)
        pixels[start:start+len(ys),:,0]=value>>8;pixels[start:start+len(ys),:,1]=value&255
        tangent=np.empty((len(points),2));tangent[index[0]]=directions[index[1]]
        pixels[start:start+len(ys),:,2:]=np.rint((tangent.reshape(*x.shape,2)*.5+.5)*255).astype('u1')
    if write:png(OUT/'road-edge-distance.png',pixels)
    # Original centimetre-scale wear mask. Photo asphalt remains the base.
    size=1024;rng=np.random.default_rng(20261027)
    x,y=np.meshgrid((np.arange(size)+.5)*1200/size,(np.arange(size)+.5)*1200/size)
    patch=np.zeros_like(x);crack=np.full_like(x,1.e6)
    for i in range(5):
        cx,cy=rng.uniform(120,1080,2);w,h=rng.uniform(35,110),rng.uniform(70,190)
        angle=rng.uniform(-.35,.35);xx=(x-cx)*np.cos(angle)+(y-cy)*np.sin(angle);yy=-(x-cx)*np.sin(angle)+(y-cy)*np.cos(angle)
        edge=np.maximum(abs(xx)-w,abs(yy)-h)+1.4*np.sin(x*.07)*np.sin(y*.11)
        patch=np.maximum(patch,np.clip(.5-edge/2,0,1))
    for i in range(11):
        p=rng.uniform(90,1110,2);angle=rng.uniform(0,2*np.pi)
        for j in range(int(rng.integers(3,7))):
            angle+=rng.uniform(-.55,.55);b=p+rng.uniform(18,43)*np.array([np.cos(angle),np.sin(angle)])
            dx,dy=b-p;s=np.clip(((x-p[0])*dx+(y-p[1])*dy)/(dx*dx+dy*dy),0,1)
            crack=np.minimum(crack,np.hypot(x-p[0]-s*dx,y-p[1]-s*dy));p=b
    cracks=np.clip((1.45-crack)/1.4,0,1)
    # Edge-fade makes the tile exactly seamless, including repaired areas.
    fade=np.clip(np.minimum.reduce([x,y,1200-x,1200-y])/40,0,1);patch*=fade;cracks*=fade
    macro=.5+.23*np.sin(2*np.pi*x/1200+.3)*np.sin(4*np.pi*y/1200)+.13*np.cos(8*np.pi*x/1200+6*np.pi*y/1200)
    age=np.stack([patch,cracks,macro,np.clip(np.hypot(*np.gradient(patch))*.8,0,1)],axis=-1)
    if write:png(OUT/'road-age-mask.png',np.rint(np.clip(age,0,1)*255).astype('u1'))
    runtime=dict(schema_version=1,recipe=RECIPE,source_scene_sha256=data['source_scene_sha256'],
        source_mesh_sha256=hashlib.sha256(blob).hexdigest(),quality_centre_cm=q.tolist(),detail_radius_cm=14500,
        atlas_bounds_cm=[float(v) for v in bounds],atlas_resolution=2048,wear_tile_cm=1200,
        preview_camera=camera,kerb_stones=kerbs,drain_grates=drains,
        appearance_provenance='Inferred granite kerbs, slab joints, wear, repairs and drains; not surveyed Paris finishes or actual drainage locations. Source GIS footprint/height/collision retained.',
        source_attribution='OpenStreetMap contributors (ODbL-1.0), IGN terrain used by unchanged source triangles',
        photographic_source='Existing verified Poly Haven CC0 asphalt_02, cobblestone_pavement and white_plaster_02; no new downloads',
        placements=placements,objects=objects)
    if write:
        runtime['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.png'))}
        (CONTENT/'Data/paris-road-detail-source.json').write_text(json.dumps(runtime,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    return runtime


if __name__=='__main__':
    result=generate()
    print(json.dumps(dict(kerb_stones=result['kerb_stones'],drain_grates=result['drain_grates'],batches=len(result['objects']),triangles=sum(o['triangles'] for o in result['objects']),camera=result['preview_camera'])))
