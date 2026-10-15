"""Inferred preview traffic on conservative, independent real-road segments.

Road source identity and driving direction are retained. No junction controller,
observed traffic density, connected city routing, or real vehicle is claimed.
The full 4.2 x 1.8m car lies inside a conservative 2.4m swept-radius clearance.
"""
import math
from collections import Counter
from shapely.geometry import Point, LineString, mapping, shape
from shapely.ops import unary_union
from shapely.ops import substring
from .pedestrians import line_parts, seed
from .detail_geometry import box, tube

RADIUS=2.4


def speed_limit(tags):
    text=tags.get('maxspeed','').lower().strip()
    try:
        value=float(text.removesuffix('mph').removesuffix('km/h').strip())
        value=value*.44704 if text.endswith('mph') else value/3.6
        return value if math.isfinite(value) and value>0 else None
    except (ValueError,TypeError):return None


def allowed(tags):
    if tags.get('highway') not in ['primary','secondary','tertiary','residential','unclassified','service']:return False
    # Restricted access, shared pedestrian streets and bus-only roads are not
    # treated as public car lanes. Complex conditional restrictions are skipped.
    if any(k.endswith(':conditional') for k in tags):return False
    if tags.get('bus')=='designated' or tags.get('oneway') not in [None,'no','yes','1','true','-1']:return False
    return all(tags.get(k) in [None,'yes','permissive','designated'] for k in ['access','vehicle','motor_vehicle','motorcar'])


def generate_traffic(geo,roads,terrain,water,buildings,road_surface,paths_surface,bridge_decks,street_features,max_agents=40,extra_obstacles=()):
    bridge_surface=unary_union([d.geometry for d in bridge_decks])
    driving=unary_union([g for g in [road_surface,bridge_surface] if g is not None])
    if water is not None:driving=driving.difference(water.difference(bridge_surface))
    # Leave all explicit walking areas and mapped furniture clear, including
    # crossings: preview cars stop/recycle before the gap rather than inventing
    # signal priority over a pedestrian crossing.
    obstacles=[buildings.buffer(.35),*extra_obstacles]
    if paths_surface is not None:obstacles.append(paths_surface)
    for f in street_features:
        p=f['properties'];point=Point(geo.forward.transform(*p['wgs84_centre']))
        obstacles.append(point.buffer(1. if p['kind'] in ['bench','bicycle_rack'] else .3))
    driving=driving.difference(unary_union(obstacles))
    safe=driving.buffer(-RADIUS)
    routes=[];excluded=Counter()
    for feature in sorted(roads,key=lambda f:f['properties']['source_id']):
        p=feature['properties'];tags=p['tags']
        if p['tunnel'] or p['layer']<0 or not allowed(tags):excluded['restricted_or_non_car_road']+=1;continue
        for part_index,line in enumerate(sorted(line_parts(shape(feature['geometry'])),key=lambda g:g.normalize().wkb_hex)):
            one=tags.get('oneway') in ['yes','1','true','-1'] or (tags.get('junction')=='roundabout' and tags.get('oneway')!='no')
            if tags.get('oneway')=='-1':line=line.reverse()
            # GEOS preserves offset direction. Negative offset is the right of
            # the directed line in projected east/north metres, before UE Y flip.
            candidates=[('oneway',line)] if one else [('forward_right',line.offset_curve(-min(1.75,p['width_m']/4))),('reverse_right',line.reverse().offset_curve(-min(1.75,p['width_m']/4)))]
            for lane,candidate in candidates:
                # Intersections retain source direction, never sort/reverse
                # coordinates into a canonical direction (would break oneway).
                for index,piece in enumerate(sorted(line_parts(candidate.intersection(safe)),key=lambda g:g.normalize().wkb_hex)):
                    if piece.length<18:continue
                    # Align to candidate direction explicitly after clipping.
                    base=min(line_parts(candidate),key=lambda g:g.distance(piece.interpolate(.5,normalized=True)))
                    if base.project(Point(piece.coords[0]))>base.project(Point(piece.coords[-1])):piece=piece.reverse()
                    piece=substring(piece,1.,piece.length-1.)
                    points=[]
                    for xy in piece.segmentize(.75).coords:
                        point=Point(xy);deck=next((d for d in bridge_decks if d.geometry.covers(point)),None)
                        z=deck.height(xy) if deck else terrain.local(xy)+.035
                        points.append([round((xy[0]-geo.origin[0])*100,3),round(-(xy[1]-geo.origin[1])*100,3),round(z*100,3)])
                    limit=speed_limit(tags)
                    routes.append(dict(id=f"sim/car-route/{p['source_id']}/{part_index}/{lane}/{index}",source_id=p['source_id'],
                        source_url=p['source_url'],source_snapshot=p['source_snapshot'],source_license=p['source_license'],
                        route_source='inferred:road centreline/width and right-hand lane; conservative swept clearance',lane=lane,
                        oneway_tag=tags.get('oneway'),maxspeed_tag=tags.get('maxspeed'),tag_speed_limit_mps=limit,
                        speed_mps=round(min(5.,limit) if limit else 5.,4),speed_source='inferred:5m/s preview capped by numeric OSM maxspeed when present',
                        points_cm=points,length_m=round(piece.length,4),geometry=mapping(piece)))
    routes.sort(key=lambda r:r['id']);agents=[];positions=[]
    for route in sorted(routes,key=lambda r:seed(r['id'])):
        if len(agents)>=max_agents:break
        progress=.2+(seed(route['id'])%600)/1000;point=shape(route['geometry']).interpolate(progress,normalized=True)
        if any(point.distance(p)<6 for p in positions):continue
        agents.append(dict(id=f'sim/car/{len(agents):04d}',route_id=route['id'],progress_m=round(progress*route['length_m'],4),
            variant=seed(route['id'])%3,speed_mps=route['speed_mps'],provenance='inferred:simulated vehicle, not observed traffic'))
        positions.append(point)
    report=dict(routes=len(routes),agents=len(agents),inferred_traffic=True,swept_radius_m=RADIUS,excluded=dict(excluded),
        policy='Independent directed segments; stop for player/people/cars; hidden recycling at segment ends; no junction routing or live signal phases')
    return dict(routes=[{k:v for k,v in r.items() if k!='geometry'} for r in routes],agents=agents,report=report),dict(
        origin_projected_m=list(geo.origin),drivable_geometry=mapping(driving),safe_centres=mapping(safe),routes=routes,report=report)


