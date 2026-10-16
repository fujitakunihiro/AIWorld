"""Inspect actual CC BY GLB buffers; no thumbnail is substituted for mesh data."""
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/notre-dame'


def load():
    data=(FOLDER/'notre-dame.glb').read_bytes();manifest=json.loads((FOLDER/'manifest.json').read_text())
    if hashlib.sha256(data).hexdigest()!=manifest['sha256']:raise ValueError('Source model changed')
    magic,version,total=struct.unpack_from('<4sII',data)
    if (magic,version,total)!=(b'glTF',2,len(data)):raise ValueError('Invalid GLB header')
    size,kind=struct.unpack_from('<II',data,12);gltf=json.loads(data[20:20+size])
    start=20+size;bin_size,kind=struct.unpack_from('<II',data,start);blob=data[start+8:start+8+bin_size]
    if gltf['asset']['extras']['source']!=manifest['original_url'] or 'CC-BY-4.0' not in gltf['asset']['extras']['license']:raise ValueError('Embedded source/license disagreement')
    return gltf,blob


def accessor(gltf,blob,index):
    a=gltf['accessors'][index];v=gltf['bufferViews'][a['bufferView']]
    types={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'};dtype=np.dtype(types[a['componentType']])
    components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
    return np.ndarray((a['count'],components),dtype=dtype,buffer=blob,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',components*dtype.itemsize),dtype.itemsize)).copy()


def primitives(gltf,blob):
    def visit(index,parent):
        node=gltf['nodes'][index];matrix=np.array(node.get('matrix',np.eye(4).flatten(order='F')),dtype=float).reshape((4,4),order='F');world=parent@matrix
        if 'mesh' in node and not node.get('name','').startswith('pPlane'):
            for primitive in gltf['meshes'][node['mesh']]['primitives']:
                a=primitive['attributes'];points=accessor(gltf,blob,a['POSITION']);positions=(np.c_[points,np.ones(len(points))]@world.T)[:,:3]
                normals=accessor(gltf,blob,a['NORMAL'])@np.linalg.inv(world[:3,:3]);normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-10)
                yield dict(name=node['name'],positions=positions,normals=normals,uvs=accessor(gltf,blob,a['TEXCOORD_0']),indices=accessor(gltf,blob,primitive['indices']).flatten(),material=primitive['material'])
        for child in node.get('children',[]):yield from visit(child,world)
    for root in gltf['scenes'][gltf.get('scene',0)]['nodes']:yield from visit(root,np.eye(4))


def image_size(data):
    if data.startswith(b'\x89PNG'):return list(struct.unpack_from('>II',data,16))
    if data.startswith(b'\xff\xd8'):
        i=2
        while i<len(data):
            if data[i]!=255:i+=1;continue
            marker=data[i+1];i+=2
            if marker in (216,217):continue
            length=struct.unpack_from('>H',data,i)[0]
            if marker in (192,193,194):return list(reversed(struct.unpack_from('>HH',data,i+3)))
            i+=length
    raise ValueError('Unknown embedded texture format')


if __name__=='__main__':
    gltf,blob=load();parts=list(primitives(gltf,blob));points=np.concatenate([p['positions'] for p in parts]);images=[]
    for image in gltf['images']:
        view=gltf['bufferViews'][image['bufferView']];offset=view.get('byteOffset',0);data=blob[offset:offset+view['byteLength']]
        images.append(dict(name=image.get('name'),resolution=image_size(data),mime=image['mimeType'],bytes=len(data)))
    report=dict(parts=len(parts),triangles=sum(len(p['indices'])//3 for p in parts),bounds_min=points.min(axis=0).tolist(),bounds_max=points.max(axis=0).tolist(),
        images=images,unlit_source_materials=sum('KHR_materials_unlit' in m.get('extensions',{}) for m in gltf['materials']),
        has_normal_maps=any('normalTexture' in m for m in gltf['materials']),has_roughness_maps=any('metallicRoughnessTexture' in m.get('pbrMetallicRoughness',{}) for m in gltf['materials']),
        removed_non_architecture='pPlane1 reference ground plane excluded')
    (FOLDER/'inspection.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
