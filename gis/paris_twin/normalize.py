import math
import re
from shapely import make_valid
from shapely.geometry import LineString, Polygon, mapping, shape
from shapely.ops import polygonize, transform, unary_union
from shapely.strtree import STRtree
from .acquire import verify_cache
from .coordinates import Georeference
from .io import paths, read, write, generation_metadata


def polygonal(geometry):
    if geometry.is_empty:
        return None
    geometry = make_valid(geometry)
    if geometry.geom_type in ['Polygon','MultiPolygon']:
        return geometry
    parts = [p for p in getattr(geometry,'geoms',[]) if p.geom_type in ['Polygon','MultiPolygon']]
    return unary_union(parts) if parts else None


def osm_geometry(element, polygon=False):
    if element['type'] == 'relation':
        rings = {'outer':[],'inner':[]}
        for member in element.get('members',[]):
            coords = [(p['lon'],p['lat']) for p in member.get('geometry',[]) if p]
            if len(coords) > 1:
                rings['inner' if member.get('role') == 'inner' else 'outer'].append(LineString(coords))
        outer = list(polygonize(unary_union(rings['outer'])))
        if not outer:
            return None
        result = unary_union(outer)
        holes = list(polygonize(unary_union(rings['inner'])))
        return polygonal(result.difference(unary_union(holes))) if holes else polygonal(result)
    coords = [(p['lon'],p['lat']) for p in element.get('geometry',[]) if p]
    if len(coords) < (4 if polygon else 2):
        return None
    if polygon:
        return polygonal(Polygon(coords)) if coords[0] == coords[-1] else None
    return LineString(coords)


def positive_number(value):
    if value is None:
        return None
    match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(m|metres|meters|ft|feet)?\s*',str(value))
    if not match:
        return None
    number = float(match[1].replace(',','.'))
    return number*.3048 if match[2] in ['ft','feet'] else number


def road_width(tags, config):
    width = positive_number(tags.get('width'))
    if width and .5 <= width <= 50:
        return width, 'osm:width', False
    lanes = positive_number(tags.get('lanes'))
    if lanes and lanes <= 10:
        return max(3,lanes*3), 'estimated:lanes*3m', True
    return config['road_width_defaults_m'].get(tags.get('highway'),6), 'estimated:highway_class', True


