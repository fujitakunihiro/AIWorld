"""Variable-height gutter walls and explicitly procedural roof profiles."""
import math
from collections import defaultdict
from shapely.geometry import LineString,Point,shape
from shapely.ops import split
from shapely.geometry.polygon import orient
from .building_heights import polygon_parts


def gutter_at(part,point):
    best=float('inf');height=part['height_gutter_m']
    for a,b in part.get('gutter_segments_m',[]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
        t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length)) if length else 0
        distance=(point[0]-a[0]-t*dx)**2+(point[1]-a[1]-t*dy)**2
        if distance<best:best=distance;height=a[2]+(b[2]-a[2])*t
    return max(.5,min(part['height_gutter_m'],height))


def variable_walls(mesh,geometry,part,base=0,terrain=None):
    from shapely.geometry.polygon import orient
    for p in polygon_parts(geometry):
        for ring in [orient(p,sign=1).exterior,*orient(p,sign=1).interiors]:
            for a,b in zip(list(ring.coords),list(ring.coords)[1:]):
                dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                if length<.001:continue
                ba=min(base,terrain.local(a)-.2) if terrain else base
                bb=min(base,terrain.local(b)-.2) if terrain else base
                mesh.face([mesh.vertex(a,ba+.02),mesh.vertex(b,bb+.02),mesh.vertex(b,base+gutter_at(part,b)+.02),mesh.vertex(a,base+gutter_at(part,a)+.02)],(dy/length,dx/length,0))


def roof_surfaces(geometry,roof):
    for polygon in polygon_parts(geometry):
        if roof['form']=='flat' or roof['rise_m']==0:
            yield polygon,lambda xy:0.
            continue
        rect=list(polygon.minimum_rotated_rectangle.exterior.coords)
        edges=[(math.dist(a,b),a,b) for a,b in zip(rect,rect[1:])]
        length,a,b=max(edges,key=lambda e:e[0]);dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
        nx,ny=-dy,dx;centre=polygon.minimum_rotated_rectangle.centroid
        half=min(e[0] for e in edges)/2
        if roof['form']=='pyramidal':
            pieces=[polygon]
            for corner in rect[:2]:
                vx,vy=corner[0]-centre.x,corner[1]-centre.y
                cutter=LineString([(centre.x-vx*3,centre.y-vy*3),(centre.x+vx*3,centre.y+vy*3)])
                pieces=[piece for current in pieces for piece in split(current,cutter).geoms]
            def rise(xy,cx=centre.x,cy=centre.y,dx=dx,dy=dy,nx=nx,ny=ny,half=half,along=length/2,height=roof['rise_m']):
                x,y=xy[0]-cx,xy[1]-cy
                return height*max(0,1-max(abs(x*nx+y*ny)/max(.001,half),abs(x*dx+y*dy)/max(.001,along)))
            for piece in pieces:yield piece,rise
        elif roof['form']=='gabled':
            cutter=LineString([(centre.x-dx*length*2,centre.y-dy*length*2),(centre.x+dx*length*2,centre.y+dy*length*2)])
            for g in split(polygon,cutter).geoms:
                def rise(xy,cx=centre.x,cy=centre.y,nx=nx,ny=ny,half=half,height=roof['rise_m']):
                    return height*max(0,1-abs((xy[0]-cx)*nx+(xy[1]-cy)*ny)/max(.001,half))
                yield g,rise
        else:
            inset_distance=max(.15,min(2.,half*.55))
            inset=polygon.buffer(-inset_distance,join_style='mitre')
            if inset.is_empty:
                yield polygon,lambda xy:0.
                continue
            rim=polygon.difference(inset)
            def rise(xy,boundary=polygon.boundary,width=inset_distance,height=roof['rise_m'],form=roof['form']):
                t=min(1,boundary.distance(Point(xy))/width)
                return height*(t if form!='mansard' else min(1,t/.7)*.85+max(0,t-.7)/.3*.15)
            yield rim,rise
            # Separate inset triangles preserve the ridge break rather than smoothing across it.
            yield inset,lambda xy,height=roof['rise_m']:height


