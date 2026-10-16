import math
import unittest
from shapely.geometry import Polygon, mapping
from paris_twin.coordinates import Georeference
from paris_twin.facades import generate_facades
from paris_twin.mesh import Mesh


class FacadeDetailTests(unittest.TestCase):
    def test_near_field_budget_provenance_and_unchanged_window_count(self):
        config=dict(projected_crs='EPSG:2154',origin_wgs84=[2.3471,48.8547],core_size_m=500,context_buffer_m=150,quality_size_m=100)
        geo=Georeference(config);x,y=geo.origin
        def building(offset,identifier,tags=None):
            g=Polygon([(x+offset,y),(x+offset+12,y),(x+offset+12,y+12),(x+offset,y+12)])
            return dict(geometry=mapping(g),properties=dict(source_id=identifier,tags=tags or {},height_parts=[dict(
                geometry=mapping(g),height_gutter_m=15,ground_ngf_m=35,gutter_segments_m=[],roof=dict(form='flat',rise_m=0))]))
        terrain=type('Terrain',(),dict(origin_ngf=35,ngf=lambda self,p:35,local=lambda self,p:0))()
        near,far=building(0,'osm/way/near'),building(150,'osm/way/far')
        objects,report=generate_facades(geo,[near,far],terrain,Mesh)
        self.assertGreater(report['detailed_windows'],0)
        self.assertEqual(report['detail_buildings'],1)
        self.assertEqual(report['detailed_windows']*2,report['windows'])
        self.assertGreater(report['planters'],0)
        self.assertGreater(report['detailed_balconies'],0)
        detail_kinds=('facade_relief','facade_joinery','facade_railing','facade_planter','facade_garden')
        for obj in objects:
            if obj['kind'] not in detail_kinds:continue
            self.assertTrue(obj['properties']['cosmetic_only'])
            self.assertEqual(obj['properties']['reproduction_level'],'L1')
            self.assertTrue(all(-65<=p[0]<=1265 for p in obj['positions_cm']))
            self.assertTrue(all(abs(math.sqrt(sum(v*v for v in n))-1)<1e-6 for n in obj['normals']))
            self.assertTrue(all(0<=i<len(obj['positions_cm']) for i in obj['indices']))
            if obj['kind'] in ('facade_joinery','facade_garden'):self.assertEqual(len(obj['vertex_colors']),len(obj['positions_cm']))
        again,repeat=generate_facades(geo,[near,far],terrain,Mesh)
        self.assertEqual(objects,again)
        self.assertEqual(report,repeat)
        config['quality_size_m']=1
        _,small=generate_facades(Georeference(config),[near,far],terrain,Mesh)
        self.assertEqual(small['detailed_windows'],0)
        self.assertEqual(small['planters'],0)
        self.assertEqual(small['detailed_balconies'],0)
        self.assertEqual(small['windows'],report['windows'])
        near['properties']['tags']={'building':'cathedral'}
        _,excluded=generate_facades(geo,[near],terrain,Mesh)
        self.assertEqual(excluded['windows'],0)
