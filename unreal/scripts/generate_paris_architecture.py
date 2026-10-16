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
    groups={name:dict(positions_cm=[],normals=[],indices=[]) for name in ['stone','recess','wood','glass','iron']}
    def face(kind,points,n):
        out=groups[kind];start=len(out['positions_cm']);points=[world(p) for p in points];normal=world(n,True)
        magnitude=math.sqrt(sum(v*v for v in normal));normal=[v/magnitude for v in normal]
        u=[points[1][i]-points[0][i] for i in range(3)];v=[points[2][i]-points[0][i] for i in range(3)]
        cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        reverse=sum(cross[i]*normal[i] for i in range(3))>0
        out['positions_cm'].extend(points);out['normals'].extend([normal]*len(points))
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
    # The authored facade is a removable visual layer, not new GIS volume.
    box('stone',0,-.55,0,43.5,.55,45)
    # The belfry is an open shell. The source display material makes the same
    # voids in the original simplified volume; its collider remains unchanged.
    for x in [-15.25,15.25]:
        holes=[opening(cx,58,4.6,64.7,48) for cx in [x-2.7,x+2.7]]
        pierced_wall(x-6.5,x+6.5,45,69,-.76,1.0,holes)
        for sx in [x-6.5,x+6.5]:
            sideholes=[opening(cy,58,4.6,64.7,48) for cy in [4.8,10.2]]
            pierced_wall(.7,15,45,69,0,.7,sideholes,side=sx)
            for cy in [4.8,10.2]:
                points=ogive(cy,58,4.6,64.7,0)
                tube('stone',[(sx+(-.14 if sx<0 else .14),p[0],p[2]) for p in points],.2,12)
                for d in [-2.3,2.3]:tube('stone',[(sx,cy+d,48),(sx,cy+d,58)],.19,12)
        box('stone',x,7.3,68.5,13.4,15.8,.45)
    for x in [-21.7,-8.5,8.5,21.7]:
        box('stone',x,-1.05,0,1.2,1.6,45)
        for z in [3,9,16,21,33,39,44]:box('stone',x,-1.30,z,1.65,1.9,.35)
        if abs(x)>10:box('stone',x,-.9,45,.9,1.2,24)
    # Three recessed portals with nested rounded archivolts and jamb columns.
    for x,w in [(-14,8.1),(0,9.5),(14,8.1)]:
        arch('recess',x,5.5,w,13,-.89)
        # Tympana are carved stone, rather than a ten-metre black opening.
        arch('stone',x,5.5,w*.98,12.9,-1.015,bottom=4.95)
        for z in [5.0,7.45,9.4]:box('stone',x,-1.10,z,w*.97,.3,.18)
        for row,(z,n,h) in enumerate([(5.25,9,1.75),(7.7,7,1.5),(9.65,3,1.55)]):
            for i in range(n):figure(x+(i-(n-1)/2)*w*.085,-1.16,z,h,i+row)
        for side in [-1,1]:
            for k in range(4):
                box('wood',x+side*(.15+(k+.5)*w*.108),-1.035,.12,w*.104,.08,4.7)
        for side in [-1,1]:
            box('wood',x+side*w*.23,-.94,0,w*.43,.16,4.85)
            for z in [.6,2.2,4.1]:box('iron',x+side*w*.23,-1.04,z,w*.4,.05,.12)
        for i in range(6):
            k=i*.27;tube('stone',ogive(x,5.5,w+k*2,13+k,-1.05-i*.13),.12,10)
            for side in [-1,1]:
                tube('stone',[(x+side*(w/2+k),-1.05-i*.13,.2),(x+side*(w/2+k),-1.05-i*.13,5.5)],.13,10)
                box('stone',x+side*(w/2+k),-1.07-i*.13,5.25,.4,.4,.4)
        # Inferred sculptural relief silhouettes, deliberately not named statues.
        for side in [-1,1]:
            for k in range(3):
                sx=x+side*(w/2+.32+k*.4);tube('stone',[(sx,-1.1,1),(sx,-1.1,3.6)],.16,8)
                tube('stone',[(sx,-1.1,3.6),(sx,-1.1,4.05)],.22,10)
    # Gallery of 28 generic kings: rhythm and volume only, no surveyed sculpture.
    for z,w in [(17,44.6),(22.1,44.6),(34.5,44),(45,44)]:
        for step in range(3):box('stone',0,-1.0-step*.15,z+step*.18,w+step*.2,1.4+step*.2,.18)
    for i in range(28):
        x=(i-13.5)*1.45
        arch('recess',x,20.2,1.15,21.3,-.89,bottom=17.6)
        for side in [-1,1]:tube('stone',[(x+side*.65,-1.25,17.6),(x+side*.65,-1.25,20.7)],.09)
        tube('stone',ogive(x,20.2,1.3,21.45,-1.25),.1)
        figure(x,-1.20,17.85,2.35,i)
    # Official western rose diameter 9.70m; radial tracery remains inferred.
    rose_z=28.1;rose_r=4.85
    face('glass',list(reversed(circle(0,rose_z,rose_r,-.9)[:-1])),(0,-1,0))
    for r,thickness in [(4.9,.2),(5.15,.15),(5.4,.14),(.65,.14),(2.45,.11)]:tube('stone',circle(0,rose_z,r,-1.2),thickness,10)
    for i in range(16):
        angle=i*math.tau/16
        tube('stone',[(.65*math.cos(angle),-1.2,rose_z+.65*math.sin(angle)),(4.8*math.cos(angle),-1.2,rose_z+4.8*math.sin(angle))],.085)
        tube('stone',circle(3.65*math.cos(angle),rose_z+3.65*math.sin(angle),.75,-1.2,32),.055)
    # Paired pointed windows flank the rose and tower belfries.
    for x in [-15.2,15.2]:
        for cx in [x-2.7,x+2.7]:
            for spring,top,w in [(28,32,3.3),(58,64.7,4.6)]:
                if spring==28:arch('recess',cx,spring,w,top,-.91,bottom=23.5)
                tube('stone',ogive(cx,spring,w,top,-1.16),.2,10)
                for side in [-1,1]:tube('stone',[(cx+side*w/2,-1.16,spring-10),(cx+side*w/2,-1.16,spring)],.18,10)
                tube('stone',[(cx,-1.19,spring-10),(cx,-1.19,top-1.3)],.1)
                if spring==58:
                    # Recessed wooden louvres sit inside the stone reveal.
                    for z in range(49,58):box('wood',cx,.1,z,w*.94,.35,.12)
                else:
                    for z in range(int(spring-9),int(spring)):box('iron',cx,-1.0,z,w*.95,.1,.10)
        for z in [46,65.5,68.6]:box('stone',x,-1.0,z,13.8,1.5,.42)
    # Open colonnade and thin balustrades create depth instead of painted windows.
    box('recess',0,-.88,36,41.8,.05,7.5)
    for i in range(35):
        x=(i-17)*1.20
        tube('stone',[(x,-1.25,36),(x,-1.25,42.5)],.12)
        tube('stone',ogive(x+.6,42.1,1.15,44,-1.25),.1)
    for z in [35.1,45.6,69.1]:
        ranges=[(-21.7,21.7)] if z<46 else [(-21.7,-8.7),(8.7,21.7)]
        for lo,hi in ranges:
            tube('stone',[(lo,-1.5,z+1.1),(hi,-1.5,z+1.1)],.14)
            for i in range(int((hi-lo)/.6)+1):
                x=lo+i*.6;tube('stone',[(x,-1.5,z),(x,-1.5,z+1.1)],.075)
    # Continuous stone courses and buttress caps break the unnaturally plain
    # silhouette; small joints are handled by the photographic material.
    for x in [-21.7,-8.5,8.5,21.7]:
        for z in [22.5,34.7,45.4,66.2]:
            for step in range(3):box('stone',x,-1.55,z+step*.14,1.75-step*.12,1.5-step*.12,.18)
        for z in [24,29,37,41,49,54,59,64]:
            box('stone',x,-1.9,z,1.08,.12,.09)
    # Upper nave / transept details follow the existing IGN volume-part edges.
    # These shapes are inferred decoration, not newly measured facade data.
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
    materials=dict(stone='/Game/Materials/M_Paris_Limestone',recess='/Game/Materials/M_Paris_Iron',wood='/Game/Materials/M_ParisWood',glass='/Game/Materials/M_Paris_Glass',iron='/Game/Materials/M_Paris_Iron')
    objects=[]
    for name,mesh in groups.items():
        mesh['color']={'stone':'d2ccbf','recess':'10151a','wood':'4b3020','glass':'18252d','iron':'262c31'}[name]
        signature=hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        objects.append(dict(id=name,asset='/Game/ParisPhotoreal/Architecture/SM_NotreDameWest_'+name+'_'+signature[:12],geometry_sha256=signature,material=materials[name],triangles=len(mesh['indices'])//3,**mesh))
    return dict(format='paris_original_architecture_study_v1',source_id=building['properties']['source_id'],source_url=building['properties']['source_url'],
        dimensions_reference='https://www.notredamedeparis.fr/comprendre/architecture/plans/',
        dimension_facts_m=dict(west_width=43.5,tower_height=69,west_rose_diameter=9.70),
        appearance_provenance='Original inferred architectural study: west facade, open belfry, upper nave and nearby hospital window relief. Not a surveyed cathedral model; sculpture, depths and opening placement are approximate. Existing GIS/collision retained.',
        source_ids=[building['properties']['source_id']]+([neighbour_id] if neighbour_windows else []),
        local_frame=dict(front_cm=world((0,0,0)),across=world((1,0,0),True),depth=world((0,1,0),True)),
        belfry_voids=dict(tower_centres=[-15.25,15.25],front_centres=[-17.95,-12.55,12.55,17.95],side_centres=[4.8,10.2],half_width=2.3,bottom=48,spring=58,top=64.7,depth_min=-2,depth_max=16),
        inferred_details=dict(upper_side_bays=side_bays,flying_buttresses=flying_buttresses,neighbour_windows=neighbour_windows,side_cornice_sections=side_cornices,flying_rib_section='rectangular masonry; inferred'),
        anchor_wgs84=list(geo.inverse.transform(*front)),origin_wgs84=config['origin_wgs84'],origin_elevation_ngf_m=terrain.origin_ngf,
        objects=objects)


if __name__=='__main__':
    output=ROOT/'unreal/AIWorld/Content/Data/paris-photo-architecture-source.json'
    data=generate();output.write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(meshes=len(data['objects']),triangles=sum(m['triangles'] for m in data['objects']),anchor=data['anchor_wgs84'])))
