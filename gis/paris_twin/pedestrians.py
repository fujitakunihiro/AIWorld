"""Deterministic simulated pedestrians on GIS-derived, obstacle-free paths.

People and motion are inferred. Source IDs describe the underlying road, never
observed people or pedestrian counts. No routing connection is invented across
water, a building, or a gap in the generated walkable surfaces.
"""
import hashlib
import math
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from .detail_geometry import box, crown


def seed(identifier):
    return int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:4],'big')


def line_parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='LineString':return [geometry]
    return [line for child in getattr(geometry,'geoms',[]) for line in line_parts(child)]


def person_models(geo,Mesh):
    x,y=geo.origin;result=[]
    for variant,color in enumerate(['#45647b','#874b3d','#596349']):
        torso=Mesh(geo);box(torso,(x,y),(1,0),(0,1),.24,.38,.84,1.44)
        result.append(torso.item(f'person_torso_{variant}','person_model',color,{}))
        arm=Mesh(geo);box(arm,(x,y),(1,0),(0,1),.11,.11,-.54,0)
        result.append(arm.item(f'person_arm_{variant}','person_model',color,{}))
    head=Mesh(geo);crown(head,(x,y,.13),(.105,.105,.13),sides=8,rings=5)
    result.append(head.item('person_head','person_model','#c29d80',{}))
    leg=Mesh(geo);box(leg,(x,y),(1,0),(0,1),.12,.14,-.79,0)
    box(leg,(x+.025,y),(1,0),(0,1),.19,.145,-.84,-.76)
    result.append(leg.item('person_leg','person_model','#343b43',{}))
    # One rigid instance beyond the near animation range, with the same human
    # proportions and vertex colours. Near people retain all six joints.
    source={m['id']:m for m in result}
    for variant in range(3):
        merged=Mesh(geo);colors=[]
        for name,offset in [(f'person_torso_{variant}',(0,0,0)),('person_head',(0,0,146)),
                            (f'person_arm_{variant}',(0,-23,139)),(f'person_arm_{variant}',(0,23,139)),
                            ('person_leg',(0,-9,84)),('person_leg',(0,9,84))]:
            part=source[name];start=len(merged.positions)
            merged.positions.extend([[p[i]+offset[i] for i in range(3)] for p in part['positions_cm']])
            merged.normals.extend(part['normals']);merged.indices.extend(i+start for i in part['indices'])
            colors.extend([part['color']]*len(part['positions_cm']))
        item=merged.item(f'person_far_{variant}','person_model','#ffffff',{})
        item['vertex_colors']=colors;result.append(item)
    thigh=Mesh(geo);box(thigh,(x,y),(1,0),(0,1),.12,.14,-.40,0)
    shin=Mesh(geo);box(shin,(x,y),(1,0),(0,1),.12,.14,-.39,0)
    box(shin,(x+.025,y),(1,0),(0,1),.19,.145,-.44,-.36)
    result.extend([thigh.item('person_thigh','person_model','#343b43',{}),shin.item('person_shin','person_model','#343b43',{})])
    source={m['id']:m for m in result}
    for variant in range(3):
        merged=Mesh(geo);colors=[]
        parts=[(f'person_torso_{variant}',(0,0,-36),0),('person_head',(0,0,110),0),
               (f'person_arm_{variant}',(0,-23,103),0),(f'person_arm_{variant}',(0,23,103),0),
               ('person_thigh',(0,-9,48),90),('person_thigh',(0,9,48),90),
               ('person_shin',(40,-9,48),0),('person_shin',(40,9,48),0)]
        for name,offset,pitch in parts:
            part=source[name];start=len(merged.positions);c=math.cos(math.radians(pitch));s=math.sin(math.radians(pitch))
            def rotate(p):return [c*p[0]-s*p[2],p[1],s*p[0]+c*p[2]]
            merged.positions.extend([[v+offset[i] for i,v in enumerate(rotate(p))] for p in part['positions_cm']])
            merged.normals.extend([rotate(n) for n in part['normals']]);merged.indices.extend(i+start for i in part['indices'])
            colors.extend([part['color']]*len(part['positions_cm']))
        item=merged.item(f'person_far_seated_{variant}','person_model','#ffffff',{});item['vertex_colors']=colors;result.append(item)
    return result


def furniture_obstacles(geo,street_features):
    obstacles=[]
    for feature in street_features:
        props=feature['properties'];point=Point(geo.forward.transform(*props['wgs84_centre']))
        radius=1.35 if props['kind'] in ['bench','bicycle_rack'] else .8 if props['kind']=='bin' else max(.6,.2*(props.get('crown_diameter_m') or 6)/6+.38) if props['kind']=='tree' else .6
        obstacles.append(point.buffer(radius))
    return obstacles


