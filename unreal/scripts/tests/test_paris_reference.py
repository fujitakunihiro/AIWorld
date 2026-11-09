"""Verify actual source attachment, geographic pose, and immutable inputs."""
import hashlib,json,math,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'unreal/scripts'))
from paris_district_layout import DTYPE
DATA=ROOT/'unreal/AIWorld/Content/Data'


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'))
        cls.packet=json.loads((ROOT/'unreal/assets/paris-reference/Generated/reference.json').read_text(encoding='utf-8'))
        cls.meshes={o['id']:o for o in cls.source['objects']}
        cls.blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r')

    def test_georeference_and_source_ids(self):
        self.assertEqual(self.packet['source_scene_sha256'],self.source['source_scene_sha256'])
        self.assertEqual(self.packet['georeference'],self.source['georeference'])
        self.assertFalse(self.packet['georeference']['cesium_transform_applied'])
        self.assertGreater(self.packet['counts']['buildings'],100)
        for r in self.packet['records']:
            if r['kind'] not in ('window_architecture','entrance_architecture'):continue
            obj=self.meshes[r['source_mesh_id']]
            self.assertIn(r['source_id'],obj['properties']['source_ids'])
            b=obj['mesh_buffer'];v=np.frombuffer(self.blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(self.blob,dtype='<u4',count=6,offset=b['offset']+28*b['vertex_count']+24*r['source_quad_index'])
            p=v['p'][np.unique(ix)].astype(float).mean(axis=0)
            self.assertLess(float(np.linalg.norm(p-r['anchor_cm'])),.03)

    def test_mesh_integrity(self):
        for m in self.packet['objects']:
            p=np.array(m['positions_cm']);n=np.array(m['normals']);ix=np.array(m['indices'])
            self.assertTrue(np.isfinite(p).all());self.assertTrue(np.isfinite(n).all())
            self.assertTrue(np.allclose(np.linalg.norm(n,axis=1),1,atol=.001))
            self.assertEqual(len(p),len(n));self.assertEqual(len(ix)%3,0)
            self.assertGreaterEqual(ix.min(),0);self.assertLess(ix.max(),len(p))
            geom={k:m[k] for k in ('positions_cm','normals','indices','uv0','colors')}
            self.assertEqual(hashlib.sha256(json.dumps(geom,sort_keys=True,separators=(',',':')).encode()).hexdigest(),m['geometry_sha256'])
        for c in self.packet['cornices']:
            self.assertLessEqual(c['boundary_error_m'],.06)
            self.assertIn(c['source_id'],self.meshes[c['source_mesh_id']]['properties']['source_ids'])

    def test_camera_real_scale_and_surface(self):
        from generate_paris_luxury import Surfaces
        c=self.packet['camera'];p=c['eye_cm'];surfaces=Surfaces(self.source);cover,heights=surfaces.query(*p[:2],25)
        self.assertGreater(cover.get('road',0),.9)
        self.assertEqual(cover.get('water',0),0)
        z=max(z for k,z in heights if k in ('road','ground','sidewalk'))
        self.assertAlmostEqual(p[2]-z,170,places=3)
        d=np.array(c['target_cm'][:2])-p[:2];d=d/np.linalg.norm(d);n=np.array([-d[1],d[0]])
        crossfall=[]
        for offset in [-300,0,300]:
            xy=np.array(p[:2])+n*offset
            crossfall.append(max(z for k,z in surfaces.query(*xy,20)[1] if k=='road'))
        self.assertLess(max(crossfall)-min(crossfall),25,'Inspection street has excessive crossfall across 6m')

    def test_pinned_tree_checksum(self):
        folder=ROOT/'unreal/assets/paris-reference-nature';m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(m['license'],'CC0-1.0');self.assertEqual(m['asset'],'tree_small_02')
        for filename,info in m['files'].items():
            with (folder/filename).open('rb') as f:self.assertEqual(hashlib.file_digest(f,'sha256').hexdigest(),info['sha256'])

    def test_chimneys_follow_actual_roof_surface(self):
        records=[r for r in self.packet['records'] if r['kind']=='roof_chimney']
        self.assertGreater(len(records),100)
        for r in records:
            obj=self.meshes[r['source_mesh_id']];self.assertEqual(obj['kind'],'roof')
            self.assertIn(r['source_id'],obj['properties']['source_ids'])
            b=obj['mesh_buffer'];v=np.frombuffer(self.blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(self.blob,dtype='<u4',count=3,offset=b['offset']+28*b['vertex_count']+12*r['source_triangle_index'])
            self.assertLess(float(np.linalg.norm(v['p'][ix].astype(float).mean(axis=0)-r['anchor_cm'])),.03)
            self.assertGreaterEqual(v['n'][ix[0],2],.94)


if __name__=='__main__':unittest.main()
