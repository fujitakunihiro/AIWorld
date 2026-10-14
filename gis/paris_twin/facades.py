"""Inferred residential facade modules, spatially batched with original IDs.

No landmark-specific design or L3/L4 accuracy is claimed by these modules.
"""
import math
from collections import defaultdict
from shapely.geometry import Point, Polygon, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.prepared import prep
from .building_mesh import gutter_at, roof_surfaces
from .building_heights import polygon_parts
from .detail_geometry import box


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
    buckets={};sources=defaultdict(set);decorated=set()
    counts=dict(windows=0,entrances=0,balconies=0,cornices=0,dormers=0,party_wall_columns_omitted=0)
    occupied=prep(unary_union([shape(f['geometry']) for f in buildings]))
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
        iron=bucket(cell,'facade_iron');wood=bucket(cell,'facade_wood');roof_trim=bucket(cell,'facade_roof')
        entrance_candidates=[];dormer_surfaces={}
        for polygon in polygon_parts(foot):
            polygon=orient(polygon,sign=1)
            for ring_index,ring in enumerate([polygon.exterior,*polygon.interiors]):
                coords=list(ring.coords)
                for a,b in zip(coords,coords[1:]):
                    length=math.dist(a,b)
                    if length<3:continue
                    dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
                    outward=(dy,-dx);count=max(1,math.floor(length/2.65))
                    visible=[]
                    for column in range(count):
                        along=(column+.5)*length/count
                        cx,cy=a[0]+dx*along,a[1]+dy*along
                        # No decoration on party walls. Courtyards remain exposed.
                        if occupied.covers(Point(cx+outward[0]*.32,cy+outward[1]*.32)):
                            counts['party_wall_columns_omitted']+=1;continue
                        point=Point(cx,cy)
                        part=min(parts,key=lambda pair:pair[0].distance(point))[1]
                        height=gutter_at(part,(cx,cy))
                        if height<5 or height>35:continue
                        base=part.get('ground_ngf_m',terrain.ngf((cx,cy)))-terrain.origin_ngf
                        # Extend no facade below the neighbouring terrain.
                        floor=max(base,terrain.local((cx,cy)))
                        visible.append((cx,cy,base+height,floor))
                        rows=min(10,math.floor((base+height-floor-1.8)/3.2))
                        if ring_index==0 and rows>=2:
                            entrance_candidates.append((length,(cx,cy),(dx,dy),outward,floor,column,count))
                        for row in range(rows):
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
                            # Second-floor and upper-floor wrought-iron balconies.
                            if row in {1,rows-1} and rows>=3 and ring_index==0 and length/count>2.35:
                                slab=bottom-.2
                                box(trim,(cx,cy),(dx,dy),outward,1.7,.58,slab-.12,slab,.31)
                                for z in [slab+.18,slab+.98]:
                                    quad(iron,.825,z,z+.045,.58)
                                for side in [-1,1]:
                                    at=(cx+dx*side*.8,cy+dy*side*.8)
                                    near=(at[0]+outward[0]*.04,at[1]+outward[1]*.04)
                                    far=(at[0]+outward[0]*.58,at[1]+outward[1]*.58)
                                    iron.face([iron.vertex(near,slab+.98),iron.vertex(far,slab+.98),iron.vertex(far,slab+1.025),iron.vertex(near,slab+1.025)],(dx,-dy,0))
                                for k in range(7):
                                    # Two-sided thin profiles keep distant ironwork
                                    # legible without twelve triangles per tiny bar.
                                    centre=cx+dx*(k-3)*.255,cy+dy*(k-3)*.255
                                    left=(centre[0]-dx*.014+outward[0]*.58,centre[1]-dy*.014+outward[1]*.58)
                                    right=(centre[0]+dx*.014+outward[0]*.58,centre[1]+dy*.014+outward[1]*.58)
                                    iron.face([iron.vertex(left,slab+.05),iron.vertex(right,slab+.05),iron.vertex(right,slab+1.),iron.vertex(left,slab+1.)],(outward[0],-outward[1],0))
                                counts['balconies']+=1
                            counts['windows']+=1;decorated.add(props['source_id']);sources[cell].add(props['source_id'])
                        # A small roof window on eligible mansards, safely inside
                        # the source polygon. Both location and shape are inferred.
                        if ring_index==0 and column%3==1 and part['roof']['form']=='mansard' and part['roof']['rise_m']>=2:
                            inset=(cx-outward[0]*.9,cy-outward[1]*.9)
                            corners=[(inset[0]+dx*s-outward[0]*d,inset[1]+dy*s-outward[1]*d) for s,d in [(-.65,-.1),(.65,-.1),(.65,1.2),(-.65,1.2)]]
                            pg=shape(part['geometry'])
                            if pg.covers(Polygon(corners)):
                                key=id(part)
                                if key not in dormer_surfaces:dormer_surfaces[key]=list(roof_surfaces(pg,part['roof']))
                                rise=next((fn(inset) for surface,fn in dormer_surfaces[key] if surface.covers(Point(inset))),0.)
                                low=base+gutter_at(part,inset)+rise+.02
                                if low+1.25<=base+height+part['roof']['rise_m']+.6:
                                    box(trim,inset,(dx,dy),outward,1.16,1.2,low,low+1.24,-.52)
                                    box(glass,inset,(dx,dy),outward,.78,.035,low+.14,low+1.08,.095)
                                    box(roof_trim,inset,(dx,dy),outward,1.38,1.45,low+1.24,low+1.36,-.48)
                                    counts['dormers']+=1
                    # Cornices follow each exposed span rather than crossing a
                    # neighbouring building or ignoring the local gutter slope.
                    for cx,cy,eave,floor in visible:
                        width=min(length/count,3.2)
                        box(trim,(cx,cy),(dx,dy),outward,width,.32,eave-.20,eave+.02,.08)
                        box(trim,(cx,cy),(dx,dy),outward,width,.2,floor+3.08,min(floor+3.23,eave-.3),.05)
                        counts['cornices']+=1
        if entrance_candidates:
            # Pick the central column of the longest exposed exterior edge.
            _,centre,along,outward,floor,_,_=max(entrance_candidates,key=lambda c:(c[0],-abs(c[5]-(c[6]-1)/2)))
            box(trim,centre,along,outward,1.65,.26,floor,floor+2.85,.12)
            box(wood,centre,along,outward,1.3,.055,floor+.02,floor+2.6,.28)
            for side in [-1,1]:
                c=(centre[0]+along[0]*side*.3,centre[1]+along[1]*side*.3)
                box(trim,c,along,outward,.025,.03,floor+.12,floor+2.45,.32)
            counts['entrances']+=1
    objects=[]
    for key,mesh in sorted(buckets.items()):
        if not mesh.positions:continue
        x,y,kind=key
        colors=dict(facade_trim='#d7ccb5',facade_glass='#283d47',facade_iron='#303a39',facade_wood='#514236',facade_roof='#71818c')
        objects.append(mesh.item(f'{kind}-cell/{x}/{y}',kind,colors[kind],
             dict(source_ids=sorted(sources[(x,y)]),facade_source='procedural:inferred windows, entrances, balconies, cornices and dormers; not photographed facades',
                  placement_source='actual OSM exterior/courtyard edges + inferred 3.2m floor spacing',
                  reproduction_level='L1',render_distance_m=180 if kind in ['facade_iron','facade_wood'] else 300)))
    return objects,dict(**counts,decorated_buildings=len(decorated),
                         facade_source='inferred modules; churches/monuments excluded; overall fidelity remains L1')
