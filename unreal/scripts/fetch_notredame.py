"""Fetch one CC BY 4.0 Notre-Dame asset from Ai2's licensed Objaverse mirror."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/notre-dame'
UID='b5808186c49a451bbf815fbccdb727a3'
URL='https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-115/'+UID+'.glb'


def acquire():
    source=json.loads((FOLDER/'source-metadata.json').read_text(encoding='utf-8'))
    if source['uid']!=UID or source['license']!='by' or source['user']['username']!='francois.bouille':
        raise ValueError('Unexpected identity/license in archived model metadata')
    path=FOLDER/'notre-dame.glb'
    if not path.is_file():
        request=urllib.request.Request(URL,headers={'User-Agent':'AIWorld-ParisAssetResearch/1.0'})
        with urllib.request.urlopen(request,timeout=120) as response, path.with_suffix('.part').open('wb') as out:
            while block:=response.read(1024*1024):out.write(block)
        path.with_suffix('.part').replace(path)
    record=dict(format='paris_notredame_source_v1',uid=UID,author='francois.bouille',
        title='Notre-Dame de Paris',license='CC-BY-4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
        original_url='https://sketchfab.com/3d-models/notre-dame-de-paris-'+UID,
        dataset_url='https://huggingface.co/datasets/allenai/objaverse',file_url=URL,
        database_license='ODC-By-1.0',file=path.name,bytes=path.stat().st_size,
        sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
        modification='To be inspected; no architectural acceptance or source survey accuracy assumed')
    manifest=FOLDER/'manifest.json'
    if manifest.is_file() and json.loads(manifest.read_text())['sha256']!=record['sha256']:
        raise ValueError('Downloaded source changed from recorded hash')
    manifest.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true',required=True)
    parser.parse_args();acquire()
