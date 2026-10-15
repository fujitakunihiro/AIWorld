"""Mapped OSM street objects with explicit inferred appearance and dimensions.

The official map XML already archived by Phase 1 includes these nodes, even
though the earlier area/road normalizer did not select them. No network call or
replacement of that snapshot is needed. Overpass snapshots use their JSON nodes.
"""
import gzip
import math
import xml.etree.ElementTree as ET
from collections import Counter
from shapely.geometry import Point, mapping, shape
from shapely.strtree import STRtree
from .io import read
from .normalize import positive_number
from .detail_geometry import box, cylinder, crown, tube


def mapped_nodes(raw, manifest, geo):
    if 'osm-map.xml.gz' in manifest['files']:
        snapshot='osm-map.xml.gz'
        root=ET.fromstring(gzip.decompress((raw/snapshot).read_bytes()))
        nodes=[dict(id=int(e.attrib['id']),lon=float(e.attrib['lon']),lat=float(e.attrib['lat']),
                    tags={t.attrib['k']:t.attrib['v'] for t in e.findall('tag')}) for e in root.findall('node')]
    else:
        snapshot='osm.json'
        nodes=[e for e in read(raw/snapshot)['elements'] if e['type']=='node']
    features=[]
    for node in sorted(nodes,key=lambda n:n['id']):
        tags=node['tags']
        kind=('tree' if tags.get('natural')=='tree' else 'lamp' if tags.get('highway')=='street_lamp'
              else 'bench' if tags.get('amenity')=='bench' else 'bin' if tags.get('amenity')=='waste_basket'
              else 'bicycle_rack' if tags.get('amenity')=='bicycle_parking' else 'signal' if tags.get('highway')=='traffic_signals' else None)
        if not kind:continue
        point=Point(geo.forward.transform(node['lon'],node['lat']))
        if not geo.extent.covers(point):continue
        height=positive_number(tags.get('height'))
        if height is not None and not .3<=height<=45:height=None
        diameter=positive_number(tags.get('diameter_crown')) if kind=='tree' else None
        if diameter is not None and not .5<=diameter<=25:diameter=None
        direction=tags.get('direction','')
        try:
            yaw=(float(direction)+180)%360
            if not math.isfinite(yaw):raise ValueError()
            direction_source='osm:direction; clockwise from north'
        except (ValueError,TypeError):
            yaw=0.;direction_source='estimated:aligned to nearest mapped road'
        identifier=f"osm/node/{node['id']}"
        features.append(dict(geometry=mapping(point),properties=dict(source_id=identifier,source='OpenStreetMap',
            source_url=f"https://www.openstreetmap.org/node/{node['id']}",source_snapshot=snapshot,
            source_license='ODbL-1.0',name=tags.get('name',''),tags=tags,kind=kind,
            wgs84_centre=[node['lon'],node['lat']],position_source='osm:mapped_node; not surveyed by this project',
            appearance_source='procedural:authored proxy; actual species/design unverified',
            height_m=height or dict(tree=10.,lamp=4.5,bench=.92,bin=.95,bicycle_rack=1.1,signal=3.2)[kind],
            height_source='osm:height (unverified tag)' if height else 'estimated:generic street object',
            crown_diameter_m=diameter or 6. if kind=='tree' else None,
            crown_diameter_source='osm:diameter_crown (unverified tag)' if diameter else 'estimated:6m' if kind=='tree' else None,
            yaw_degrees=yaw,direction_source=direction_source,reproduction_level='L1')))
    return features


