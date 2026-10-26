"""Pinned, verified CC0 stone; subsequent builds use the offline cache."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/textures/paris-bridges'


def read(url):
    if not url.startswith(('https://api.polyhaven.com/','https://dl.polyhaven.org/')):raise ValueError('Unexpected bridge texture source')
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AIWorld local bridge development'}),timeout=120) as response:return response.read()


def acquire():
    FOLDER.mkdir(parents=True,exist_ok=True);path=FOLDER/'manifest.json';asset='sandstone_blocks_05'
    if path.exists():manifest=json.loads(path.read_text(encoding='utf-8'))
    else:
        catalog=json.loads(read('https://api.polyhaven.com/files/'+asset));maps={}
        for role,key in [('albedo','Diffuse'),('normal','nor_dx'),('orm','arm')]:
            record=catalog[key]['2k']['jpg'];maps[role]=dict(url=record['url'],md5=record['md5'],file=asset+'_'+role+'.jpg')
        manifest=dict(asset=asset,source_url='https://polyhaven.com/a/'+asset,license='CC0-1.0',license_url='https://polyhaven.com/license',tile_cm=300,resolution=2048,normal_convention='DirectX',maps=maps)
    if manifest['asset']!=asset or manifest['license']!='CC0-1.0':raise ValueError('Unverified bridge texture manifest')
    for info in manifest['maps'].values():
        p=FOLDER/info['file']
        if p.parent!=FOLDER:raise ValueError('Invalid bridge texture path')
        if not p.exists() or hashlib.md5(p.read_bytes()).hexdigest()!=info['md5']:
            data=read(info['url'])
            if hashlib.md5(data).hexdigest()!=info['md5']:raise ValueError('Bridge texture provider checksum mismatch')
            p.write_bytes(data)
        data=p.read_bytes();sha=hashlib.sha256(data).hexdigest()
        if info.get('sha256') and sha!=info['sha256']:raise ValueError('Pinned bridge texture checksum mismatch')
        info.update(sha256=sha,bytes=len(data));print('Verified '+p.name,flush=True)
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':acquire()
