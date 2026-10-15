"""Inferred cafe visits connected only by verified clear, local walking links.

These are simulation destinations, never surveyed entrances or occupancy. A
standing stop outside each terrace preserves the table/chair exclusion area.
"""
import math
from shapely.geometry import LineString, Point, mapping, shape
from shapely.prepared import prep


def sample(points, distance):
    """Match UE's planar arclength interpolation, including the source Z."""
    for a,b in zip(points,points[1:]):
        length=math.dist(a[:2],b[:2])
        if distance<=length:
            t=distance/max(length,.001)
            return [a[i]+(b[i]-a[i])*t for i in range(3)]
        distance-=length
    return list(points[-1])


def generate_visits(crowd,network,geo,terrain,sidewalks,businesses,road_surface=None):
    walking=shape(network['walkable_geometry'])
    # Existing bridge paths may share their deck surface with traffic. Local
    # cafe approaches must never add a shortcut across those vehicle lanes.
    if road_surface is not None:walking=walking.difference(road_surface)
    safe=prep(walking.buffer(.00001))
    base=list(network['routes']);destinations=[];skipped=[]
    for business in sorted(businesses,key=lambda b:b['id']):
        p=business['properties']
        if not p.get('terrace_placed') or p['kind'] not in ['cafe','restaurant','bar','fast_food']:continue
        # +Y is the outward local axis in UE. Stop outside the furniture's
        # expanded footprint, on its two sides or its street-facing edge.
        yaw=math.radians(p['facade_yaw_degrees']);along=(math.cos(yaw),-math.sin(yaw));out=(-math.sin(yaw),-math.cos(yaw))
        cx,cy=geo.origin[0]+p['terrace_cm'][0]/100,geo.origin[1]-p['terrace_cm'][1]/100
        targets=[(cx+along[0]*d,cy+along[1]*d) for d in [-1.65,1.65]]+[(cx+out[0]*1.4,cy+out[1]*1.4)]
        choices=[]
        for route in base:
            line=shape(route['geometry'])
            if line.distance(Point(cx,cy))>14:continue
            ue_line=LineString([v[:2] for v in route['points_cm']])
            for target in targets:
                if not safe.covers(Point(target)):continue
                ue_target=((target[0]-geo.origin[0])*100,-(target[1]-geo.origin[1])*100)
                distance=ue_line.project(Point(ue_target));entry=sample(route['points_cm'],distance)
                start=(geo.origin[0]+entry[0]/100,geo.origin[1]-entry[1]/100)
                link=LineString([start,target])
                if not 1.25<=link.length<=12 or not safe.covers(link):continue
                points=[]
                for xy in link.segmentize(1.).coords:
                    z=terrain.local(xy)+(.15 if sidewalks is not None and sidewalks.covers(Point(xy)) else .04)
                    points.append([round((xy[0]-geo.origin[0])*100,3),round(-(xy[1]-geo.origin[1])*100,3),round(z*100,3)])
                if abs(points[0][2]-entry[2])>20:continue
                points[0]=entry
                if any(abs(a[2]-b[2])>math.dist(a[:2],b[:2])*.3 for a,b in zip(points,points[1:])):continue
                choices.append((link.length,route['id'],target,route,distance,points,link))
        if not choices:
            skipped.append(dict(business_id=business['id'],reason='no direct clear approach from a generated pedestrian route within 12m'));continue
        _,_,_,parent,distance,points,link=min(choices,key=lambda c:c[:3])
        identifier='sim/visit/'+business['id']
        route={k:parent[k] for k in ['source_id','source_url','source_snapshot','source_license']}
        route.update(id=identifier,route_source='inferred_business_approach',placement_source='inferred:clear standing approach outside terrace; not a surveyed entrance',
                     points_cm=points,length_m=round(link.length,4),geometry=mapping(link))
        network['routes'].append(route)
        crowd['routes'].append({k:v for k,v in route.items() if k!='geometry'})
        facade=business['point_cm'];end=points[-1]
        destinations.append(dict(id=identifier,business_id=business['id'],name=p.get('name') or p['kind'],route_id=identifier,
            parent_route_id=parent['id'],parent_distance_cm=distance,capacity=1,dwell_seconds=10+(len(destinations)%5)*2,
            facing_yaw_degrees=round(math.degrees(math.atan2(facade[1]-end[1],facade[0]-end[0])),3),
            provenance='inferred:simulated standing cafe visit; not real customers, seating or a surveyed entrance'))
    crowd['destinations']=destinations;network['destinations']=destinations
    report=dict(destinations=len(destinations),skipped=skipped,capacity_per_stop=1,maximum_link_m=12,
        policy='Local clear approaches only; reserve a standing stop, dwell, retrace approach and resume source route. No invented road crossings or global connectivity')
    crowd['report']['visits']=report;crowd['report']['routes']=len(crowd['routes']);crowd['report']['policy']=report['policy']
    # Distribute the existing inferred population across visit-capable routes
    # first. Visitors still walk to a destination; none spawn at the stop.
    assigned=set();by_id={r['id']:r for r in base}
    positions=[sample(by_id[a['route_id']]['points_cm'],a['progress_m']*100) for a in crowd['agents']]
    for index,(agent,destination) in enumerate(zip(crowd['agents'],destinations)):
        parent=by_id[destination['parent_route_id']]
        if parent['id'] in assigned:continue
        entry=destination['parent_distance_cm'];length=LineString([p[:2] for p in parent['points_cm']]).length
        for offset in [-250,250,-500,500]:
            distance=entry+offset
            if not 10<distance<length-10:continue
            position=sample(parent['points_cm'],distance)
            if any(math.dist(position[:2],other[:2])<125.1 for j,other in enumerate(positions) if j!=index):continue
            assigned.add(parent['id']);positions[index]=position
            agent.update(route_id=parent['id'],progress_m=round(distance/100,4),direction=1 if offset<0 else -1)
            break
    return report


def validate_visits(crowd,business_ids):
    errors=[];routes={r['id']:r for r in crowd['routes']};used=set()
    for d in crowd.get('destinations',[]):
        if d['id'] in used or d['business_id'] not in business_ids or d.get('capacity')!=1:errors.append('invalid_visit_destination')
        used.add(d['id']);parent=routes.get(d['parent_route_id']);link=routes.get(d['route_id'])
        if not parent or not link or parent is link:errors.append('invalid_visit_route');continue
        length=LineString([p[:2] for p in parent['points_cm']]).length
        if not 0<=d['parent_distance_cm']<=length+.000001 or math.dist(sample(parent['points_cm'],d['parent_distance_cm']),link['points_cm'][0])>.05:errors.append('disconnected_visit_approach')
        if not 1<=d['dwell_seconds']<=60 or not math.isfinite(d['facing_yaw_degrees']):errors.append('invalid_visit_duration_or_yaw')
    return errors
