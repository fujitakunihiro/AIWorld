"""Snapshot public GIS services. Generation never calls these services."""
import datetime
import gzip
import json
import tempfile
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .coordinates import Georeference
from .io import paths, read, sha, write

PARIS = 'https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/volumesbatisparis'
IGN = 'https://data.geopf.fr/altimetrie'
UA = 'AIWorld-ParisDigitalTwin/0.1 (local GIS research; small district snapshot)'


def osm_api_snapshot(bounds, raw, register):
    """Official OSM map API fallback; retain the original XML beside parsed JSON."""
    elements = {}
    def get_xml(url, name):
        req = urllib.request.Request(url,headers={'User-Agent':UA})
        with urllib.request.urlopen(req,timeout=90) as response:
            data=response.read()
        name += '.gz'
        raw.mkdir(parents=True,exist_ok=True);(raw/name).write_bytes(gzip.compress(data,mtime=0))
        register[name]={'url':url,'sha256':sha(raw/name),'license':'ODbL-1.0','license_url':'https://www.openstreetmap.org/copyright','archive':'gzip; original XML bytes unchanged on decompression'}
        root=ET.fromstring(data)
        for e in root:
            if e.tag not in ['node','way','relation']:continue
            item={'type':e.tag,'id':int(e.attrib['id']),
                  'tags':{t.attrib['k']:t.attrib['v'] for t in e.findall('tag')},
                  'version':e.attrib.get('version'),'timestamp':e.attrib.get('timestamp')}
            if e.tag=='node':item.update(lon=float(e.attrib['lon']),lat=float(e.attrib['lat']))
            elif e.tag=='way':item['nodes']=[int(n.attrib['ref']) for n in e.findall('nd')]
            else:item['members']=[{'type':m.attrib['type'],'ref':int(m.attrib['ref']),'role':m.attrib.get('role','')} for m in e.findall('member')]
            elements[(e.tag,item['id'])]=item
    url='https://api.openstreetmap.org/api/0.6/map?bbox='+','.join(f'{v:.9f}' for v in bounds)
    get_xml(url,'osm-map.xml')
    def wanted(tags):
        return (tags.get('building') not in [None,'no'] or tags.get('highway') or
                tags.get('natural')=='water' or tags.get('waterway')=='riverbank' or
                tags.get('leisure') in ['park','garden'] or tags.get('place')=='square')
    relations=[e for e in elements.values() if e['type']=='relation' and wanted(e['tags']) and
               any(('way',m['ref']) not in elements for m in e['members'] if m['type']=='way')]
    if len(relations)>40:raise ValueError('Too many full relation requests; reduce district extent')
    for e in relations:
        if any(('way',m['ref']) not in elements for m in e['members'] if m['type']=='way'):
            get_xml(f"https://api.openstreetmap.org/api/0.6/relation/{e['id']}/full",f"osm-relation-{e['id']}.xml")
    def geometry(way):
        return [{k:elements[('node',n)][k] for k in ['lat','lon']} for n in way['nodes'] if ('node',n) in elements]
    selected=[]
    for e in elements.values():
        if e['type']=='node' or not wanted(e['tags']):continue
        if e['type']=='way':e['geometry']=geometry(e)
        else:
            for m in e['members']:
                if m['type']=='way' and ('way',m['ref']) in elements:m['geometry']=geometry(elements[('way',m['ref'])])
        selected.append(e)
    return {'version':0.6,'generator':'OSM official map API; XML archived unchanged','elements':sorted(selected,key=lambda e:(e['type'],e['id']))},url


def request(url, body=None, form=False):
    headers = {'User-Agent':UA, 'Accept':'application/json'}
    if body is not None:
        body = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=100) as response:
        return json.load(response)


def verify_cache(config):
    raw = paths(config)['Raw']
    manifest = read(raw/'manifest.json')
    for name, item in manifest['files'].items():
        if sha(raw/name) != item['sha256']:
            raise ValueError('Raw snapshot checksum differs: '+name)
    requested=Georeference(config).bounds_wgs84()
    if max(abs(a-b) for a,b in zip(requested,manifest['bounds_wgs84']))>1e-9:
        raise ValueError('District extent differs from downloaded coverage; acquire a new snapshot')
    if len(read(raw/'ign_elevation.json')['elevations'])!=(config['elevation_grid_steps']+1)**2:
        raise ValueError('Requested elevation sampling differs from cached samples')
    if (raw/'heights/manifest.json').exists():
        from .building_source import verify_buildings
        extra=verify_buildings(config)
        manifest['files'].update({'heights/'+name:item for name,item in extra['files'].items()})
        manifest['files']['heights/manifest.json']={'sha256':sha(raw/'heights/manifest.json'),'url':extra['catalog_url'],'license':'Etalab Open Licence 2.0'}
    return manifest


