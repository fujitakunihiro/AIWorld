"""Mesh safety, reference lineage, entrance clearance and repeatable rebuilds."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'unreal/scripts'))
from generate_paris_florist import generate,REFERENCE_SHA


class FloristGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=generate()

    def test_repeatable_geometry_and_reference(self):
        again=generate()
        self.assertEqual([m['geometry_sha256'] for m in self.data['models']],[m['geometry_sha256'] for m in again['models']])
        meta=json.loads((ROOT/'unreal/assets/paris-florist/reference.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['sha256'],REFERENCE_SHA)
        raw=ROOT/'unreal/assets/paris-florist/Raw/reference.png'
        if raw.exists():self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),REFERENCE_SHA)

    def test_finite_unit_normals_and_nonzero_triangles(self):
        for m in self.data['models']:
            p=np.array(m['positions_cm']);n=np.array(m['normals']);ix=np.array(m['indices']).reshape(-1,3)
            self.assertTrue(np.isfinite(p).all(),m['id']);self.assertTrue(np.isfinite(n).all(),m['id'])
            self.assertLess(np.abs(np.linalg.norm(n,axis=1)-1).max(),.001,m['id'])
            tri=p[ix];cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(cross,axis=1)
            self.assertGreater(area.min(),.00001,m['id'])
            self.assertLess((cross*n[ix].mean(axis=1)).sum(axis=1).max(),.0001,m['id'])
        self.assertLess(sum(m['triangles'] for m in self.data['models']),180000)

    def test_human_scale_and_clear_doorway(self):
        for m in self.data['models']:
            p=np.array(m['positions_cm'])
            self.assertLessEqual(abs(p[:,0]).max(),180,m['id']);self.assertLessEqual(p[:,2].max(),306,m['id'])
            # Leave a full metre wide, two metre tall entrance between the banks.
            obstructs=(abs(p[:,0])<50)&(p[:,1]>17)&(p[:,2]<200)
            self.assertFalse(obstructs.any(),m['id'])
            self.assertGreaterEqual(p[:,2].min(),0,m['id'])


if __name__=='__main__':unittest.main()
