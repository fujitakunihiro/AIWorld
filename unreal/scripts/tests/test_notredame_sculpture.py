"""Geometric checks for inferred sculptures, not a claim of historical accuracy."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from notredame_sculpture import build_figure


def generate():
    faces=[]
    def face(kind,points,normal,tint=None,vertex_normals=None):
        faces.append(dict(points=points,normals=vertex_normals or [normal]*len(points)))
    counts=build_figure(face,0,0,0,3.4,2)
    return faces,counts


class NearSculptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.faces,cls.counts=generate()

    def test_reproducible_original_geometry(self):
        other,counts=generate()
        def digest(x):return hashlib.sha256(json.dumps(x,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(digest(self.faces),digest(other))
        self.assertEqual(counts,self.counts)
        self.assertEqual(counts['sculpted_faces'],1)

    def test_finite_unit_normals_and_existing_envelope(self):
        p=np.array([v for f in self.faces for v in f['points']])
        n=np.array([v for f in self.faces for v in f['normals']])
        self.assertTrue(np.isfinite(p).all() and np.isfinite(n).all())
        self.assertTrue(np.allclose(np.linalg.norm(n,axis=1),1,atol=1e-8))
        self.assertGreaterEqual(p[:,2].min(),0)
        self.assertLessEqual(p[:,2].max(),3.4)
        self.assertLess(np.ptp(p[:,0]),3.4*.45)
        self.assertLess(np.ptp(p[:,1]),3.4*.35)
        head=p[p[:,2]>3.4*.865]
        self.assertLess(np.ptp(head[:,0]),3.4*.11,'Head proportions must not return to the broad primitive proxy')
        collar=p[(p[:,2]>3.4*.805)&(p[:,2]<3.4*.815)]
        self.assertGreater(np.ptp(collar[:,0]),3.4*.08,'The garment must reach the collar rather than expose an elongated neck')

    def test_closed_surfaces_have_no_latitude_or_sweep_gaps(self):
        edges={}
        def key(p):return tuple(round(v,8) for v in p)
        for f in self.faces:
            ring=f['points']
            for a,b in zip(ring,ring[1:]+ring[:1]):
                edge=tuple(sorted((key(a),key(b))))
                self.assertNotEqual(edge[0],edge[1])
                edges[edge]=edges.get(edge,0)+1
        self.assertTrue(all(v==2 for v in edges.values()),'An individual surface has an open or nonmanifold edge')

    def test_no_degenerate_faces_or_inverted_smooth_normals(self):
        for f in self.faces:
            p=np.array(f['points']);n=np.array(f['normals'])
            for i in range(1,len(p)-1):
                cross=np.cross(p[i]-p[0],p[i+1]-p[0]);size=np.linalg.norm(cross)
                self.assertGreater(size,1e-10)
                average=n[[0,i,i+1]].mean(0);cosine=abs(cross@average/size/np.linalg.norm(average))
                self.assertGreater(cosine,.35,'A normal is inconsistent with its real triangle')

    def test_curves_interpolate_normals_without_flattening_caps(self):
        varying=sum(any(math.dist(f['normals'][0],n)>.005 for n in f['normals'][1:]) for f in self.faces)
        constant=len(self.faces)-varying
        self.assertGreater(varying,len(self.faces)*.8)
        self.assertGreater(constant,20,'Surface end caps need their own geometric normals')


if __name__=='__main__':unittest.main()
