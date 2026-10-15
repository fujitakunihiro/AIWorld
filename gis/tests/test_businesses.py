import gzip,tempfile,unittest
from pathlib import Path
from shapely.geometry import Point,Polygon,mapping,shape
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,read
from paris_twin.mesh import Mesh
from paris_twin.businesses import mapped_businesses,generate_businesses,prototypes

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.geo=Georeference(CONFIG);self.x,self.y=self.geo.origin
        x,y=self.x,self.y
        self.building=dict(geometry=mapping(Polygon([(x,y),(x+20,y),(x+20,y+10),(x,y+10)])),properties=dict(source_id='osm/way/1',tags={'building':'residential'}))
        self.walk=Polygon([(x-3,y-10),(x+23,y-10),(x+23,y),(x-3,y)])
        self.terrain=type('Terrain',(),dict(local=lambda self,p:2.))()

    def poi(self,outdoor='yes'):
        x,y=self.x,self.y
        return dict(geometry=mapping(Point(x+10,y+4)),properties=dict(source_id='osm/node/2',wgs84_centre=list(self.geo.inverse.transform(x+10,y+4)),
            name='Fixture café',outdoor_seating_tag=outdoor))

    def generate(self,feature=None,walking=None,roads=None):
        return generate_businesses(self.geo,[feature or self.poi()],[self.building],self.terrain,walking if walking is not None else self.walk,None,roads,[])

    def test_mapped_poi_is_retained_and_facade_and_seats_are_inferred(self):
        poi=self.poi();a=self.generate(poi);b=self.generate(poi);self.assertEqual(a,b)
        batches,features,obstacles,report=a
        self.assertEqual(len(features),1);self.assertEqual(len(obstacles),1)
        p=features[0]['properties'];self.assertEqual(p['wgs84_centre'],poi['properties']['wgs84_centre'])
        self.assertIn('inferred:',p['facade_position_source']);self.assertTrue(p['terrace_placed'])
        self.assertTrue(self.walk.covers(obstacles[0]));self.assertGreaterEqual(obstacles[0].distance(shape(self.building['geometry'])),1.2)
        self.assertEqual({i['source_id'] for b in batches for i in b['instances']},{'osm/node/2'})
        self.assertAlmostEqual(p['terrace_cm'][2],204)

    def test_no_tag_narrow_walkway_or_road_conflict_never_gets_seats(self):
        for tag in [None,'no']:
            self.assertEqual(self.generate(self.poi(tag))[3]['report']['terraces'],0)
        x,y=self.x,self.y
        narrow=Polygon([(x-3,y-1.5),(x+23,y-1.5),(x+23,y),(x-3,y)])
        a=self.generate(walking=narrow);self.assertEqual(len(a[1]),1);self.assertEqual(a[3]['report']['terraces'],0)
        a=self.generate(roads=self.walk);self.assertEqual(a[1],[])

    def test_monuments_and_duplicate_facade_space_are_not_decorated(self):
        self.building['properties']['tags']['building']='cathedral';self.assertEqual(self.generate()[1],[])
        self.building['properties']['tags']['building']='residential'
        p=self.poi();p2=self.poi();p2['properties']['source_id']='osm/node/3'
        a=generate_businesses(self.geo,[p,p2],[self.building],self.terrain,self.walk,None,None,[])
        self.assertEqual(len(a[1]),1);self.assertEqual(len(a[3]['report']['skipped']),1)

    def test_archived_node_name_and_tag_are_not_an_entrance_claim(self):
        lon,lat=CONFIG['origin_wgs84']
        xml=f'<osm><node id="2" lon="{lon}" lat="{lat}"><tag k="amenity" v="cafe"/><tag k="name" v="Café Test"/><tag k="outdoor_seating" v="yes"/></node></osm>'
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'osm-map.xml.gz').write_bytes(gzip.compress(xml.encode()))
            f=mapped_businesses(p,{'files':{'osm-map.xml.gz':{}}},self.geo)[0]['properties']
            self.assertEqual(f['name'],'Café Test');self.assertEqual(f['source_id'],'osm/node/2')
            self.assertIn('not a surveyed entrance',f['position_source'])
        for m in prototypes(self.geo,Mesh):
            self.assertEqual(len(m['positions_cm']),len(m['normals']))
            self.assertTrue(all(0<=i<len(m['positions_cm']) for i in m['indices']))


if __name__=='__main__':unittest.main()
