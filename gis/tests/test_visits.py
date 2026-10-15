import copy
import unittest
from shapely.geometry import LineString, Polygon, mapping, shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.pedestrians import generate_routes,validate_network
from paris_twin.visits import generate_visits,validate_visits


class VisitTests(unittest.TestCase):
    def fixture(self,barrier=False):
        geo=Georeference(read(ROOT/'gis/config/ile_de_la_cite.json'));x,y=geo.origin
        terrain=type('Flat',(),{'local':lambda self,p:2.})()
        line=LineString([(x,y),(x+40,y)])
        road=dict(geometry=mapping(line),properties=dict(source_id='osm/way/1',source_url='https://www.openstreetmap.org/way/1',source_snapshot='fixture',source_license='ODbL-1.0',width_m=4,tunnel=False,layer=0,tags={'highway':'footway'}))
        walking=Polygon([(x-2,y-2),(x+42,y-2),(x+42,y+9),(x-2,y+9)])
        obstruction=Polygon([(x-2,y+2),(x+42,y+2),(x+42,y+3),(x-2,y+3)]) if barrier else Polygon()
        crowd,network=generate_routes(geo,[road],terrain,None,obstruction,None,walking,[],[])
        business=dict(id='osm/node/10',point_cm=[2000,-850,200],properties=dict(kind='cafe',name='Fixture cafe',terrace_placed=True,terrace_cm=[2000,-600,204],facade_yaw_degrees=180))
        return geo,terrain,crowd,network,business

    def test_visits_are_connected_clear_reproducible_and_traceable(self):
        geo,terrain,crowd,network,business=self.fixture()
        before=copy.deepcopy((crowd,network))
        report=generate_visits(crowd,network,geo,terrain,None,[business])
        self.assertEqual(report['destinations'],1)
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        self.assertEqual(validate_visits(crowd,{business['id']}),[])
        d=crowd['destinations'][0]
        self.assertEqual(d['capacity'],1);self.assertIn('not real customers',d['provenance'])
        self.assertIn('osm/way/1',d['parent_route_id'])
        self.assertGreater(shape(network['routes'][-1]['geometry']).length,1)
        crowd2,network2=before;generate_visits(crowd2,network2,geo,terrain,None,[business])
        self.assertEqual(crowd,crowd2);self.assertEqual(network,network2)
        crowd['destinations'][0]['parent_distance_cm']+=100
        self.assertIn('disconnected_visit_approach',validate_visits(crowd,{business['id']}))

    def test_no_visit_can_cross_buildings_water_or_disconnected_surfaces(self):
        geo,terrain,crowd,network,business=self.fixture(True)
        report=generate_visits(crowd,network,geo,terrain,None,[business])
        self.assertEqual(crowd['destinations'],[])
        self.assertEqual(len(report['skipped']),1)
        self.assertIn('no direct clear approach',report['skipped'][0]['reason'])

    def test_unplaced_terraces_and_non_food_shops_are_not_visit_targets(self):
        geo,terrain,crowd,network,business=self.fixture()
        business['properties']['kind']='shop'
        generate_visits(crowd,network,geo,terrain,None,[business])
        self.assertEqual(crowd['destinations'],[])

    def test_shared_bridge_surface_does_not_allow_a_cafe_road_shortcut(self):
        geo,terrain,crowd,network,business=self.fixture();x,y=geo.origin
        road=Polygon([(x-2,y+2),(x+42,y+2),(x+42,y+3),(x-2,y+3)])
        generate_visits(crowd,network,geo,terrain,None,[business],road)
        self.assertEqual(crowd['destinations'],[])

    def test_endpoint_connection_keeps_planar_distance_precision(self):
        geo,terrain,crowd,network,business=self.fixture()
        # Far beyond the route end, so the nearest projection is an endpoint
        # with an irrational arclength instead of a rounded six-digit value.
        network['routes'][0]['points_cm'][-1][1]=.1234567
        business['properties']['terrace_cm'][0]=4300
        generate_visits(crowd,network,geo,terrain,None,[business])
        self.assertEqual(len(crowd['destinations']),1)
        self.assertAlmostEqual(crowd['destinations'][0]['parent_distance_cm'],LineString([p[:2] for p in network['routes'][0]['points_cm']]).length)
        self.assertEqual(validate_visits(crowd,{business['id']}),[])

    def test_visit_seed_preserves_existing_population_clearance(self):
        from paris_twin.visits import sample
        import math
        geo,terrain,crowd,network,business=self.fixture()
        trial=copy.deepcopy(crowd);generate_visits(trial,copy.deepcopy(network),geo,terrain,None,[business])
        conflicting=copy.deepcopy(crowd['agents'][0]);conflicting.update(id='sim/person/extra',progress_m=trial['agents'][0]['progress_m'])
        crowd['agents'].append(conflicting)
        generate_visits(crowd,network,geo,terrain,None,[business])
        routes={r['id']:r for r in crowd['routes']}
        a,b=[sample(routes[a['route_id']]['points_cm'],a['progress_m']*100) for a in crowd['agents']]
        self.assertGreaterEqual(math.dist(a[:2],b[:2]),125)


if __name__=='__main__':unittest.main()