def model_meshes(geo, Mesh):
    """Shared cm prototypes; the renderer builds each static mesh once."""
    x,y=geo.origin;meshes={k:Mesh(geo) for k in ['tree_trunk','tree_crown','lamp_metal','lamp_glass','bench_wood','bench_metal','bin_metal','bicycle_metal','bicycle_rubber','signal_metal','signal_lens']}
    cylinder(meshes['tree_trunk'],(x,y),.2,0,4.8,10,.09)
    crown(meshes['tree_crown'],(x,y,7.1),(2.65,2.45,2.9),2)
    crown(meshes['tree_crown'],(x+1.6,y+.3,6.4),(1.6,1.85,2.35),4)
    crown(meshes['tree_crown'],(x-1.35,y-.5,6.2),(1.75,1.65,2.2),7)
    metal=meshes['lamp_metal']
    cylinder(metal,(x,y),.2,0,.18,10);cylinder(metal,(x,y),.1,.18,.65,10,.065)
    cylinder(metal,(x,y),.055,.65,3.72,8,.038)
    cylinder(metal,(x,y),.2,3.72,3.85,8,.27)
    cylinder(metal,(x,y),.29,4.27,4.48,8,0)
    box(meshes['lamp_glass'],(x,y),(1,0),(0,1),.34,.34,3.85,4.27)
    for dx in [-.19,.19]:
        for dy in [-.19,.19]:box(metal,(x+dx,y+dy),(1,0),(0,1),.035,.035,3.82,4.3)
    wood=meshes['bench_wood'];legs=meshes['bench_metal']
    for i in range(4):box(wood,(x,y-.22+i*.145),(1,0),(0,1),1.8,.115,.43,.49)
    for i in range(3):box(wood,(x,y+.29),(1,0),(0,1),1.8,.065,.59+i*.12,.68+i*.12)
    for dx in [-.64,.64]:
        for dy in [-.2,.2]:box(legs,(x+dx,y+dy),(1,0),(0,1),.06,.06,0,.44)
        box(legs,(x+dx,y+.29),(1,0),(0,1),.05,.05,.25,.92)
    cylinder(meshes['bin_metal'],(x,y),.23,.06,.85,12,.27)
    cylinder(meshes['bin_metal'],(x,y),.29,.85,.95,12,.24)
    # One inferred bicycle and one generic stand per mapped parking point;
    # neither mapped capacity nor actual occupancy is asserted.
    metal=meshes['bicycle_metal'];rubber=meshes['bicycle_rubber']
    for dx in [-.55,.55]:
        for i in range(24):
            a,b=i*math.tau/24,(i+1)*math.tau/24
            tube(rubber,(x+dx+.33*math.cos(a),y,.36+.33*math.sin(a)),(x+dx+.33*math.cos(b),y,.36+.33*math.sin(b)),.027,6)
        for i in range(8):
            a=i*math.tau/8
            tube(metal,(x+dx,y,.35),(x+dx+.31*math.cos(a),y,.35+.31*math.sin(a)),.005,4)
    frame=[(-.55,.35),(-.12,.78),(.12,.35),(-.55,.35)]
    for a,b in zip(frame,frame[1:]):tube(metal,(x+a[0],y,a[1]),(x+b[0],y,b[1]),.022)
    for a,b in [((-.12,.78),(.34,.81)),((.34,.81),(.12,.35)),((.34,.81),(.55,.35)),((-.12,.78),(-.16,.95)),((.34,.81),(.39,1.03))]:
        tube(metal,(x+a[0],y,a[1]),(x+b[0],y,b[1]),.022)
    tube(metal,(x+.39,y-.24,1.03),(x+.39,y+.24,1.03),.022)
    box(rubber,(x-.17,y),(1,0),(0,1),.23,.15,.94,.99)
    for dx in [-.65,.65]:tube(metal,(x+dx,y+.3,0),(x+dx,y+.3,.72),.035)
    tube(metal,(x-.65,y+.3,.72),(x+.65,y+.3,.72),.035)
    cylinder(meshes['signal_metal'],(x,y),.065,0,3.2,10)
    box(meshes['signal_metal'],(x,y),(1,0),(0,1),.22,.3,2.25,3.16)
    # Unlit lenses: these proxies do not claim a real signal phase/controller.
    for z in [2.42,2.7,2.98]:tube(meshes['signal_lens'],(x+.115,y,z),(x+.13,y,z),.09,12)
    colors=dict(tree_trunk='#64523b',tree_crown='#536a38',lamp_metal='#303c3a',lamp_glass='#d5d7bc',bench_wood='#68533b',bench_metal='#283b34',bin_metal='#3c574c',bicycle_metal='#6c7e84',bicycle_rubber='#24282d',signal_metal='#303b39',signal_lens='#49504a')
    return [m.item(name,'street_model',colors[name],dict(authored_proxy=True)) for name,m in meshes.items()]


