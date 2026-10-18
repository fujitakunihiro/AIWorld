import hashlib
import struct
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_notredame_statue import generate,FOLDER,UID,SHA


@unittest.skipUnless((FOLDER/(UID+'.glb')).is_file(),'Optional CC BY-NC original not acquired')
class RealStatueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m,cls.geometry,cls.image=generate()
        magic,n,t=struct.unpack_from('<8sII',cls.geometry)
        cls.p=np.frombuffer(cls.geometry,dtype='<f4',count=n*3,offset=16).reshape(-1,3)
        cls.normal=np.frombuffer(cls.geometry,dtype='<f4',count=n*3,offset=16+n*12).reshape(-1,3)
        cls.uv=np.frombuffer(cls.geometry,dtype='<f4',count=n*2,offset=16+n*24).reshape(-1,2)
        cls.t=np.frombuffer(cls.geometry,dtype='<u4',count=t*3,offset=16+n*32).reshape(-1,3)

    def test_repeatable_real_source_and_license(self):
        m,b,image=generate();self.assertEqual(b,self.geometry);self.assertEqual(m,self.m);self.assertEqual(image,self.image)
        self.assertEqual(m['license'],'CC-BY-NC-4.0');self.assertEqual(m['source_sha256'],SHA)
        self.assertEqual(m['uid'],UID);self.assertEqual(m['original_triangles'],1001053)
        self.assertIn('shadows44',m['author']);self.assertFalse(m['registration']['measured'])
        self.assertEqual(hashlib.sha256(b).hexdigest(),m['geometry_sha256'])

    def test_single_gis_transform_and_correct_left_portal(self):
        f=self.m['local_frame'];p=(self.p.astype(float)-f['front_cm'])/100
        x=p@f['across'];y=p@f['depth'];z=p[:,2]
        # The retained lower canopy is wider than the figure, but stays within
        # the left entrance; it cannot be reused on the central/right portal.
        self.assertTrue(np.all((x>12.65)&(x<15.35)))
        self.assertEqual(self.m['registration']['center_x_m'],14)
        # In UE, a camera looking into the facade sees +across on its left.
        forward=np.array(f['depth']);screen_right=np.array([-forward[1],forward[0],0])
        self.assertAlmostEqual(np.dot(screen_right,f['across']),-1)
        self.assertLess(np.dot(14*np.array(f['across']),screen_right),0)
        # glTF is right handed, UE is left handed. UVs stay on the original
        # vertices, while coordinates and normals receive this reflection.
        basis=np.array(self.m['registration']['gltf_to_facade_basis'])
        self.assertAlmostEqual(np.linalg.det(basis),-1)
        self.assertTrue(np.allclose(basis.T@basis,np.eye(3)))
        self.assertTrue(np.all(abs(y)<1.5))
        self.assertAlmostEqual(z.min(),.15,places=4);self.assertAlmostEqual(z.max(),4.55,places=4)
        self.assertGreater(len(p[z>3.8]),5000,'The actual face/head must not be cropped away')

    def test_source_uv_and_geometric_normals_survive(self):
        self.assertTrue(np.isfinite(self.p).all() and np.isfinite(self.normal).all() and np.isfinite(self.uv).all())
        self.assertTrue(np.allclose(np.linalg.norm(self.normal,axis=1),1,atol=1e-6))
        self.assertTrue(np.all((self.uv>=0)&(self.uv<=1)))
        self.assertEqual(self.m['texture']['resolution'],[1024,1024])
        self.assertEqual(hashlib.sha256(self.image).hexdigest(),self.m['texture']['sha256'])

    def test_mesh_has_valid_non_degenerate_ue_winding(self):
        self.assertLess(self.t.max(),len(self.p));self.assertGreater(len(self.t),500000)
        p=self.p.astype(float);t=self.t;cross=np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]])
        self.assertGreater(np.linalg.norm(cross,axis=1).min(),1e-8)
        dot=np.einsum('ij,ij->i',cross,self.normal[t].sum(axis=1))
        self.assertLessEqual(dot.max(),.001)


if __name__=='__main__':unittest.main()
