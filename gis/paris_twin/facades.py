"""Inferred residential facade modules, spatially batched with original IDs.

No landmark-specific design or L3/L4 accuracy is claimed by these modules.
"""
import math
from collections import defaultdict
from shapely.geometry import Point, shape
from shapely.geometry.polygon import orient
from .building_mesh import gutter_at
from .building_heights import polygon_parts


def batch_bodies(objects, geo, Mesh):
    buckets={}; sources=defaultdict(set)
    for obj in objects:
        if obj['kind']!='building':continue
        props=obj['properties'];points=obj['positions_cm']
        # Keep the complete building together; cells are a rendering partition.
        x,y=props['wgs84_centre'];e,n=geo.forward.transform(x,y)
        cell=(math.floor((e-geo.origin[0])/100),math.floor((n-geo.origin[1])/100))
        if cell not in buckets:buckets[cell]=Mesh(geo);buckets[cell].ranges=[];buckets[cell].colors=[]
        mesh=buckets[cell];start=len(mesh.positions);index_offset=start
        mesh.positions.extend(points);mesh.normals.extend(obj['normals'])
        mesh.indices.extend(i+index_offset for i in obj['indices'])
        palette=['#d3c7ad','#cbbca1','#d7ccb6','#c5b69a']
        tint=palette[sum(props['source_id'].encode())%len(palette)]
        mesh.colors.extend([tint]*len(points))
        mesh.ranges.append(dict(source_id=props['source_id'],start=start,count=len(points),
                                body_level=props['reproduction_level_body'],color=tint))
        sources[cell].add(props['source_id'])
    result=[o for o in objects if o['kind']!='building']
    for cell,mesh in sorted(buckets.items()):
        item=mesh.item(f'building-cell/{cell[0]}/{cell[1]}','building','#d0c3a7',
                      dict(source_ids=sorted(sources[cell]),batching='100m cells; original polygons remain independently selectable'))
        item['appearance_ranges']=mesh.ranges;item['vertex_colors']=mesh.colors
        result.append(item)
    return result


def generate_facades(geo, buildings, terrain, Mesh):
    buckets={};sources=defaultdict(set);windows=0;decorated=set()
    def bucket(cell,kind):
        key=(*cell,kind)
        if key not in buckets:buckets[key]=Mesh(geo)
        return buckets[key]
    for feature in buildings:
        props=feature['properties'];tags=props['tags']
        # Churches and singular monuments need documented custom facades.
        if tags.get('building') in ['church','cathedral','chapel','tower','public'] or tags.get('historic') in ['castle','monument']:
            continue
        foot=shape(feature['geometry']);parts=[(shape(p['geometry']),p) for p in props['height_parts']]
        center=foot.representative_point();cell=(math.floor((center.x-geo.origin[0])/100),math.floor((center.y-geo.origin[1])/100))
        glass=bucket(cell,'facade_glass');trim=bucket(cell,'facade_trim')
        for polygon in polygon_parts(foot):
            polygon=orient(polygon,sign=1)
            for ring in [polygon.exterior,*polygon.interiors]:
                coords=list(ring.coords)
                for a,b in zip(coords,coords[1:]):
                    length=math.dist(a,b)
                    if length<3:continue
                    dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
                    outward=(dy,-dx);count=max(1,math.floor(length/2.65))
                    for column in range(count):
                        along=(column+.5)*length/count
                        cx,cy=a[0]+dx*along,a[1]+dy*along
                        point=Point(cx,cy)
                        part=min(parts,key=lambda pair:pair[0].distance(point))[1]
                        height=gutter_at(part,(cx,cy))
                        if height<5 or height>35:continue
                        base=part.get('ground_ngf_m',terrain.ngf((cx,cy)))-terrain.origin_ngf
                        # Extend no facade below the neighbouring terrain.
                        floor=max(base,terrain.local((cx,cy)))
                        for row in range(min(10,math.floor((base+height-floor-1.8)/3.2))):
                            bottom=floor+1.1+row*3.2;top=bottom+1.65
                            if top>base+height-.5:continue
                            def quad(mesh,half,z0,z1,offset):
                                left=(cx-dx*half+outward[0]*offset,cy-dy*half+outward[1]*offset)
                                right=(cx+dx*half+outward[0]*offset,cy+dy*half+outward[1]*offset)
                                mesh.face([mesh.vertex(left,z0),mesh.vertex(right,z0),mesh.vertex(right,z1),mesh.vertex(left,z1)],(outward[0],-outward[1],0))
                            quad(trim,.56,bottom-.09,top+.09,.065)
                            quad(glass,.45,bottom,top,.085)
                            # Slim central stone mullion, with a projecting sill.
                            quad(trim,.027,bottom,top,.10)
                            left=(cx-dx*.61+outward[0]*.065,cy-dy*.61+outward[1]*.065)
                            right=(cx+dx*.61+outward[0]*.065,cy+dy*.61+outward[1]*.065)
                            farleft=(left[0]+outward[0]*.2,left[1]+outward[1]*.2)
                            farright=(right[0]+outward[0]*.2,right[1]+outward[1]*.2)
                            trim.face([trim.vertex(left,bottom-.08),trim.vertex(farleft,bottom-.08),trim.vertex(farright,bottom-.08),trim.vertex(right,bottom-.08)],(0,0,1))
                            windows+=1;decorated.add(props['source_id']);sources[cell].add(props['source_id'])
    objects=[]
    for key,mesh in sorted(buckets.items()):
        if not mesh.positions:continue
        x,y,kind=key
        objects.append(mesh.item(f'{kind}-cell/{x}/{y}',kind,'#d7ccb5' if kind=='facade_trim' else '#283d47',
             dict(source_ids=sorted(sources[(x,y)]),facade_source='procedural:inferred limestone window modules; not photographed facades',
                  placement_source='actual OSM exterior/courtyard edges + inferred 3.2m floor spacing',
                  reproduction_level='L1',render_distance_m=300)))
    return objects,dict(windows=windows,decorated_buildings=len(decorated),
                         facade_source='inferred modules; churches/monuments excluded; overall fidelity remains L1')
