"""Acquire the pinned CC0 source, with an offline cache and checksum."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/paris-cruise'


def main():
    manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    if manifest['license']!='CC0-1.0':raise ValueError('Cruise source license differs from the reviewed asset')
    raw=FOLDER/'Raw';raw.mkdir(parents=True,exist_ok=True);target=raw/manifest['file']
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==manifest['sha256']:
        print('PARIS_CRUISE_SOURCE_CACHED');return
    part=target.with_suffix('.part')
    subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--retry','2',manifest['download_url'],'--output',str(part)],check=True)
    if hashlib.sha256(part.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Cruise model changed: review source and license before updating the pin')
    part.replace(target);print('PARIS_CRUISE_SOURCE_READY')


if __name__=='__main__':main()
