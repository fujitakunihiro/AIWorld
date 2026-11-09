import sys,json,unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,shape
from shapely.ops import transform
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
import generate_paris_minimap as m


class MinimapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=m.generate()

    def test_same_gis_produces_the_same_offline_map(self):self.assertEqual(self.data,m.generate())

    def test_sources_bounds_and_shared_origin(self):
        d=self.data;scene=json.loads((m.DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'));self.assertEqual(d['georeference'],scene['georeference']);self.assertEqual(d['source_scene_sha256'],scene['source_scene_sha256'])
        self.assertEqual(d['landmarks'],scene['landmarks']);self.assertEqual({g['kind'] for g in d['groups']},{'water','roads','parks','buildings'})
        for group in d['groups']:
            self.assertTrue(group['triangles_cm']);p=np.asarray(group['triangles_cm']);self.assertTrue(np.isfinite(p).all());self.assertGreaterEqual(p.min(),-40000.01);self.assertLessEqual(p.max(),40000.01)
        ids={f['source_id'] for f in d['features']};self.assertIn('osm/way/201611261',ids)

    def test_courtyards_are_not_filled_in(self):
        d=json.loads((m.ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'));ox,oy=d['origin_projected_m'];local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-ox)*100,-(np.asarray(y)-oy)*100),g)
        features={(layer,f['properties']['source_id']):f for layer in ('roads','buildings') for f in d['layers'][layer]};groups={g['kind']:g for g in self.data['groups']};checked=0
        for row in self.data['features']:
            if row['layer'] not in ('roads','buildings'):continue
            g=local(shape(features[(row['layer'],row['source_id'])]['geometry']));parts=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
            holes=[Polygon(ring).buffer(-65) for poly in parts for ring in poly.interiors];holes=[h for h in holes if not h.is_empty]
            if not holes:continue
            tris=groups[row['layer']]['triangles_cm'][row['triangle_start']:row['triangle_start']+row['triangle_count']]
            for t in tris:
                for h in holes:self.assertLess(Polygon(t).intersection(h).area,1.)
            checked+=1
            if checked>=20:break
        self.assertGreater(checked,5)


if __name__=='__main__':unittest.main()
