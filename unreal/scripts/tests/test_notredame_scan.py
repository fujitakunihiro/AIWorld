import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_notredame_scan import DATA,FOLDER,ROOT,generate


class ScannedFacadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((DATA/'paris-notredame-scan-source.json').read_text(encoding='utf-8'))
        cls.blob=(ROOT/cls.source['binary']).read_bytes()
        magic,n,t=struct.unpack_from('<8sII',cls.blob)
        assert magic==b'NDSCAN01'
        cls.p=np.frombuffer(cls.blob,dtype='<f4',offset=16,count=n*3).reshape(n,3)
        cls.normals=np.frombuffer(cls.blob,dtype='<f4',offset=16+n*12,count=n*3).reshape(n,3)
        cls.uv=np.frombuffer(cls.blob,dtype='<f4',offset=16+n*24,count=n*2).reshape(n,2)
        cls.indices=np.frombuffer(cls.blob,dtype='<u4',offset=16+n*32,count=t*3).reshape(t,3)

    def test_geographic_frame_license_and_provisional_registration(self):
        self.assertEqual(self.source['source_id'],'osm/way/201611261')
        self.assertEqual(self.source['source']['license'],'CC-BY-4.0')
        self.assertEqual(self.source['source']['sha256'],'7dec002065505a878941f663a2e8a5df528cb7a94dbf359405617a0cdfdf7b1e')
        architecture=json.loads((DATA/'paris-photo-architecture.json').read_text(encoding='utf-8'))
        self.assertEqual(self.source['local_frame'],architecture['local_frame'])
        self.assertIn('Not survey',self.source['registration']['method'])
        self.assertIn('photographed lighting',self.source['provenance'])

    def test_non_degenerate_surface_and_outward_normals(self):
        self.assertTrue(np.isfinite(self.p).all())
        self.assertTrue(np.isfinite(self.normals).all())
        self.assertTrue(np.allclose(np.linalg.norm(self.normals,axis=1),1,atol=1e-5))
        self.assertLess(int(self.indices.max()),len(self.p))
        triangles=self.p[self.indices]
        cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        self.assertTrue((np.linalg.norm(cross,axis=1)>1).all())
        dot=(cross*self.normals[self.indices].mean(1)).sum(1)
        self.assertTrue((dot<1e-3).all(),'A scan face has the wrong Unreal winding')
        self.assertTrue(((self.uv>=0)&(self.uv<=1)).all())

    def test_underlay_coverage_agrees_with_actual_mesh(self):
        raw=(FOLDER/'facade-coverage.png').read_bytes();w,h=struct.unpack_from('>II',raw,16);start=8;parts=[]
        while start<len(raw):
            n=struct.unpack_from('>I',raw,start)[0];tag=raw[start+4:start+8]
            if tag==b'IDAT':parts.append(raw[start+8:start+8+n])
            start+=n+12
        rows=np.frombuffer(zlib.decompress(b''.join(parts)),dtype=np.uint8).reshape(h,w+1)
        self.assertTrue((rows[:,0]==0).all())
        mask=rows[:,1:]
        centre=self.uv[self.indices[::31]].mean(1)
        x=np.clip(np.rint(centre[:,0]*(w-1)).astype(int),0,w-1);y=np.clip(np.rint(centre[:,1]*(h-1)).astype(int),0,h-1)
        self.assertGreater(float((mask[y,x]>0).mean()),.95,'Mask would expose source geometry through most observed faces')
        self.assertLess(float((mask>0).mean()),.9,'Missing source areas must not be claimed as measured geometry')

    def test_regeneration_is_deterministic_and_does_not_modify_gis(self):
        scene=DATA/'paris-digital-twin.json';before=hashlib.sha256(scene.read_bytes()).hexdigest()
        expected=json.dumps(self.source,sort_keys=True);digest=hashlib.sha256(self.blob).hexdigest()
        generate()
        self.assertEqual(json.dumps(json.loads((DATA/'paris-notredame-scan-source.json').read_text()),sort_keys=True),expected)
        self.assertEqual(hashlib.sha256((ROOT/self.source['binary']).read_bytes()).hexdigest(),digest)
        self.assertEqual(hashlib.sha256(scene.read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
