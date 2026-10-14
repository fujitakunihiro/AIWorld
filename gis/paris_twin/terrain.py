"""One NGF-IGN69 datum for terrain, roads, building gutters and cameras."""
import math
import statistics
from shapely.geometry import Point, box
from .io import paths, read


class Terrain:
    def __init__(self, config, geo):
        self.geo = geo
        raw = paths(config)['Raw']
        if (raw/'terrain/manifest.json').exists():
            manifest = read(raw/'terrain/manifest.json')
            data = read(raw/'terrain/elevations.json')
            self.steps = manifest['grid_steps']
            self.origin_ngf = data['origin']['z']
            self.snapshot = 'terrain/elevations.json'
            self.samples = data['elevations']
        else:
            self.steps = config['elevation_grid_steps']
            self.samples = read(raw/'ign_elevation.json')['elevations']
            self.snapshot = 'ign_elevation.json'
            if self.steps%2 or geo.centre != geo.origin:
                raise ValueError('Shared NGF origin requires download-terrain for this district')
            self.origin_ngf = self.samples[(self.steps//2)*(self.steps+1)+self.steps//2]['z']
        self.bounds = geo.extent.bounds
        self.measured_origin_ngf=self.origin_ngf
        # A refreshed DEM must not move the frame relative to archived neighbours.
        self.origin_ngf=float(config.get('origin_elevation_ngf_m',self.origin_ngf))
        if not math.isfinite(self.origin_ngf):raise ValueError('Shared NGF origin must be finite')
        self.spacing = (self.bounds[2]-self.bounds[0])/self.steps
        if len(self.samples) != (self.steps+1)**2:
            raise ValueError('Terrain samples are not a complete regular grid')
        for sample in self.samples:
            if not math.isfinite(sample['z']) or sample['z'] <= -9999:
                raise ValueError('Terrain contains no-data elevations')

    def ngf(self, xy):
        x,y = xy[:2]; x0,y0,_,_ = self.bounds
        fx = max(0., min(self.steps, (x-x0)/self.spacing))
        fy = max(0., min(self.steps, (y-y0)/self.spacing))
        ix = min(self.steps-1, math.floor(fx)); iy = min(self.steps-1, math.floor(fy))
        tx,ty = fx-ix,fy-iy
        def z(dx,dy): return self.samples[(iy+dy)*(self.steps+1)+ix+dx]['z']
        return (z(0,0)*(1-tx)+z(1,0)*tx)*(1-ty)+(z(0,1)*(1-tx)+z(1,1)*tx)*ty

    def local(self, xy):
        return self.ngf(xy)-self.origin_ngf

    def water_level(self, river, bridge_shapes):
        values = []
        excluded=bridge_shapes.buffer(2) if bridge_shapes is not None else None
        for sample in self.samples:
            point = Point(self.geo.forward.transform(sample['lon'],sample['lat']))
            if river.contains(point) and (excluded is None or not excluded.covers(point)):
                values.append(sample['z'])
        if len(values) < 3:
            raise ValueError('Not enough river DEM samples to derive an explicitly estimated water level')
        return round(statistics.median(values),2), len(values)

    def metadata(self):
        return dict(source='IGN RGE ALTI', source_snapshot=self.snapshot, vertical_datum='NGF-IGN69',
                    interpolation='bilinear regular point grid; not a surveyed kerb or bathymetry',
                    samples=len(self.samples), sampling_spacing_m=self.spacing,
                    origin_elevation_ngf_m=self.origin_ngf,
                    origin_elevation_source='configured shared anchor' if 'origin_elevation_ngf_m' in self.geo.config else 'archived IGN origin sample',
                    origin_sample_ngf_m=self.measured_origin_ngf,
                    sample_min_ngf_m=min(s['z'] for s in self.samples),
                    sample_max_ngf_m=max(s['z'] for s in self.samples))


def cells(geometry, geo, spacing):
    """Clip before triangulating so long triangles follow the height field."""
    if geometry is None or geometry.is_empty: return
    x0,y0,x1,y1 = geometry.bounds
    ox,oy = geo.origin
    for iy in range(math.floor((y0-oy)/spacing),math.ceil((y1-oy)/spacing)):
        for ix in range(math.floor((x0-ox)/spacing),math.ceil((x1-ox)/spacing)):
            cell = box(ox+ix*spacing,oy+iy*spacing,ox+(ix+1)*spacing,oy+(iy+1)*spacing)
            if geometry.intersects(cell):
                clipped = geometry.intersection(cell)
                if not clipped.is_empty: yield clipped
