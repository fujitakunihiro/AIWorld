"""Optional IGN BD TOPO enrichment; base OSM/Paris snapshot stays intact."""
import datetime
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from .coordinates import Georeference
from .io import paths,read,sha,write
from .acquire import request,UA

WFS='https://data.geopf.fr/wfs/ows'
LICENCE='https://www.etalab.gouv.fr/licence-ouverte-open-licence/'
CATALOG='https://www.data.gouv.fr/datasets/bd-topo-r'


def verify_buildings(config):
    folder=paths(config)['Raw']/'heights'
    manifest=read(folder/'manifest.json')
    if manifest['projected_crs']!=config['projected_crs'] or any(abs(a-b)>.001 for a,b in zip(manifest['extent_projected_m'],Georeference(config).extent.bounds)):
        raise ValueError('IGN building snapshot does not cover this district configuration')
    for name,item in manifest['files'].items():
        if Path(name).name!=name or sha(folder/name)!=item['sha256']:
            raise ValueError('IGN building snapshot checksum differs: '+name)
    return manifest


def download_buildings(config,offline=False,refresh=False):
    raw=paths(config)['Raw'];folder=raw/'heights'
    if offline or (not refresh and (folder/'manifest.json').exists()):
        return verify_buildings(config)
    raw.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ign-buildings-',dir=raw) as temporary:
        staging=Path(temporary);files={};features=[];total=None;offset=0
        while total is None or offset<total:
            params=dict(service='WFS',version='2.0.0',request='GetFeature',typeNames='BDTOPO_V3:batiment',
                        srsName=config['projected_crs'],bbox=','.join(map(str,Georeference(config).extent.bounds))+','+config['projected_crs'],
                        outputFormat='application/json',count=500,startIndex=offset,sortBy='cleabs')
            url=WFS+'?'+urllib.parse.urlencode(params);page=request(url)
            total=int(page['numberMatched'])
            if total>10000 or not page.get('features') or page.get('numberReturned')!=len(page['features']):
                raise ValueError('Incomplete or unbounded IGN building page')
            crs=page.get('crs',{}).get('properties',{}).get('name','')
            if not crs.endswith('::2154') or config['projected_crs']!='EPSG:2154':
                raise ValueError('IGN building coordinates must be returned in Lambert-93')
            name=f'page-{offset:05d}.json';write(staging/name,page)
            files[name]={'url':url,'sha256':sha(staging/name),'license':'Etalab Open Licence 2.0','license_url':LICENCE}
            features.extend(page['features']);offset+=len(page['features'])
        identifiers=[f['properties']['cleabs'] for f in features]
        if len(features)!=total or len(identifiers)!=len(set(identifiers)):
            raise ValueError('IGN pagination contains duplicate or missing buildings')
        schema_url=WFS+'?'+urllib.parse.urlencode(dict(service='WFS',version='2.0.0',request='DescribeFeatureType',typeNames='BDTOPO_V3:batiment'))
        with urllib.request.urlopen(urllib.request.Request(schema_url,headers={'User-Agent':UA}),timeout=90) as response:
            (staging/'schema.xsd').write_bytes(response.read())
        files['schema.xsd']={'url':schema_url,'sha256':sha(staging/'schema.xsd'),'license':'Etalab Open Licence 2.0','license_url':LICENCE}
        write(staging/'buildings.json',{'type':'FeatureCollection','features':sorted(features,key=lambda f:f['properties']['cleabs']),
                                      'crs':'EPSG:2154','numberMatched':total})
        files['buildings.json']={'url':WFS,'sha256':sha(staging/'buildings.json'),'license':'Etalab Open Licence 2.0',
                                'license_url':LICENCE,'derived_from_pages':sorted(n for n in files if n.startswith('page-'))}
        manifest={'format':1,'source':'IGN BD TOPO / BDTOPO_V3:batiment','catalog_url':CATALOG,
                  'projected_crs':config['projected_crs'],'extent_projected_m':list(Georeference(config).extent.bounds),
                  'acquired_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'features':total,'files':files,
                  'height_semantics':'hauteur is a topographic building/gutter height, not the highest spire; acquisition method and precision retained'}
        write(staging/'manifest.json',manifest)
        folder.mkdir(parents=True,exist_ok=True)
        for name in files:(staging/name).replace(folder/name)
        (staging/'manifest.json').replace(folder/'manifest.json')
    return verify_buildings(config)
