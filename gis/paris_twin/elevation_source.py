"""Optional dense IGN terrain snapshot; never replaces the initial GIS cache."""
import datetime
import math
import tempfile
from pathlib import Path
from .coordinates import Georeference
from .io import paths, read, sha, write
from .acquire import request, IGN

URL = IGN + '/1.0/calcul/alti/rest/elevation.json'
LICENSE = 'https://www.etalab.gouv.fr/licence-ouverte-open-licence/'


def verify_terrain(config):
    folder = paths(config)['Raw'] / 'terrain'
    manifest = read(folder / 'manifest.json')
    geo = Georeference(config)
    if (manifest['grid_steps'] != config.get('terrain_grid_steps', 40) or
            manifest['origin_wgs84'] != config['origin_wgs84'] or
            any(abs(a-b) > .001 for a,b in zip(manifest['extent_projected_m'], geo.extent.bounds))):
        raise ValueError('IGN terrain snapshot differs from the requested extent/grid/origin')
    for name, item in manifest['files'].items():
        if Path(name).name != name or sha(folder/name) != item['sha256']:
            raise ValueError('IGN terrain snapshot checksum differs: ' + name)
    samples = read(folder/'elevations.json')['elevations']
    if len(samples) != (manifest['grid_steps']+1)**2:
        raise ValueError('Incomplete cached IGN terrain grid')
    return manifest


def download_terrain(config, offline=False, refresh=False):
    raw = paths(config)['Raw']; folder = raw/'terrain'
    if offline or (not refresh and (folder/'manifest.json').exists()):
        return verify_terrain(config)
    geo = Georeference(config); steps = config.get('terrain_grid_steps', 40)
    if not 2 <= steps <= 80:
        raise ValueError('Terrain grid must have 2..80 steps')
    x0,y0,x1,y1 = geo.extent.bounds
    points = [geo.inverse.transform(x0+(x1-x0)*ix/steps, y0+(y1-y0)*iy/steps)
              for iy in range(steps+1) for ix in range(steps+1)]
    # Always sample the same shared origin, even for adjoining districts.
    all_points = points + [config['origin_wgs84']]
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ign-terrain-', dir=raw) as temp:
        staging = Path(temp); files = {}; records = []
        for offset in range(0, len(all_points), 400):
            batch = all_points[offset:offset+400]
            body = dict(lon='|'.join(f'{p[0]:.9f}' for p in batch),
                        lat='|'.join(f'{p[1]:.9f}' for p in batch), resource='ign_rge_alti_wld',
                        delimiter='|', measures='true', zonly='false')
            result = request(URL, body); samples = result.get('elevations', [])
            if len(samples) != len(batch):
                raise ValueError('Incomplete IGN terrain response')
            for expected, sample in zip(batch, samples):
                if (not math.isfinite(sample['z']) or sample['z'] <= -9999 or
                        abs(sample['lon']-expected[0]) > 1e-7 or abs(sample['lat']-expected[1]) > 1e-7):
                    raise ValueError('Invalid IGN terrain coordinate/elevation')
            name = f'page-{offset:05d}.json'; write(staging/name, result)
            files[name] = dict(url=URL, request=body, sha256=sha(staging/name),
                               license='Etalab Open Licence 2.0', license_url=LICENSE)
            records.extend(samples)
        write(staging/'elevations.json', dict(elevations=records[:-1], origin=records[-1]))
        files['elevations.json'] = dict(url=URL, sha256=sha(staging/'elevations.json'),
                license='Etalab Open Licence 2.0', license_url=LICENSE,
                derived_from_pages=sorted(files))
        manifest = dict(format=1, source='IGN RGE ALTI point sampling', grid_steps=steps,
                grid_spacing_m=(x1-x0)/steps, extent_projected_m=list(geo.extent.bounds),
                projected_crs=config['projected_crs'], origin_wgs84=config['origin_wgs84'],
                origin_elevation_ngf_m=records[-1]['z'], vertical_datum='NGF-IGN69',
                acquired_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), files=files,
                sampling_is_not_dem_resolution=True,
                documentation_url='https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/calcul-altimetrique/')
        write(staging/'manifest.json', manifest)
        folder.mkdir(parents=True, exist_ok=True)
        for name in files: (staging/name).replace(folder/name)
        (staging/'manifest.json').replace(folder/'manifest.json')
    return verify_terrain(config)
