import math
from collections import defaultdict
from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .acquire import verify_cache
from .coordinates import Georeference
from .io import paths, read, sha, write


def connectivity(roads,geo):
    graph=defaultdict(set)
    for f in roads:
        p=f['properties']
        if p['tunnel'] or p['layer']<0:continue
        coords=p['source_geometry_projected'].get('coordinates',[])
        ids=p.get('osm_node_ids',[])
        if len(coords)!=len(ids):continue
        for a,b,ca,cb in zip(ids,ids[1:],coords,coords[1:]):
            if not LineString([ca,cb]).intersects(geo.extent):continue
            graph[a].add(b);graph[b].add(a)
    remaining=set(graph);components=[]
    while remaining:
        todo=[remaining.pop()];count=0
        while todo:
            node=todo.pop();count+=1
            for neighbor in graph[node]:
                if neighbor in remaining:remaining.remove(neighbor);todo.append(neighbor)
        components.append(count)
    return {'nodes':len(graph),'edges':sum(map(len,graph.values()))//2,
            'component_sizes':sorted(components,reverse=True),
            'largest_component_ratio':round(max(components,default=0)/max(1,len(graph)),4),
            'method':'original OSM shared node IDs; underground omitted; disconnected clipped paths reported'}


def validate(config):
    manifest=verify_cache(config);p=paths(config);geo=Georeference(config)
    data=read(p['Processed']/'district.json');surface=read(p['Generated']/'surface-validation.json')
    scene=read(p['Generated']/'scene.json');layers=data['layers'];errors=[];warnings=[]
    worst=0
    for e,n in [geo.origin,*[(x,y) for x in [geo.extent.bounds[0],geo.extent.bounds[2]] for y in [geo.extent.bounds[1],geo.extent.bounds[3]]]]:
        lon,lat=geo.inverse.transform(e,n)
        ue=geo.to_ue(lon,lat,37.25,30)
        lon2,lat2,z=geo.from_ue(*ue,origin_elevation=30)
        e2,n2=geo.forward.transform(lon2,lat2)
        worst=max(worst,math.hypot(e-e2,n-n2),abs(z-37.25))
    if worst>.0001:errors.append('coordinate_roundtrip_gt_0.1mm')
    invalid=[];ids=set();untraced=[]
    for layer in layers.values():
        for f in layer:
            props=f['properties'];identifier=props['source_id']
            if not shape(f['geometry']).is_valid:invalid.append(identifier)
            if identifier in ids:errors.append('duplicate_source_id:'+identifier)
            ids.add(identifier)
            if props['source_snapshot'] not in manifest['files'] or not props.get('source_url'):untraced.append(identifier)
    if invalid:errors.append('invalid_normalized_geometry')
    if untraced:errors.append('source_trace_missing')
    buildings=layers['buildings'];shapes=[shape(f['geometry']) for f in buildings];tree=STRtree(shapes)
    overlaps=[]
    for i,g in enumerate(shapes):
        for j in tree.query(g):
            j=int(j)
            if j<=i:continue
            area=g.intersection(shapes[j]).area
            if area>.25:overlaps.append({'a':buildings[i]['properties']['source_id'],'b':buildings[j]['properties']['source_id'],'area_m2':round(area,3)})
    if overlaps:warnings.append('OSM footprint overlaps require source review; not silently treated as surveyed')
    missing=sum(bool(f['properties']['height_measured_missing']) for f in buildings)
    estimates=sum(f['properties']['height_kind']=='estimated' for f in buildings)
    for f in buildings:
        props=f['properties']
        if not math.isfinite(props['height_m']) or not 0<props['height_m']<300:errors.append('height_out_of_preview_range:'+props['source_id'])
        if props['height_kind']=='estimated' and not props['height_source'].startswith('estimated:'):errors.append('unlabelled_height_estimate')
    if missing:warnings.append(f'{missing} buildings have no verified measured metre height; L1 only')
    network=connectivity(layers['roads'],geo)
    if not network['edges']:errors.append('road_network_empty')
    if len(network['component_sizes'])>1:warnings.append('Road network has disconnected components; inspect clipped paths and source gaps')
    water=unary_union([shape(f['geometry']) for f in layers['water'] if f['properties']['water_role']=='river'])
    bridges=[]
    for f in layers['roads']:
        props=f['properties']
        if props['bridge']:
            area=shape(f['geometry']).buffer(props['width_m']/2).intersection(water).area
            bridges.append({'id':props['source_id'],'name':props['name'],'water_overlap_m2':round(area,3)})
    if water.is_empty:errors.append('Seine_water_polygon_missing')
    if not any(b['water_overlap_m2']>1 for b in bridges):errors.append('no_bridge_crosses_water')
    if surface['generated_road_building_overlap_m2']>.001:errors.append('generated_road_building_overlap')
    triangles=0
    for obj in scene['objects']:
        refs=obj['properties'].get('source_ids',[])
        if any(identifier not in ids for identifier in refs):errors.append('untraced_mesh_source:'+obj['id'])
        positions=obj['positions_cm'];indices=obj['indices']
        if len(indices)%3 or any(i<0 or i>=len(positions) for i in indices):errors.append('invalid_mesh_indices:'+obj['id'])
        if any(not math.isfinite(v) for pos in positions for v in pos):errors.append('nonfinite_mesh:'+obj['id'])
        triangles+=len(indices)//3
    if scene['georeference']['cesium_transform_applied']:errors.append('unexpected_double_georeference')
    report={'format':1,'generation':data['generation'],'errors':errors,'warnings':warnings,'coordinate_roundtrip_max_m':worst,
            'invalid_geometry':invalid,'untraced_ids':untraced,'building_overlaps':overlaps,
            'buildings':len(buildings),'missing_verified_measured_heights':missing,'estimated_heights':estimates,
            'source_declared_heights':len(buildings)-estimates,'road_network':network,'bridges':bridges,
            'source_feature_ids':len(ids),'layers':{k:len(v) for k,v in layers.items()},
            'normalized_issues':data['issues'],'generated_surface_validation':surface,
            'water_roles':{role:sum(f['properties']['water_role']==role for f in layers['water']) for role in ['river','basin','waterbody']},
            'scene_sha256':sha(p['Generated']/'scene.json'),'triangles':triangles,
            'height_semantics':'Paris h_et_max is floors, not metres; OSM height is source-declared, unverified'}
    write(p['Generated']/'validation.json',report)
    return report
