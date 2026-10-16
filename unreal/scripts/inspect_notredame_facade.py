"""Inspect the licensed raw point cloud. Optional preview is NOT an Unreal render."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/notre-dame-facade'


def load_points():
    manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    path=FOLDER/manifest['file']
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=manifest['sha256']:
        raise ValueError('Point-cloud checksum differs from the accepted raw source')
    with path.open('rb') as f:
        magic,version,total=struct.unpack('<4sII',f.read(12))
        if magic!=b'glTF' or version!=2 or total!=path.stat().st_size:raise ValueError('Invalid source GLB')
        length,kind=struct.unpack('<II',f.read(8));data=json.loads(f.read(length))
        size,kind=struct.unpack('<II',f.read(8));offset=f.tell()
    extras=data['asset']['extras']
    if 'CC-BY-4.0' not in extras['license'] or '50deeb164f324d1c8607bafa67f948b9' not in extras['source']:
        raise ValueError('Embedded attribution/license does not match the source')
    binary=np.memmap(path,dtype='u1',mode='r')

    def accessor(index):
        a=data['accessors'][index];v=data['bufferViews'][a['bufferView']]
        dtype=np.dtype({5126:'<f4',5121:'u1',5123:'<u2'}[a['componentType']]);n={'VEC3':3,'VEC4':4}[a['type']]
        values=np.ndarray((a['count'],n),dtype=dtype,buffer=binary,offset=offset+v.get('byteOffset',0)+a.get('byteOffset',0),
                          strides=(v.get('byteStride',n*dtype.itemsize),dtype.itemsize)).copy()
        if a.get('normalized') and dtype.kind=='u':values=values.astype(np.float32)/np.iinfo(dtype).max
        return values

    positions=[];colours=[]
    def visit(index,parent):
        node=data['nodes'][index]
        # This particular source uses explicit matrices (including its offset).
        if any(k in node for k in ('translation','rotation','scale')):raise ValueError('Unimplemented TRS transform; do not silently ignore it')
        matrix=parent@np.array(node.get('matrix',np.eye(4).flatten(order='F')),dtype=float).reshape(4,4,order='F')
        if 'mesh' in node:
            for primitive in data['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4)!=0:raise ValueError('Expected the published POINTS asset')
                attrs=primitive['attributes'];p=accessor(attrs['POSITION']);colour=accessor(attrs['COLOR_0'])[:,:3].astype(np.float32)
                # Ignore explicitly empty padding, if present. Never infer a
                # missing transform or synthesize observations from zero data.
                valid=~(np.all(p==0,axis=1)&np.all(colour==0,axis=1));p=p[valid];colour=colour[valid]
                positions.append((p@matrix[:3,:3].T+matrix[:3,3]).astype(np.float32))
                colours.append(colour)
        for child in node.get('children',[]):visit(child,matrix)
    for node in data['scenes'][data.get('scene',0)]['nodes']:visit(node,np.eye(4))
    return np.concatenate(positions),np.concatenate(colours),extras


def inspect(preview=None):
    p,c,extras=load_points()
    sample=p[::31];middle=sample[(sample[:,1]>np.quantile(sample[:,1],.2))&(sample[:,1]<np.quantile(sample[:,1],.85))]
    centre=np.median(middle[:,[0,2]],axis=0)
    _,axes=np.linalg.eigh(np.cov((middle[:,[0,2]]-centre).T))
    across=axes[:,1];depth=axes[:,0]
    report=dict(format='notredame_point_cloud_inspection_v1',points=len(p),triangles=0,
        embedded_credit=extras,bounds_min=p.min(0).tolist(),bounds_max=p.max(0).tolist(),
        robust_bounds_min=np.quantile(p,.001,axis=0).tolist(),robust_bounds_max=np.quantile(p,.999,axis=0).tolist(),
        colour_range=[float(c.min()),float(c.max())],horizontal_across=across.tolist(),horizontal_depth=depth.tolist(),
        pbr_textures=False,geographic_registration='Not supplied; no accepted WGS84 registration',
        acceptance='Research only. A point-cloud diagnostic does not establish a manifold facade, PBR, present-day appearance, or scene integration.')
    (FOLDER/'inspection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if preview:
        from PIL import Image,ImageDraw
        p=p[::4];c=c[::4]
        x=(p[:,[0,2]]-centre)@across;z=p[:,1];d=(p[:,[0,2]]-centre)@depth
        lo=np.quantile(x,.001);hi=np.quantile(x,.999);bottom=np.quantile(z,.001);top=np.quantile(z,.999)
        width=1600;height=1600;scale=min((width-40)/(hi-lo),(height-80)/(top-bottom))
        u=np.rint((x-(lo+hi)/2)*scale+width/2).astype(np.int32);v=np.rint((top-z)*scale+55).astype(np.int32)
        valid=(u>=0)&(u<width)&(v>=55)&(v<height)
        ids=v[valid]*width+u[valid];values=c[valid];distance=d[valid]
        canvas=np.full((height*width,3),225,dtype=np.uint8)
        # Far-to-near painter order shows measured colour only. Missing data
        # remains visibly empty; no inpainting or invented surface is accepted.
        order=np.argsort(distance)
        canvas[ids[order]]=np.uint8(np.clip(values[order],0,1)**(1/2.2)*255)
        image=Image.fromarray(canvas.reshape(height,width,3));draw=ImageDraw.Draw(image)
        draw.text((15,12),'SOURCE POINT-CLOUD DIAGNOSTIC - not an Unreal screenshot; missing areas are unfilled',fill='black')
        image.save(preview)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preview',type=Path)
    inspect(parser.parse_args().preview)
