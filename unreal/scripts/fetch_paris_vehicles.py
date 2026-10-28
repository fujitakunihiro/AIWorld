"""Restore the verified CC0 archive; cached acquisition works offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/paris-vehicles'


def main():
    manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    if manifest['license']!='CC0-1.0':raise ValueError('Unexpected vehicle license')
    raw=FOLDER/'Raw';raw.mkdir(parents=True,exist_ok=True)
    def verified(name):
        file=raw/name
        return file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==manifest['files'][name]['sha256']
    if all(verified(n) for n in ('bmw.obj','bmw.mtl')):
        print('PARIS_VEHICLE_SOURCE_CACHED');return
    archive=raw/'bmw.zip'
    if not verified('bmw.zip'):
        temporary=archive.with_suffix('.part')
        subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--retry','2',manifest['download_url'],'--output',str(temporary)],check=True)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=manifest['files']['bmw.zip']['sha256']:
            raise ValueError('Vehicle archive changed; review source and license before updating the pin')
        temporary.replace(archive)
    with zipfile.ZipFile(archive) as z:
        for name in ('bmw.obj','bmw.mtl'):
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=manifest['files'][name]['sha256']:raise ValueError('Vehicle member changed')
            (raw/name).write_bytes(data)
    print('PARIS_VEHICLE_SOURCE_READY')


if __name__=='__main__':main()
