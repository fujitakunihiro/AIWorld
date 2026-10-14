import gzip
import tempfile
import unittest
from pathlib import Path
from shapely.geometry import Point, Polygon, LineString, GeometryCollection, mapping
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT, read, write
from paris_twin.mesh import Mesh
from paris_twin.street_furniture import mapped_nodes, generate_street_objects, model_meshes
from paris_twin.facades import generate_facades

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class StreetTests(unittest.TestCase):
    def setUp(self):
        self.geo=Georeference(CONFIG);self.x,self.y=self.geo.origin
        self.terrain=type('TerrainFixture',(),dict(origin_ngf=30.,local=lambda self,p:5.,ngf=lambda self,p:35.))()

    def test_xml_and_json_nodes_preserve_ids_tags_and_direction(self):
        lon,lat=CONFIG['origin_wgs84']
        xml=f'<osm><node id="12" lon="{lon}" lat="{lat}"><tag k="natural" v="tree"/><tag k="height" v="12"/></node><node id="21" lon="{lon}" lat="{lat}"><tag k="amenity" v="bench"/><tag k="direction" v="90"/></node><node id="30" lon="0" lat="0"><tag k="natural" v="tree"/></node></osm>'
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp);(raw/'osm-map.xml.gz').write_bytes(gzip.compress(xml.encode()))
            result=mapped_nodes(raw,{'files':{'osm-map.xml.gz':{}}},self.geo)
            self.assertEqual([f['properties']['source_id'] for f in result],['osm/node/12','osm/node/21'])
            self.assertEqual(result[0]['properties']['height_source'],'osm:height (unverified tag)')
            self.assertEqual(result[0]['properties']['height_m'],12)
            # Bench model faces local UE +Y; rotating 270 degrees faces east.
            self.assertEqual(result[1]['properties']['yaw_degrees'],270)
            write(raw/'osm.json',{'elements':[dict(type='node',id=12,lon=lon,lat=lat,tags={'natural':'tree','height':'12'})]})
            json_result=mapped_nodes(raw,{'files':{'osm.json':{}}},self.geo)
            self.assertEqual(json_result[0]['geometry'],result[0]['geometry'])
            self.assertEqual(json_result[0]['properties']['source_id'],result[0]['properties']['source_id'])

    def feature(self,identifier,xy,kind='tree'):
        return dict(geometry=mapping(Point(xy)),properties=dict(source_id=identifier,kind=kind,tags={},
            wgs84_centre=list(self.geo.inverse.transform(*xy)),height_m=10 if kind=='tree' else 4.5,
            height_source='estimated:fixture',crown_diameter_m=6,direction_source='estimated:road',yaw_degrees=0))

    def test_no_relocation_and_bridge_surface_for_mapped_instances(self):
        x,y=self.x,self.y
        features=[self.feature('osm/node/1',(x,y)),self.feature('osm/node/2',(x+10,y)),
                  self.feature('osm/node/3',(x+20,y)),self.feature('osm/node/4',(x+30,y))]
        buildings=Polygon([(x-1,y-1),(x+1,y-1),(x+1,y+1),(x-1,y+1)])
        water=Polygon([(x+9,y-3),(x+21,y-3),(x+21,y+3),(x+9,y+3)])
        deck=type('DeckFixture',(),dict(geometry=Point(x+20,y).buffer(2),height=lambda self,p:8.))()
        batches,picks,report=generate_street_objects(self.geo,features,self.terrain,water,buildings,[],None,None,[deck])
        self.assertEqual([p['id'] for p in picks],['osm/node/3','osm/node/4'])
        self.assertEqual([i['source_id'] for i in report['skipped']],['osm/node/1','osm/node/2'])
        self.assertEqual(picks[0]['point_cm'],[2000.,0.,800.])
        self.assertEqual(report['inferred_positions'],0)
        self.assertEqual(sum(len(b['instances']) for b in batches),4)
        self.assertEqual(batches[0]['instances'][0]['position_cm'],picks[0]['point_cm'])

    def test_authored_prototypes_are_small_valid_and_shared(self):
        models=model_meshes(self.geo,Mesh)
        self.assertEqual(len(models),6)
        for model in models:
            self.assertTrue(model['indices'])
            self.assertEqual(len(model['positions_cm']),len(model['normals']))
            self.assertTrue(all(0<=i<len(model['positions_cm']) for i in model['indices']))
            self.assertLess(len(model['indices'])//3,500)
            self.assertGreaterEqual(min(p[2] for p in model['positions_cm']),0)

    def test_clipped_roads_with_point_fragments_can_orient_benches(self):
        x,y=self.x,self.y
        feature=self.feature('osm/node/1',(x+5,y+1),'bench')
        road=dict(geometry=mapping(GeometryCollection([LineString([(x,y),(x+20,y)]),Point(x+22,y)])),
                  properties=dict(tunnel=False,layer=0,source_id='osm/way/9'))
        _,picks,_=generate_street_objects(self.geo,[feature],self.terrain,None,Polygon(),[road],None,None,[])
        self.assertEqual(picks[0]['properties']['yaw_degrees'],0)
        self.assertEqual(picks[0]['properties']['orientation_road_source_id'],'osm/way/9')

    def building(self,identifier,g):
        return dict(geometry=mapping(g),properties=dict(source_id=identifier,tags={'building':'apartments'},height_parts=[
            dict(geometry=mapping(g),height_gutter_m=17,ground_ngf_m=35,gutter_segments_m=[],roof=dict(form='mansard',rise_m=3))]))

    def test_party_walls_omit_windows_and_keep_exposed_courtyards(self):
        x,y=self.x,self.y
        a=Polygon([(x,y),(x+12,y),(x+12,y+12),(x,y+12)])
        b=Polygon([(x+12,y),(x+24,y),(x+24,y+12),(x+12,y+12)])
        _,alone=generate_facades(self.geo,[self.building('a',a)],self.terrain,Mesh)
        objects,together=generate_facades(self.geo,[self.building('a',a),self.building('b',b)],self.terrain,Mesh)
        self.assertLess(together['windows'],alone['windows']*2)
        self.assertGreater(together['party_wall_columns_omitted'],0)
        for key in ['entrances','balconies','cornices','dormers']:self.assertGreater(together[key],0)
        self.assertTrue(all(o['properties']['reproduction_level']=='L1' for o in objects))
        # No generated glass or iron crosses the shared x=12m party wall.
        for o in objects:
            if o['kind']=='facade_glass':self.assertFalse(any(abs(p[0]-1200)<1 and 100<p[1]*-1<1100 for p in o['positions_cm']))
        courtyard=Polygon([(x,y),(x+24,y),(x+24,y+24),(x,y+24)],holes=[[(x+7,y+7),(x+7,y+17),(x+17,y+17),(x+17,y+7)]])
        objects,report=generate_facades(self.geo,[self.building('c',courtyard)],self.terrain,Mesh)
        self.assertTrue(any(700<=p[0]<=1700 and -1700<=p[1]<=-700 for o in objects if o['kind']=='facade_glass' for p in o['positions_cm']))


if __name__=='__main__':unittest.main()
