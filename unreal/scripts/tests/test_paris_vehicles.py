"""Spatial and conversion checks for source geometry imported into traffic."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_paris_vehicles import ASSETS,read_obj


class VehicleGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ASSETS/'Generated/source.json').read_text())

    def test_mesh_integrity_and_normals(self):
        count=0
        for part in self.source['parts']:
            for primitive in part['primitives']:
                data=(ASSETS/'Generated'/primitive['file']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),primitive['sha256'])
                magic,n,t=struct.unpack_from('<8sII',data);self.assertEqual(magic,b'NDSCAN01')
                self.assertEqual(len(data),16+n*32+t*12)
                p=np.frombuffer(data,dtype='<f4',offset=16,count=n*3).reshape(-1,3)
                normal=np.frombuffer(data,dtype='<f4',offset=16+n*12,count=n*3).reshape(-1,3)
                uv=np.frombuffer(data,dtype='<f4',offset=16+n*24,count=n*2).reshape(-1,2)
                ix=np.frombuffer(data,dtype='<u4',offset=16+n*32,count=t*3).reshape(-1,3)
                self.assertTrue(np.isfinite(p).all() and np.isfinite(normal).all() and np.isfinite(uv).all())
                self.assertLess(ix.max(),n);self.assertLess(np.abs(np.linalg.norm(normal,axis=1)-1).max(),1.e-4)
                cross=np.cross(p[ix[:,1]]-p[ix[:,0]],p[ix[:,2]]-p[ix[:,0]])
                self.assertGreater(np.linalg.norm(cross,axis=1).min(),1.e-7)
                self.assertLessEqual(np.einsum('ij,ij->i',cross,normal[ix].sum(axis=1)).max(),1.e-4)
                a,b=uv[ix[:,1]]-uv[ix[:,0]],uv[ix[:,2]]-uv[ix[:,0]]
                self.assertGreater(np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0]).min(),1.e-12)
                world=p+part['pivot_cm'];self.assertGreaterEqual(world[:,2].min(),-.01)
                self.assertLess(np.linalg.norm(world[:,:2],axis=1).max(),240.)
                count+=t
        self.assertEqual(count,self.source['source_triangles']);self.assertGreater(count,350000)

    def test_wheel_pivots_and_safety_envelope(self):
        s=self.source;self.assertAlmostEqual(s['dimensions_cm'][0],420.,places=3)
        self.assertLess(s['dimensions_cm'][1],200);self.assertLess(s['swept_radius_cm'],240)
        self.assertGreater(s['wheel_radius_cm'],30);self.assertLess(s['wheel_radius_cm'],35)
        parts={p['id']:p for p in s['parts']};self.assertEqual(len(parts),6)
        for name in ('front_left','front_right','rear_left','rear_right'):
            x,y,z=parts['wheel_'+name]['pivot_cm']
            self.assertGreater(x if name.startswith('front') else -x,100.)
            self.assertGreater(y if name.endswith('right') else -y,60.)
            self.assertAlmostEqual(z,s['wheel_radius_cm'],delta=1.)

    def test_obj_relative_indices_follow_current_attribute_lists(self):
        # A later object must not shift a negative reference from an earlier one.
        import tempfile
        fixture='v 0 0 0\nv 1 0 0\nv 0 1 0\nvn 0 0 1\no first\nusemtl paint\nf -3//-1 -2//-1 -1//-1\nv 99 99 99\no later\n'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'relative.obj';path.write_text(fixture)
            p,n,uv,groups=read_obj(path)
        self.assertEqual([v[0] for v in groups['first','paint']],[0,1,2])
        self.assertEqual(len(p),4)


if __name__=='__main__':unittest.main()
