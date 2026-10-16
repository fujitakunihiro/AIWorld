import hashlib
import importlib.util
import json
import struct
import unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Point,shape

SCRIPTS=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('frontages',SCRIPTS/'generate_paris_frontages.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class FrontageGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene=module.read('paris-digital-twin-runtime.json')
        cls.blob=(module.DATA/'paris-digital-twin-meshes.bin').read_bytes()
        cls.before=hashlib.sha256(cls.blob).hexdigest()
        cls.result=module.generate()

    def test_windows_match_original_glass_quads_and_source_ids(self):
        objects={o['id']:o for o in self.scene['objects']};unique=set()
        self.assertGreater(self.result['window_count'],500)
        for w in self.result['windows']:
            self.assertNotIn(w['source_id'],['osm/way/201611261','osm/relation/2449758'])
            o=objects[w['source_mesh_id']];s=o['mesh_buffer'];k=w['source_quad_index']*6
            ids=struct.unpack_from('<6I',self.blob,s['offset']+s['vertex_count']*28+k*4)
            pts=[struct.unpack_from('<3f',self.blob,s['offset']+i*28) for i in set(ids)]
            self.assertTrue(np.allclose(np.mean(pts,axis=0),w['centre_cm'],atol=.001,rtol=0))
            self.assertIn(w['source_id'],o['properties']['source_ids'])
            self.assertLessEqual(np.linalg.norm(np.subtract(w['centre_cm'][:2],self.result['anchor_cm'][:2])),self.result['radius_cm'])
            key=tuple(w['centre_cm']+w['normal']);self.assertNotIn(key,unique);unique.add(key)

    def test_render_geometry_is_finite_clockwise_and_well_formed(self):
        for o in self.result['objects']:
            p=np.asarray(o['positions_cm']);n=np.asarray(o['normals']);tri=np.asarray(o['indices']).reshape(-1,3)
            self.assertTrue(np.isfinite(p).all());self.assertTrue(np.allclose(np.linalg.norm(n,axis=1),1,atol=1e-6))
            self.assertEqual(len(p),len(o['uv0']));self.assertEqual(len(p),len(o['colors']))
            self.assertLess(tri.max(),len(p));self.assertGreaterEqual(tri.min(),0)
            cross=np.cross(p[tri[:,1]]-p[tri[:,0]],p[tri[:,2]]-p[tri[:,0]])
            self.assertTrue((np.einsum('ij,ij->i',cross,n[tri[:,0]])<-.01).all())
            if o['id']=='glass':
                self.assertEqual(set(map(tuple,o['uv0'])),{(0,0),(0,1),(1,0),(1,1)})
                self.assertEqual(o['triangles'],self.result['window_count']*2)

    def test_glazing_remains_parallel_to_original_at_five_centimetres(self):
        glass=next(o for o in self.result['objects'] if o['id']=='glass')
        points=np.asarray(glass['positions_cm']).reshape(-1,4,3)
        for w,quad in zip(self.result['windows'],points):
            self.assertTrue(np.allclose(quad.mean(axis=0),np.asarray(w['centre_cm'])+np.asarray(w['normal'])*5,atol=.001,rtol=0))
            self.assertTrue(np.allclose((quad-np.asarray(w['centre_cm']))@np.asarray(w['normal']),5,atol=.001,rtol=0))

    def test_bevels_preserve_box_bounds_and_form_a_closed_solid(self):
        m=module.Mesh(bevel_cm=.35);m.box([0,0,0],[1,0,0],[0,1,0],[11,24,53],[14,28,165],[200,190,170,255])
        p=np.asarray(m.positions_cm);tri=np.asarray(m.indices).reshape(-1,3)
        self.assertTrue(np.allclose(p.min(axis=0),[4,10,-29.5]))
        self.assertTrue(np.allclose(p.max(axis=0),[18,38,135.5]))
        edges={}
        for t in tri:
            for a,b in zip(t,np.roll(t,-1)):
                key=tuple(sorted([tuple(p[a]),tuple(p[b])]))
                edges[key]=edges.get(key,0)+1
        self.assertTrue(all(n==2 for n in edges.values()),'No cracks or internal faces at the chamfers')
        volume=abs(np.einsum('ij,ij->i',p[tri[:,0]],np.cross(p[tri[:,1]],p[tri[:,2]])).sum()/6)
        self.assertLess(volume,14*28*165)
        self.assertGreater(volume,14*28*165*.99)

    def test_regeneration_is_deterministic_and_source_is_read_only(self):
        again=module.generate()
        self.assertEqual([o['geometry_sha256'] for o in self.result['objects']],[o['geometry_sha256'] for o in again['objects']])
        self.assertEqual(self.before,hashlib.sha256((module.DATA/'paris-digital-twin-meshes.bin').read_bytes()).hexdigest())
        self.assertIn('inferred',self.result['appearance_provenance'].lower())

    def test_entrances_and_cornices_follow_source_quads_without_duplicate_sites(self):
        objects={o['id']:o for o in self.scene['objects']};unique=set()
        district=json.loads((module.ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
        ox,oy=district['origin_projected_m'];polygons={f['properties']['source_id']:shape(f['geometry']) for f in district['layers']['buildings']}
        self.assertEqual(self.result['entrance_count'],11);self.assertEqual(self.result['cornice_count'],107)
        for key in ['entrances','cornices']:
            for detail in self.result[key]:
                o=objects[detail['source_mesh_id']];s=o['mesh_buffer'];k=detail['source_quad_index']*6
                ids=struct.unpack_from('<6I',self.blob,s['offset']+s['vertex_count']*28+k*4)
                pts=[struct.unpack_from('<3f',self.blob,s['offset']+i*28) for i in set(ids)]
                self.assertTrue(np.allclose(np.mean(pts,axis=0),detail['centre_cm'],atol=.001,rtol=0))
                self.assertIn(detail['source_id'],o['properties']['source_ids'])
                c=detail['centre_cm'];n=detail['normal'];offset=detail['wall_offset_cm']
                wall=Point(ox+(c[0]-n[0]*offset)/100,oy-(c[1]-n[1]*offset)/100)
                self.assertLess(polygons[detail['source_id']].boundary.distance(wall),.03)
                self.assertLessEqual(np.linalg.norm(np.subtract(c[:2],self.result['anchor_cm'][:2])),10000)
                identity=(key,)+tuple(round(v,2) for v in c+n)
                self.assertNotIn(identity,unique);unique.add(identity)
        # The source inference placed ground-floor windows across entrances.
        # They remain in GIS, but their added relief must not cross the doors.
        occluded=self.result['occluded_source_windows']
        self.assertGreater(len(occluded),0)
        self.assertEqual(self.result['window_count']+len(occluded),584)
        kept={(w['source_mesh_id'],w['source_quad_index']) for w in self.result['windows']}
        for w in occluded:
            self.assertNotIn((w['source_mesh_id'],w['source_quad_index']),kept)
            door=next(e for e in self.result['entrances'] if e['source_mesh_id']==w['entrance_source_mesh_id'] and e['source_quad_index']==w['entrance_source_quad_index'])
            self.assertEqual(w['source_id'],door['source_id'])
            self.assertLess(abs(w['centre_cm'][2]-door['centre_cm'][2]),door['height_cm']/2)

    def test_entry_camera_is_at_human_scale_outside_building_footprints(self):
        camera=np.asarray(self.result['inspection_entry_camera_cm']);target=np.asarray(self.result['inspection_entry_target_cm'])
        door=next(e for e in self.result['entrances'] if e['source_id']==self.result['inspection_entry_source_id'])
        self.assertAlmostEqual(camera[2]-(door['centre_cm'][2]-door['height_cm']/2),170)
        self.assertGreater(np.dot(camera-target,door['normal']),240)
        self.assertLessEqual(np.linalg.norm((camera-target)[:2]),601)
        district=json.loads((module.ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'));ox,oy=district['origin_projected_m']
        point=Point(ox+camera[0]/100,oy-camera[1]/100)
        self.assertFalse(any(shape(f['geometry']).buffer(.6).covers(point) for f in district['layers']['buildings']))


if __name__=='__main__':unittest.main()
