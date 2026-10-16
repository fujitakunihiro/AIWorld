"""Acquire an openly published CC BY facade point cloud for asset evaluation.

This is not a production-ready PBR mesh. No automatic scene replacement occurs.
The public Zenodo file has a published byte count and MD5; both are verified.
"""
import hashlib
import json
from pathlib import Path
import urllib.request
import time

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/notre-dame-facade'
UID='50deeb164f324d1c8607bafa67f948b9'
URL=f'https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-093/{UID}.glb'
EXPECTED_BYTES=405027212
EXPECTED_MD5='6d5d5ae624614283ddc99a5cfc3d3452'


def digest(path,algorithm):
    with path.open('rb') as stream:return hashlib.file_digest(stream,algorithm).hexdigest()


def acquire():
    FOLDER.mkdir(parents=True,exist_ok=True)
    path=FOLDER/(UID+'.glb')
    if not path.is_file():
        part=path.with_suffix('.part')
        deadline=time.monotonic()+180
        request=urllib.request.Request(URL,headers={'User-Agent':'AIWorld-ParisAssetResearch/1.0'})
        with urllib.request.urlopen(request,timeout=30) as response,part.open('wb') as out:
            # read1 returns available data instead of waiting for an entire large
            # block; enforce the wall-clock bound even on a trickling connection.
            read=getattr(response,'read1',response.read)
            while block:=read(1024*1024):
                out.write(block)
                if time.monotonic()>deadline:raise TimeoutError('Facade download exceeded three minutes; incomplete data was not accepted')
        if part.stat().st_size!=EXPECTED_BYTES or digest(part,'md5')!=EXPECTED_MD5:
            raise ValueError('Public facade point cloud differs from the pinned Zenodo object')
        part.replace(path)
    if path.stat().st_size!=EXPECTED_BYTES or digest(path,'md5')!=EXPECTED_MD5:
        raise ValueError('Cached point cloud differs from the source checksum')
    record=dict(format='paris_facade_point_cloud_v1',uid=UID,
        title='Notre Dame Paris Facade - Hi Res Point Cloud',
        author='UC San Diego - Digital Media Lab (embedded credit); current Sketchfab account CHEI - UC San Diego',
        source_url=f'https://sketchfab.com/3d-models/notre-dame-paris-facade-hi-res-point-cloud-{UID}',
        record_url='https://zenodo.org/records/10363984',file_url=URL,
        license='CC-BY-4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
        published='2019-05-06',description='Reconstruction from 105 Flickr and Wikimedia tourist photos; historical appearance, not the 2024 restoration.',
        file=path.name,bytes=EXPECTED_BYTES,md5=EXPECTED_MD5,
        sha256=digest(path,'sha256'),
        acceptance='Research candidate: points only; no claim of surface reconstruction, PBR or surveyed georegistration')
    (FOLDER/'manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record),flush=True)


if __name__=='__main__':acquire()