def download(config, offline=False, refresh=False):
    raw = paths(config)['Raw']
    if offline or (not refresh and (raw/'manifest.json').exists()):
        return verify_cache(config)
    raw.parent.mkdir(parents=True,exist_ok=True)
    # A network failure must leave the last complete, reproducible cache intact.
    with tempfile.TemporaryDirectory(prefix='paris-download-',dir=raw.parent) as temporary:
        staging=Path(temporary).resolve()
        if staging.parent != raw.parent.resolve():
            raise ValueError('Download staging directory escaped the raw-data root')
        manifest=_download_snapshot(config,staging)
        raw.mkdir(parents=True,exist_ok=True)
        for name in manifest['files']:
            (staging/name).replace(raw/name)
        (staging/'manifest.json').replace(raw/'manifest.json')
        return manifest


def _download_snapshot(config,raw):
    geo = Georeference(config)
    west, south, east, north = geo.bounds_wgs84()
    bbox = f'{south:.9f},{west:.9f},{north:.9f},{east:.9f}'
    query = f'''[out:json][timeout:90];(
way["building"]({bbox});relation["building"]({bbox});
way["highway"]({bbox});way["natural"="water"]({bbox});relation["natural"="water"]({bbox});
way["waterway"="riverbank"]({bbox});relation["waterway"="riverbank"]({bbox});
way["leisure"~"park|garden"]({bbox});way["place"="square"]({bbox});
);out geom;'''
    files = {}
    def save(name, data, source, license_name, license_url, extra=None):
        write(raw/name, data)
        files[name] = {'sha256':sha(raw/name),'url':source,'license':license_name,
                       'license_url':license_url, **(extra or {})}
    errors = []
    for endpoint in ([] if config.get('osm_provider')=='official_map_api' else config['overpass_endpoints']):
        try:
            osm = request(endpoint, {'data':query}, form=True)
            if 'remark' in osm or not osm.get('elements'):
                raise ValueError('Incomplete Overpass response: '+str(osm.get('remark','empty')))
            save('osm.json',osm,endpoint,'ODbL-1.0','https://www.openstreetmap.org/copyright',{'query':query,'osm_timestamp':osm.get('osm3s',{}).get('timestamp_osm_base')})
            break
        except Exception as error:
            errors.append(endpoint+': '+str(error))
    else:
        osm, url = osm_api_snapshot((west,south,east,north),raw,files)
        save('osm.json',osm,url,'ODbL-1.0','https://www.openstreetmap.org/copyright',{'conversion':'XML to JSON with original IDs, tags, member geometry; original XML retained'})

    metadata = request(PARIS)
    meta = metadata['metas']['default']
    save('paris_metadata.json',metadata,PARIS,meta['license'],meta['license_url'])
    wkt = f'POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))'
    records, offset, count = [], 0, None
    while count is None or len(records) < count:
        params = {'where':f"intersects(geom, geom'{wkt}')",'limit':100,'offset':offset,'order_by':'n_sq_vb'}
        page = request(PARIS+'/records?'+urllib.parse.urlencode(params))
        count = page['total_count']
        if count > 10000:
            raise ValueError('Paris extent returned too many records; refuse an unbounded download')
        records.extend(page['results'])
        if not page['results'] and len(records) < count:
            raise ValueError('Incomplete Paris pagination')
        offset += 100
    save('paris_volumes.json',{'records':records,'total_count':count,'where':params['where']},PARIS+'/records',meta['license'],meta['license_url'],{'dataset_modified':meta['modified']})

    resource = request(IGN+'/resources/ign_rge_alti_wld')
    save('ign_resource.json',resource,IGN+'/resources/ign_rge_alti_wld','Etalab Open Licence 2.0','https://www.etalab.gouv.fr/licence-ouverte-open-licence/')
    points = []
    x0,y0,x1,y1 = geo.extent.bounds
    steps = config['elevation_grid_steps']
    for iy in range(steps+1):
        for ix in range(steps+1):
            points.append(geo.inverse.transform(x0+(x1-x0)*ix/steps,y0+(y1-y0)*iy/steps))
    body = {'lon':'|'.join(f'{p[0]:.9f}' for p in points),'lat':'|'.join(f'{p[1]:.9f}' for p in points),
            'resource':'ign_rge_alti_wld','delimiter':'|','measures':'true','zonly':'false'}
    elevation = request(IGN+'/1.0/calcul/alti/rest/elevation.json',body)
    if len(elevation.get('elevations',[])) != len(points):
        raise ValueError('Incomplete IGN elevation grid')
    save('ign_elevation.json',elevation,IGN+'/1.0/calcul/alti/rest/elevation.json','Etalab Open Licence 2.0','https://www.etalab.gouv.fr/licence-ouverte-open-licence/',{'request':body,'grid_spacing_m':(x1-x0)/steps,'vertical_datum':'NGF-IGN69; orthometric, not WGS84 ellipsoid'})
    manifest = {'format':1,'district_id':config['district_id'],'bounds_wgs84':[west,south,east,north],
                'acquired_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'config_sha256':__import__('hashlib').sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),
                'files':files,'failed_osm_endpoints':errors}
    write(raw/'manifest.json',manifest)
    return manifest
