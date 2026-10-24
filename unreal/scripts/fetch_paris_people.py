"""Fetch a pinned, MIT-licensed subset of Microsoft Rocketbox. Offline re-use is supported."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'unreal/assets/paris-people'
COMMIT = '0943055db6ec570bcef9f2c8b41c9e5467c808f9'
BASE = f'https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/{COMMIT}/'
AVATARS = [('Male_Adult_01', 'm002', 'm'), ('Female_Adult_01', 'f001', 'f')]


def acquire(offline=False):
    DEST.mkdir(parents=True, exist_ok=True)
    files = ['LICENSE.md']
    for name, prefix, sex in AVATARS:
        folder = f'Assets/Avatars/Adults/{name}'
        files.append(f'{folder}/Export/{name}.fbx')
        files += [f'{folder}/Textures/{prefix}_{part}_{channel}.tga'
                  for part in ['head', 'body'] for channel in ['color', 'normal', 'specular']]
        files.append(f'{folder}/Textures/{prefix}_opacity_color.tga')
        files += [f'Assets/Animations/all_animations_max_motextr_{kind}/{sex}_{clip}.max.fbx'
                  for kind, clip in [('xy', 'walk_neutral_01'), ('xy', 'run_neutral_01'), ('static', 'idle_breathe_01'), ('static', 'sit_chair_breathe_01')]]
    prior_path = DEST / 'sources.json'
    prior = {e['path']: e for e in json.loads(prior_path.read_text())['files']} if prior_path.exists() else {}

    def fetch(relative):
        target = DEST / 'Raw' / relative
        url = BASE + urllib.parse.quote(relative)
        if not target.exists():
            if offline:
                raise FileNotFoundError('Offline source is missing: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            data = urllib.request.urlopen(url, timeout=90).read()
            if data.startswith(b'version https://git-lfs'):
                raise RuntimeError('Unexpected LFS pointer: ' + relative)
            target.write_bytes(data)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if relative in prior and digest != prior[relative]['sha256']:
            raise RuntimeError('Source hash mismatch: ' + relative)
        return dict(path=relative, url=url, sha256=digest, bytes=target.stat().st_size)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        sources = list(pool.map(fetch, files))
    manifest = dict(schema_version=1, commit=COMMIT, license='MIT',
                    repository='https://github.com/microsoft/Microsoft-Rocketbox',
                    avatars=[dict(name=n, texture_prefix=p, animation_prefix=s) for n, p, s in AVATARS], files=sources)
    prior_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (DEST / 'LICENSE.md').write_bytes((DEST / 'Raw/LICENSE.md').read_bytes())
    print(f'PARIS_PEOPLE_SOURCES_READY {len(sources)} files / {sum(e["bytes"] for e in sources)} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    acquire(parser.parse_args().offline)
