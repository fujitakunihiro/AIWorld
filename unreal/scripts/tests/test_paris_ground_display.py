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
    def test_surface_coverage_and_bounded_path_edge_adjustments(self):
        source=FOLDER/'paris-digital-twin-meshes.bin'
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        result=generate();second=generate();self.assertEqual(result,second)
        self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
        scene,_,original,ids,coverage,_,other=input_meshes(include_other_coverage=True)
        input_centre=scene['quality_centre_ue_cm'][:2]
        tris=np.array(result['positions_cm'])[np.array(result['indices']).reshape(-1,3)]
        visible=unary_union([Polygon(t[:,:2]) for t in tris])
        self.assertLess(visible.intersection(other).area/10000,.0001,'Display overlaps non-path road/park/water coverage')
        full=unary_union([Polygon(t[:,:2]) for t in original['p'][ids]])
        base=full.difference(coverage);added=visible.difference(base)
        self.assertLess(base.difference(visible).area/10000,.0001,'Cutout omitted terrain')
        self.assertLess(added.difference(coverage.difference(other)).area/10000,.0001,'Restoration left path-only coverage')
        self.assertGreater(result['restored_beneath_raised_paths_m2'],0,'No raised-path gaps were filled')
        self.assertAlmostEqual(added.area/10000,result['restored_beneath_raised_paths_m2'],delta=.02)
        # Interpolate each sampled new vertex on its original terrain triangle.
        old=original['p'][ids].astype('f8');a=old[:,0];u=old[:,1]-a;v=old[:,2]-a;den=u[:,0]*v[:,1]-u[:,1]*v[:,0]
        for p in result['positions_cm'][::151]:
            d=np.array(p[:2])-a[:,:2];s=(d[:,0]*v[:,1]-d[:,1]*v[:,0])/den;r=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/den
            hit=(s>=-1.e-6)&(r>=-1.e-6)&(s+r<=1.000001)
            self.assertTrue(hit.any());z=a[:,2]+s*u[:,2]+r*v[:,2]
            shift=float(min(abs(z[hit]-p[2])))
            self.assertLess(shift,20.01,'Display shifted more than the maximum path-edge correction')
            if np.linalg.norm(np.array(p[:2])-np.array(input_centre))>20000.1:
                self.assertLess(shift,.001,'Terrain outside the local correction was displaced')
        self.assertTrue(all(math.isfinite(v) for p in result['positions_cm'] for v in p))


if __name__=='__main__':unittest.main()
