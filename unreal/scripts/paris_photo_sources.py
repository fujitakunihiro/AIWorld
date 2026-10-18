"""Pinned CC0 photographic surfaces and sky, cached for offline UE imports."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'unreal/textures/paris-photo'
USER_AGENT = 'AIWorld-ParisDevelopment/1.0 offline surface integration'
ASSETS = {
    'stone': dict(id='white_plaster_02', tile_cm=100, author='Rob Tuytel',
                  material='M_ParisLimestone', description='Scanned fine plaster grain plus inferred dressed-limestone coursing; not surveyed Paris stone'),
    'paving': dict(id='cobblestone_pavement', tile_cm=250, author='Charlotte Baglioni',
                   material='M_ParisPaving', description='Photographic cobblestone appearance proxy; not a surveyed Paris pavement'),
    'slate': dict(id='roof_slates_02',tile_cm=200,author='Rob Tuytel',
                  material='M_ParisSlatePhotographic',description='Photographic slate roof appearance proxy; not surveyed Notre-Dame roofing'),
    'grass': dict(id='sparse_grass',tile_cm=200,author='Amal Kumar',
                  material='M_ParisGrassPhotographic',description='Photographic grass/soil appearance proxy on mapped parks; not surveyed Paris vegetation'),
    'asphalt': dict(id='asphalt_02',tile_cm=300,author='Rob Tuytel',
                  material='M_ParisAsphaltPhotographic',description='Photographic asphalt at source scale; inferred road finish, not a surveyed Paris pavement'),
    'wood': dict(id='dark_wood',tile_cm=200,author='Dimitrios Savva, Dario Barresi, Rico Cilliers',
                material='M_ParisWood',description='CC0 dark hardwood grain appearance proxy; not sampled from Notre-Dame doors and no claim about their timber species'),
}
MAPS = dict(albedo='Diffuse', normal='nor_dx', orm='arm')
ENVIRONMENT = 'kloppenheim_05_puresky'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def validate(manifest, folder=FOLDER):
    errors = []
    if manifest.get('format') != 'paris_photo_surfaces_v1':
        return ['Unsupported photographic surface manifest']
    keys=[item.get('key') for item in manifest.get('sets',[])]
    if set(keys)!=set(ASSETS) or len(keys)!=len(ASSETS):
        errors.append('Missing, duplicate or unsupported photographic surface set')
    for item in manifest['sets']:
        expected=ASSETS.get(item.get('key'))
        if expected and (item.get('id')!=expected['id'] or item.get('tile_cm')!=expected['tile_cm']):
            errors.append('Surface identity/physical scale differs from the pinned recipe: '+str(item.get('key')))
        if item.get('license') != 'CC0-1.0' or not item.get('source_url', '').startswith('https://polyhaven.com/a/'):
            errors.append('Unverified provenance: ' + item['id'])
        if item.get('surface_layout') != 'ORM' or item.get('normal_convention') != 'DirectX':
            errors.append('Unsafe normal/channel declaration: ' + item['id'])
        for role in MAPS:
            info = item.get('maps', {}).get(role)
            if not info or not isinstance(info.get('file'), str):
                errors.append('Missing photographic role: ' + role);continue
            path = folder / info['file']
            if Path(info['file']).name != info['file']:
                errors.append('Invalid asset filename');continue
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != info['sha256']:
                errors.append('Missing or changed photographic map: ' + info['file'])
            if info.get('srgb') != (role == 'albedo'):
                errors.append('Wrong colour space: ' + role)
    environment = manifest.get('environment')
    if environment:
        if environment.get('license') != 'CC0-1.0' or not environment.get('source_url', '').startswith('https://polyhaven.com/a/'):
            errors.append('Unverified environment provenance')
        path = folder / environment['file']
        if Path(environment['file']).name != environment['file'] or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != environment['sha256']:
            errors.append('Missing or changed environment')
    else:
        errors.append('Missing lighting environment declaration')
    return errors


def acquire():
    FOLDER.mkdir(parents=True, exist_ok=True)
    manifest = dict(format='paris_photo_surfaces_v1', license_url='https://polyhaven.com/license',
                    api_terms='https://github.com/Poly-Haven/Public-API/blob/master/ToS.md',
                    usage='Offline bundled assets; no live API in the game', resolution=2048, sets=[])
    for key, config in ASSETS.items():
        asset = config['id'];metadata_file = FOLDER / (asset + '-files.json')
        if not metadata_file.is_file():
            metadata_file.write_bytes(fetch('https://api.polyhaven.com/files/' + asset))
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        entry = dict(config, key=key, license='CC0-1.0', source_url='https://polyhaven.com/a/' + asset,
                     metadata_url='https://api.polyhaven.com/files/' + asset, surface_layout='ORM',
                     normal_convention='DirectX', photographic=True, paris_site_reference=False, maps={})
        for role, api_name in MAPS.items():
            # Lossless normal/ORM; albedo JPEG is the provider's 2K original.
            fmt = 'jpg' if role == 'albedo' else 'png'
            source = metadata[api_name]['2k'][fmt]
            name = f'{key}_{role}_2k.{fmt}';path = FOLDER / name
            if not path.is_file() or hashlib.md5(path.read_bytes()).hexdigest() != source['md5']:
                data = fetch(source['url'])
                if len(data) != source['size'] or hashlib.md5(data).hexdigest() != source['md5']:
                    raise ValueError('Provider checksum/size mismatch: ' + name)
                temporary = path.with_suffix(path.suffix + '.part');temporary.write_bytes(data);temporary.replace(path)
            entry['maps'][role] = dict(file=name, url=source['url'], bytes=path.stat().st_size,
                                      provider_md5=source['md5'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      srgb=role == 'albedo')
        manifest['sets'].append(entry)
    metadata_file = FOLDER / (ENVIRONMENT + '-files.json')
    if not metadata_file.is_file():
        metadata_file.write_bytes(fetch('https://api.polyhaven.com/files/' + ENVIRONMENT))
    source = json.loads(metadata_file.read_text())['hdri']['4k']['hdr']
    path = FOLDER / (ENVIRONMENT + '_4k.hdr')
    if not path.is_file() or hashlib.md5(path.read_bytes()).hexdigest() != source['md5']:
        data = fetch(source['url'])
        if len(data) != source['size'] or hashlib.md5(data).hexdigest() != source['md5']:
            raise ValueError('Environment provider checksum mismatch')
        path.write_bytes(data)
    manifest['environment'] = dict(id=ENVIRONMENT, source_url='https://polyhaven.com/a/' + ENVIRONMENT,
        authors=['Greg Zaal','Jarod Guest'], license='CC0-1.0', file=path.name, url=source['url'],
        provider_md5=source['md5'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,
        resolution=4096,use='Visible sky, sky lighting and reflection environment; not the surveyed Paris sky')
    if errors := validate(manifest):
        raise ValueError(errors)
    (FOLDER / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def load():
    manifest = json.loads((FOLDER / 'manifest.json').read_text(encoding='utf-8'))
    if errors := validate(manifest):
        raise ValueError(errors)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--ensure', action='store_true',help='Use verified offline cache, acquiring missing originals only when needed')
    args = parser.parse_args()
    if args.download:result=acquire()
    elif args.ensure:
        try:result=load()
        except (OSError,ValueError):result=acquire()
    else:result=load()
    print(json.dumps(dict(sets=len(result['sets']), files=sum(len(x['maps']) for x in result['sets']),
                         bytes=sum(m['bytes'] for x in result['sets'] for m in x['maps'].values()))))
