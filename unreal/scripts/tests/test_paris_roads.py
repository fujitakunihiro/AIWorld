"""Validate generated street finish against the archived GIS, not a mock city."""
import hashlib
import json
import sys
from pathlib import Path
import unittest
import numpy as np
import shapely
from shapely.geometry import Point, Polygon

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_paris_roads import CONTENT, DTYPE, Surface, digest


class ParisRoadGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((CONTENT/'Data/paris-road-detail-source.json').read_text(encoding='utf-8'))
        cls.scene=json.loads((CONTENT/'Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
        cls.blob=np.memmap(CONTENT/'Data/paris-digital-twin-meshes.bin',dtype='u1',mode='r')
        cls.road=Surface(next(o for o in cls.scene['objects'] if o['kind']=='road'),cls.blob)
        cls.walk=Surface(next(o for o in cls.scene['objects'] if o['kind']=='sidewalk'),cls.blob)

    def test_source_archive_and_geometry_hashes(self):
        self.assertEqual(self.data['source_scene_sha256'],self.scene['source_scene_sha256'])
        self.assertEqual(self.data['source_mesh_sha256'],hashlib.sha256(self.blob).hexdigest())
        for item in self.data['objects']:
            self.assertEqual(item['geometry_sha256'],digest({k:item[k] for k in ('positions_cm','normals','vertex_colors','indices')}))

    def test_cosmetic_meshes_remain_on_existing_street_coverage(self):
        coverage=self.road.geometry.union(self.walk.geometry).buffer(2)
        shapely.prepare(coverage)
        self.assertGreater(self.data['kerb_stones'],0)
        for item in self.data['objects']:
            p=np.asarray(item['positions_cm']);n=np.asarray(item['normals']);ix=np.asarray(item['indices']).reshape(-1,3)
            self.assertTrue(np.isfinite(p).all())
            self.assertTrue(np.allclose(np.linalg.norm(n,axis=1),1,atol=1.e-6))
            self.assertTrue(shapely.covers(coverage,shapely.points(p[:,:2])).all(),item['id'])
            # A reversed winding creates black surfaces in real rendering.
            normal=np.cross(p[ix[:,2]]-p[ix[:,0]],p[ix[:,1]]-p[ix[:,0]])
            self.assertTrue((np.sum(normal*n[ix[:,0]],axis=1)>0).all(),item['id'])

    def test_inferred_drains_fit_roadway_and_exact_source_grade(self):
        self.assertGreater(self.data['drain_grates'],0)
        for item in self.data['placements']:
            self.assertEqual(item['source_surface_id'],'roads')
            self.assertTrue(self.road.geometry.covers(Polygon(item['footprint_cm'])))
            self.assertAlmostEqual(item['height_cm'],self.road.height(item['xy_cm'])+.3,places=4)

    def test_comparison_camera_preserves_real_scale_and_source_id(self):
        camera=self.data['preview_camera'];p=camera['position_cm']
        self.assertIn(camera['source_id'],{f['id'] for f in self.scene['pick_features'] if f['kind']=='road'})
        self.assertTrue(self.road.geometry.covers(Point(p[:2])))
        self.assertAlmostEqual(p[2]-self.road.height(p[:2]),170,places=4)


if __name__=='__main__':unittest.main()
