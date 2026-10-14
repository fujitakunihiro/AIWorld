import math
from collections import defaultdict
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .acquire import verify_cache
from .coordinates import Georeference
from .io import paths, read, sha, write
from .diagnostics import road_components


def connectivity(roads,geo):
    return road_components(roads,geo)[0]


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
        parts=props['height_parts'];foot=shape(f['geometry']);union=unary_union([shape(p['geometry']) for p in parts])
        if union.symmetric_difference(foot).area>.0001:errors.append('building_parts_do_not_cover_footprint:'+props['source_id'])
        if abs(sum(shape(p['geometry']).area for p in parts)-union.area)>.0001:errors.append('building_parts_overlap:'+props['source_id'])
        for part in parts:
            if part['source_snapshot'] not in manifest['files'] or part['source_id'] not in ids:errors.append('untraced_height_part:'+props['source_id'])
            if part['height_kind']=='official_topographic' and not 0<part['vertical_precision_m']<=3:errors.append('invalid_official_height_precision')
            if not .5<=part['height_gutter_m']<150 or not 0<=part['roof']['rise_m']<20:errors.append('height_part_out_of_range')
            if part['roof']['reproduction_level']!='L1':errors.append('unverified_roof_promoted')
        if props['reproduction_level_body']=='L2' and props['official_height_coverage']<.98:errors.append('insufficient_L2_body_coverage')
    if missing:warnings.append(f'{missing} buildings lack near-complete official gutter coverage; roof profiles remain inferred')
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
        if len(obj['normals'])!=len(positions):errors.append('normal_count_mismatch:'+obj['id'])
        if 'vertex_colors' in obj and len(obj['vertex_colors'])!=len(positions):errors.append('vertex_color_count_mismatch:'+obj['id'])
        if 'appearance_ranges' in obj:
            ranges=obj['appearance_ranges'];cursor=0
            for r in ranges:
                if r['start']!=cursor or r['count']<1 or r['source_id'] not in ids:errors.append('invalid_batched_building_range')
                cursor+=r['count']
            if cursor!=len(positions):errors.append('building_batch_not_fully_covered')
        if obj['kind'].startswith('facade_') and obj['properties']['reproduction_level']!='L1':errors.append('unverified_facade_promoted')
        triangles+=len(indices)//3
    if scene['georeference']['cesium_transform_applied']:errors.append('unexpected_double_georeference')
    review=read(p['Generated']/'diagnostics.json')
    if review['road_network']!=network:errors.append('diagnostic_network_mismatch')
    if review['building_overlaps']!=overlaps:errors.append('diagnostic_overlap_mismatch')
    for issue in review['issues']:
        if not issue['source_ids'] or any(identifier not in ids for identifier in issue['source_ids']):errors.append('untraced_diagnostic:'+issue['id'])
    if len(scene['pick_features'])!=len({f['id'] for f in scene['pick_features']}):errors.append('duplicate_pick_feature')
    if any(f['id'] not in ids for f in scene['pick_features']):errors.append('untraced_pick_feature')
    models={m['id']:m for m in scene.get('instance_models',[])}
    for model in models.values():
        if len(model['normals'])!=len(model['positions_cm']) or len(model['indices'])%3 or any(i<0 or i>=len(model['positions_cm']) for i in model['indices']):errors.append('invalid_instance_model:'+model['id'])
    streets={f['properties']['source_id']:f for f in layers.get('street_objects',[])}
    for batch in scene.get('instance_batches',[]):
        if batch['model'] not in models:errors.append('missing_instance_model:'+batch['model'])
        used=set()
        for instance in batch['instances']:
            identifier=instance['source_id']
            if identifier not in streets or identifier in used:errors.append('invalid_or_duplicated_street_instance:'+identifier);continue
            used.add(identifier);feature=streets[identifier]
            point=shape(feature['geometry']);expected=(geo.origin[0]+instance['position_cm'][0]/100,geo.origin[1]-instance['position_cm'][1]/100)
            if point.distance(Point(expected))>.001:errors.append('street_point_silently_relocated:'+identifier)
            if len(instance['scale'])!=3 or any(not math.isfinite(v) or v<=0 or v>10 for v in instance['scale']):errors.append('invalid_street_instance_scale:'+identifier)
            if not all(math.isfinite(v) for v in instance['position_cm']) or not math.isfinite(instance['yaw_degrees']):errors.append('nonfinite_street_instance:'+identifier)
    street_pick={f['id'] for f in scene['pick_features'] if f['kind'].startswith('street_')}
    model_ids={i['source_id'] for b in scene.get('instance_batches',[]) for i in b['instances']}
    if street_pick!=model_ids:errors.append('street_instance_selection_mismatch')
    from .pedestrians import validate_network
    crowd=scene.get('pedestrians',{})
    errors.extend(validate_network(read(p['Generated']/'pedestrian-network.json'),ids))
    route_ids={r['id'] for r in crowd.get('routes',[])};agent_ids=set()
    for agent in crowd.get('agents',[]):
        if agent['id'] in agent_ids or agent['route_id'] not in route_ids:errors.append('invalid_pedestrian_agent')
        agent_ids.add(agent['id'])
        if not .5<=agent['speed_mps']<=2 or agent['direction'] not in [-1,1] or agent['variant'] not in [0,1,2]:errors.append('invalid_pedestrian_motion')
    footprint=scene['footprint_mesh']
    if len(footprint['positions_cm'])!=len(footprint['vertex_colors']):errors.append('footprint_colour_count_mismatch')
    if any(i<0 or i>=len(footprint['positions_cm']) for i in footprint['indices']) or len(footprint['indices'])%3:errors.append('invalid_footprint_mesh_indices')
    from .terrain import Terrain
    terrain=Terrain(config,geo)
    expected_centre=geo.to_ue(*config.get('district_center_wgs84',config['origin_wgs84']),terrain.ngf(geo.centre),terrain.origin_ngf)
    if any(abs(a-b)>.001 for a,b in zip(expected_centre,scene['scene_centre_ue_cm'])):errors.append('district_centre_mismatch')
    if abs(scene['georeference']['origin_elevation_ngf_m']-terrain.origin_ngf)>1e-9:errors.append('vertical_origin_mismatch')
    if scene['georeference']['vertical_datum']!='NGF-IGN69':errors.append('vertical_datum_mismatch')
    for obj in scene['objects']:
        kind=obj['kind']
        if kind in ['ground','road','path','sidewalk','park']:
            offset={'ground':0,'road':.035,'path':.04,'sidewalk':.15,'park':.025}[kind]
            for x,y,z in obj['positions_cm']:
                projected=(geo.origin[0]+x/100,geo.origin[1]-y/100)
                if abs(z/100-terrain.local(projected)-offset)>.0001:
                    errors.append('surface_not_on_shared_terrain:'+obj['id']);break
    if surface['quay_segments']<10:errors.append('river_quay_missing')
    if not surface['bridge_decks']:errors.append('terrain_bridge_decks_missing')
    low_bridges=[b for b in surface['bridge_decks'] if b['minimum_centerline_clearance_m']<1]
    if low_bridges:warnings.append(f'{len(low_bridges)} low bridge fragments ({sum(b["clipped_at_context_boundary"] for b in low_bridges)} boundary-clipped) need full coverage / surveyed deck elevations; estimates retained')
    report={'format':1,'generation':data['generation'],'errors':errors,'warnings':warnings,'coordinate_roundtrip_max_m':worst,
            'invalid_geometry':invalid,'untraced_ids':untraced,'building_overlaps':overlaps,
            'buildings':len(buildings),'missing_verified_measured_heights':missing,'estimated_heights':estimates,
            'source_declared_heights':sum(f['properties']['height_kind']=='source_declared_unverified' for f in buildings),
            'official_height_buildings':sum(bool(f['properties']['height_reference_ids']) for f in buildings),
            'body_L2_buildings':sum(f['properties']['reproduction_level_body']=='L2' for f in buildings),
            'height_parts':sum(len(f['properties']['height_parts']) for f in buildings),
            'road_network':network,'bridges':bridges,
            'source_feature_ids':len(ids),'layers':{k:len(v) for k,v in layers.items()},
            'normalized_issues':data['issues'],'generated_surface_validation':surface,
            'water_roles':{role:sum(f['properties']['water_role']==role for f in layers['water']) for role in ['river','basin','waterbody']},
            'scene_sha256':sha(p['Generated']/'scene.json'),'triangles':triangles,
            'review_issue_counts':{kind:sum(i['kind']==kind for i in review['issues']) for kind in ['building_overlap','disconnected_road']},
            'review_road_classes':{kind:sum(i['classification']==kind for i in review['issues']) for kind in ['boundary_clipped','interior_unconnected']},
            'shared_georeference':scene['georeference']['reference_id'],
            'height_semantics':'IGN hauteur/3D Z describe gutters; source precision retained; extra roof profiles inferred; Paris h_et_max is floors',
            'terrain':terrain.metadata(),'bridge_decks':len(surface['bridge_decks']),'low_bridge_fragments':len(low_bridges),
            'facades':surface['facades'],'building_render_batches':sum(o['kind']=='building' for o in scene['objects']),
            'street_furniture':surface.get('street_furniture',{}),'instance_batches':len(scene.get('instance_batches',[])),
            'rendered_instances':sum(len(b['instances']) for b in scene.get('instance_batches',[]))}
    report['pedestrians']=crowd.get('report',{})
    write(p['Generated']/'validation.json',report)
    return report
