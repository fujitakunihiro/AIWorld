"""Acquire a single CC0 Poly Haven tree with recorded, verified source files."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/paris-nature'
ASSET='island_tree_01'
AGENT='AIWorld/1.0 (local Unreal photoreal development)'


def fetch(url):
    if not url.startswith(('https://api.polyhaven.com/','https://dl.polyhaven.org/')):raise ValueError('Unexpected asset host')
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':AGENT}),timeout=120)


def acquire():
    FOLDER.mkdir(parents=True,exist_ok=True)
    pinned=FOLDER/'manifest.json'
    if pinned.exists():
        manifest=json.loads(pinned.read_text(encoding='utf-8'))
        if manifest['asset']!=ASSET or manifest['license']!='CC0-1.0':raise ValueError('Unexpected pinned nature manifest')
        files=manifest['files']
    else:
        with fetch('https://api.polyhaven.com/files/'+ASSET) as response:catalog=json.load(response)
        source=catalog['gltf']['2k']['gltf']
        files={ASSET+'_2k.gltf':{k:v for k,v in source.items() if k!='include'},**source['include']}
        files['textures/'+ASSET+'_leaves_alpha_2k.png']=catalog['leaves_alpha']['2k']['png']
    records={}
    for name,info in files.items():
        path=FOLDER/name
        if not path.resolve().is_relative_to(FOLDER.resolve()):raise ValueError('Asset path escapes source directory')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists() or hashlib.file_digest(path.open('rb'),'md5').hexdigest()!=info['md5']:
            with fetch(info['url']) as response,path.with_suffix(path.suffix+'.part').open('wb') as target:
                while data:=response.read(1024*1024):target.write(data)
            temp=path.with_suffix(path.suffix+'.part')
            if hashlib.file_digest(temp.open('rb'),'md5').hexdigest()!=info['md5']:raise ValueError('Source checksum mismatch: '+name)
            temp.replace(path)
        digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
        if info.get('sha256') and digest!=info['sha256']:raise ValueError('Pinned source SHA-256 mismatch: '+name)
        records[name]=dict(url=info['url'],bytes=path.stat().st_size,md5=info['md5'],sha256=digest)
        print('Verified '+name,flush=True)
    manifest=dict(format='paris_photo_nature_v1',asset=ASSET,source_url='https://polyhaven.com/a/'+ASSET,
        license='CC0-1.0',license_url='https://polyhaven.com/license',maps_resolution=2048,files=records,
        appearance_provenance='Broadleaf appearance proxy; not identification of actual Paris tree species; mapped OSM locations retained')
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':acquire()
