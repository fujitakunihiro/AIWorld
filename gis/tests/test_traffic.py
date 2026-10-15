import unittest
from shapely.geometry import LineString,Point,Polygon,mapping,shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.mesh import Mesh
from paris_twin.traffic import generate_traffic,validate_traffic,vehicle_models,speed_limit

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.geo=Georeference(CONFIG);self.x,self.y=self.geo.origin
        self.line=LineString([(self.x,self.y),(self.x+100,self.y)])
        self.terrain=type('Terrain',(),dict(local=lambda self,p:2.))()

    def road(self,**tags):
        return dict(geometry=mapping(self.line),properties=dict(source_id='osm/way/1',source_url='https://www.openstreetmap.org/way/1',
            source_snapshot='osm.json',source_license='ODbL-1.0',width_m=12,tunnel=False,layer=0,tags=dict(highway='primary',**tags)))

    def generate(self,road=None,water=None,buildings=None,paths=None,decks=None):
        return generate_traffic(self.geo,[road or self.road()],self.terrain,water,buildings if buildings is not None else Polygon(),
            self.line.buffer(6),paths,decks or [],[])

    def test_direction_and_speed_caps(self):
        for oneway,direction in [('yes',1),('-1',-1)]:
            cars,network=self.generate(self.road(oneway=oneway,maxspeed='10'))
            self.assertEqual(len(cars['routes']),1)
            r=cars['routes'][0];self.assertGreater((r['points_cm'][-1][0]-r['points_cm'][0][0])*direction,0)
            self.assertAlmostEqual(r['speed_mps'],10/3.6,places=4)
            self.assertEqual(validate_traffic(network,{'osm/way/1'}),[])
        cars,_=self.generate();self.assertEqual({r['lane'] for r in cars['routes']},{'forward_right','reverse_right'})
        forward=next(r for r in cars['routes'] if r['lane']=='forward_right')
        self.assertGreater(forward['points_cm'][0][1],0) # right of east is south
        self.assertAlmostEqual(speed_limit({'maxspeed':'20 mph'}),8.9408)
        self.assertIsNone(speed_limit({'maxspeed':'signals'}))

    def test_restrictions_and_narrow_roads_are_excluded(self):
        for tags in [dict(access='private'),dict(motor_vehicle='destination;permit'),dict(highway='footway'),dict(oneway='reversible')]:
            road=self.road();road['properties']['tags'].update(tags)
            self.assertEqual(self.generate(road)[0]['agents'],[])
        road=self.road();road['properties']['width_m']=3
        cars,_=generate_traffic(self.geo,[road],self.terrain,None,Polygon(),self.line.buffer(1.5),None,[],[])
        self.assertEqual(cars['routes'],[])

    def test_full_vehicle_clearance_water_crossing_and_building(self):
        x,y=self.x,self.y;water=Point(x+50,y).buffer(8);building=Point(x+20,y).buffer(3)
        crossing=LineString([(x+70,y-10),(x+70,y+10)]).buffer(1)
        cars,network=self.generate(water=water,buildings=building,paths=crossing)
        self.assertEqual(validate_traffic(network,{'osm/way/1'}),[])
        for r in network['routes']:
            sweep=shape(r['geometry']).buffer(2.4)
            self.assertEqual(sweep.intersection(water).area,0)
            self.assertEqual(sweep.intersection(crossing).area,0)
            self.assertEqual(sweep.intersection(building).area,0)
        deck=type('Deck',(),dict(geometry=self.line.buffer(6),height=lambda self,p:7.))()
        cars,network=self.generate(water=water,decks=[deck])
        self.assertTrue(all(p[2]==700 for r in cars['routes'] for p in r['points_cm']))
        self.assertEqual(validate_traffic(network,{'osm/way/1'}),[])

    def test_stable_generation_and_vehicle_scale(self):
        self.assertEqual(self.generate(),self.generate())
        models=vehicle_models(self.geo,Mesh);self.assertEqual(len(models),6)
        body=models[0];self.assertAlmostEqual(max(p[0] for p in body['positions_cm'])-min(p[0] for p in body['positions_cm']),420)
        self.assertAlmostEqual(max(p[2] for p in body['positions_cm']),155)
        self.assertTrue(all('inferred:' in a['provenance'] for a in self.generate()[0]['agents']))
        for m in models:
            self.assertEqual(len(m['positions_cm']),len(m['normals']))
            self.assertTrue(all(0<=i<len(m['positions_cm']) for i in m['indices']))


if __name__=='__main__':unittest.main()