def normalize(config):
    manifest = verify_cache(config)
    p = paths(config)
    geo = Georeference(config)
    osm = read(p['Raw']/'osm.json')['elements']
    volumes, rows = [], []
    for row in read(p['Raw']/'paris_volumes.json')['records']:
        g = polygonal(transform(geo.forward.transform,shape(row['geom']['geometry'])))
        if g and g.intersects(geo.extent):
            volumes.append(g); rows.append(row)
    tree = STRtree(volumes)
    relation_building_members = {m['ref'] for e in osm if e['type']=='relation' and e.get('tags',{}).get('building') not in [None,'no'] for m in e.get('members',[]) if m['type']=='way'}
    layers = {key:[] for key in ['buildings','roads','water','parks','squares','elevations','paris_volumes']}
    issues = []
    for e in sorted(osm,key=lambda e:(e['type'],e['id'])):
        tags = e.get('tags',{})
        category = None
        if tags.get('building') not in [None,'no']:
            if e['type']=='way' and e['id'] in relation_building_members:
                continue
            category = 'buildings'
        elif tags.get('natural')=='water' or tags.get('waterway')=='riverbank':
            category = 'water'
        elif tags.get('highway'):
            category = 'squares' if tags.get('area')=='yes' else 'roads'
        elif tags.get('leisure') in ['park','garden']:
            category = 'parks'
        elif tags.get('place')=='square':
            category = 'squares'
        if not category:
            continue
        source_id = f"osm/{e['type']}/{e['id']}"
        g = osm_geometry(e,category!='roads')
        if not g:
            issues.append({'id':source_id,'issue':'unclosed_or_incomplete_geometry'});continue
        g = transform(geo.forward.transform,g)
        original = g
        g = g.intersection(geo.extent)
        if category != 'roads':
            g = polygonal(g)
        if g is None or g.is_empty:
            continue
        centre = original.representative_point()
        props = {'source_id':source_id,'source':'OpenStreetMap','source_url':f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
                 'source_snapshot':'osm.json','source_license':'ODbL-1.0','name':tags.get('name',''),
                 'tags':tags,'wgs84_centre':list(geo.inverse.transform(centre.x,centre.y)),
                 'clipped_at_context_boundary':not g.equals(original),'source_geometry_projected':mapping(original)}
        if category=='buildings':
            height = positive_number(tags.get('height')) or positive_number(tags.get('building:height'))
            height_source = 'osm:height_tag' if height else None
            height_kind = 'source_declared_unverified' if height else 'estimated'
            matches = sorted([(volumes[int(i)].intersection(original).area,int(i)) for i in tree.query(original)],reverse=True)
            matches = [(a,i) for a,i in matches if a > original.area*.03]
            props['paris_volume_ids'] = sorted({str(rows[i]['n_sq_vb']) for a,i in matches})
            levels = positive_number(tags.get('building:levels'))
            if not height and levels:
                height, height_source = levels*config['estimated_floor_height_m'], 'estimated:osm_building_levels'
            if not height and matches:
                row = rows[matches[0][1]]
                floors_above_ground = row.get('h_et_max')
                if floors_above_ground is not None and floors_above_ground >= 0:
                    height = (floors_above_ground+1)*config['estimated_floor_height_m']
                    height_source = 'estimated:paris_h_et_max_plus_ground_floor'
            if not height:
                height, height_source = config['default_building_height_m'],'estimated:district_default'
            props.update(height_m=round(height,3),height_source=height_source,height_kind=height_kind,
                         height_measured_missing=True,reproduction_level='L1',
                         roof_form_source='preview:flat_roof_not_surveyed',facade_source='preview:no_facade_claim')
        elif category=='roads':
            width, source, estimated = road_width(tags,config)
            props.update(width_m=width,width_source=source,width_estimated=estimated,
                         osm_node_ids=e.get('nodes',[]),
                         bridge=tags.get('bridge') not in [None,'no'],tunnel=tags.get('tunnel') not in [None,'no'],
                         layer=int(tags.get('layer',0)) if str(tags.get('layer','0')).lstrip('-').isdigit() else 0)
        elif category=='water':
            role='river' if tags.get('water')=='river' or tags.get('waterway')=='riverbank' else 'basin' if tags.get('water')=='basin' or tags.get('amenity')=='fountain' else 'waterbody'
            props.update(water_role=role,water_level_source='preview:visual_estimate_not_gauge',water_level_local_m=-4 if role=='river' else .12)
        layers[category].append({'geometry':mapping(g),'properties':props})
    for g,row in zip(volumes,rows):
        layers['paris_volumes'].append({'geometry':mapping(g.intersection(geo.extent)),
            'properties':{'source_id':f"paris/volume/{row['n_sq_vb']}",'source':'Ville de Paris',
                          'source_url':'https://opendata.paris.fr/explore/dataset/volumesbatisparis/',
                          'source_snapshot':'paris_volumes.json','source_license':'ODbL-1.0',
                          'h_et_max_floors':row.get('h_et_max'),'nb_pl':row.get('nb_pl'),'source_type':row.get('l_src'),
                          'height_m':None,'height_measured_missing':True,'updated':row.get('d_maj')}})
    elevation_snapshot='terrain/elevations.json' if (p['Raw']/'terrain/elevations.json').exists() else 'ign_elevation.json'
    for i,point in enumerate(read(p['Raw']/elevation_snapshot)['elevations']):
        if not math.isfinite(point['z']) or point['z'] <= -9999:
            issues.append({'id':f'ign/elevation/{i}','issue':'elevation_nodata'});continue
        e,n = geo.forward.transform(point['lon'],point['lat'])
        layers['elevations'].append({'geometry':{'type':'Point','coordinates':[e,n]},
            'properties':{'source_id':f'ign/elevation/{i}','source':'IGN RGE ALTI','source_url':manifest['files']['ign_elevation.json']['url'],
                          'source_snapshot':elevation_snapshot,'source_license':'Etalab Open Licence 2.0',
                          'height_ngf_m':point['z'],'accuracy':point.get('acc'),'measures':point.get('measures',[])}})
    for layer in layers.values():
        layer.sort(key=lambda f:f['properties']['source_id'])
    from .building_heights import enrich_buildings
    enrich_buildings(config,p['Raw'],layers,polygonal)
    result = {'format':1,'generation':generation_metadata(config),'district_id':config['district_id'],'projected_crs':geo.crs.to_string(),
              'origin_wgs84':config['origin_wgs84'],'origin_projected_m':list(geo.origin),
              'district_center_wgs84':config.get('district_center_wgs84',config['origin_wgs84']),
              'extent_projected_m':list(geo.extent.bounds),'core_size_m':config['core_size_m'],
              'context_buffer_m':config['context_buffer_m'],'quality_size_m':config['quality_size_m'],
              'quality_center_wgs84':config['quality_center_wgs84'],
              'raw_checksums':{n:d['sha256'] for n,d in manifest['files'].items()},'layers':layers,'issues':issues}
    write(p['Processed']/'district.json',result)
    features = []
    for name,layer in layers.items():
        for feature in layer:
            props = {k:v for k,v in feature['properties'].items() if k!='source_geometry_projected'}
            features.append({'type':'Feature','geometry':mapping(transform(geo.inverse.transform,shape(feature['geometry']))),
                             'properties':{**props,'layer':name}})
    write(p['Processed']/'features.wgs84.geojson',{'type':'FeatureCollection','features':features})
    return result
