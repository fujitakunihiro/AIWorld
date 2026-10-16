"""Display-only window relief derived from existing GIS facade quads, offline.

No new geographic facts: even the source windows were inferred. Keep their
position/size and building IDs; do not regenerate or edit the source scene.
"""
import hashlib
import json
import math
import struct
from pathlib import Path
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'unreal/AIWorld/Content/Data'


def read(name):
    return json.loads((DATA / name).read_text(encoding='utf-8-sig'))


class Mesh:
    def __init__(self,bevel_cm=0):
        self.positions_cm=[];self.normals=[];self.indices=[];self.uv0=[];self.colors=[]
        self.bevel_cm=bevel_cm

    def face(self, points, normal, color, uvs=None):
        # UE front faces use clockwise winding when seen from outside.
        a,b,c=points[:3]
        cross=((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),
               (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),
               (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        uvs=uvs or [(0,0)]*len(points)
        if sum(x*y for x,y in zip(cross,normal))>0:points=list(reversed(points));uvs=list(reversed(uvs))
        start=len(self.positions_cm)
        self.positions_cm.extend([[round(v,5) for v in p] for p in points]);self.normals.extend([list(normal)]*len(points))
        self.uv0.extend(uvs);self.colors.extend([color]*len(points));self.indices.extend([start,start+1,start+2] if len(points)==3 else [start,start+1,start+2,start,start+2,start+3])

    def box(self, origin, tangent, normal, centre, size, color):
        if self.bevel_cm:return self.beveled_box(origin,tangent,normal,centre,size,color)
        def world(x,y,z):return [origin[i]+tangent[i]*x+normal[i]*y+(z if i==2 else 0) for i in range(3)]
        bounds=[(centre[i]-size[i]/2,centre[i]+size[i]/2) for i in range(3)]
        p=[world(x,y,z) for x in bounds[0] for y in bounds[1] for z in bounds[2]]
        for ids,n in [([0,1,3,2],[-v for v in tangent]),([4,6,7,5],tangent),
                      ([0,4,5,1],[-v for v in normal]),([2,3,7,6],normal),
                      ([0,2,6,4],[0,0,-1]),([1,5,7,3],[0,0,1])]:
            self.face([p[i] for i in ids],n,color)

    def beveled_box(self,origin,tangent,normal,centre,size,color):
        # An inset box: 6 broad faces, 12 edge strips, 8 corner triangles.
        # The original bounds stay exact. Only the visible edge is softened.
        e=[s/2 for s in size];b=min(self.bevel_cm,min(e)*.3)
        def world(q):
            x,y,z=[q[i]+centre[i] for i in range(3)]
            return [origin[i]+tangent[i]*x+normal[i]*y+(z if i==2 else 0) for i in range(3)]
        def face(points,n):
            length=math.sqrt(sum(v*v for v in n));n=[v/length for v in n]
            outward=[tangent[i]*n[0]+normal[i]*n[1]+(n[2] if i==2 else 0) for i in range(3)]
            self.face([world(p) for p in points],outward,color)
        for i in range(3):
            j,k=[a for a in range(3) if a!=i]
            for sign in [-1,1]:
                points=[]
                for sj,sk in [(-1,-1),(1,-1),(1,1),(-1,1)]:
                    p=[0,0,0];p[i]=sign*e[i];p[j]=sj*(e[j]-b);p[k]=sk*(e[k]-b);points.append(p)
                n=[0,0,0];n[i]=sign;face(points,n)
        for i,j in [(0,1),(0,2),(1,2)]:
            k=3-i-j
            for si in [-1,1]:
                for sj in [-1,1]:
                    points=[]
                    for ai,aj,sk in [(e[i],e[j]-b,-1),(e[i]-b,e[j],-1),(e[i]-b,e[j],1),(e[i],e[j]-b,1)]:
                        p=[0,0,0];p[i]=si*ai;p[j]=sj*aj;p[k]=sk*(e[k]-b);points.append(p)
                    n=[0,0,0];n[i]=si;n[j]=sj;face(points,n)
        for sx in [-1,1]:
            for sy in [-1,1]:
                for sz in [-1,1]:
                    signs=[sx,sy,sz];points=[]
                    for axis in range(3):points.append([signs[i]*(e[i] if i==axis else e[i]-b) for i in range(3)])
                    face(points,signs)

    def item(self, name, material):
        geometry=dict(positions_cm=self.positions_cm,normals=self.normals,indices=self.indices,uv0=self.uv0,colors=self.colors)
        sha=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return dict(id=name,asset='/Game/ParisPhotoreal/Frontages/SM_ParisFrontage_'+name+'_'+sha[:12],
                    geometry_sha256=sha,material='/Game/Materials/'+material,triangles=len(self.indices)//3,**geometry)

    def extend(self, other):
        start=len(self.positions_cm)
        for field in ['positions_cm','normals','uv0','colors']:getattr(self,field).extend(getattr(other,field))
        self.indices.extend(start+i for i in other.indices)

    def tube(self,a,b,radius,color,sides=8):
        axis=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(v*v for v in axis));axis=[v/length for v in axis]
        reference=[0,0,1] if abs(axis[2])<.9 else [1,0,0]
        u=[axis[1]*reference[2]-axis[2]*reference[1],axis[2]*reference[0]-axis[0]*reference[2],axis[0]*reference[1]-axis[1]*reference[0]]
        length=math.sqrt(sum(v*v for v in u));u=[v/length for v in u]
        v=[axis[1]*u[2]-axis[2]*u[1],axis[2]*u[0]-axis[0]*u[2],axis[0]*u[1]-axis[1]*u[0]]
        rim=[[u[i]*math.cos(k*2*math.pi/sides)+v[i]*math.sin(k*2*math.pi/sides) for i in range(3)] for k in range(sides)]
        for k in range(sides):
            j=(k+1)%sides
            self.face([[p[i]+rim[q][i]*radius for i in range(3)] for p,q in [(a,k),(b,k),(b,j),(a,j)]],[(rim[k][i]+rim[j][i])/(2*math.cos(math.pi/sides)) for i in range(3)],color)
            self.face([a,[a[i]+rim[k][i]*radius for i in range(3)],[a[i]+rim[j][i]*radius for i in range(3)]],[-x for x in axis],color)
            self.face([b,[b[i]+rim[k][i]*radius for i in range(3)],[b[i]+rim[j][i]*radius for i in range(3)]],axis,color)


def add_entry_details(scene,blob,polygons,ox,oy,anchor,stone,wood):
    """Decorate existing inferred door/eave quads, never choose new GIS sites."""
    iron=Mesh(bevel_cm=.18);joinery=Mesh(bevel_cm=.18);entrances=[];cornices=[];seen=set()
    for obj in scene['objects']:
        if obj['kind'] not in ('facade_wood','facade_trim'):continue
        span=obj['mesh_buffer'];offset=span['offset'];count=span['vertex_count']
        rows=list(struct.iter_unpack('<6f4B',blob[offset:offset+28*count]))
        indices=struct.unpack_from('<'+str(span['index_count'])+'I',blob,offset+28*count)
        for k in range(0,len(indices),6):
            ids=list(dict.fromkeys(indices[k:k+6]))
            if len(ids)!=4:continue
            pts=[rows[i][:3] for i in ids];n=list(rows[ids[0]][3:6]);length=math.hypot(n[0],n[1])
            if length<.99 or abs(n[2])>.001:continue
            n=[n[0]/length,n[1]/length,0];t=[n[1],-n[0],0]
            centre=[sum(p[i] for p in pts)/4 for i in range(3)]
            if math.dist(centre[:2],anchor[:2])>10000:continue
            xs=[sum((p[i]-centre[i])*t[i] for i in range(3)) for p in pts]
            width=max(xs)-min(xs);height=max(p[2] for p in pts)-min(p[2] for p in pts)
            role='entrance' if obj['kind']=='facade_wood' and 129<width<131 and 257<height<259 else 'cornice' if obj['kind']=='facade_trim' and width>150 and 20<height<23 else None
            if not role:continue
            wall_offset=30.75 if role=='entrance' else 24
            projected=Point(ox+(centre[0]-n[0]*wall_offset)/100,oy-(centre[1]-n[1]*wall_offset)/100)
            candidates=[(polygons[sid].boundary.distance(projected),sid) for sid in obj['properties']['source_ids'] if sid in polygons]
            if not candidates:continue
            distance,sid=min(candidates)
            key=(role,)+tuple(round(v,2) for v in centre+n)
            if distance>.03 or sid in ('osm/relation/2449758','osm/way/201611261') or key in seen:continue
            seen.add(key)
            record=dict(source_id=sid,source_mesh_id=obj['id'],source_quad_index=k//6,centre_cm=centre,normal=n,width_cm=width,height_cm=height,wall_offset_cm=wall_offset)
            c=[212,204,185,255]
            if role=='cornice':
                # Small stepped crown and corbels, retaining source width/eave.
                for z,depth,high,y in [(-9,12,4,4),(-3,18,8,7),(4,26,6,10),(9,34,5,13)]:
                    stone.box(centre,t,n,(0,y,z),(width,depth,high),c)
                brackets=max(1,round(width/80))
                for j in range(brackets):
                    x=(j+.5)*width/brackets-width/2
                    stone.box(centre,t,n,(x,3,-21),(11,19,20),c)
                    stone.box(centre,t,n,(x,10,-14),(14,22,7),c)
                cornices.append(record);continue
            digest=hashlib.sha256(sid.encode()).digest();paint=[[39,56,51,255],[48,57,64,255],[68,53,42,255]][digest[0]%3]
            bottom=-height/2;top=height/2
            # The panel sits ahead of the old door; surrounds project farther,
            # producing a shallow reveal without cutting the collision mesh.
            joinery.box(centre,t,n,(0,1,0),(width,4,height),paint)
            for side in [-1,1]:
                stone.box(centre,t,n,(side*(width/2+9),-4,6),(16,32,height+12),c)
                stone.box(centre,t,n,(side*(width/2+9),7,6),(7,10,height+12),c)
            for z,w,d,h,y in [(top+6,width+48,32,18,0),(top+22,width+42,28,16,0),(top+37,width+56,40,14,4),(top+46,width+62,46,6,7)]:
                stone.box(centre,t,n,(0,y,z),(w,d,h),c)
            for x in [-width/2+3,0,width/2-3]:joinery.box(centre,t,n,(x,4,0),(5,5,height),paint)
            # Three raised, bevelled panels on each leaf, with inset centres.
            for side in [-1,1]:
                x=side*width/4
                for z,h in [(bottom+32,40),(bottom+92,46),(top-55,90)]:
                    joinery.box(centre,t,n,(x,3.8,z),(width/2-17,2.4,h),[max(0,v-7) if i<3 else v for i,v in enumerate(paint)])
                    for dx in [-1,1]:joinery.box(centre,t,n,(x+dx*(width/4-8.5),5.2,z),(3.5,3,h+4),paint)
                    for dz in [-1,1]:joinery.box(centre,t,n,(x,5.2,z+dz*h/2),(width/2-13.5,3,3.5),paint)
                # Black iron escutcheon and a round pull held away from timber.
                hx=side*10;hz=bottom+104;iron.box(centre,t,n,(hx,7,hz),(5,2,24),[62,65,62,255])
                def world(x,y,z):return [centre[i]+t[i]*x+n[i]*y+(z if i==2 else 0) for i in range(3)]
                for a,b in [((hx,8,hz-8),(hx,12,hz-8)),((hx,12,hz-8),(hx,12,hz+8)),((hx,12,hz+8),(hx,8,hz+8))]:
                    iron.tube(world(*a),world(*b),.8,[62,65,62,255])
            entrances.append(record)
    wood.extend(joinery)
    return entrances,cornices,iron


def generate():
    scene=read('paris-digital-twin-runtime.json');architecture=read('paris-photo-architecture.json')
    blob=(DATA/'paris-digital-twin-meshes.bin').read_bytes()
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    ox,oy=district['origin_projected_m'];anchor=architecture['local_frame']['front_cm']
    polygons={f['properties']['source_id']:shape(f['geometry']) for f in district['layers']['buildings']}
    stone,wood,glass=Mesh(bevel_cm=.35),Mesh(),Mesh();windows=[];seen=set();occluded=[]
    entrances,cornices,iron=add_entry_details(scene,blob,polygons,ox,oy,anchor,stone,wood)
    if not entrances or not cornices:raise RuntimeError('No source-aligned entrances/eaves found')
    for obj in scene['objects']:
        if obj['kind']!='facade_glass':continue
        span=obj['mesh_buffer'];offset=span['offset'];count=span['vertex_count']
        rows=list(struct.iter_unpack('<6f4B',blob[offset:offset+28*count]))
        indices=struct.unpack_from('<'+str(span['index_count'])+'I',blob,offset+28*count)
        for k in range(0,len(indices),6):
            ids=list(dict.fromkeys(indices[k:k+6]))
            if len(ids)!=4:continue
            pts=[rows[i][:3] for i in ids];n=list(rows[ids[0]][3:6]);length=math.hypot(n[0],n[1])
            if length<.99 or abs(n[2])>.001:continue
            n=[n[0]/length,n[1]/length,0];t=[n[1],-n[0],0]
            centre=[sum(p[i] for p in pts)/4 for i in range(3)]
            if math.dist(centre[:2],anchor[:2])>10000:continue
            xs=[sum((p[i]-centre[i])*t[i] for i in range(3)) for p in pts]
            width=max(xs)-min(xs);height=max(p[2] for p in pts)-min(p[2] for p in pts)
            if not (85<width<95 and 160<height<170):continue # exclude dormers / storefront panes
            key=tuple(round(v,2) for v in centre+n)
            if key in seen:continue
            projected=Point(ox+(centre[0]-n[0]*9)/100,oy-(centre[1]-n[1]*9)/100)
            candidates=[(polygons[sid].boundary.distance(projected),sid) for sid in obj['properties']['source_ids'] if sid in polygons]
            if not candidates:continue
            distance,source_id=min(candidates)
            if distance>.03 or source_id in ('osm/relation/2449758','osm/way/201611261'):continue
            seen.add(key)
            covering=next((e for e in entrances if e['source_id']==source_id and
                sum(e['normal'][i]*n[i] for i in range(3))>.999 and
                abs(sum((centre[i]-e['centre_cm'][i])*t[i] for i in range(3)))<(width+e['width_cm'])/2 and
                centre[2]-height/2<e['centre_cm'][2]+e['height_cm']/2 and centre[2]+height/2>e['centre_cm'][2]-e['height_cm']/2),None)
            if covering:
                occluded.append(dict(source_id=source_id,source_mesh_id=obj['id'],source_quad_index=k//6,centre_cm=centre,
                    entrance_source_mesh_id=covering['source_mesh_id'],entrance_source_quad_index=covering['source_quad_index'],reason='Inferred source window overlaps source entrance; omit display-only window relief, retain source GIS'))
                continue
            digest=hashlib.sha256((source_id+str(key)).encode()).digest();seed=digest[0]
            c=[205+digest[1]%12,195+digest[1]%12,174+digest[1]%12,255]
            # Original glass is 9cm in front of the OSM wall. New glazing lies
            # 14cm forward; joinery/stone conceal the legacy flat border.
            bottom=-height/2;top=height/2;half=width/2
            for x in [-half-7,half+7]:
                stone.box(centre,t,n,(x,9,0),(14,28,height+24),c)
                stone.box(centre,t,n,(x+(2 if x<0 else -2),21,0),(5,6,height+10),c)
            for z,sx,sy,sz,y in [(bottom-8,width+38,42,12,12),(bottom-1,width+28,34,5,12),(top+8,width+32,27,16,8),(top+18,width+40,33,5,10)]:
                stone.box(centre,t,n,(0,y,z),(sx,sy,sz),c)
            if digest[2]%3==0:stone.box(centre,t,n,(0,24,top+7),(17,12,23),c)
            for x in [-half+10,half-10]:stone.box(centre,t,n,(x,10,bottom-21),(12,22,16),c)
            paint=[57+digest[3]%17,65+digest[3]%15,61+digest[3]%14,255]
            for x in [-half+2,0,half-2]:wood.box(centre,t,n,(x,8,0),(5,8,height),paint)
            for z in [bottom+2,top-55,top-2]:wood.box(centre,t,n,(0,8,z),(width,8,5),paint)
            corners=[[centre[i]+t[i]*x+n[i]*5+(z if i==2 else 0) for i in range(3)] for x,z in [(-half,bottom),(half,bottom),(half,top),(-half,top)]]
            glass.face(corners,n,[seed,digest[4],digest[5],255],[(0,0),(1,0),(1,1),(0,1)])
            windows.append(dict(source_id=source_id,source_mesh_id=obj['id'],source_quad_index=k//6,
                                centre_cm=centre,normal=n,width_cm=width,height_cm=height))
    if not windows:raise RuntimeError('No source-aligned windows found')
    street=next(c for c in scene['photo_cameras'] if c['name']=='Camera_Paris_Street')
    # Inspect an upper-storey window so existing ground-floor awnings do not
    # obscure the glazing. Camera position and all geographic data stay fixed.
    upper=[w for w in windows if 200<w['centre_cm'][2]-street['position_cm'][2]<650]
    nearest=min(upper or windows,key=lambda w:math.dist(w['centre_cm'],street['position_cm']))
    entry=min(entrances,key=lambda w:math.dist(w['centre_cm'],street['position_cm']))
    entry_camera=None
    for distance in [600,550,500,400,300,250]:
        candidate=[entry['centre_cm'][i]+entry['normal'][i]*distance for i in range(3)]
        candidate[2]=entry['centre_cm'][2]-entry['height_cm']/2+170
        point=Point(ox+candidate[0]/100,oy-candidate[1]/100)
        if not any(p.buffer(.6).covers(point) for p in polygons.values()):entry_camera=candidate;break
    if entry_camera is None:raise RuntimeError('No safe entry inspection camera outside source buildings')
    return dict(format='paris_inferred_frontages_v2',source_scene_sha256=scene['source_scene_sha256'],
        origin_wgs84=architecture['origin_wgs84'],origin_elevation_ngf_m=architecture['origin_elevation_ngf_m'],
        radius_cm=10000,anchor_cm=anchor,window_count=len(windows),windows=windows,
        inspection_target_cm=nearest['centre_cm'],inspection_source_id=nearest['source_id'],
        entrance_count=len(entrances),cornice_count=len(cornices),entrances=entrances,cornices=cornices,occluded_source_windows=occluded,
        inspection_entry_camera_cm=entry_camera,inspection_entry_target_cm=[*entry['centre_cm'][:2],entry['centre_cm'][2]+25],inspection_entry_source_id=entry['source_id'],
        stone_bevel_cm=.35,
        appearance_provenance='Inferred window profiles, panelled entrances, iron pulls and stepped cornices at existing inferred source facade quads; not surveyed facades or real interiors. GIS footprints, volumes and collision unchanged.',
        objects=[stone.item('stone','M_Paris_Limestone'),wood.item('joinery','M_ParisWindowPaintedWood'),glass.item('glass','M_ParisWindowGlass'),iron.item('iron','M_ParisCastIron')])


if __name__=='__main__':
    result=generate();(DATA/'paris-photo-frontages-source.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(windows=result['window_count'],entrances=result['entrance_count'],cornices=result['cornice_count'],buildings=len(set(w['source_id'] for w in result['windows'])),triangles=sum(o['triangles'] for o in result['objects']))))
