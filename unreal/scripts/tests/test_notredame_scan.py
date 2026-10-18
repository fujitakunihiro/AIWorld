import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_notredame_scan import DATA,FOLDER,ROOT,generate,fill_small,allowed_region,median_depth,smooth_sparse,box_sum
from notredame_scan_atlas import atlas_uv,atlas_uv_hlsl


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
        atlas=self.source['surface']['atlas']
        for lower,upper in zip(atlas['tiles'],atlas['tiles'][1:]):
            bottom=lower['row']+lower['height'];top=upper['row']
            self.assertFalse(mask[h-top:h-bottom].any(),'Atlas gutter must never hide source geometry')
        self.assertEqual(atlas_uv(0,55.,self.source['surface']),(-1.,-1.),'Rejected upper data must not sample the lower coverage map')

    def test_regeneration_is_deterministic_and_does_not_modify_gis(self):
        scene=DATA/'paris-digital-twin.json';before=hashlib.sha256(scene.read_bytes()).hexdigest()
        expected=json.dumps(self.source,sort_keys=True);digest=hashlib.sha256(self.blob).hexdigest()
        generate()
        self.assertEqual(json.dumps(json.loads((DATA/'paris-notredame-scan-source.json').read_text()),sort_keys=True),expected)
        self.assertEqual(hashlib.sha256((ROOT/self.source['binary']).read_bytes()).hexdigest(),digest)
        self.assertEqual(hashlib.sha256(scene.read_bytes()).hexdigest(),before)

    def test_atlas_preserves_portal_resolution_and_matches_world_mapping(self):
        surface=self.source['surface'];atlas=surface['atlas']
        self.assertLessEqual(max(atlas['width'],atlas['height']),4096)
        lower=atlas['tiles'][0]
        self.assertEqual(lower['step_m'],.0125)
        self.assertEqual(lower['stride'],6)
        self.assertEqual([t['id'] for t in atlas['tiles']],['lower'])
        self.assertLess(self.source['surface']['rejected_tiles'][0]['observed_fraction'],.60)
        frame=self.source['local_frame'];d=(self.p-np.array(frame['front_cm']))/100
        x=d@frame['across'];z=d[:,2]
        # The seam has two legitimate UVs at its duplicated vertices. Away
        # from it, the underlay mapping must agree with the actual binary UVs.
        for i in range(0,len(self.p),43):
            if abs(z[i]-45)<.001:continue
            self.assertTrue(np.allclose(self.uv[i],atlas_uv(float(x[i]),float(z[i]),surface),atol=2e-5))
        self.assertTrue(np.allclose(atlas_uv(0,-1e-8,surface),atlas_uv(0,0,surface),atol=1e-7))

    def test_lateral_portals_are_added_and_unsupported_upper_surfaces_are_not_adopted(self):
        frame=self.source['local_frame'];d=(self.p-np.array(frame['front_cm']))/100
        local=np.column_stack((d@frame['across'],d@frame['depth'],d[:,2]))
        centre=local[self.indices].mean(1)
        for side in [-1,1]:
            self.assertGreater(int(((centre[:,0]*side>9)&(centre[:,0]*side<20)&(centre[:,2]<16)).sum()),1000)
            self.assertEqual(int(((centre[:,0]*side>9)&(centre[:,0]*side<20)&(centre[:,2]<5.19)).sum()),0,
                'Unreliable lower-door observations must not replace the complete authored doors and lintels')
        self.assertLessEqual(float(centre[:,2].max()),45.001)
        self.assertEqual(self.source['surface']['rejected_tiles'][0]['id'],'upper')
        self.assertGreater(self.source['surface']['mesh_coverage_fraction'],.35)


class BoundedCompletionTests(unittest.TestCase):
    def test_sparse_regularization_preserves_dense_detail_and_does_not_extend_support(self):
        depth=np.arange(13*17,dtype=np.float32).reshape(13,17)
        colour=np.repeat((depth/300)[:,:,None],3,axis=2);valid=np.ones(depth.shape,bool)
        got,rgb=smooth_sparse(depth.copy(),colour.copy(),valid,valid.copy(),3)
        self.assertTrue(np.array_equal(got,depth))
        self.assertTrue(np.allclose(rgb,colour,atol=1e-6))
        valid[0,0]=False;observed=np.zeros_like(valid);observed[6,8]=True;before=valid.copy()
        smooth_sparse(depth.copy(),colour.copy(),valid,observed,3)
        self.assertTrue(np.array_equal(valid,before),'Regularization must never invent supported cells')
        sums=box_sum(np.ones((13,17),np.float32),3)
        self.assertEqual(float(sums[0,0]),16.)
        self.assertEqual(float(sums[6,8]),49.)

    def test_median_filter_does_not_wrap_and_agrees_across_row_chunks(self):
        depth=np.arange(260*7,dtype=np.float32).reshape(260,7)
        valid=np.ones(depth.shape,bool);valid[128,3]=False
        expected=np.full_like(depth,np.nan)
        for y in range(len(depth)):
            for x in range(depth.shape[1]):
                if valid[y,x]:
                    block=depth[max(0,y-1):y+2,max(0,x-1):x+2]
                    mask=valid[max(0,y-1):y+2,max(0,x-1):x+2]
                    expected[y,x]=np.median(block[mask])
        got=median_depth(depth.copy(),valid)
        self.assertTrue(np.array_equal(got[valid],expected[valid]))

    def test_fill_does_not_wrap_cross_depth_cliffs_or_escape_its_region(self):
        depth=np.zeros((9,11),np.float32);colour=np.zeros((9,11,3),np.float32);valid=np.zeros((9,11),bool)
        valid[4,4]=valid[4,6]=True;depth[4,6]=2.
        permitted=np.zeros_like(valid);permitted[4,4:7]=True
        _,_,filled=fill_small(depth,colour,valid,4,1,max_depth_range=.6,region=permitted)
        self.assertFalse(filled[4,5],'Do not interpolate a two-metre depth discontinuity')
        self.assertEqual(int(filled.sum()),2)
        valid=np.zeros((3,7),bool);valid[1,0]=True
        _,_,filled=fill_small(np.zeros((3,7),np.float32),np.zeros((3,7,3),np.float32),valid,1,1)
        self.assertFalse(filled[1,-1],'Opposite edges must never become neighbours')
        self.assertFalse(filled[1,2],'Completion must obey its maximum grid distance')


if __name__=='__main__':unittest.main()
