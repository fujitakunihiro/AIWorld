"""Check real-source provenance, safe lane occupancy and deterministic output."""
import hashlib,json,math,sys,unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,Point,LineString
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'unreal/scripts'))
from generate_paris_lane import generate,OUTPUT


class LaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet=json.loads(OUTPUT.read_text(encoding='utf-8'));cls.base=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-reference.json').read_text(encoding='utf-8'));cls.source=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8'))

    def test_source_and_base_preserved(self):
        p=self.packet;b=self.base
        self.assertEqual(p['source_scene_sha256'],b['source_scene_sha256']);self.assertEqual(p['georeference'],b['georeference']);self.assertEqual(p['records'][:len(b['records'])],b['records'])
        self.assertEqual(p['objects'][:len(b['objects'])],b['objects']);self.assertEqual(p['lane']['mapped_surface'],'sett')
        self.assertGreater(p['lane']['bicycles'],10);self.assertGreaterEqual(p['lane']['storefronts'],3)

    def test_geometry_and_provenance(self):
        ids={f['id'] for f in self.source['pick_features']};ids.add(self.packet['lane']['source_street_id'])
        for r in self.packet['records']:
            if not r['kind'].startswith('lane_'):continue
            self.assertIn(r['source_id'],ids);self.assertTrue(np.isfinite(r['anchor_cm']).all())
            for box in r.get('collision_boxes',[]):self.assertGreater(min(box['size_cm']),0);self.assertLess(max(box['size_cm']),500)
        for m in self.packet['objects']:
            if 'positions_cm' not in m:continue
            pos=np.array(m['positions_cm']);norm=np.array(m['normals']);indices=np.array(m['indices'])
            self.assertGreater(len(pos),0);self.assertTrue(np.isfinite(pos).all());self.assertTrue(np.isfinite(norm).all());self.assertTrue(np.allclose(np.linalg.norm(norm,axis=1),1,atol=.001));self.assertGreaterEqual(indices.min(),0);self.assertLess(indices.max(),len(pos))
            g={k:m[k] for k in ('positions_cm','normals','indices','uv0','colors')};self.assertEqual(hashlib.sha256(json.dumps(g,sort_keys=True,separators=(',',':')).encode()).hexdigest(),m['geometry_sha256'])

    def test_parking_keeps_walking_route(self):
        from shapely.ops import unary_union
        p=self.packet;route=LineString(p['lane']['centreline_cm']).buffer(105)
        routes=unary_union([LineString([p[:2] for p in r['points_cm']]) for r in self.source['pedestrians']['routes'] if len(r['points_cm'])>1]).buffer(55)
        bikes=[r for r in p['records'] if r['kind']=='lane_bicycle'];polys=[]
        for r in bikes:
            foot=Polygon(r['footprint_cm']);self.assertFalse(foot.intersects(route));self.assertFalse(foot.intersects(routes));polys.append(foot)
        for i,a in enumerate(polys):
            for b in polys[i+1:]:self.assertLess(a.intersection(b).area,1)
        self.assertEqual(p['lane']['walking_ribbon_width_cm'],210)

    def test_camera_height(self):
        from generate_paris_luxury import Surfaces
        c=self.packet['camera'];p=c['eye_cm'];hs=Surfaces(self.source).query(*p[:2],20)[1];z=max(z for k,z in hs if k in ('path','road','ground'));self.assertAlmostEqual(p[2]-z,170,places=3)

    def test_regeneration(self):
        before=hashlib.sha256(OUTPUT.read_bytes()).hexdigest();generate();self.assertEqual(before,hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
