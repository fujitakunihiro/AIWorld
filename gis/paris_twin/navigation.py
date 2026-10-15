"""Deterministic, conservative walking graph over the generated GIS paths.

Short connectors are inferred, not surveyed crossings. They must fit wholly in
the existing clear walking surface with vehicle surfaces removed.
"""
import heapq
import math
from shapely.geometry import LineString, Point, mapping, shape
from shapely.prepared import prep
from shapely.strtree import STRtree
from .visits import sample


def generate_navigation(crowd,network,geo,roads,road_surface,terrain,sidewalks,bridge_decks=()):
    routes=[r for r in network['routes'] if r['route_source']!='inferred_business_approach']
    lines=[LineString([p[:2] for p in r['points_cm']]) for r in routes]
    source={f['properties']['source_id']:f['properties'] for f in roads}
    safe_geometry=shape(network['walkable_geometry'])
    if road_surface is not None:safe_geometry=safe_geometry.difference(road_surface.buffer(.38))
    safe=prep(safe_geometry.buffer(.00001));tree=STRtree(lines)
    distances=[[] for _ in routes];positions={};connections={}

    def node(i,d):
        d=max(0.,min(lines[i].length,d))
        prior=next((v for v in distances[i] if abs(v-d)<.01),None)
        if prior is not None:d=prior
        else:distances[i].append(d)
        key=(i,d);positions[key]=sample(routes[i]['points_cm'],d)
        return key

    def compatible(i,j):
        a=source.get(routes[i]['source_id'],{});b=source.get(routes[j]['source_id'],{})
        return a.get('layer',0)==b.get('layer',0) or bool(set(a.get('osm_node_ids',[]))&set(b.get('osm_node_ids',[])))

    def connect(i,j,di,dj):
        if not compatible(i,j):return
        a=sample(routes[i]['points_cm'],di);b=sample(routes[j]['points_cm'],dj)
        length=math.dist(a[:2],b[:2])
        if length<.01:
            if math.dist(a,b)>.05:return
            points=None
        else:
            if length>600 or abs(a[2]-b[2])>length*.3:return
            projected=lambda p:(geo.origin[0]+p[0]/100,geo.origin[1]-p[1]/100)
            line=LineString([projected(a),projected(b)])
            if not safe.covers(line):return
            points=[]
            for xy in line.segmentize(1).coords:
                p=Point(xy);deck=next((d for d in bridge_decks if d.geometry.covers(p)),None)
                z=deck.height(xy) if deck else terrain.local(xy)+(.15 if sidewalks is not None and sidewalks.covers(p) else .04)
                points.append([round((xy[0]-geo.origin[0])*100,3),round(-(xy[1]-geo.origin[1])*100,3),round(z*100,3)])
            if abs(points[0][2]-a[2])>20 or abs(points[-1][2]-b[2])>20:return
            points[0]=a;points[-1]=b
            if any(abs(p[2]-q[2])>math.dist(p[:2],q[:2])*.3 for p,q in zip(points,points[1:])):return
        ka,kb=node(i,di),node(j,dj)
        key=tuple(sorted([ka,kb]))
        if ka!=kb:connections[key]=(ka,kb,points)

    for i,line in enumerate(lines):
        node(i,0);node(i,line.length)
        for d in [0,line.length]:
            p=line.interpolate(d)
            for j in sorted(int(v) for v in tree.query(p.buffer(600))):
                if i==j:continue
                dj=lines[j].project(p)
                if p.distance(lines[j])<=600:connect(i,j,d,dj)
        for j in sorted(int(v) for v in tree.query(line,predicate='intersects')):
            if j<=i:continue
            intersection=line.intersection(lines[j])
            def anchors(g):
                if g.is_empty:return []
                if g.geom_type=='Point':return [g]
                if g.geom_type=='LineString':return [Point(g.coords[0]),Point(g.coords[-1])]
                return [p for child in getattr(g,'geoms',[]) for p in anchors(child)]
            for p in anchors(intersection):connect(i,j,line.project(p),lines[j].project(p))
    by_id={r['id']:i for i,r in enumerate(routes)};dest_keys={}
    for destination in crowd.get('destinations',[]):
        dest_keys[destination['id']]=node(by_id[destination['parent_route_id']],destination['parent_distance_cm'])
    keys=sorted(positions,key=lambda k:(routes[k[0]]['id'],k[1]));ids={k:f'sim/nav/{i:05d}' for i,k in enumerate(keys)}
    nodes=[dict(id=ids[k],route_id=routes[k[0]]['id'],distance_cm=k[1],position_cm=positions[k]) for k in keys]
    edges=[]
    def edge(a,b,route_id,start,end,length,kind):
        edges.append(dict(a=ids[a],b=ids[b],route_id=route_id,start_cm=start,end_cm=end,length_cm=length,kind=kind))
    for i,items in enumerate(distances):
        for a,b in zip(sorted(items),sorted(items)[1:]):edge((i,a),(i,b),routes[i]['id'],a,b,b-a,'source_path')
    connectors=0;junctions=0
    for a,b,points in (connections[k] for k in sorted(connections)):
        if points is None:
            edge(a,b,'',0,0,0,'coincident_junction');junctions+=1;continue
        identifier=f'sim/connect/{connectors:05d}';parent=routes[a[0]]
        geometry=LineString([(geo.origin[0]+p[0]/100,geo.origin[1]-p[1]/100) for p in points])
        route={k:parent[k] for k in ['source_id','source_url','source_snapshot','source_license']}
        route.update(id=identifier,route_source='inferred_walking_connector',placement_source='inferred:short clear walking connection; not a surveyed crossing',
            connected_source_ids=sorted({routes[a[0]]['source_id'],routes[b[0]]['source_id']}),points_cm=points,length_m=geometry.length,geometry=mapping(geometry))
        network['routes'].append(route);crowd['routes'].append({k:v for k,v in route.items() if k!='geometry'})
        length=sum(math.dist(p[:2],q[:2]) for p,q in zip(points,points[1:]))
        edge(a,b,identifier,0,length,length,'clear_connector');connectors+=1
    for d in crowd.get('destinations',[]):d['navigation_node_id']=ids[dest_keys[d['id']]]
    adjacency={n['id']:[] for n in nodes}
    for e in edges:adjacency[e['a']].append(e['b']);adjacency[e['b']].append(e['a'])
    unseen=set(adjacency);components=[]
    while unseen:
        stack=[min(unseen)];unseen.remove(stack[0]);count=0
        while stack:
            n=stack.pop();count+=1
            for other in adjacency[n]:
                if other in unseen:unseen.remove(other);stack.append(other)
        components.append(count)
    report=dict(nodes=len(nodes),edges=len(edges),connectors=connectors,coincident_junctions=junctions,
        components=len(components),component_sizes=sorted(components,reverse=True),maximum_connector_m=6,
        policy='Existing paths + short clear links; no inferred vehicle-road crossings. Disconnected areas remain disconnected')
    graph=dict(nodes=nodes,edges=edges,report=report)
    crowd['navigation']=graph;network['navigation']=graph;crowd['report']['navigation']=report
    crowd['report']['routes']=len(crowd['routes']);crowd['report']['route_sources']['inferred_walking_connector']=connectors
    network['report']=crowd['report']
    return graph


