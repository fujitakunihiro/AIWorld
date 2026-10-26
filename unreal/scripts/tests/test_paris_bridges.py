"""Validate generated bridge geometry, including the formerly missing deck."""
import json
import unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[3]


class BridgeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-bridges-source.json').read_text(encoding='utf-8'))

    def test_indices_normals_and_uvs_are_valid(self):
        for item in self.data['objects']:
            p=np.array(item['positions_cm']);n=np.array(item['normals']);uv=np.array(item['uv0']);ix=np.array(item['indices']).reshape(-1,3)
            self.assertTrue(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all(),item['id'])
            self.assertEqual(len(p),len(n));self.assertEqual(len(p),len(uv));self.assertTrue(ix.min()>=0 and ix.max()<len(p))
            t=p[ix];cross=np.cross(t[:,2]-t[:,0],t[:,1]-t[:,0]);area=np.linalg.norm(cross,axis=1)
            self.assertTrue(np.all(area>1.e-5),item['id'])
            self.assertTrue(np.all(np.sum(cross*n[ix[:,0]],axis=1)>0),item['id'])

    def test_deck_covers_gaps_across_the_complete_bridge_width(self):
        for bridge in self.data['profiles']:
            collision=next(o for o in self.data['objects'] if o['bridge_id']==bridge['id'] and o['collision_only'])
            p=np.array(collision['positions_cm']);ix=np.array(collision['indices']).reshape(-1,3);n=np.array(collision['normals']);ix=ix[n[ix[:,0],2]>.5]
            coverage=unary_union([Polygon(t[:,:2]) for t in p[ix]])
            d=np.array(bridge['direction']);side=np.array([-d[1],d[0]]);c=np.array(bridge['centre_cm'][:2])
            for x in np.linspace(-.48,.48,15):
                for y in np.linspace(-.48,.48,13):
                    point=c+d*x*bridge['length_cm']+side*y*bridge['width_cm']
                    self.assertTrue(coverage.buffer(.01).covers(Point(point)),(bridge['id'],x,y))

    def test_documented_structural_types_and_arch_openings(self):
        profiles={b['id']:b for b in self.data['profiles']}
        self.assertEqual(len(profiles['michel']['arches']),3)
        self.assertEqual([a['type'] for a in profiles['double']['arches']],['copper'])
        self.assertEqual([a['type'] for a in profiles['notredame']['arches']],['stone','iron','stone'])
        self.assertEqual(profiles['archeveche']['width_cm'],1100)
        for bridge in self.data['profiles']:
            d=np.array(bridge['direction']);side=np.array([-d[1],d[0]]);centre=np.array(bridge['centre_cm'][:2])
            meshes=[o for o in self.data['objects'] if o['bridge_id']==bridge['id'] and not o['collision_only']]
            projected=[]
            for item in meshes:
                p=np.array(item['positions_cm']);ix=np.array(item['indices']).reshape(-1,3)
                localx=(p[:,:2]-centre)@d;localy=(p[:,:2]-centre)@side
                local=np.stack([localx,p[:,2]],axis=1);tris=local[ix]
                # Only geometry inside the bridge's width can obstruct a ray
                # across the actual opening; bank decorations are excluded.
                valid=np.max(np.abs(localy[ix]),axis=1)<bridge['width_cm']/2+100
                projected.extend(Polygon(t) for t in tris[valid] if Polygon(t).area>.01)
            for arch in bridge['arches']:
                mid=(arch['start_cm']+arch['end_cm'])/2
                probe=Point(mid,bridge['water_level_cm']+100)
                self.assertFalse(any(poly.contains(probe) for poly in projected),(bridge['id'],'arch unexpectedly filled'))

    def test_arch_soffit_normals_face_the_opening(self):
        for bridge in self.data['profiles']:
            item=next(o for o in self.data['objects'] if o['bridge_id']==bridge['id'] and o['id'].endswith('_stone'))
            p=np.array(item['positions_cm']);n=np.array(item['normals']);ix=np.array(item['indices']).reshape(-1,3)
            d=np.array(bridge['direction']);side=np.array([-d[1],d[0]]);centre=np.array(bridge['centre_cm'][:2]);x=(p[:,:2]-centre)@d;y=(p[:,:2]-centre)@side
            for arch in bridge['arches']:
                if arch['type']!='stone':continue
                localx=x[ix].mean(axis=1);ys=y[ix]
                full_width=(ys.min(axis=1)<-bridge['width_cm']*.45)&(ys.max(axis=1)>bridge['width_cm']*.45)
                inside=(localx>arch['start_cm']+.01)&(localx<arch['end_cm']-.01)
                self.assertTrue(np.all(n[ix[full_width&inside,0],2]<0),bridge['id'])


if __name__=='__main__':unittest.main()