def validate_traffic(network,source_ids):
    safe=shape(network['safe_centres']).buffer(.001);driving=shape(network['drivable_geometry']).buffer(.002)
    errors=[];ids=set();ox,oy=network['origin_projected_m']
    for r in network['routes']:
        if r['id'] in ids:errors.append('duplicate_car_route')
        ids.add(r['id'])
        if r['source_id'] not in source_ids:errors.append('untraced_car_route')
        if len(r['points_cm'])<2 or any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in r['points_cm']):errors.append('invalid_car_coordinates');continue
        line=LineString([(ox+p[0]/100,oy-p[1]/100) for p in r['points_cm']])
        if not safe.covers(line) or not driving.covers(line.buffer(RADIUS,quad_segs=16)):errors.append('car_swept_footprint_outside_drivable_surface')
        if r['oneway_tag'] in ['yes','1','true','-1'] and r['lane']!='oneway':errors.append('oneway_has_reverse_lane')
        if r['speed_mps']<=0 or r['speed_mps']>5.001 or (r['tag_speed_limit_mps'] is not None and r['speed_mps']>r['tag_speed_limit_mps']+.001):errors.append('car_speed_above_cap')
    return errors


def vehicle_models(geo,Mesh):
    """Original generic 4.2m compact car. No manufacturer/model design used."""
    x,y=geo.origin;result=[];glass=Mesh(geo);rubber=Mesh(geo);metal=Mesh(geo)
    # Chamfered shell and sloped windscreen; units match the swept safety radius.
    def skin(mesh,rings):
        for a,b in zip(rings,rings[1:]):
            for j in range(len(a)):
                ps=[a[j],a[(j+1)%len(a)],b[(j+1)%len(b)],b[j]]
                u=[ps[1][k]-ps[0][k] for k in range(3)];v=[ps[2][k]-ps[0][k] for k in range(3)]
                n=[u[1]*v[2]-u[2]*v[1],-(u[2]*v[0]-u[0]*v[2]),u[0]*v[1]-u[1]*v[0]]
                size=math.sqrt(sum(t*t for t in n));n=[t/max(size,1e-9) for t in n]
                mesh.face([mesh.vertex((x+p[0],y+p[1]),p[2]) for p in ps],n)
    def ring(half_length,half_width,z,chamfer=.18):
        l,w,c=half_length,half_width,chamfer
        return [(-l+c,-w,z),(l-c,-w,z),(l,-w+c,z),(l,w-c,z),(l-c,w,z),(-l+c,w,z),(-l,w-c,z),(-l,-w+c,z)]
    for variant,color in enumerate(['#486879','#8a4941','#c2bdac']):
        body=Mesh(geo);skin(body,[ring(1.97,.76,.28),ring(2.1,.9,.5),ring(1.93,.86,.9),ring(1.85,.78,1.01)])
        # Roof; glass forms the cabin sides, including both sloped screens.
        roof=ring(.85,.67,1.48,.16);base=ring(1.3,.78,.99,.16)
        if variant==0:skin(glass,[base,roof])
        skin(body,[ring(.85,.67,1.48,.16),ring(.78,.6,1.55,.16)])
        top=ring(.78,.6,1.55,.16)
        for a,b in zip(top,top[1:]+top[:1]):body.face([body.vertex((x,y),1.55),body.vertex((x+a[0],y+a[1]),a[2]),body.vertex((x+b[0],y+b[1]),b[2])],(0,0,1))
        # Flat hood and boot, plus four pillars around the glazed cabin.
        for cx,w in [(1.57,.52),(-1.57,.52)]:box(body,(x+cx,y),(1,0),(0,1),w,1.48,.94,1.01)
        for dx in [-1.24,1.24]:
            for dy in [-.74,.74]:tube(body,(x+dx,y+dy,1.0),(x+math.copysign(.8,dx),y+math.copysign(.64,dy),1.49),.035)
        for dy in [-.78,.78]:tube(body,(x,y+dy,.99),(x,y+math.copysign(.68,dy),1.48),.035)
        result.append(body.item(f'car_body_{variant}','vehicle_model',color,{}))
    for dx in [-1.32,1.32]:
        for dy in [-.85,.85]:
            tube(rubber,(x+dx,y+dy-.11,.33),(x+dx,y+dy+.11,.33),.32,16)
            tube(metal,(x+dx,y+dy-math.copysign(.115,dy),.33),(x+dx,y+dy+math.copysign(.115,dy),.33),.17,12)
    for dx in [-2.02,2.02]:box(metal,(x+dx,y),(1,0),(0,1),.1,1.52,.46,.56)
    result.extend([glass.item('car_glass','vehicle_model','#667f89',{}),rubber.item('car_rubber','vehicle_model','#25292b',{}),metal.item('car_metal','vehicle_model','#8c989b',{})])
    return result
