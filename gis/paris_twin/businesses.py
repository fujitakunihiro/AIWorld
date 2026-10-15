"""Archived OSM businesses, with explicitly inferred storefronts and terraces."""
import math
from collections import Counter
from shapely.geometry import Point,Polygon,mapping,shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .street_furniture import source_nodes
from .pedestrians import seed
from .detail_geometry import box,cylinder,tube


def mapped_businesses(raw,manifest,geo):
    nodes,snapshot=source_nodes(raw,manifest);result=[]
    for node in sorted(nodes,key=lambda n:n['id']):
        tags=node['tags'];amenity=tags.get('amenity');shop=tags.get('shop')
        if amenity not in ['cafe','restaurant','bar','fast_food'] and (not shop or shop in ['vacant','no','yes']):continue
        point=Point(geo.forward.transform(node['lon'],node['lat']))
        if not geo.extent.covers(point):continue
        identifier=f"osm/node/{node['id']}"
        result.append(dict(geometry=mapping(point),properties=dict(source_id=identifier,source='OpenStreetMap',
            source_snapshot=snapshot,source_license='ODbL-1.0',source_url=f"https://www.openstreetmap.org/node/{node['id']}",
            wgs84_centre=[node['lon'],node['lat']],name=tags.get('name',''),tags=tags,
            kind=amenity if amenity in ['cafe','restaurant','bar','fast_food'] else 'shop',category=shop or amenity,
            position_source='OSM POI in archived snapshot; not a surveyed entrance or current business verification',
            outdoor_seating_tag=tags.get('outdoor_seating'),reproduction_level='L1')))
    return result


def prototypes(geo,Mesh):
    x,y=geo.origin;models={name:Mesh(geo) for name in ['store_glass','store_wood','store_metal','awning_red','awning_green','awning_cream','terrace_wood','terrace_metal']}
    along,out=(1,0),(0,-1)
    for dx in [-1.02,1.02]:box(models['store_glass'],(x+dx,y),along,out,1.05,.1,.28,2.38,.12)
    box(models['store_wood'],(x,y),along,out,.78,.12,.05,2.42,.12)
    # A transom/sign panel is an inferred module, not a copy of a real sign.
    box(models['store_wood'],(x,y),along,out,3.2,.16,2.44,2.75,.12)
    for dx in [-1.59,-.45,.45,1.59]:box(models['store_metal'],(x+dx,y),along,out,.055,.18,.06,2.75,.12)
    for name in ['awning_red','awning_green','awning_cream']:
        m=models[name]
        for a,b,z0,z1 in [(0.05,1.12,2.92,2.63),(1.12,1.14,2.63,2.42)]:
            m.face([m.vertex((x-1.72,y-a),z0),m.vertex((x+1.72,y-a),z0),m.vertex((x+1.72,y-b),z1),m.vertex((x-1.72,y-b),z1)],(0,0,1) if a<1 else (0,1,0))
    cylinder(models['terrace_wood'],(x,y),.37,.7,.76,16)
    cylinder(models['terrace_metal'],(x,y),.045,0,.7,8)
    for sign in [-1,1]:
        cx=x+sign*.72
        box(models['terrace_wood'],(cx,y),along,out,.4,.4,.43,.48)
        for dx in [-.17,.17]:
            for dy in [-.17,.17]:tube(models['terrace_metal'],(cx+dx,y+dy,.02),(cx+dx,y+dy,.45),.018,6)
        for dy in [-.18,.18]:tube(models['terrace_metal'],(cx+sign*.18,y+dy,.43),(cx+sign*.18,y+dy,.91),.018,6)
        tube(models['terrace_metal'],(cx+sign*.18,y-.18,.91),(cx+sign*.18,y+.18,.91),.025,6)
    colors=dict(store_glass='#506e76',store_wood='#3d5149',store_metal='#303e3c',awning_red='#8c3c32',awning_green='#405e50',awning_cream='#c9b68d',terrace_wood='#775c40',terrace_metal='#323e38')
    return [m.item(name,'business_model',colors[name],dict(authored_proxy=True)) for name,m in models.items()]


def rectangle(centre,along,out,width,depth):
    return Polygon([(centre[0]+along[0]*a+out[0]*b,centre[1]+along[1]*a+out[1]*b) for a,b in [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]])


