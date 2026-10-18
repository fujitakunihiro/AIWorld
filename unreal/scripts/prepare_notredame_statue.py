"""Acquire and prepare the licensed Portal of the Virgin scan for personal NC use.

The original is preserved. Only the upper canopy is cropped; unseen geometry is
never synthesized. Placement/scale are provisional, not measured registration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import urllib.request
import numpy as np

from inspect_notredame import primitives, image_size

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT/'unreal/assets/notre-dame-sculptures'
UID = 'b5bbdc379daa4ee19e3775bb179dbcc1'
SHA = '73c16fb28067adc8480f8719192329b66ac8b84b1ceff8193d8a0245923a1b54'
URL = 'https://huggingface.co/datasets/allenai/objaverse/resolve/main/glbs/000-090/'+UID+'.glb'
SOURCE = 'https://sketchfab.com/3d-models/notre-dame-de-paris-virgin-mary-'+UID
UPPER_CROP = 11.0
HEIGHT_M = 4.4
# glTF right-handed X-right/Y-up/Z-out -> facade X-left/Y-in/Z-up.
# A reflection is required for UE's handedness. Frame +X is geographic north
# and viewer-left on this west facade, not screen-right.
ORIENTATION = np.array([[-1.,0,0],[0,0,-1.],[0,1.,0]])


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def acquire():
    FOLDER.mkdir(parents=True,exist_ok=True)
    target=FOLDER/(UID+'.glb')
    if not target.exists():
        request=urllib.request.Request(URL,headers={'User-Agent':'AIWorld-ParisAssetResearch/1.0'})
        part=target.with_suffix('.part')
        with urllib.request.urlopen(request,timeout=180) as response,part.open('wb') as stream:
            while block:=response.read(1024*1024):stream.write(block)
        if sha(part)!=SHA:raise ValueError('Downloaded sculpture differs from the reviewed original')
        part.replace(target)
    return target


def generate(path=None):
    path=path or FOLDER/(UID+'.glb')
    if sha(path)!=SHA:raise ValueError('Original sculpture SHA256 mismatch')
    data=path.read_bytes()
    if struct.unpack_from('<4sII',data)!=(b'glTF',2,len(data)):raise ValueError('Invalid GLB')
    n,kind=struct.unpack_from('<II',data,12)
    if kind!=0x4e4f534a:raise ValueError('Missing GLB JSON')
    gltf=json.loads(data[20:20+n]);start=20+n
    size,kind=struct.unpack_from('<II',data,start)
    if kind!=0x004e4942:raise ValueError('Missing GLB binary')
    blob=data[start+8:start+8+size]
    credits=gltf['asset']['extras']
    if credits['source']!=SOURCE or 'CC-BY-NC-4.0' not in credits['license'] or 'shadows44' not in credits['author']:
        raise ValueError('Embedded author/source/license disagreement')
    parts=list(primitives(gltf,blob))
    all_positions=np.concatenate([p['positions'] for p in parts])
    base=all_positions[:,1].min()
    # glTF is Y up; the source root matrix flips the raw OBJ's inverted Y.
    # Keep a real statue and its pedestal, exclude the wide upper canopy.
    out=[]
    for p in parts:
        triangles=p['indices'].reshape(-1,3)
        keep=np.all(p['positions'][triangles,1]-base<=UPPER_CROP,axis=1)
        triangles=triangles[keep]
        used,remap=np.unique(triangles,return_inverse=True)
        if len(used):out.append(dict(positions=p['positions'][used],normals=p['normals'][used],uvs=p['uvs'][used],indices=remap.reshape(-1,3)))
    points=np.concatenate([p['positions'] for p in out])
    center_x=(points[:,0].min()+points[:,0].max())/2
    center_depth=(points[:,2].min()+points[:,2].max())/2
    scale=HEIGHT_M/(points[:,1].max()-base)
    architecture=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-photo-architecture.json').read_text(encoding='utf-8'))
    frame=architecture['local_frame'];across=np.array(frame['across']);depth=np.array(frame['depth']);origin=np.array(frame['front_cm'])
    positions=[];normals=[];uvs=[];indices=[];offset=0
    for p in out:
        v=p['positions'];local=((v-[center_x,base,center_depth])@ORIENTATION.T)*scale+[14,-.30,.15]
        world=origin+100*(local[:,0,None]*across+local[:,1,None]*depth+np.column_stack([np.zeros(len(v)),np.zeros(len(v)),local[:,2]]))
        normal=p['normals']@ORIENTATION.T;normal=normal[:,0,None]*across+normal[:,1,None]*depth+np.column_stack([np.zeros(len(v)),np.zeros(len(v)),normal[:,2]])
        normal/=np.linalg.norm(normal,axis=1,keepdims=True)
        tri=p['indices'].copy();cross=np.cross(world[tri[:,1]]-world[tri[:,0]],world[tri[:,2]]-world[tri[:,0]])
        valid=np.linalg.norm(cross,axis=1)>1e-7;tri=tri[valid];cross=cross[valid]
        reverse=np.einsum('ij,ij->i',cross,normal[tri].sum(axis=1))>0
        tri[reverse]=tri[reverse][:,[0,2,1]]  # UE front-face winding.
        positions.append(world);normals.append(normal);uvs.append(p['uvs']);indices.append(tri+offset);offset+=len(v)
    p=np.concatenate(positions).astype('<f4');n=np.concatenate(normals).astype('<f4');uv=np.concatenate(uvs).astype('<f4');t=np.concatenate(indices).astype('<u4')
    # Validate the serialized cm precision, not just the double-precision input.
    pf=p.astype(float);cross=np.cross(pf[t[:,1]]-pf[t[:,0]],pf[t[:,2]]-pf[t[:,0]])
    valid=np.linalg.norm(cross,axis=1)>1e-7;t=t[valid];cross=cross[valid]
    reverse=np.einsum('ij,ij->i',cross,n[t].sum(axis=1))>0;t[reverse]=t[reverse][:,[0,2,1]]
    geometry=struct.pack('<8sII',b'NDSCAN01',len(p),len(t))+p.tobytes()+n.tobytes()+uv.tobytes()+t.tobytes()
    digest=hashlib.sha256(geometry).hexdigest()
    view=gltf['bufferViews'][gltf['images'][0]['bufferView']];o=view.get('byteOffset',0);image=blob[o:o+view['byteLength']]
    texture_sha=hashlib.sha256(image).hexdigest()
    manifest=dict(format='paris_noncommercial_scanned_statue_v1',uid=UID,source_id='osm/way/201611261',
        source_url=SOURCE,mirror_url=URL,author=credits['author'],title=credits['title'],license='CC-BY-NC-4.0',license_url='https://creativecommons.org/licenses/by-nc/4.0/',
        use_scope='personal_noncommercial',source_sha256=SHA,source_bytes=len(data),local_frame=frame,
        geometry_sha256=digest,vertices=len(p),triangles=len(t),original_triangles=sum(len(q['indices'])//3 for q in parts),
        binary='unreal/assets/notre-dame-sculptures/virgin-mary.bin',
        texture=dict(file='unreal/assets/notre-dame-sculptures/virgin-mary.jpg',sha256=texture_sha,resolution=image_size(image)),
        registration=dict(portal='western north/left Portal of the Virgin',center_x_m=14,center_y_m=-.30,base_z_m=.15,height_m=HEIGHT_M,source_upper_crop_units=UPPER_CROP,scale=scale,measured=False,
            gltf_to_facade_basis=ORIENTATION.tolist(),handedness_determinant=float(np.linalg.det(ORIENTATION)),
            location_reference='https://www.notredamedeparis.fr/comprendre/architecture/la-facade-occidentale/'),
        provenance='Actual historical photo scan by Benoit Rogez, cropped upper canopy, provisional scale and registration. Original photographed lighting remains in 1024px colour; no measured roughness/normal maps or unseen geometry claimed.',
        material_calibration=dict(albedo_multiplier=.72,roughness=.85,metallic=0,lighting='Default Lit, photographed shading remains'))
    return manifest,geometry,image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if args.download:acquire()
    manifest,geometry,image=generate()
    (FOLDER/'virgin-mary.bin').write_bytes(geometry);(FOLDER/'virgin-mary.jpg').write_bytes(image)
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (ROOT/'unreal/AIWorld/Content/Data/paris-notredame-statue-source.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(vertices=manifest['vertices'],triangles=manifest['triangles'],geometry_sha256=manifest['geometry_sha256'],texture=manifest['texture']['resolution'])))


if __name__=='__main__':main()
