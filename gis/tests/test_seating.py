import copy
import math
import unittest
from shapely.geometry import LineString,Point,Polygon,mapping,shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.businesses import rectangle
from paris_twin.seating import generate_seating,validate_seating
from paris_twin.pedestrians import validate_network,person_models
from paris_twin.mesh import Mesh


class SeatingTests(unittest.TestCase):
    def fixture(self):
        geo=Georeference(read(ROOT/'gis/config/ile_de_la_cite.json'));x,y=geo.origin
        terrain=type('Flat',(),{'local':lambda self,p:2.})()
        foot=rectangle((x,y),(1,0),(0,-1),2.2,1.65)
        walk=Point(x,y).buffer(10)
        line=LineString([(x-4,y),(x-1.65,y)])
        route=dict(id='approach',source_id='osm/way/1',source_url='fixture',source_snapshot='fixture',source_license='ODbL',
            route_source='inferred_business_approach',points_cm=[[-400,0,204],[-165,0,204]],geometry=mapping(line))
        crowd=dict(routes=[{k:v for k,v in route.items() if k!='geometry'}],destinations=[dict(id='visit',business_id='osm/node/1',route_id='approach')],report={})
        network=dict(routes=[route],walkable_geometry=mapping(walk.difference(foot.buffer(.38))),origin_projected_m=list(geo.origin))
        business=dict(id='osm/node/1',properties=dict(terrace_cm=[0,0,204],facade_yaw_degrees=0))
        placement=dict(walking_geometry=mapping(walk),road_geometry=mapping(Polygon()),terraces=[dict(source_id=business['id'],geometry=mapping(foot))])
        return geo,terrain,crowd,network,business,placement

    def generate(self,values,buildings=None,water=None):
        geo,terrain,crowd,network,b,p=values
        return generate_seating(crowd,network,geo,terrain,None,[b],p,buildings if buildings is not None else Polygon(),water,[])

    def test_reserved_seat_is_connected_clear_repeatable_and_not_public(self):
        values=self.fixture();saved=copy.deepcopy(values[2:]);report=self.generate(values)
        geo,_,crowd,network,_,_=values
        self.assertEqual(report['seats'],1);self.assertEqual(validate_seating(crowd),[])
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        d=crowd['destinations'][0];route=crowd['routes'][-1]
        self.assertEqual(route['points_cm'][0],[-165,0,204]);self.assertAlmostEqual(abs(route['points_cm'][-1][0]),72)
        self.assertEqual(route['points_cm'][-1][1:], [0,204]);self.assertEqual(d['seat_height_cm'],48)
        self.assertFalse(shape(network['walkable_geometry']).covers(shape(network['routes'][-1]['geometry'])))
        self.assertGreater(shape(network['routes'][-1]['geometry']).distance(Point(*geo.origin)),.60)
        other=self.fixture();other=other[:2]+saved;self.generate(other)
        self.assertEqual(crowd,other[2]);self.assertEqual(network,other[3])
        crowd['navigation']=dict(edges=[dict(route_id=route['id'])])
        self.assertIn('private_seat_in_public_graph',validate_seating(crowd))

    def test_obstructed_chair_keeps_standing_visit_and_does_not_invent_a_path(self):
        values=self.fixture();geo=values[0];x,y=geo.origin
        barrier=Point(x,y).buffer(1.5)
        report=self.generate(values,buildings=barrier)
        self.assertEqual(report['seats'],0);self.assertEqual(report['standing_fallbacks'],1)
        self.assertNotIn('seat_route_id',values[2]['destinations'][0]);self.assertEqual(len(values[2]['routes']),1)

    def test_roads_water_and_other_terraces_are_never_crossed(self):
        for obstacle in ['road','water','other_terrace']:
            values=self.fixture();geo=values[0];x,y=geo.origin
            barrier=Point(x,y).buffer(1.5)
            if obstacle=='road':values[5]['road_geometry']=mapping(barrier)
            if obstacle=='other_terrace':values[5]['terraces'].append(dict(source_id='other',geometry=mapping(barrier)))
            report=self.generate(values,water=barrier if obstacle=='water' else None)
            self.assertEqual(report['seats'],0,obstacle)

    def test_corrupt_private_route_and_seat_pose_are_rejected(self):
        values=self.fixture();self.generate(values);crowd=values[2]
        crowd['routes'][-1]['points_cm'][0][0]+=100
        self.assertIn('disconnected_reserved_seat',validate_seating(crowd))
        crowd['destinations'][0]['seat_height_cm']=500
        self.assertIn('invalid_reserved_seat_pose',validate_seating(crowd))
        values[3]['reserved_seat_surfaces']=[]
        self.assertIn('missing_reserved_seat_surface',validate_network(values[3],{'osm/way/1'}))

    def test_seated_far_lod_keeps_human_proportions_colours_and_feet_above_ground(self):
        models=person_models(self.fixture()[0],Mesh)
        for variant in range(3):
            m=next(m for m in models if m['id']==f'person_far_seated_{variant}')
            self.assertAlmostEqual(max(p[2] for p in m['positions_cm']),136)
            self.assertGreaterEqual(min(p[2] for p in m['positions_cm']),4)
            self.assertEqual(len(m['positions_cm']),len(m['vertex_colors']))
            self.assertGreaterEqual(max(p[0] for p in m['positions_cm']),50)
            source={p['id']:p for p in models}
            start=sum(len(source[name]['positions_cm']) for name in [f'person_torso_{variant}','person_head',f'person_arm_{variant}',f'person_arm_{variant}'])
            thighs=m['positions_cm'][start:start+2*len(source['person_thigh']['positions_cm'])]
            self.assertGreaterEqual(min(p[0] for p in thighs),-.00001)
            self.assertAlmostEqual(max(p[0] for p in thighs),40)


if __name__=='__main__':unittest.main()