def generate_businesses(geo,features,buildings,terrain,walking,water,road_surface,street_features,sidewalks=None):
    shapes=[shape(f['geometry']) for f in buildings];tree=STRtree(shapes);occupied=unary_union(shapes)
    walking=walking if walking is not None else Polygon();water=water if water is not None else Polygon()
    roads=road_surface if road_surface is not None else Polygon()
    placed=[];skipped=[];obstacles=[];batches={};assigned=[];terraces=[]
    furniture=[]
    for f in street_features:
        p=f['properties'];point=Point(geo.forward.transform(*p['wgs84_centre']))
        furniture.append(point.buffer(1.05 if p['kind'] in ['bench','bicycle_rack'] else .35))
    furniture=unary_union(furniture)
    for feature in sorted(features,key=lambda f:f['properties']['source_id']):
        p=feature['properties'];poi=shape(feature['geometry']);candidates=[]
        for index in sorted(int(i) for i in tree.query(poi.buffer(5))):
            building=buildings[index];tags=building['properties']['tags']
            if building['properties'].get('height_m',15)<3.4:continue
            if tags.get('building') in ['church','cathedral','chapel','tower','public'] or tags.get('historic') in ['castle','monument']:continue
            g=shapes[index]
            if g.distance(poi)>5:continue
            for poly in [g] if g.geom_type=='Polygon' else g.geoms:
                coords=list(orient(poly,sign=1).exterior.coords)
                for a,b in zip(coords,coords[1:]):
                    length=math.dist(a,b)
                    if length<3.8:continue
                    dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length;out=(dy,-dx)
                    t=max(1.85,min(length-1.85,(poi.x-a[0])*dx+(poi.y-a[1])*dy))
                    xy=(a[0]+dx*t,a[1]+dy*t);front=Point(xy[0]+out[0]*.65,xy[1]+out[1]*.65)
                    module=rectangle((xy[0]+out[0]*.6,xy[1]+out[1]*.6),(dx,dy),out,3.5,1.1)
                    if occupied.intersection(module).area>.005 or module.intersection(water).area>.001:continue
                    if poi.distance(Point(xy))>25 or module.intersection(furniture).area>.005:continue
                    if walking.distance(front)>.65 or module.intersection(roads).area>.01:continue
                    if any(Point(xy).distance(other)<3.65 for other in assigned):continue
                    candidates.append((poi.distance(Point(xy)),building['properties']['source_id'],xy,(dx,dy),out))
        if not candidates:
            skipped.append(dict(source_id=p['source_id'],reason='no_free_walk_facing_facade_within_nearby_building'));continue
        distance,bid,xy,along,out=min(candidates,key=lambda c:(c[0],c[1],c[2]));assigned.append(Point(xy))
        z=terrain.local(xy);yaw=round(math.degrees(math.atan2(-along[1],along[0])),3)
        point_cm=[round((xy[0]-geo.origin[0])*100,3),round(-(xy[1]-geo.origin[1])*100,3),round(z*100,3)]
        props={**p,'building_source_id':bid,'facade_position_source':'inferred:nearby exposed facade facing generated walking surface; not a surveyed storefront',
            'facade_distance_from_poi_m':round(distance,3),'appearance_source':'authored generic facade/awning; real design unverified',
            'terrace_placed':False,'terrace_not_placed_reason':'no positive outdoor_seating tag' if p['outdoor_seating_tag']!='yes' else 'insufficient unobstructed walking space; preserve corridor','terrace_position_source':'inferred:generic one-table layout; no surveyed seats or occupancy',
            'facade_yaw_degrees':yaw}
        item=dict(id=p['source_id'],kind='business',point_cm=point_cm,properties=props)
        def instance(name,position):
            batches.setdefault(name,[]).append(dict(source_id=p['source_id'],position_cm=position,yaw_degrees=yaw,scale=[1.,1.,1.]))
        for name in ['store_glass','store_wood','store_metal']:instance(name,point_cm)
        color=['red','green','cream'][seed(p['source_id'])%3];instance('awning_'+color,point_cm)
        # Only an explicit positive tag authorizes an outdoor-seating proxy.
        if p['outdoor_seating_tag']=='yes':
            centre=(xy[0]+out[0]*2.25,xy[1]+out[1]*2.25)
            foot=rectangle(centre,along,out,2.2,1.65)
            # Keep >=1.2m between wall and table footprint. Remaining walking
            # paths are regenerated around these obstacles, never through seats.
            if walking.covers(foot.buffer(.1)) and not foot.intersects(occupied.buffer(.3)) and not foot.intersects(water) and not foot.intersects(roads.buffer(.3)) and not foot.intersects(furniture) and not any(foot.intersects(other.buffer(.35)) for other in obstacles):
                tz=terrain.local(centre)+(.15 if sidewalks is not None and sidewalks.covers(Point(centre)) else .04)
                pos=[round((centre[0]-geo.origin[0])*100,3),round(-(centre[1]-geo.origin[1])*100,3),round(tz*100,3)]
                instance('terrace_wood',pos);instance('terrace_metal',pos)
                props.update(terrace_placed=True,terrace_cm=pos,terrace_not_placed_reason=None)
                obstacles.append(foot);terraces.append(dict(source_id=p['source_id'],geometry=mapping(foot)))
        placed.append(item)
    report=dict(mapped_pois=len(features),storefronts=len(placed),terraces=len(terraces),skipped=skipped,
        policy='POI anchor retained; facade and outdoor seats inferred. No current business, actual sign, entrance or occupancy verification',
        outdoor_seating_policy='Only OSM outdoor_seating=yes; proxy position must fit a clear generated walking area with a 1.2m wall corridor')
    return [dict(model=name,instances=items) for name,items in sorted(batches.items())],placed,obstacles,dict(report=report,terraces=terraces,walking_geometry=mapping(walking),road_geometry=mapping(roads))
