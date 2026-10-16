"""Original, seamless PBR patterns. Standard library only; no downloaded imagery.

Base colour is an sRGB multiplier for the existing GIS vertex tint. The linear
surface map packs occlusion/roughness/height in R/G/B. Heights are centimetres
in the UE material, never geometry displacement or surveyed building detail.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

RECIPES = {
    'Limestone': dict(tile_cm=240, height_cm=.8, metallic=0, rows=6, columns=3, joint_cm=.65),
    'Slate': dict(tile_cm=120, height_cm=.45, metallic=0, rows=6, columns=4, joint_cm=.3),
    'Zinc': dict(tile_cm=240, height_cm=1.2, metallic=.78, panels=4),
    'Paving': dict(tile_cm=200, height_cm=.65, metallic=0, rows=10, columns=8, joint_cm=.8),
    'Asphalt': dict(tile_cm=100, height_cm=.06, metallic=0),
}


def clamp(x):
    return max(0., min(1., x))


def smooth(a, b, x):
    t = clamp((x-a)/(b-a))
    return t*t*(3-2*t)


def cell_value(x, y):
    n = ((x+17)*374761393+(y+31)*668265263) & 0xffffffff
    n = ((n ^ (n >> 13))*1274126177) & 0xffffffff
    return (n ^ (n >> 16))/4294967295.


def noise(u, v, frequency):
    x,y=u*frequency,v*frequency
    ix,iy=math.floor(x),math.floor(y);fx,fy=x-ix,y-iy
    fx,fy=fx*fx*(3-2*fx),fy*fy*(3-2*fy)
    a,b=cell_value(ix % frequency,iy % frequency),cell_value((ix+1) % frequency,iy % frequency)
    c,d=cell_value(ix % frequency,(iy+1) % frequency),cell_value((ix+1) % frequency,(iy+1) % frequency)
    return (a+(b-a)*fx)*(1-fy)+(c+(d-c)*fx)*fy


def sample(name, u, v):
    u, v = u % 1., v % 1.
    # Toroidal value noise avoids directional/checker grain and keeps seams shut.
    broad = .65*noise(u,v,4)+.35*noise(u,v,16)
    grain = noise(u,v,128)
    recipe = RECIPES[name]
    if name in ('Limestone', 'Slate', 'Paving'):
        rows, columns = recipe['rows'], recipe['columns']
        row = math.floor(v*rows)
        x, y = (u*columns+(row % 2)*.5) % columns, v*rows-row
        column, x = math.floor(x), x % 1.
        joint = recipe['joint_cm']/recipe['tile_cm']
        edge = min(x, 1-x)/columns
        edge = min(edge, min(y, 1-y)/rows)
        stone = smooth(joint*.3, joint*1.5, edge)
        variation = cell_value(column, row)
        if name == 'Limestone':
            albedo = .92+.055*variation+.025*grain-.16*(1-stone)
            rough = .78+.12*broad+.06*(1-stone)
            height = .5*stone+.06*grain
        elif name == 'Slate':
            albedo = .76+.19*variation+.05*grain-.14*(1-stone)
            rough = .55+.17*broad+.10*(1-stone)
            height = stone*(.35+.35*y)+.035*grain
        else:
            albedo = .77+.17*variation+.06*grain-.19*(1-stone)
            rough = .77+.16*broad+.04*(1-stone)
            height = stone*(.55+.12*variation)+.04*grain
        ao = .70+.30*stone
    elif name == 'Zinc':
        panel = (u*recipe['panels']) % 1.
        seam_distance = min(panel, 1-panel)*recipe['tile_cm']/recipe['panels']
        seam = 1-smooth(.22, 1.05, seam_distance)
        albedo = .84+.11*broad+.025*grain-.06*seam
        rough = .43+.18*broad+.035*grain
        height, ao = .07+.82*seam+.045*broad, .98-.09*seam
    else:
        albedo, rough = .81+.15*grain+.04*broad, .79+.16*grain
        height, ao = .20+.6*grain, .95+.05*grain
    return (clamp(albedo),)*3, tuple(clamp(x) for x in (ao, rough, height))


def pixels(name, size=512):
    if size < 16 or size > 2048:
        raise ValueError('Surface resolution must be 16..2048')
    base, packed = bytearray(), bytearray()
    for y in range(size):
        for x in range(size):
            albedo, surface = sample(name, x/(size-1), y/(size-1))
            base.extend(round(v*255) for v in albedo)
            packed.extend(round(v*255) for v in surface)
    return bytes(base), bytes(packed)


def png(rgb, size):
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    rows = b''.join(b'\0'+rgb[y*size*3:(y+1)*size*3] for y in range(size))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            +chunk(b'IDAT', zlib.compress(rows, 9))+chunk(b'IEND', b''))


def generate(folder=None, size=512):
    folder = Path(folder) if folder else Path(__file__).resolve().parents[1]/'textures'/'paris'
    folder.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    manifest_path = folder/'manifest.json'
    if manifest_path.exists():
        try:manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):manifest={}
        if (manifest.get('generator_sha256') == signature and manifest.get('resolution') == size
                and all((folder/name).exists() and hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
                        for name, digest in manifest.get('files', {}).items()) and len(manifest.get('files', {})) == len(RECIPES)*2):
            return manifest
    files = {}
    for name in RECIPES:
        for suffix, rgb in zip(('basecolor', 'surface'), pixels(name, size)):
            filename = f'{name}_{suffix}.png'
            data = png(rgb, size)
            (folder/filename).write_bytes(data)
            files[filename] = hashlib.sha256(data).hexdigest()
    manifest = dict(generator_sha256=signature, resolution=size, files=files, recipes=RECIPES,
                    channels=dict(basecolor='sRGB vertex-tint multiplier', surface='linear R=AO G=roughness B=height'),
                    source='Original procedural project assets; no photographs or external textures',
                    accuracy='Inferred regional materials, not measured surfaces; reproduction levels unchanged',
                    license='Original project asset; distribution follows the repository license')
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(generate(), sort_keys=True))
