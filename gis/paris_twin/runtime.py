"""Deterministic compact UE mesh packet; full JSON remains the audit source.

Little-endian PARISM01 + version/count header. Vertices: 3f position cm,
3f normal, 4B sRGB colour. Indices: uint32. Metadata owns bounded byte ranges.
"""
import math
import struct
import tempfile
import zlib
from pathlib import Path
from .io import write,sha

MAGIC=b'PARISM01'
HEADER=struct.Struct('<8sII')
VERTEX=struct.Struct('<6f4B')
UINT=struct.Struct('<I')
FIELDS=('positions_cm','normals','indices','vertex_colors')


def color(value):
    value=value.lstrip('#')
    if len(value)!=6:raise ValueError('Runtime colours must use RRGGBB')
    return tuple(bytes.fromhex(value))+(255,)


def pack(scene):
    # Do not deep-copy millions of geometry numbers just to remove them.
    runtime={k:v for k,v in scene.items() if k not in ['objects','footprint_mesh']}
    objects=[*scene['objects'],scene['footprint_mesh']];result=[]
    blob=bytearray(HEADER.pack(MAGIC,1,len(objects)))
    for obj in objects:
        points=obj['positions_cm'];normals=obj['normals'];indices=obj['indices']
        if len(normals)!=len(points) or len(indices)%3:raise ValueError('Malformed runtime input mesh')
        offset=len(blob);colors=obj.get('vertex_colors');base=color(obj['color'])
        if colors is not None and len(colors)!=len(points):raise ValueError('Malformed runtime colours')
        for i,(p,n) in enumerate(zip(points,normals)):
            if len(p)!=3 or len(n)!=3 or not all(math.isfinite(v) for v in [*p,*n]):raise ValueError('Nonfinite runtime vertex')
            blob.extend(VERTEX.pack(*p,*n,*(color(colors[i]) if colors is not None else base)))
        for index in indices:
            if type(index) is not int or not 0<=index<len(points):raise ValueError('Runtime index out of bounds')
            blob.extend(UINT.pack(index))
        item={k:v for k,v in obj.items() if k not in FIELDS}
        item['mesh_buffer']=dict(offset=offset,vertex_count=len(points),index_count=len(indices),byte_length=len(blob)-offset)
        result.append(item)
    runtime['objects']=result[:-1];runtime['footprint_mesh']=result[-1]
    runtime['geometry_blob']=dict(file='paris-digital-twin-meshes.bin',format='paris_mesh_le_v1',bytes=len(blob),
        crc32=f'{zlib.crc32(blob):08x}',vertex_stride=VERTEX.size,mesh_count=len(objects),
        precision='float32 cm positions; original double-valued coordinates retained in full scene.json')
    return runtime,bytes(blob)


def write_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.tmp',delete=False) as file:
        file.write(data);temporary=Path(file.name)
    try:temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()


def export_runtime(scene,dest,native):
    runtime,blob=pack(scene);runtime['source_scene_sha256']=sha(dest/'scene.json')
    write(dest/'runtime.json',runtime);write_bytes(dest/'runtime-meshes.bin',blob)
    write(native/'paris-digital-twin-runtime.json',runtime);write_bytes(native/'paris-digital-twin-meshes.bin',blob)
    return runtime


def validate_runtime(runtime,blob,scene=None):
    meta=runtime['geometry_blob']
    if len(blob)<HEADER.size or HEADER.unpack_from(blob)!=(MAGIC,1,meta['mesh_count']):raise ValueError('Runtime header mismatch')
    if meta['bytes']!=len(blob) or meta['crc32']!=f'{zlib.crc32(blob):08x}':raise ValueError('Runtime checksum/length mismatch')
    objects=[*runtime['objects'],runtime['footprint_mesh']]
    if len(objects)!=meta['mesh_count']:raise ValueError('Runtime mesh count mismatch')
    originals=[*scene['objects'],scene['footprint_mesh']] if scene is not None else None
    cursor=HEADER.size;max_error=0
    for i,obj in enumerate(objects):
        d=obj['mesh_buffer'];count=d['vertex_count'];indices=d['index_count'];length=count*VERTEX.size+indices*4
        if count<1 or count>1000000 or indices%3 or d['offset']!=cursor or d['byte_length']!=length or cursor+length>len(blob):raise ValueError('Runtime buffer range invalid')
        source=originals[i] if originals else None
        if source and (obj['id']!=source['id'] or count!=len(source['positions_cm']) or indices!=len(source['indices'])):raise ValueError('Runtime source mesh mismatch')
        for v in range(count):
            row=VERTEX.unpack_from(blob,cursor+v*VERTEX.size)
            if not all(math.isfinite(n) for n in row[:6]):raise ValueError('Runtime nonfinite vertex')
            if source:
                max_error=max(max_error,*(abs(row[k]-source['positions_cm'][v][k]) for k in range(3)))
                expected=color(source.get('vertex_colors',[source['color']])[v] if 'vertex_colors' in source else source['color'])
                if row[6:]!=expected:raise ValueError('Runtime colour mismatch')
        for j in range(indices):
            value=UINT.unpack_from(blob,cursor+count*VERTEX.size+j*4)[0]
            if value>=count or (source and value!=source['indices'][j]):raise ValueError('Runtime index mismatch')
        cursor+=length
    if cursor!=len(blob) or max_error>.01:raise ValueError('Runtime trailing bytes / precision loss over 0.01cm')
    return dict(meshes=len(objects),blob_bytes=len(blob),max_position_error_cm=max_error,crc32=meta['crc32'])
