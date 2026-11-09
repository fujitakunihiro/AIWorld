import hashlib,json,sys,unittest
from pathlib import Path
import numpy as np
SCRIPTS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SCRIPTS))
import generate_paris_weathering as weather

class WeatheringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=weather.generate()

    def test_stains_are_reproducible_and_attached_to_source_windows(self):
        scene=weather.DATA/'paris-digital-twin-meshes.bin'
        before=hashlib.sha256(scene.read_bytes()).hexdigest()
        result=self.data;again=weather.generate();self.assertEqual(result,again)
        self.assertEqual(before,hashlib.sha256(scene.read_bytes()).hexdigest())
        source=json.loads((weather.DATA/'paris-photo-frontages-source.json').read_text(encoding='utf-8'))
        self.assertEqual(result['source_scene_sha256'],source['source_scene_sha256'])
        lookup={(w['source_mesh_id'],w['source_quad_index']):w for w in source['windows']}
        streaks=[r for r in result['records'] if r['kind']=='window_streak'];bases=[r for r in result['records'] if r['kind']=='wall_base']
        self.assertGreater(len(streaks),300);self.assertGreater(len(bases),50)
        objects={o['id']:o for o in result['objects']}
        self.assertEqual(len(objects['streak']['positions_cm']),4*len(streaks))
        self.assertEqual(len(objects['base']['positions_cm']),4*len(bases))
        for i,record in enumerate(streaks):
            w=lookup[(record['source_mesh_id'],record['source_quad_index'])];self.assertEqual(record['source_id'],w['source_id'])
            quad=np.asarray(objects['streak']['positions_cm'][4*i:4*i+4]);centre=np.asarray(w['centre_cm']);normal=np.asarray(w['normal'])
            self.assertTrue(np.allclose((quad-centre)@normal,-8.35,atol=.002))
            self.assertLess(float(quad[:,2].max()),centre[2]-w['height_cm']/2)
            self.assertGreaterEqual(record['length_cm'],40);self.assertLessEqual(record['length_cm'],75)
        for i,record in enumerate(bases):
            quad=np.asarray(objects['base']['positions_cm'][4*i:4*i+4]);self.assertAlmostEqual(float(quad[:,2].min()),record['ground_cm']+3,delta=.002)
            self.assertLessEqual(float(np.ptp(quad[:,2])),50)
        for obj in result['objects']:
            self.assertEqual(obj['triangles']*3,len(obj['indices']))
            self.assertTrue(np.isfinite(np.asarray(obj['positions_cm'])).all())

    def test_district_streaks_remain_below_the_original_window_sills(self):
        from paris_district_layout import district_windows
        windows,_=district_windows(self.data['source_scene_sha256']);lookup={(w['source_mesh_id'],w['source_quad_index']):w for w in windows}
        objects={o['id']:o for o in self.data['objects']};rows=[r for r in self.data['records'] if r['kind']=='district_window_streak'];self.assertGreater(len(rows),8000)
        self.assertGreater(len({r['source_id'] for r in rows}),400)
        for r in rows:
            w=lookup[(r['source_mesh_id'],r['source_quad_index'])];quad=np.asarray(objects[r['mesh_id']]['positions_cm'][r['vertex_start']:r['vertex_start']+4]);p=np.asarray(w['centre_cm']);n=np.asarray(w['normal'])
            self.assertEqual(r['source_id'],w['source_id']);self.assertTrue(np.allclose((quad-p)@n,-8.35,atol=.002));self.assertLess(quad[:,2].max(),p[2]-w['height_cm']/2-20)

    def test_road_grime_keeps_water_buildings_and_surface_height_clear(self):
        from shapely.geometry import shape,Polygon
        from shapely.ops import unary_union,transform
        from generate_paris_luxury import Surfaces
        district=json.loads((weather.ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'));ox,oy=district['origin_projected_m']
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-ox)*100,-(np.asarray(y)-oy)*100),g)
        buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
        water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
        roads={f['properties']['source_id']:f for f in district['layers']['roads']};objects={o['id']:o for o in self.data['objects']};scene=json.loads((weather.DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'));surfaces=Surfaces(scene)
        rows=[r for r in self.data['records'] if r['kind']=='road_edge_grime'];self.assertGreater(len(rows),200)
        for r in rows:
            f=roads[r['source_id']];self.assertFalse(f['properties']['bridge']);self.assertFalse(f['properties']['tunnel'])
            quad=np.asarray(objects[r['mesh_id']]['positions_cm'][r['vertex_start']:r['vertex_start']+4]);p=Polygon(quad[:,:2]);self.assertTrue(local(shape(f['geometry'])).covers(p))
            self.assertFalse(p.intersects(buildings));self.assertFalse(p.intersects(water))
            for x,y,z in quad:
                _,hs=surfaces.query(x,y,.5);h=max(h for k,h in hs if k in ('road','path','sidewalk'));self.assertAlmostEqual(z-h,.35,delta=.002)

if __name__=='__main__':unittest.main()
