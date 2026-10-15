"""Reservation-only approaches to authored cafe chairs, never public shortcuts.

One chair per mapped food business can be reserved. Positions, furniture and
customers remain inferred; a rejected chair keeps the original standing stop.
"""
import math
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union
from .businesses import rectangle
from .pedestrians import furniture_obstacles


def generate_seating(crowd,network,geo,terrain,sidewalks,businesses,placement,buildings,water,street_features):
    by_id={b['id']:b for b in businesses};routes={r['id']:r for r in network['routes']}
    terraces={t['source_id']:shape(t['geometry']) for t in placement['terraces']}
    roads=shape(placement['road_geometry'])
    clear=shape(placement['walking_geometry']).buffer(-.24).difference(buildings.buffer(.35)).difference(roads.buffer(.38))
    if water is not None:clear=clear.difference(water)
    clear=clear.difference(unary_union(furniture_obstacles(geo,street_features)))
    seats=[];skipped=[]
    for d in crowd['destinations']:
        p=by_id[d['business_id']]['properties'];yaw=math.radians(p['facade_yaw_degrees'])
        along=(math.cos(yaw),-math.sin(yaw));out=(-math.sin(yaw),-math.cos(yaw))
        centre=(geo.origin[0]+p['terrace_cm'][0]/100,geo.origin[1]-p['terrace_cm'][1]/100)
        def xy(a,b=0):return (centre[0]+along[0]*a+out[0]*b,centre[1]+along[1]*a+out[1]*b)
        parent=routes[d['route_id']];start=parent['points_cm'][-1]
        entry=(geo.origin[0]+start[0]/100,geo.origin[1]-start[1]/100)
        others=[g.buffer(.38) for key,g in terraces.items() if key!=d['business_id']]
        base=clear.intersection(Point(centre).buffer(15)).difference(unary_union(others));choices=[]
        for sign in [-1,1]:
            seat=xy(sign*.72)
            # Table clearance uses a 23cm body radius. The selected seat plate
            # is entered with a sit animation; its back remains an obstacle.
            forbidden=unary_union([Point(centre).buffer(.37+.23),rectangle(xy(-sign*.72),along,out,.4,.4).buffer(.23),
                LineString([xy(sign*.90,-.20),xy(sign*.90,.20)]).buffer(.14)])
            allowed=base.difference(forbidden)
            for side in [-1,1]:
                link=LineString([entry,xy(sign*.72,side*.65),seat])
                if not .5<link.length<=6 or not allowed.buffer(.00001).covers(link):continue
                points=[]
                for coord in link.segmentize(.35).coords:
                    z=terrain.local(coord)+(.15 if sidewalks is not None and sidewalks.covers(Point(coord)) else .04)
                    points.append([round((coord[0]-geo.origin[0])*100,3),round(-(coord[1]-geo.origin[1])*100,3),round(z*100,3)])
                if abs(points[-1][2]-p['terrace_cm'][2])>20:continue
                points[0]=list(start);points[-1][2]=p['terrace_cm'][2]
                if any(abs(a[2]-b[2])>math.dist(a[:2],b[:2])*.3 for a,b in zip(points,points[1:])):continue
                choices.append((link.length,sign,side,link,points,allowed))
        if not choices:
            skipped.append(dict(business_id=d['business_id'],reason='no clear reserved chair approach; preserve standing visit'));continue
        _,sign,_,link,points,allowed=min(choices,key=lambda c:c[:3]);identifier='sim/seat/'+d['business_id']
        route={k:parent[k] for k in ['source_id','source_url','source_snapshot','source_license']}
        route.update(id=identifier,route_source='inferred_reserved_seat_approach',placement_source='inferred:exclusive chair approach; never a public walking graph edge',
            points_cm=points,length_m=round(link.length,4),geometry=mapping(link))
        network['routes'].append(route);crowd['routes'].append({k:v for k,v in route.items() if k!='geometry'})
        d.update(seat_route_id=identifier,seat_height_cm=48.,seat_facing_yaw_degrees=round(p['facade_yaw_degrees']+(180 if sign>0 else 0),3),
            provenance='inferred:one reserved proxy chair; not real customers, surveyed seats or occupancy')
        seats.append(dict(route_id=identifier,business_id=d['business_id'],geometry=mapping(allowed.intersection(link.envelope.buffer(.5)))))
    network['reserved_seat_surfaces']=seats
    crowd['social']=dict(enabled=True,range_cm=280,duration_seconds=2.5,cooldown_seconds=25,
        provenance='inferred:brief local greetings between simulated people; static visibility checked; no LLM')
    report=dict(seats=len(seats),standing_fallbacks=len(skipped),skipped=skipped,capacity_per_business=1,
        body_clearance_m=.23,maximum_approach_m=6,policy='One exclusive chair; private approach excluded from public graph; standing fallback if blocked')
    crowd['report']['seating']=report;crowd['report']['routes']=len(crowd['routes'])
    return report


def validate_seating(crowd):
    routes={r['id']:r for r in crowd['routes']};errors=[];used=set()
    for d in crowd.get('destinations',[]):
        if 'seat_route_id' not in d:continue
        seat=routes.get(d['seat_route_id']);entry=routes.get(d['route_id'])
        if not seat or not entry or seat['id'] in used:errors.append('invalid_reserved_seat_route');continue
        used.add(seat['id'])
        if seat.get('route_source')!='inferred_reserved_seat_approach' or math.dist(entry['points_cm'][-1],seat['points_cm'][0])>.05:errors.append('disconnected_reserved_seat')
        if not .4<=seat['length_m']<=6.001 or not 40<=d.get('seat_height_cm',0)<=52 or not math.isfinite(d.get('seat_facing_yaw_degrees',math.nan)):errors.append('invalid_reserved_seat_pose')
    if used!={r['id'] for r in crowd['routes'] if r.get('route_source')=='inferred_reserved_seat_approach'}:errors.append('unreserved_seat_route')
    graph=crowd.get('navigation',{})
    if any(e.get('route_id') in used for e in graph.get('edges',[])) or any(n.get('route_id') in used for n in graph.get('nodes',[])):errors.append('private_seat_in_public_graph')
    return errors
