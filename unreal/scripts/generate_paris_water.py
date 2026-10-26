"""Original water normals and an OSM-aligned shore distance field; no network."""
import hashlib
import json
from pathlib import Path
import struct
import zlib
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, MultiLineString, LineString
from shapely.ops import unary_union, nearest_points

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / 'unreal/AIWorld/Content'
OUT = ROOT / 'unreal/textures/paris-water'


def png(path, pixels):
    h, w, _ = pixels.shape
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    rows = b''.join(b'\0' + row.tobytes() for row in pixels)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def generate():
    data = json.loads((CONTENT / 'Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    OUT.mkdir(parents=True, exist_ok=True)
    water = next(f for f in data['pick_features'] if f['id'] == 'osm/relation/2191006')
    river = unary_union([shapely.make_valid(Polygon(p[0], p[1:])) for p in water['polygons_cm']])
    radius = data['extent_m'] * 50
    cx, cy, _ = data['scene_centre_ue_cm']
    bounds = [cx-radius, cy-radius, cx+radius, cy+radius]
    shore = []
    for poly in shapely.get_parts(river):
        for ring in [poly.exterior, *poly.interiors]:
            coords = list(ring.coords)
            for a, b in zip(coords, coords[1:]):
                # Clipped context edges are not river banks.
                if any(abs(a[k]-edge)<1 and abs(b[k]-edge)<1
                       for k, edge in [(0,bounds[0]),(0,bounds[2]),(1,bounds[1]),(1,bounds[3])]):
                    continue
                shore.append((a[:2], b[:2]))
    shoreline = MultiLineString(shore)
    size = 1024
    packed = np.empty((size, size, 4), dtype=np.uint8)
    x = bounds[0] + (np.arange(size)+.5)*(bounds[2]-bounds[0])/size
    for start in range(0, size, 64):
        y = bounds[1] + (np.arange(start, min(start+64,size))+.5)*(bounds[3]-bounds[1])/size
        xx, yy = np.meshgrid(x, y)
        points = shapely.points(xx, yy)
        distance = shapely.distance(points, shoreline)
        signed = np.where(shapely.contains(river, points), distance, -distance)
        q = np.rint(np.clip((signed+6400)/12800, 0, 1)*65535).astype(np.uint16)
        packed[start:start+len(y), :, 0] = q >> 8
        packed[start:start+len(y), :, 1] = q & 255
        packed[start:start+len(y), :, 2] = 0
        packed[start:start+len(y), :, 3] = 255
    png(OUT / 'seine-shore-distance.png', packed)

    # Integer Fourier frequencies make the normal tile periodic in both axes.
    # Analytic gradients retain smooth small ripples without 3D noise shaders.
    u, v = np.meshgrid(np.arange(size)/size, np.arange(size)/size)
    gx, gy = np.zeros_like(u), np.zeros_like(v)
    rng = np.random.default_rng(20261026)
    for i in range(42):
        kx, ky = int(rng.integers(1,22)), int(rng.integers(-14,15))
        phase = 2*np.pi*(kx*u+ky*v)+rng.uniform(0,2*np.pi)
        amplitude = .055 / (kx*kx+ky*ky)**.65
        gx += amplitude*kx*np.cos(phase)
        gy += amplitude*ky*np.cos(phase)
    norm = np.sqrt(1+gx*gx+gy*gy)
    normals = np.stack((-gx/norm, -gy/norm, 1/norm), axis=-1)
    rgba = np.full((size,size,4),255,dtype=np.uint8)
    rgba[:,:,:3] = np.rint((normals*.5+.5)*255).astype(np.uint8)
    png(OUT / 'seine-ripple-normal.png', rgba)

    level = next(o['properties']['water_level_ngf_m'] for o in data['objects'] if o['id']=='seine')
    level_cm = (level-data['georeference']['origin_elevation_ngf_m'])*100
    q = Point(data['quality_centre_ue_cm'][:2])
    bank = nearest_points(q, river)[1]
    inner = nearest_points(q, river.buffer(-1800))[1]
    direction = np.array([inner.x-bank.x,inner.y-bank.y]); direction /= np.linalg.norm(direction)
    # Look along the real channel rather than directly into the opposite bank.
    # Prefer a long uninterrupted water sight line inside the acquired district.
    options=[]
    for angle in np.linspace(0,2*np.pi,96,endpoint=False):
        d=np.array([np.cos(angle),np.sin(angle)])
        ray=LineString([(inner.x,inner.y),(inner.x+d[0]*18000,inner.y+d[1]*18000)])
        first=LineString([(inner.x,inner.y),(inner.x+d[0]*5000,inner.y+d[1]*5000)])
        score=ray.intersection(river).length+first.intersection(river).length*3
        options.append((score,angle,d))
    direction=max(options,key=lambda e:e[0])[2]
    manifest = dict(schema_version=1, recipe='seine_single_layer_v1',
        source_scene_sha256=data['source_scene_sha256'], source_id=water['id'],
        source_attribution=data['attribution'], world_bounds_cm=bounds, water_level_cm=level_cm,
        shore_distance_range_cm=6400, texture_size=size,
        appearance_provenance='Original inferred river optics, flow and ripples; not measured bathymetry or hydrodynamics.',
        preview_camera=dict(position_cm=[inner.x,inner.y,level_cm+700],
                            target_cm=[inner.x+direction[0]*7000,inner.y+direction[1]*7000,level_cm+15]),
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.png'))})
    (CONTENT/'Data/paris-water.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PARIS_WATER_INPUTS_READY', manifest['source_id'])
    return manifest


if __name__ == '__main__':
    generate()
