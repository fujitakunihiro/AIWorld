import hashlib
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_paris_ground_display import FOLDER,generate,input_meshes


class TerrainDisplayTests(unittest.TestCase):
    def test_exact_surface_coverage_without_source_edits_or_vertical_offsets(self):
        source=FOLDER/'paris-digital-twin-meshes.bin'
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        result=generate();second=generate();self.assertEqual(result,second)
        self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
        _,_,original,ids,coverage,_=input_meshes()
        tris=np.array(result['positions_cm'])[np.array(result['indices']).reshape(-1,3)]
        visible=unary_union([Polygon(t[:,:2]) for t in tris])
        self.assertLess(visible.intersection(coverage).area/10000,.00001,'Display still lies beneath road/park/water coverage')
        full=unary_union([Polygon(t[:,:2]) for t in original['p'][ids]])
        self.assertLess(visible.symmetric_difference(full.difference(coverage)).area/10000,.0001,'Cutout has missing or excess terrain')
        # Interpolate each sampled new vertex on its original terrain triangle.
        old=original['p'][ids].astype('f8');a=old[:,0];u=old[:,1]-a;v=old[:,2]-a;den=u[:,0]*v[:,1]-u[:,1]*v[:,0]
        for p in result['positions_cm'][::151]:
            d=np.array(p[:2])-a[:,:2];s=(d[:,0]*v[:,1]-d[:,1]*v[:,0])/den;r=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/den
            hit=(s>=-1.e-6)&(r>=-1.e-6)&(s+r<=1.000001)
            self.assertTrue(hit.any());z=a[:,2]+s*u[:,2]+r*v[:,2]
            self.assertLess(float(min(abs(z[hit]-p[2]))),.001,'New display was vertically displaced')
        self.assertTrue(all(math.isfinite(v) for p in result['positions_cm'] for v in p))


if __name__=='__main__':unittest.main()