def shortest_path(graph,start,end):
    """Independent reference search used for deterministic pipeline tests."""
    adjacency={n['id']:[] for n in graph['nodes']}
    for e in graph['edges']:
        adjacency[e['a']].append((e['b'],e['length_cm']));adjacency[e['b']].append((e['a'],e['length_cm']))
    distance={start:0};queue=[(0,start)]
    while queue:
        cost,node=heapq.heappop(queue)
        if cost!=distance[node]:continue
        if node==end:return cost
        for other,length in adjacency[node]:
            new=cost+length
            if new<distance.get(other,math.inf):distance[other]=new;heapq.heappush(queue,(new,other))
    return math.inf


def validate_navigation(crowd):
    graph=crowd.get('navigation',{});nodes={n['id']:n for n in graph.get('nodes',[])};routes={r['id']:r for r in crowd['routes']};errors=[]
    if len(nodes)!=len(graph.get('nodes',[])):errors.append('duplicate_navigation_node')
    for n in nodes.values():
        r=routes.get(n['route_id'])
        if not r or not 0<=n['distance_cm']<=LineString([p[:2] for p in r['points_cm']]).length+.000001:errors.append('invalid_navigation_node');continue
        if math.dist(sample(r['points_cm'],n['distance_cm']),n['position_cm'])>.05:errors.append('navigation_node_position_mismatch')
    for e in graph.get('edges',[]):
        a,b=nodes.get(e['a']),nodes.get(e['b'])
        if not a or not b or not math.isfinite(e['length_cm']) or e['length_cm']<0:errors.append('invalid_navigation_edge');continue
        if not e['route_id']:
            if math.dist(a['position_cm'],b['position_cm'])>.05 or e['length_cm']!=0:errors.append('invalid_coincident_junction')
            continue
        r=routes.get(e['route_id'])
        if not r:errors.append('untraced_navigation_edge');continue
        for n,d in [(a,e['start_cm']),(b,e['end_cm'])]:
            if math.dist(sample(r['points_cm'],d),n['position_cm'])>.05:errors.append('disconnected_navigation_edge')
        if abs(abs(e['end_cm']-e['start_cm'])-e['length_cm'])>.01:errors.append('invalid_navigation_cost')
    for d in crowd.get('destinations',[]):
        n=nodes.get(d.get('navigation_node_id'))
        if not n or n['route_id']!=d['parent_route_id'] or abs(n['distance_cm']-d['parent_distance_cm'])>.01:errors.append('unconnected_navigation_destination')
    return errors
