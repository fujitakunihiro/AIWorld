import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT/'unreal/scripts/generate_paris_morris.py'
spec=importlib.util.spec_from_file_location('paris_morris',SCRIPT)
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)


class MorrisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first=module.generate();cls.second=module.generate()

    def test_reproducible_from_same_archived_osm_and_scene(self):
        self.assertEqual(self.first,self.second)
        self.assertEqual(len(self.first['texture_sha256']),64)

    def test_mapped_positions_surface_and_clearances(self):
        records=self.first['records']
        self.assertEqual(sum(r['kind']=='column' for r in records),7)
        self.assertEqual(sum(r['kind']=='sign' for r in records),1)
        self.assertEqual(self.first['rejected'],[])
        self.assertEqual(len({r['source_id'] for r in records}),len(records))
        geo=module.Georeference(module.read(ROOT/'gis/config/ile_de_la_cite.json'))
        for r in records:
            self.assertTrue(r['source_id'].startswith('osm/node/'))
            self.assertEqual(r['position_provenance'],'mapped_osm_node')
            self.assertEqual(r['appearance_provenance'],'original_inferred_design')
            self.assertGreaterEqual(r['path_coverage'],.98)
            self.assertGreaterEqual(r['one_metre_clearance_coverage'],.9)
            self.assertGreater(r['building_distance_m'],1)
            self.assertGreater(r['water_distance_m'],1)
            self.assertGreater(r['nearest_furniture_cm'],r['footprint_radius_cm']+65)
            lon,lat,_=geo.from_ue(*r['anchor_cm'])
            self.assertLess(math.dist((lon,lat),r['wgs84']),1e-8)

    def test_geometry_and_distinct_source_types(self):
        self.assertEqual({o['id'] for o in self.first['objects']},{'column_iron','column_paper','sign_iron','sign_paper'})
        for o in self.first['objects']:
            self.assertEqual(len(o['positions_cm']),len(o['uv0']))
            self.assertEqual(len(o['indices'])%3,0)
            self.assertTrue(all(math.isfinite(v) for p in o['positions_cm'] for v in p))
        self.assertEqual(self.first['inspection_camera']['source_id'],'osm/node/9693401739')

    def test_poster_reading_direction_on_cylinder(self):
        paper=next(o for o in self.first['objects'] if o['id']=='column_paper')
        samples=[]
        for p,uv in zip(paper['positions_cm'],paper['uv0']):
            a=math.atan2(p[1],p[0])
            if abs(p[2]-58)<.001 and -.001<=a<=.10:samples.append((a,uv[0]))
        a,u=min(samples,key=lambda s:s[0]);b,v=max(samples,key=lambda s:s[0])
        self.assertGreater(b-a,.09)
        self.assertGreater(u,v,'Outside-facing text must not be mirrored')


if __name__=='__main__':unittest.main()
