import unittest
from shapely.geometry import LineString,Point,Polygon,MultiLineString,mapping,shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.mesh import Mesh
from paris_twin.pedestrians import generate_routes,validate_network,person_models

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class PedestrianTests(unittest.TestCase):
    def setUp(self):
        self.geo=Georeference(CONFIG);self.x,self.y=self.geo.origin
        self.terrain=type('TerrainFixture',(),dict(local=lambda self,p:2.))()

    def road(self,identifier,line,highway='footway'):
        return dict(geometry=mapping(line),properties=dict(source_id=identifier,source_snapshot='osm.json',source_license='ODbL-1.0',
            source_url='https://www.openstreetmap.org/way/'+identifier.split('/')[-1],width_m=4,
            tunnel=False,layer=0,tags={'highway':highway}))

    def test_paths_do_not_cut_corners_or_cross_water_and_are_repeatable(self):
        x,y=self.x,self.y
        line=LineString([(x,y),(x+25,y),(x+25,y+30),(x+65,y+30)])
        path=line.buffer(1.7);water=Point(x+45,y+30).buffer(3)
        roads=[self.road('osm/way/1',line)]
        a,network=generate_routes(self.geo,roads,self.terrain,water,Polygon(),None,path,[],[])
        b,_=generate_routes(self.geo,roads,self.terrain,water,Polygon(),None,path,[],[])
        self.assertEqual(a,b);self.assertGreater(len(a['routes']),1)
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        for route in network['routes']:
            self.assertEqual(shape(route['geometry']).intersection(water).length,0)
            self.assertTrue(all(p[2]==204 for p in route['points_cm']))
        self.assertTrue(all(p['provenance'].startswith('inferred:') for p in a['agents']))

    def test_bridges_furniture_and_buildings_limit_routes(self):
        x,y=self.x,self.y;line=LineString([(x,y),(x+100,y)])
        water=Polygon([(x+30,y-10),(x+70,y-10),(x+70,y+10),(x+30,y+10)])
        deck=type('DeckFixture',(),dict(geometry=line.buffer(2),height=lambda self,p:7.))()
        building=Point(x+20,y).buffer(2)
        furniture=[dict(properties=dict(kind='bench',wgs84_centre=list(self.geo.inverse.transform(x+80,y))))]
        crowd,network=generate_routes(self.geo,[self.road('osm/way/1',line)],self.terrain,water,building,None,line.buffer(2),[deck],furniture)
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        self.assertTrue(any(max(p[0] for p in r['points_cm'])>4000 and min(p[0] for p in r['points_cm'])<4000 for r in crowd['routes']))
        self.assertTrue(all(p[2]==700 for r in crowd['routes'] for p in r['points_cm']))
        for route in network['routes']:
            g=shape(route['geometry']);self.assertFalse(g.intersects(building.buffer(.49)))
            self.assertGreater(g.distance(Point(x+80,y)),1.24)

    def test_sidewalks_are_inferred_and_private_roads_are_excluded(self):
        x,y=self.x,self.y;line=LineString([(x,y),(x+80,y)])
        sidewalk=line.buffer(3.5).difference(line.buffer(2))
        road=self.road('osm/way/2',line,'residential')
        crowd,network=generate_routes(self.geo,[road],self.terrain,None,Polygon(),sidewalk,None,[],[])
        self.assertEqual({r['route_source'] for r in crowd['routes']},{'inferred_sidewalk_left','inferred_sidewalk_right'})
        self.assertEqual(validate_network(network,{'osm/way/2'}),[])
        road['properties']['tags']['access']='private'
        self.assertEqual(generate_routes(self.geo,[road],self.terrain,None,Polygon(),sidewalk,None,[],[])[0]['agents'],[])

    def test_joint_models_have_real_human_scale_and_valid_indices(self):
        models=person_models(self.geo,Mesh);self.assertEqual(len(models),11)
        for m in models:
            self.assertEqual(len(m['positions_cm']),len(m['normals']))
            self.assertTrue(all(0<=i<len(m['positions_cm']) for i in m['indices']))
            self.assertLess(len(m['indices'])//3,200)
        torso=next(m for m in models if m['id']=='person_torso_0')
        self.assertEqual(max(p[2] for p in torso['positions_cm']),144)
        head=next(m for m in models if m['id']=='person_head')
        self.assertEqual(max(p[2] for p in head['positions_cm']),26)
        far=next(m for m in models if m['id']=='person_far_0')
        self.assertEqual(len(far['vertex_colors']),len(far['positions_cm']))
        self.assertEqual(set(far['vertex_colors']),{'#45647b','#c29d80','#343b43'})
        self.assertEqual(max(p[2] for p in far['positions_cm']),172)

    def test_new_bin_and_bicycle_proxies_leave_room_for_people(self):
        x,y=self.x,self.y;line=LineString([(x,y),(x+120,y)])
        furniture=[dict(properties=dict(kind=kind,wgs84_centre=list(self.geo.inverse.transform(x+dx,y)))) for kind,dx in [('bin',35),('bicycle_rack',80)]]
        _,network=generate_routes(self.geo,[self.road('osm/way/1',line)],self.terrain,None,Polygon(),None,line.buffer(2),[],furniture)
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        for route in network['routes']:
            self.assertGreaterEqual(shape(route['geometry']).distance(Point(x+35,y)),.79)
            self.assertGreaterEqual(shape(route['geometry']).distance(Point(x+80,y)),1.34)

    def test_terrace_footprint_is_excluded_from_walking_routes(self):
        x,y=self.x,self.y;line=LineString([(x,y),(x+120,y)])
        table=Polygon([(x+50,y-2),(x+55,y-2),(x+55,y+2),(x+50,y+2)])
        _,network=generate_routes(self.geo,[self.road('osm/way/1',line)],self.terrain,None,Polygon(),None,line.buffer(2),[],[],extra_obstacles=[table])
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])
        for r in network['routes']:self.assertGreaterEqual(shape(r['geometry']).distance(table),.37)

    def test_multipart_road_keeps_distinct_reproducible_route_ids(self):
        x,y=self.x,self.y
        lines=[LineString([(x,y),(x+30,y)]),LineString([(x,y+15),(x+30,y+15)])]
        surface=MultiLineString(lines).buffer(2)
        road=self.road('osm/way/1',MultiLineString(lines))
        a,network=generate_routes(self.geo,[road],self.terrain,None,Polygon(),None,surface,[],[])
        road['geometry']=mapping(MultiLineString(list(reversed(lines))))
        b,_=generate_routes(self.geo,[road],self.terrain,None,Polygon(),None,surface,[],[])
        self.assertEqual(a,b);self.assertEqual(len(a['routes']),2)
        self.assertEqual(len({r['id'] for r in a['routes']}),2)
        self.assertEqual(validate_network(network,{'osm/way/1'}),[])


if __name__=='__main__':unittest.main()
