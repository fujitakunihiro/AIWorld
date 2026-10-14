"""OSM-aligned decks; cross sections are labelled procedural estimates."""
import math
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from .building_heights import polygon_parts


class BridgeDeck:
    def __init__(self, polygon, features, terrain):
        self.geometry = polygon
        self.source_ids = sorted(f['properties']['source_id'] for f in features)
        self.names = sorted({f['properties']['name'] for f in features if f['properties']['name']})
        self.clipped = any(f['properties']['clipped_at_context_boundary'] for f in features)
        rect = list(polygon.minimum_rotated_rectangle.exterior.coords)
        length,a,b = max((math.dist(a,b),a,b) for a,b in zip(rect,rect[1:]))
        self.direction = ((b[0]-a[0])/length,(b[1]-a[1])/length)
        center = polygon.centroid; self.center = (center.x,center.y)
        dx,dy = self.direction
        coords = [p for ring in [polygon.exterior,*polygon.interiors] for p in ring.coords]
        projections = [(p[0]-center.x)*dx+(p[1]-center.y)*dy for p in coords]
        self.start,self.end = min(projections),max(projections)
        self.ends = [(center.x+dx*t,center.y+dy*t) for t in [self.start,self.end]]
        self.heights = [terrain.local(p)+.035 for p in self.ends]
        self.terrain = terrain
        self.crown = .35 if length>25 else .08

    def height(self, xy):
        dx,dy = self.direction
        along = (xy[0]-self.center[0])*dx+(xy[1]-self.center[1])*dy
        t = max(0,min(1,(along-self.start)/max(.001,self.end-self.start)))
        return self.heights[0]*(1-t)+self.heights[1]*t+4*self.crown*t*(1-t)

    def properties(self, water_ngf):
        return dict(source_ids=self.source_ids, names=self.names,clipped_at_context_boundary=self.clipped,
                deck_elevation_source='estimated:interpolate IGN terrain at OSM deck endpoints + procedural crown',
                cross_section_source='procedural:0.7m slab, 0.35m maximum crown; not surveyed bridge structure',
                endpoint_ngf_m=[round(h+self.terrain.origin_ngf,3) for h in self.heights],
                endpoint_xy_projected_m=[list(p) for p in self.ends],
                minimum_centerline_clearance_m=round(min(self.height((self.center[0]+self.direction[0]*(self.start+(self.end-self.start)*t),
                        self.center[1]+self.direction[1]*(self.start+(self.end-self.start)*t)))+self.terrain.origin_ngf-water_ngf
                        for t in [.1,.25,.5,.75,.9]),3))


def decks(geometry, features, terrain):
    if geometry is None: return []
    result = []
    for polygon in polygon_parts(geometry):
        matches = [f for f in features if shape(f['geometry']).buffer(f['properties']['width_m']/2+.01).intersects(polygon)]
        if matches: result.append(BridgeDeck(polygon,matches,terrain))
    return sorted(result,key=lambda d:(d.source_ids,d.center))
