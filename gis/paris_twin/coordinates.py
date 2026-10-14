from pyproj import CRS, Transformer
from shapely.geometry import box


class Georeference:
    """WGS84 -> Lambert-93 -> UE cm. X=east, Y=south, Z=up.

    IGN elevations are orthometric NGF-IGN69; do not pass them as WGS84
    ellipsoidal heights. Cesium is not enabled and must not convert these again.
    """
    def __init__(self, config):
        self.config = config
        self.crs = CRS.from_user_input(config['projected_crs'])
        if not self.crs.is_projected or self.crs.axis_info[0].unit_conversion_factor!=1:
            raise ValueError('Projected CRS must use metres before conversion to UE cm')
        self.forward = Transformer.from_crs('EPSG:4326', self.crs, always_xy=True)
        self.inverse = Transformer.from_crs(self.crs, 'EPSG:4326', always_xy=True)
        self.origin = self.forward.transform(*config['origin_wgs84'])
        half = config['core_size_m'] / 2 + config['context_buffer_m']
        x, y = self.origin
        self.extent = box(x-half, y-half, x+half, y+half)

    def to_ue(self, lon, lat, elevation=0, origin_elevation=0):
        e, n = self.forward.transform(lon, lat)
        return ((e-self.origin[0])*100, -(n-self.origin[1])*100,
                (elevation-origin_elevation)*100)

    def from_ue(self, x, y, z=0, origin_elevation=0):
        lon, lat = self.inverse.transform(self.origin[0]+x/100, self.origin[1]-y/100)
        return lon, lat, z/100+origin_elevation

    def bounds_wgs84(self):
        x0, y0, x1, y1 = self.extent.bounds
        corners = [self.inverse.transform(x,y) for x,y in [(x0,y0),(x0,y1),(x1,y0),(x1,y1)]]
        return min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)
