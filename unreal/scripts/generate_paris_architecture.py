"""Original west-facade study. No surveyed facade or imported finished model claim.

The GIS source is read only. Dimensions: Notre-Dame's official architecture page.
Mouldings, sculpture silhouettes, opening depths and individual stones are inferred.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gis'))
from shapely.geometry import shape, Point, Polygon, box as polygon_box
from shapely.ops import triangulate
from paris_twin.coordinates import Georeference
from paris_twin.terrain import Terrain


def generate():
    config=json.loads((ROOT/'gis/config/ile_de_la_cite.json').read_text(encoding='utf-8'))
    dataset=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    geo=Georeference(config);terrain=Terrain(config,geo)
    building=next(f for f in dataset['layers']['buildings'] if f['properties']['source_id']=='osm/way/201611261')
    g=shape(building['geometry']);rect=list(g.minimum_rotated_rectangle.exterior.coords)
    a,b=max(zip(rect,rect[1:]),key=lambda pair:math.dist(*pair));length=math.dist(a,b)
    dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
    if dx<0:dx,dy=-dx,-dy
    c=g.centroid;low=min((x-c.x)*dx+(y-c.y)*dy for x,y in g.exterior.coords)
    front=(c.x+dx*low,c.y+dy*low);ground=terrain.local(front)
    def world(p,normal=False):
        x,y,z=p;e=-dy*x+dx*y;n=dx*x+dy*y
        return [e,-n,z] if normal else [round((front[0]+e-geo.origin[0])*100,4),round(-(front[1]+n-geo.origin[1])*100,4),round((ground+z)*100,4)]
    groups={name:dict(positions_cm=[],normals=[],indices=[]) for name in ['stone','wood','glass','iron','sculpture','stained','virgin_fallback']}
    def face(kind,points,n,tint=None,vertex_normals=None):
        out=groups[kind];start=len(out['positions_cm']);points=[world(p) for p in points];normal=world(n,True)
        magnitude=math.sqrt(sum(v*v for v in normal));normal=[v/magnitude for v in normal]
        u=[points[1][i]-points[0][i] for i in range(3)];v=[points[2][i]-points[0][i] for i in range(3)]
        cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        reverse=sum(cross[i]*normal[i] for i in range(3))>0
        out['positions_cm'].extend(points)
        if vertex_normals is not None:
            if len(vertex_normals)!=len(points):raise ValueError('Sculpture vertex normal count differs from its face')
            normals=[world(v,True) for v in vertex_normals]
            out['normals'].extend([[v/math.sqrt(sum(q*q for q in row)) for v in row] for row in normals])
        else:out['normals'].extend([normal]*len(points))
        if kind=='stained':out.setdefault('colors_srgb',[]).extend([tint or '233943']*len(points))
        for i in range(1,len(points)-1):out['indices'].extend([start,start+i+1,start+i] if reverse else [start,start+i,start+i+1])
    def box(kind,x,y,z,w,d,h):
        x0,x1=x-w/2,x+w/2;y0,y1=y-d/2,y+d/2;z0,z1=z,z+h
        face(kind,[(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],(0,-1,0))
        face(kind,[(x1,y1,z0),(x0,y1,z0),(x0,y1,z1),(x1,y1,z1)],(0,1,0))
        face(kind,[(x0,y1,z0),(x0,y0,z0),(x0,y0,z1),(x0,y1,z1)],(-1,0,0))
        face(kind,[(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)],(1,0,0))
        face(kind,[(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],(0,0,1))
    def tube(kind,points,r,sides=8):
        for a,b in zip(points,points[1:]):
            direction=[b[i]-a[i] for i in range(3)];mag=math.sqrt(sum(v*v for v in direction))
            if mag<1e-8:continue
            direction=[v/mag for v in direction];ref=(0,1,0) if abs(direction[1])<.8 else (1,0,0)
            u=[direction[1]*ref[2]-direction[2]*ref[1],direction[2]*ref[0]-direction[0]*ref[2],direction[0]*ref[1]-direction[1]*ref[0]];mag=math.sqrt(sum(v*v for v in u));u=[v/mag for v in u]
            v=[direction[1]*u[2]-direction[2]*u[1],direction[2]*u[0]-direction[0]*u[2],direction[0]*u[1]-direction[1]*u[0]]
            ring=[[u[k]*math.cos(t*math.tau/sides)+v[k]*math.sin(t*math.tau/sides) for k in range(3)] for t in range(sides)]
            for j in range(sides):
                k=(j+1)%sides;n=[(ring[j][i]+ring[k][i])/2 for i in range(3)]
                face(kind,[[p[i]+r*ring[q][i] for i in range(3)] for p,q in [(a,j),(a,k),(b,k),(b,j)]],n)
    def circle(x,z,r,y,segments=96):return [(x+r*math.cos(i*math.tau/segments),y,z+r*math.sin(i*math.tau/segments)) for i in range(segments+1)]
    def stone_rib(points,normal,width=.8,thickness=.5):
        """Rectangular masonry voussoirs, rather than a round pipe in mid-air."""
        side=(-normal[1]*width/2,normal[0]*width/2,0)
        for a,b in zip(points,points[1:]):
            tangent=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);horizontal=math.hypot(tangent[0],tangent[1])
            top_normal=(-tangent[0]*tangent[2]/horizontal,-tangent[1]*tangent[2]/horizontal,horizontal)
            low=[(p[0]+s*side[0],p[1]+s*side[1],p[2]) for p,s in [(a,-1),(b,-1),(b,1),(a,1)]]
            high=[(p[0],p[1],p[2]+thickness) for p in low]
            face('stone',high,top_normal);face('stone',list(reversed(low)),tuple(-v for v in top_normal))
            for j,n in [(0,(-side[0],-side[1],0)),(2,side)]:
                k=(j+1)%4;face('stone',[low[j],low[k],high[k],high[j]],n)
        for p,s in [(points[0],1),(points[-1],-1)]:
            face('stone',[(p[0]-side[0],p[1]-side[1],p[2]),(p[0]+side[0],p[1]+side[1],p[2]),(p[0]+side[0],p[1]+side[1],p[2]+thickness),(p[0]-side[0],p[1]-side[1],p[2]+thickness)],(normal[0]*s,normal[1]*s,0))
    def ogive(x,z,width,height,y,segments=48):
        # Parametric two-centred pointed arch, sampled continuously at the apex.
        half=width/2;rise=height-z;offset=(rise*rise-half*half)/(2*half);radius=half+offset
        apex=math.atan2(rise,-offset)
        left=[(x+offset+radius*math.cos(math.pi+(apex-math.pi)*i/(segments//2)),y,z+radius*math.sin(math.pi+(apex-math.pi)*i/(segments//2))) for i in range(segments//2+1)]
        return left+[(2*x-p[0],p[1],p[2]) for p in reversed(left[:-1])]
    def arch(kind,x,z,width,top,y,bottom=None):
        points=ogive(x,z,width,top,y)
        base=(0 if z<8 else z-10) if bottom is None else bottom
        face(kind,[(x-width/2,y,base),(x+width/2,y,base),*reversed(points)],(0,-1,0))
    def pierced_wall(x0,x1,z0,z1,y,depth,holes,side=None):
        """Solid stone surround and real reveals; openings contain no black card.

        Profile coordinates are across/height; side walls rotate this profile
        around the same GIS anchor. Triangles are clipped to preserve holes.
        """
        wall=polygon_box(x0,z0,x1,z1)
        for h in holes:wall=wall.difference(Polygon(h))
        def pt(p,d):
            return (p[0],d,p[1]) if side is None else (side,d+p[0],p[1])
        def rotated_pt(p,d):
            return pt(p,d) if side is None else (side+(d-y),p[0],p[1])
        normal=(0,-1,0) if side is None else ((-1,0,0) if side<0 else (1,0,0))
        for t in triangulate(wall):
            if wall.covers(t):
                coords=list(t.exterior.coords)[:-1]
                face('stone',[rotated_pt(p,y) for p in coords],normal)
                face('stone',[rotated_pt(p,y+depth) for p in reversed(coords)],tuple(-v for v in normal))
        for ring in [wall.exterior,*wall.interiors]:
            for a,b in zip(list(ring.coords),list(ring.coords)[1:]):
                # Inward reveal normal is derived from the ring, not a front normal.
                ax,az=b[0]-a[0],b[1]-a[1]
                n=(az,0,-ax) if side is None else (0,az,-ax)
                if ax*ax+az*az>1e-12:face('stone',[rotated_pt(a,y),rotated_pt(b,y),rotated_pt(b,y+depth),rotated_pt(a,y+depth)],n)
    def opening(cx,spring,width,top,bottom):
        return [(cx-width/2,bottom),(cx+width/2,bottom),*[(p[0],p[2]) for p in reversed(ogive(cx,spring,width,top,0))]]
    def ellipsoid(kind,x,y,z,rx,ry,rz,segments=12,rings=8):
        # Individually shaped relief, not stacked cylindrical statue proxies.
        for i in range(rings):
            a=-math.pi/2+math.pi*(i+.005)/rings;b=-math.pi/2+math.pi*(i+.995)/rings
            for j in range(segments):
                ps=[]
                for latitude,longitude in [(a,j),(a,j+1),(b,j+1),(b,j)]:
                    t=longitude*math.tau/segments;ps.append((x+rx*math.cos(latitude)*math.cos(t),y+ry*math.cos(latitude)*math.sin(t),z+rz*math.sin(latitude)))
                normal=(sum((p[0]-x)/rx**2 for p in ps),sum((p[1]-y)/ry**2 for p in ps),sum((p[2]-z)/rz**2 for p in ps))
                face(kind,ps,normal)
    def figure(x,y,z,h,seed):
        """Inferred relief figure with drapery and arms, no identity claim."""
        ellipsoid('stone',x,y,z+h*.88,h*.09,h*.082,h*.12)
        ellipsoid('stone',x,y,z+h*.56,h*.14,h*.09,h*.25)
        for i in range(7):
            a=(i-3)*.3;xx=x+math.sin(a)*h*.115
            tube('stone',[(x+(xx-x)*1.5,y-h*.055,z+h*.08),(xx,y-h*.07,z+h*.52)],h*(.021+.003*(i%3)),8)
        for side in [-1,1]:
            tube('stone',[(x+side*h*.12,y,z+h*.71),(x+side*h*.2,y-h*.045,z+h*(.5 if seed%2 else .63)),(x+side*h*.08,y-h*.12,z+h*.45)],h*.041,10)
        box('stone',x,y,z,h*.36,h*.22,h*.07)
    from notredame_west import build as build_west, opening_spec, REVISION
    west_details=build_west(face,box,tube,ellipsoid,ogive,opening,pierced_wall)
    # Upper nave / transept details retain the existing IGN volume-part edges.
    side_bays=0;flying_buttresses=0;side_cornices=0
    for part in building['properties'].get('height_parts',[]):
        height=part.get('height_gutter_max_m',part.get('height_m',0))
        # IGN records use gutter_segments_m for roofline heights.
        segments=part.get('gutter_segments_m',[])
        if segments:height=sum(p[2] for line in segments for p in line)/sum(len(line) for line in segments)
        if not 25<height<45:continue
        pg=shape(part['geometry'])
        if pg.geom_type!='Polygon':continue
        ring=list(pg.exterior.coords)
        for a,b in zip(ring,ring[1:]):
            span=math.dist(a,b)
            if span<13:continue
            e=((b[0]-a[0])/span,(b[1]-a[1])/span)
            outward=(e[1],-e[0])
            mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
            if pg.contains(Point(mid[0]+outward[0]*.2,mid[1]+outward[1]*.2)):outward=(-outward[0],-outward[1])
            def local_xy(p):return (-dy*(p[0]-front[0])+dx*(p[1]-front[1]),dx*(p[0]-front[0])+dy*(p[1]-front[1]))
            tangent=(-dy*e[0]+dx*e[1],dx*e[0]+dy*e[1])
            normal=(-dy*outward[0]+dx*outward[1],dx*outward[0]+dy*outward[1])
            n=max(1,int(span/6.2))
            for k in range(n):
                t=(k+.5)/n;p=(a[0]+e[0]*span*t,a[1]+e[1]*span*t);cx,cy=local_xy(p)
                # The west facade and belfry already have dedicated geometry.
                if cy<18:continue
                base=height-13.8;spring=height-5;top=height-1.2;width=min(3.8,span/n*.65)
                def on_wall(u,z,offset=.23):return (cx+tangent[0]*u+normal[0]*offset,cy+tangent[1]*u+normal[1]*offset,z)
                profile=ogive(0,spring,width,top,0)
                face('glass',[on_wall(-width/2,base),on_wall(width/2,base),*[on_wall(q[0],q[2]) for q in reversed(profile)]],(*normal,0))
                tube('stone',[on_wall(q[0],q[2],.43) for q in profile],.16,12)
                for u in [-width/2,0,width/2]:tube('stone',[on_wall(u,base,.43),on_wall(u,spring,.43)],.12,12)
                for z in [base,base+4,base+8]:tube('stone',[on_wall(-width/2,z,.43),on_wall(width/2,z,.43)],.09,10)
                # Deep projecting cornice / dentils at the actual volume gutter,
                # and stepped window hoods. No change to the source wall/roof.
                for z,depth_offset in [(height-.55,.35),(height-.35,.48),(base-.45,.33)]:
                    half=span/n/2
                    face('stone',[on_wall(-half,z,depth_offset),on_wall(half,z,depth_offset),on_wall(half,z+.16,depth_offset),on_wall(-half,z+.16,depth_offset)],(*normal,0))
                    face('stone',[on_wall(-half,z+.16,.05),on_wall(half,z+.16,.05),on_wall(half,z+.16,depth_offset),on_wall(-half,z+.16,depth_offset)],(0,0,1))
                    side_cornices+=1
                for j in range(8):
                    u=(j-3.5)*span/n/8;p0=on_wall(u,height-.9,.36)
                    # Small real volumes catch grazing sunlight under the eave.
                    box('stone',*p0,.19,.19,.28)
                side_bays+=1
                # A flying rib lands on the original mapped building footprint.
                # Skip edges where a foot would intrude onto a real road.
                foot=(p[0]+outward[0]*7,p[1]+outward[1]*7)
                if abs(tangent[1])<.8 or not g.covers(Point(foot)):continue
                bx,by=local_xy(foot);body=on_wall(0,height-4,.5)
                points=[]
                for j in range(25):
                    t=j/24;points.append((bx*(1-t)+body[0]*t,by*(1-t)+body[1]*t,18+(height-22)*(1-(1-t)**.55)))
                stone_rib(points,normal)
                box('stone',bx,by,0,1.8,1.8,1.25)
                box('stone',bx,by,1.25,1.4,1.4,17.35)
                for z in [5,10,15,18.4]:box('stone',bx,by,z,1.65,1.65,.25)
                tube('stone',[(bx,by,18.6),(bx,by,23)],.32,12)
                ellipsoid('stone',bx,by,22.8,.43,.43,.8)
                flying_buttresses+=1
    # Hospital walls in the source scene follow IGN volume parts. Decorating
    # only the OSM outer ring leaves frames buried behind those real volumes.
    # Attach nearby modules to those same visible volume edges instead.
    neighbour_id='osm/relation/2449758';neighbour_windows=0
    neighbour=next((f for f in dataset['layers']['buildings'] if f['properties']['source_id']==neighbour_id),None)
    if neighbour:
        from paris_twin.building_mesh import gutter_at
        from shapely.geometry.polygon import orient
        neighbour_parts=[(shape(p['geometry']),p) for p in neighbour['properties'].get('height_parts',[])]
        for pg,part in neighbour_parts:
            pg=shape(part['geometry'])
            if pg.geom_type!='Polygon':continue
            pg=orient(pg,sign=1)
            for ring in [pg.exterior,*pg.interiors]:
                for a,b in zip(list(ring.coords),list(ring.coords)[1:]):
                    span=math.dist(a,b)
                    if span<9:continue
                    e=((b[0]-a[0])/span,(b[1]-a[1])/span);out=(e[1],-e[0])
                    tangent=(-dy*e[0]+dx*e[1],dx*e[0]+dy*e[1]);normal=(-dy*out[0]+dx*out[1],dx*out[0]+dy*out[1])
                    count=max(1,int(span/3.1))
                    for column in range(count):
                        t=(column+.5)/count;p=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
                        if math.dist(p,front)>140:continue
                        height=gutter_at(part,p)
                        if not 14<height<32:continue
                        cx,cy=-dy*(p[0]-front[0])+dx*(p[1]-front[1]),dx*(p[0]-front[0])+dy*(p[1]-front[1])
                        base=part.get('ground_ngf_m',terrain.ngf(p))-terrain.origin_ngf-ground
                        def pt(u,d,z):return (cx+tangent[0]*u+normal[0]*d,cy+tangent[1]*u+normal[1]*d,z)
                        def module(kind,u,d,z,w,depth,h):
                            face(kind,[pt(u-w/2,d,z),pt(u+w/2,d,z),pt(u+w/2,d,z+h),pt(u-w/2,d,z+h)],(*normal,0))
                            face(kind,[pt(u-w/2,d-depth,z+h),pt(u+w/2,d-depth,z+h),pt(u+w/2,d,z+h),pt(u-w/2,d,z+h)],(0,0,1))
                            for sign in [-1,1]:
                                face(kind,[pt(u+sign*w/2,d-depth,z),pt(u+sign*w/2,d,z),pt(u+sign*w/2,d,z+h),pt(u+sign*w/2,d-depth,z+h)],(tangent[0]*sign,tangent[1]*sign,0))
                        for row in range(int((height-1)/3.6)):
                            bottom=base+1.15+row*3.6;top=bottom+2.15
                            if top>base+height-.65:continue
                            outside=Point(p[0]+out[0]*.5,p[1]+out[1]*.5)
                            if any(other is not part and poly.covers(outside) and other.get('ground_ngf_m',terrain.origin_ngf)+gutter_at(other,(outside.x,outside.y))-terrain.origin_ngf-ground>=top for poly,other in neighbour_parts):continue
                            face('glass',[pt(-.62,.11,bottom),pt(.62,.11,bottom),pt(.62,.11,top),pt(-.62,.11,top)],(*normal,0))
                            for u in [-.73,.73]:module('stone',u,.28,bottom-.14,.15,.22,2.45)
                            module('stone',0,.29,top,1.62,.22,.18)
                            module('stone',0,.46,bottom-.18,1.68,.42,.18)
                            for u in [-.6,0,.6]:module('wood',u,.15,bottom,.045,.04,2.15)
                            for z in [bottom,top-.65,top]:module('wood',0,.16,z,1.25,.045,.05)
                            if row in [1,3]:module('stone',0,.23,bottom-.52,span/count,.18,.18)
                            neighbour_windows+=1
    materials=dict(stone='/Game/Materials/M_Paris_Limestone',recess='/Game/Materials/M_Paris_Iron',wood='/Game/Materials/M_ParisWood',glass='/Game/Materials/M_Paris_Glass',iron='/Game/Materials/M_Paris_Iron',sculpture='/Game/Materials/M_ParisSculptedStone',stained='/Game/Materials/M_ParisStainedGlass')
    materials['virgin_fallback']=materials['sculpture']
    objects=[]
    for name,mesh in groups.items():
        mesh['color']={'stone':'d2ccbf','recess':'10151a','wood':'4b3020','glass':'18252d','iron':'262c31','sculpture':'dbd4c6','stained':'233943','virgin_fallback':'dbd4c6'}[name]
        signature=hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        objects.append(dict(id=name,asset='/Game/ParisPhotoreal/Architecture/SM_NotreDameWest_'+name+'_'+signature[:12],geometry_sha256=signature,material=materials[name],triangles=len(mesh['indices'])//3,**mesh))
    return dict(format='paris_original_architecture_study_v1',source_id=building['properties']['source_id'],source_url=building['properties']['source_url'],
        detail_revision=REVISION,west_openings=opening_spec(),west_details=west_details,
        detail_camera=dict(position_cm=world((-3,-22,1.7)),target_cm=world((0,-.5,8.0)),focal_length_mm=50),
        door_camera=dict(position_cm=world((16.3,-12,1.7)),target_cm=world((14,.5,3.2)),focal_length_mm=42),
        virgin_camera=dict(position_cm=world((15.6,-12.5,1.7)),target_cm=world((14,-.30,2.45)),focal_length_mm=50),
        architecture_references=['https://www.notredamedeparis.fr/comprendre/architecture/la-facade-occidentale/','https://www.notredamedeparis.fr/comprendre/architecture/le-portail-du-jugement-dernier/','https://www.notredamedeparis.fr/comprendre/architecture/portail-sainte-anne/'],
        dimensions_reference='https://www.notredamedeparis.fr/comprendre/architecture/plans/',
        dimension_facts_m=dict(west_width=43.5,tower_height=69,west_rose_diameter=9.70),
        appearance_provenance='Original inferred architectural study: pierced west facade, deep portals, authored sculptural relief, rose tracery and open belfry; upper nave and nearby hospital window relief. Not a surveyed cathedral model; sculpture, depths and opening placement are approximate. Existing GIS/collision retained.',
        source_ids=[building['properties']['source_id']]+([neighbour_id] if neighbour_windows else []),
        local_frame=dict(front_cm=world((0,0,0)),across=world((1,0,0),True),depth=world((0,1,0),True)),
        belfry_voids=dict(tower_centres=[-15.25,15.25],front_centres=[-17.95,-12.55,12.55,17.95],side_centres=[4.8,10.2],half_width=2.3,bottom=48,spring=58,top=64.7,depth_min=-2,depth_max=16),
        inferred_details=dict(upper_side_bays=side_bays,flying_buttresses=flying_buttresses,neighbour_windows=neighbour_windows,side_cornice_sections=side_cornices,flying_rib_section='rectangular masonry; inferred'),
        door_provenance='Original inferred plank joinery, flat forged scrollwork and rivets; reference-informed medieval hinge style, not a traced or measured penture pattern. CC0 photographic wood is an appearance proxy, not cathedral timber.',
        near_sculpture_provenance='Original inferred continuous stone figures: analytic facial relief, draped robes, swept sleeves and carved hands with geometric vertex normals. No surveyed shape, actual saint identity or historical iconography claim; jamb spacing, width and depth corrected to avoid occlusion; central anchors and GIS collision retained.',
        anchor_wgs84=list(geo.inverse.transform(*front)),origin_wgs84=config['origin_wgs84'],origin_elevation_ngf_m=terrain.origin_ngf,
        objects=objects)


if __name__=='__main__':
    output=ROOT/'unreal/AIWorld/Content/Data/paris-photo-architecture-source.json'
    data=generate();output.write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(meshes=len(data['objects']),triangles=sum(m['triangles'] for m in data['objects']),anchor=data['anchor_wgs84'])))
