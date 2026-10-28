"""Validate the full rotating vessel envelope against the actual river and bridges."""
import hashlib, json, math, struct, sys, unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
import shapely
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'unreal/scripts'))
from prepare_paris_cruise import bridge_obstacles
G=ROOT/'unreal/assets/paris-cruise/Generated';D=ROOT/'unreal/AIWorld/Content/Data'
class CruiseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((G/'source.json').read_text(encoding='utf8'))
        cls.scene=json.loads((D/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
        cls.bridges=json.loads((D/'paris-bridges.json').read_text(encoding='utf8'))
        cls.water=json.loads((D/'paris-water.json').read_text(encoding='utf8'))
    def test_route_clears_riverbanks_and_every_bridge_through_full_rotation(self):
        s=self.source; r=s['route']; feature=next(f for f in self.scene['pick_features'] if f['id']==r['water_source_id'])
        river=unary_union([shapely.make_valid(Polygon(p[0],p[1:])) for p in feature['polygons_cm']])
        bridges=bridge_obstacles(self.scene,self.bridges,(D/'paris-digital-twin-meshes.bin').read_bytes())
        line=LineString([r['start_cm'],r['end_cm']]); sweep=line.buffer(r['clearance_radius_cm'],quad_segs=24)
        self.assertGreater(line.length,8000);self.assertAlmostEqual(line.length,r['length_cm']);self.assertTrue(river.buffer(.05).covers(sweep));self.assertFalse(sweep.intersects(bridges))
        self.assertGreater(r['clearance_radius_cm'],s['model_radius_cm']);self.assertEqual(self.scene['source_scene_sha256'],s['source_scene_sha256']);self.assertEqual(self.water['water_level_cm'],s['water_level_cm'])
    def test_checked_geometry_and_textures(self):
        count=0
        for part in self.source['parts']:
            for p in part['primitives']:
                raw=(G/p['file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),p['sha256']);magic,n,t=struct.unpack_from('<8sII',raw)
                self.assertEqual(magic,b'NDSCAN01');self.assertEqual(len(raw),16+n*32+t*12)
                self.assertTrue(np.isfinite(np.frombuffer(raw,dtype='<f4',count=n*8,offset=16)).all())
                self.assertLess(int(np.frombuffer(raw,dtype='<u4',offset=16+n*32).max()),n);count+=t
        self.assertGreater(count,140000);self.assertEqual(count,self.source['source_triangles'])
        for tex in self.source['textures']:self.assertEqual(hashlib.sha256((G/tex['file']).read_bytes()).hexdigest(),tex['sha256'])
if __name__=='__main__':unittest.main()
