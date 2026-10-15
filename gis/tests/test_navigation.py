import copy,math,unittest
from shapely.geometry import LineString,Polygon,mapping,shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.pedestrians import generate_routes,validate_network
from paris_twin.navigation import generate_navigation,validate_navigation,shortest_path


class NavigationTests(unittest.TestCase):
    def fixture(self,barrier=False,layers=(0,0)):
        self.geo=Georeference(read(ROOT/'gis/config/ile_de_la_cite.json'));x,y=self.geo.origin
        self.terrain=type('Flat',(),{'local':lambda self,p:2.})()
        lines=[LineString([(x,y),(x+20,y)]),LineString([(x+22,y),(x+40,y),(x+40,y+20)])]
        roads=[dict(geometry=mapping(line),properties=dict(source_id=f'osm/way/{i}',source_url=f'https://www.openstreetmap.org/way/{i}',source_snapshot='fixture',source_license='ODbL-1.0',width_m=4,tunnel=False,layer=layers[i],tags={'highway':'footway'})) for i,line in enumerate(lines)]
        walking=Polygon([(x-3,y-3),(x+44,y-3),(x+44,y+24),(x-3,y+24)])
        blocked=Polygon([(x+20.5,y-3),(x+21.5,y-3),(x+21.5,y+24),(x+20.5,y+24)]) if barrier else Polygon()
        crowd,network=generate_routes(self.geo,roads,self.terrain,None,blocked,None,walking,[],[])
        return crowd,network,roads,blocked

    def test_routes_join_with_safe_traceable_connectors_and_reproduce(self):
        crowd,network,roads,_=self.fixture();a,b=copy.deepcopy(crowd),copy.deepcopy(network)
        graph=generate_navigation(crowd,network,self.geo,roads,Polygon(),self.terrain,None)
        self.assertGreater(graph['report']['connectors'],0);self.assertEqual(graph['report']['components'],1)
        self.assertEqual(validate_navigation(crowd),[]);self.assertEqual(validate_network(network,{'osm/way/0','osm/way/1'}),[])
        self.assertLess(shortest_path(graph,graph['nodes'][0]['id'],graph['nodes'][-1]['id']),math.inf)
        generate_navigation(a,b,self.geo,roads,Polygon(),self.terrain,None)
        self.assertEqual(a,crowd);self.assertEqual(b,network)

    def test_building_or_vehicle_lane_keeps_components_separate(self):
        for mode in ['building','vehicle']:
            crowd,network,roads,blocked=self.fixture(mode=='building');x,y=self.geo.origin
            lane=Polygon([(x+20.5,y-3),(x+21.5,y-3),(x+21.5,y+24),(x+20.5,y+24)]) if mode=='vehicle' else Polygon()
            graph=generate_navigation(crowd,network,self.geo,roads,lane,self.terrain,None)
            self.assertEqual(graph['report']['components'],2)
            self.assertEqual(graph['report']['connectors'],0)
            self.assertTrue(math.isinf(shortest_path(graph,graph['nodes'][0]['id'],graph['nodes'][-1]['id'])))

    def test_different_layers_do_not_join_without_an_explicit_osm_node(self):
        crowd,network,roads,_=self.fixture(layers=(0,1))
        graph=generate_navigation(crowd,network,self.geo,roads,Polygon(),self.terrain,None)
        self.assertEqual(graph['report']['components'],2)

    def test_corrupt_graph_cost_or_endpoint_is_rejected(self):
        crowd,network,roads,_=self.fixture()
        graph=generate_navigation(crowd,network,self.geo,roads,Polygon(),self.terrain,None)
        graph['edges'][0]['length_cm']=-1
        self.assertIn('invalid_navigation_edge',validate_navigation(crowd))
        graph['edges'][0]['length_cm']=999999
        self.assertIn('invalid_navigation_cost',validate_navigation(crowd))

    def test_vehicle_boundary_keeps_a_body_width_clearance(self):
        crowd,network,roads,_=self.fixture();x,y=self.geo.origin
        # The old zero-margin difference could accept a line along a road's
        # boundary; the pedestrian body must also stay out of the lane.
        lane=Polygon([(x-3,y-.2),(x+44,y-.2),(x+44,y),(x-3,y)])
        graph=generate_navigation(crowd,network,self.geo,roads,lane,self.terrain,None)
        self.assertEqual(graph['report']['connectors'],0)


if __name__=='__main__':unittest.main()