def generate_routes(geo,roads,terrain,water,buildings,sidewalks,paths_surface,bridge_decks,street_features,max_agents=160,extra_obstacles=()):
    bridge_surface=unary_union([d.geometry for d in bridge_decks])
    walking=unary_union([g for g in [sidewalks,paths_surface,bridge_surface] if g is not None])
    if water is not None:walking=walking.difference(water.difference(bridge_surface))
    obstacles=furniture_obstacles(geo,street_features)
    safe=walking.buffer(-.38).difference(buildings.buffer(.5)).difference(unary_union(obstacles+[g.buffer(.38) for g in extra_obstacles]))
    routes=[]
    for feature in roads:
        props=feature['properties'];tags=props['tags'];highway=tags.get('highway')
        if props['tunnel'] or props['layer']<0 or tags.get('foot') in ['no','private'] or tags.get('access')=='private':continue
        if highway not in ['footway','path','pedestrian','living_street','residential','service','tertiary','secondary','primary','unclassified']:continue
        for part_index,line in enumerate(sorted(line_parts(shape(feature['geometry'])),key=lambda g:g.normalize().wkb_hex)):
            candidates=[('osm_pedestrian_centreline',line)] if highway in ['footway','path','pedestrian'] else [
                ('inferred_sidewalk_left',line.offset_curve(props['width_m']/2+.75)),
                ('inferred_sidewalk_right',line.offset_curve(-props['width_m']/2-.75))]
            for origin,candidate in candidates:
                pieces=sorted(line_parts(candidate.intersection(safe)),key=lambda g:g.normalize().wkb_hex)
                for index,piece in enumerate(pieces):
                    if piece.length<12:continue
                    identifier=f"sim/route/{props['source_id']}/{origin}/{part_index}/{index}"
                    points=[]
                    for coord in piece.segmentize(1.5).coords:
                        p=Point(coord);xy=(p.x,p.y)
                        deck=next((d for d in bridge_decks if d.geometry.covers(p)),None)
                        z=deck.height(xy) if deck else terrain.local(xy)+(.15 if sidewalks is not None and sidewalks.covers(p) else .04)
                        points.append([round((p.x-geo.origin[0])*100,3),round(-(p.y-geo.origin[1])*100,3),round(z*100,3)])
                    routes.append(dict(id=identifier,source_id=props['source_id'],source_url=props['source_url'],
                        source_snapshot=props['source_snapshot'],source_license=props['source_license'],
                        route_source=origin,placement_source='inferred:clipped to generated walkable surfaces minus buildings and mapped furniture',
                        points_cm=points,length_m=round(piece.length,4),geometry=mapping(piece)))
    # Retain the network and budget the crowd independently. This avoids moving
    # or deleting geographic geometry when the visual crowd budget changes.
    routes.sort(key=lambda r:r['id'])
    agents=[];positions=[]
    # Stable spatial coverage, then near-field density; no random global state.
    ordered=sorted(routes,key=lambda r:seed(r['id']))
    for route in ordered:
        if len(agents)>=max_agents:break
        line=shape(route['geometry']);s=seed(route['id'])
        progress=.15+(s%700)/1000
        point=line.interpolate(progress,normalized=True)
        if any(point.distance(p)<1.25 for p in positions):continue
        agents.append(dict(id=f"sim/person/{len(agents):04d}",route_id=route['id'],
            progress_m=round(line.length*progress,4),direction=1 if s%2 else -1,
            speed_mps=round(.9+(s%61)/100,2),variant=s%3,
            provenance='inferred:simulated pedestrian; not an observed person or measured population'))
        positions.append(point)
    public=[{k:v for k,v in r.items() if k!='geometry'} for r in routes]
    report=dict(routes=len(routes),agents=len(agents),inferred_population=True,
        route_sources={kind:sum(r['route_source']==kind for r in routes) for kind in ['osm_pedestrian_centreline','inferred_sidewalk_left','inferred_sidewalk_right']},
        obstacle_clearance_m=.38,policy='Independent safe path segments; turn at ends; no assumed network connectivity or traffic simulation')
    return dict(routes=public,agents=agents,report=report),dict(origin_projected_m=list(geo.origin),walkable_geometry=mapping(safe),routes=routes,report=report)


def validate_network(network,source_ids):
    """Validate the exported paths, including their interpolated swept footprint."""
    from shapely.geometry import LineString
    from shapely.prepared import prep
    safe=prep(shape(network['walkable_geometry']).buffer(.001));errors=[];ids=set()
    for route in network['routes']:
        if route['id'] in ids:errors.append('duplicate_pedestrian_route')
        ids.add(route['id'])
        if route['source_id'] not in source_ids:errors.append('untraced_pedestrian_road')
        geometry=shape(route['geometry'])
        route_safe=safe
        if route.get('route_source')=='inferred_reserved_seat_approach':
            reserved=next((s for s in network.get('reserved_seat_surfaces',[]) if s['route_id']==route['id']),None)
            if reserved is None:errors.append('missing_reserved_seat_surface');continue
            route_safe=prep(shape(reserved['geometry']).buffer(.001))
        if not route_safe.covers(geometry):errors.append('pedestrian_route_outside_safe_surface')
        if len(route['points_cm'])<2 or any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in route['points_cm']):errors.append('invalid_pedestrian_coordinates')
        else:
            ox,oy=network['origin_projected_m'];line=LineString([(ox+p[0]/100,oy-p[1]/100) for p in route['points_cm']])
            if not route_safe.covers(line):errors.append('sampled_pedestrian_route_cuts_corner')
    return errors
