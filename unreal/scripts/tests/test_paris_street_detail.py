"""Reproducible, valid centimetre assets; no dependency on GIS acquisition."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_paris_street_detail import generate


class LanternAssetTests(unittest.TestCase):
    def test_deterministic_asset_has_real_scale_and_valid_triangles(self):
        first=generate();self.assertEqual(first,generate())
        self.assertEqual([m['id'] for m in first['objects']],['lamp_metal','lamp_glass'])
        self.assertIn('unverified',first['appearance_provenance'])
        highest=0
        for mesh in first['objects']:
            self.assertGreater(mesh['triangles'],0)
            self.assertLess(mesh['triangles'],12000)
            ps=mesh['positions_cm'];ns=mesh['normals'];ids=mesh['indices']
            self.assertEqual(len(ps),len(ns));self.assertEqual(len(ids),mesh['triangles']*3)
            self.assertTrue(all(math.isfinite(v) for row in ps for v in row))
            self.assertTrue(all(abs(sum(v*v for v in n)-1)<1.e-9 for n in ns))
            self.assertTrue(all(abs(p[0])<=31.01 and abs(p[1])<=31.01 and 0<=p[2]<=448 for p in ps))
            highest=max(highest,max(p[2] for p in ps))
            for i in range(0,len(ids),3):
                a,b,c=[ps[j] for j in ids[i:i+3]]
                u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)]
                cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                self.assertGreater(sum(x*x for x in cross),1.e-12,'Degenerate triangle')
                self.assertLess(sum(cross[j]*ns[ids[i]][j] for j in range(3)),1.e-7,'Winding is not UE clockwise')
        self.assertAlmostEqual(highest,448)


if __name__=='__main__':unittest.main()