def generate_street_objects(geo, features, terrain, water, buildings, roads, sidewalks, paths_surface, bridge_decks):
    batches={name:[] for name in ['tree_trunk','tree_crown','lamp_metal','lamp_glass','bench_wood','bench_metal','bin_metal','bicycle_metal','bicycle_rubber','signal_metal','signal_lens']}
    rendered=[];skipped=[];by_kind=Counter();source_heights=0
    def line_parts(g):
        if g.geom_type=='LineString':return [g] if g.length>.001 else []
        return [line for child in getattr(g,'geoms',[]) for line in line_parts(child)]
    road_lines=[(line,f['properties']['source_id']) for f in roads if not f['properties']['tunnel'] and f['properties']['layer']>=0 for line in line_parts(shape(f['geometry']))]
    road_tree=STRtree([line for line,_ in road_lines])
    for feature in features:
        props=feature['properties'];kind=props['kind'];point=shape(feature['geometry']);xy=(point.x,point.y)
        reason=None
        if kind=='lamp' and props['tags'].get('lamp_mount') in ['wall','suspended','ceiling']:
            reason='non_pole_mount_needs_custom_asset'
        if kind=='signal' and props['tags'].get('traffic_signals')!='signal':
            reason='logical_signal_node_not_a_mapped_physical_pole'
        footprint=point.buffer(.22 if kind in ['tree','lamp','signal'] else .3 if kind=='bin' else .95)
        if footprint.intersects(buildings):reason=reason or 'mapped_point_conflicts_with_building_footprint'
        deck=next((d for d in bridge_decks if d.geometry.covers(point)),None)
        if water and water.covers(point) and deck is None:reason=reason or 'mapped_point_in_water_without_bridge'
        if reason:
            skipped.append(dict(source_id=props['source_id'],reason=reason));continue
        if deck:z=deck.height(xy)
        else:z=terrain.local(xy)+(.15 if sidewalks and sidewalks.covers(point) else .04 if paths_surface and paths_surface.covers(point) else .025)
        yaw=props['yaw_degrees'];orientation=props['direction_source'];nearest_id=None
        if orientation.startswith('estimated:') and road_lines:
            line,nearest_id=road_lines[int(road_tree.nearest(point))]
            distance=line.project(point);a=line.interpolate(max(0,distance-.5));b=line.interpolate(min(line.length,distance+.5))
            yaw=math.degrees(math.atan2(-(b.y-a.y),b.x-a.x))
        p={**props,'base_height_ngf_m':round(z+terrain.origin_ngf,3),'base_height_source':'estimated:shared IGN terrain / generated road-deck surface',
            'yaw_degrees':round(yaw,3),'orientation_road_source_id':nearest_id,
            'occupancy_source':'inferred:one proxy bicycle; no observed occupancy' if kind=='bicycle_rack' else None,
            'signal_state_source':'unlit proxy; no controller or phase observation' if kind=='signal' else None}
        rendered.append(dict(id=props['source_id'],kind='street_'+kind,point_cm=[round(v,3) for v in geo.to_ue(*props['wgs84_centre'],z+terrain.origin_ngf,terrain.origin_ngf)],properties=p))
        height=props['height_m'];scale=[props['crown_diameter_m']/6,props['crown_diameter_m']/6,height/10] if kind=='tree' else [1.,1.,height/dict(lamp=4.5,bench=.92,bin=.95,bicycle_rack=1.1,signal=3.2)[kind]]
        names=dict(tree=['tree_trunk','tree_crown'],lamp=['lamp_metal','lamp_glass'],bench=['bench_wood','bench_metal'],bin=['bin_metal'],bicycle_rack=['bicycle_metal','bicycle_rubber'],signal=['signal_metal','signal_lens'])[kind]
        for name in names:
            batches[name].append(dict(source_id=props['source_id'],position_cm=rendered[-1]['point_cm'],yaw_degrees=round(yaw,3),scale=[round(v,5) for v in scale]))
        by_kind[kind]+=1;source_heights+=props['height_source'].startswith('osm:')
    result=[dict(model=name,instances=items) for name,items in batches.items() if items]
    return result,rendered,dict(mapped_nodes=len(features),rendered=dict(by_kind),skipped=skipped,
        inferred_positions=0,osm_tag_heights=source_heights,placement_policy='Keep OSM points; conflicting points skipped and reported; no silent relocation',
        appearance='Authored generic proxies; dimensions/orientation inferred unless tagged; not surveyed assets')
