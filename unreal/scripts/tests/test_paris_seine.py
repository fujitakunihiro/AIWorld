"""Contracts for saved source geography and geographic camera poses."""
import hashlib,json,math,unittest
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'unreal/AIWorld/Content/Data'

class SeineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
        cls.packet=json.loads((DATA/'paris-seine.json').read_text(encoding='utf-8'))

    def test_shared_geography_and_source_geometry(self):
        p=self.packet;s=self.scene
        self.assertEqual(p['georeference'],s['georeference'])
        self.assertEqual(p['source_scene_sha256'],s['source_scene_sha256'])
        digest=hashlib.sha256((DATA/'paris-digital-twin-meshes.bin').read_bytes()).hexdigest()
        self.assertEqual(digest,p['seine']['source_geometry_sha256'])
        self.assertEqual(digest,'fba61d4426bf6cc2fc40bda2818d48fe4a6d8e3c58bf13e025254ddc20bc97d8')
        self.assertFalse(p['georeference']['cesium_transform_applied'])

    def test_viewpoints_and_coordinate_roundtrip(self):
        g=self.packet['georeference'];ox,oy=g['projected_origin_m'];t=Transformer.from_crs(4326,2154,always_xy=True)
        f=next(f for f in self.scene['pick_features'] if f['id']==self.packet['seine']['water_source_id'])
        river=unary_union([Polygon(p[0],p[1:]) for p in f['polygons_cm']])
        for name,c in self.packet['cameras'].items():
            x,y,z=c['eye_cm'];px,py=t.transform(*c['eye_wgs84'])
            self.assertLess(math.hypot(px-(ox+x/100),py-(oy-y/100)),1.e-4)
            self.assertGreater(math.dist(c['eye_cm'],c['target_cm']),1000)
            if name!='Aerial':
                self.assertTrue(river.contains(Point(x,y)),name+' viewpoint must be over mapped river')
                self.assertGreater(z,self.packet['seine']['water_level_cm']+300)

    def test_attachment_provenance_and_assets(self):
        for name in ('M_ParisSeineWater','M_ParisSeineStone','M_ParisSeineTwilight'):self.assertTrue((ROOT/'unreal/AIWorld/Content/Materials'/(name+'.uasset')).is_file())
        known={f['id'] for f in self.scene['pick_features']};models={m['id'] for m in self.packet['objects']}
        self.assertGreater(self.packet['counts']['buildings'],500)
        self.assertTrue(self.packet['seine']['appearance_inferred'])
        for r in self.packet['records']:
            self.assertTrue(all(math.isfinite(v) for k in ('anchor_cm','scale_xyz') for v in r[k]))
            self.assertTrue(set(r['models'])<=models)
            self.assertTrue(0<min(r['scale_xyz'])<=max(r['scale_xyz'])<=4)
            if 'source_id' in r:self.assertIn(r['source_id'],known)
        for c in self.packet['cornices']:self.assertLess(c['boundary_error_m'],.061)
        for m in self.packet['objects']:
            for path in (m['asset'],m['material']):self.assertTrue((ROOT/'unreal/AIWorld/Content'/(path[6:]+'.uasset')).is_file(),path)

if __name__=='__main__':unittest.main()