def generate_buildings(geo,buildings,Mesh,triangulate,terrain=None):
    bodies=[];buckets={};sources=defaultdict(set)
    for feature in buildings:
        props=feature['properties'];body=Mesh(geo);root_id=props['source_id']
        for part in props['height_parts']:
            g=shape(part['geometry']);point=g.representative_point()
            base=(part.get('ground_ngf_m',terrain.ngf((point.x,point.y)))-terrain.origin_ngf) if terrain else 0.
            variable_walls(body,g,part,base,terrain)
            point=g.representative_point();cell=(math.floor((point.x-geo.origin[0])/100),math.floor((point.y-geo.origin[1])/100))
            tagged=props['tags'].get('roof:material')
            material='zinc' if tagged in ['metal','zinc','steel'] or (not tagged and part['roof']['form'] in ['mansard','flat']) else 'slate'
            key=(*cell,material)
            if key not in buckets:buckets[key]=Mesh(geo);buckets[key].level_colors=[]
            roof=buckets[key];sources[key].add(root_id)
            for surface,extra in roof_surfaces(g,part['roof']):
                if part['roof']['form'] in ['gabled','pyramidal']:
                    boundary=g.boundary.buffer(.00001)
                    for polygon in polygon_parts(surface):
                        polygon=orient(polygon,sign=1)
                        for ring in [polygon.exterior,*polygon.interiors]:
                            for a,b in zip(list(ring.coords),list(ring.coords)[1:]):
                                ra,rb=extra(a),extra(b)
                                if max(ra,rb)<.001 or not boundary.covers(LineString([a,b])):continue
                                dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                                points=[body.vertex(a,base+gutter_at(part,a)+.02),body.vertex(b,base+gutter_at(part,b)+.02),body.vertex(b,base+gutter_at(part,b)+rb+.02),body.vertex(a,base+gutter_at(part,a)+ra+.02)]
                                if ra<.001:points.pop(3)
                                elif rb<.001:points.pop(2)
                                body.face(points,(dy/length,dx/length,0))
                for triangle in triangulate(surface):
                    xy=list(orient(triangle,sign=1).exterior.coords)[:3]
                    vertices=[roof.vertex(p,base+gutter_at(part,p)+extra(p)+.02) for p in xy]
                    u=[vertices[1][i]-vertices[0][i] for i in range(3)];v=[vertices[2][i]-vertices[0][i] for i in range(3)]
                    normal=[v[1]*u[2]-v[2]*u[1],v[2]*u[0]-v[0]*u[2],v[0]*u[1]-v[1]*u[0]]
                    size=math.sqrt(sum(n*n for n in normal));normal=[n/max(size,1e-9) for n in normal]
                    if normal[2]<0:normal=[-n for n in normal]
                    roof.face(vertices,normal)
                    roof.level_colors.extend(['#4eae94' if props['reproduction_level_body']=='L2' else '#ef9c42']*3)
        bodies.append(body.item(root_id,'building','#d0c3a7',props))
    roofs=[]
    for cell,mesh in sorted(buckets.items()):
        item=mesh.item(f'roof-cell/{cell[0]}/{cell[1]}/{cell[2]}','roof','#7c8790' if cell[2]=='zinc' else '#596679',{'source_ids':sorted(sources[cell]),'roof_material':cell[2],
             'roof_material_source':'OSM roof:material when tagged; inferred zinc for untagged mansard/flat roofs, slate otherwise; not an observed facade',
             'roof_shape_source':'OSM declared or procedural; not a scanned roof', 'gutter_height_source':'IGN BD TOPO where spatially matched; labelled estimates otherwise'})
        item['level_colors']=mesh.level_colors;roofs.append(item)
    return bodies+roofs
