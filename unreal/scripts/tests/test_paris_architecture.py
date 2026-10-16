import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_paris_architecture import ROOT,generate


class ArchitectureStudyTests(unittest.TestCase):
    def test_deterministic_read_only_geographic_art_layer(self):
        source=ROOT/'gis/Data/Processed/ile_de_la_cite/district.json'
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        first=generate();second=generate()
        self.assertEqual(first,second)
        self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(first['source_id'],'osm/way/201611261')
        self.assertIn('Not a surveyed',first['appearance_provenance'])
        self.assertEqual(first['origin_wgs84'],[2.3471,48.8547])
        # The art must remain at the existing western GIS anchor, not the origin.
        self.assertAlmostEqual(first['anchor_wgs84'][0],2.3490682619,places=7)
        self.assertAlmostEqual(first['anchor_wgs84'][1],48.8532499221,places=7)
        for mesh in first['objects']:
            self.assertEqual(len(mesh['positions_cm']),len(mesh['normals']))
            self.assertEqual(len(mesh['indices']),mesh['triangles']*3)
            self.assertTrue(all(0<=i<len(mesh['positions_cm']) for i in mesh['indices']))
            self.assertTrue(all(math.isfinite(v) for row in mesh['positions_cm'] for v in row))
            self.assertTrue(all(abs(sum(x*x for x in n)-1)<1e-9 for n in mesh['normals']))
            frame=first['local_frame'];origin=frame['front_cm']
            for p in mesh['positions_cm'][::37]:
                d=[(p[i]-origin[i])/100 for i in range(3)]
                across=sum(d[i]*frame['across'][i] for i in range(3))
                depth=sum(d[i]*frame['depth'][i] for i in range(3))
                self.assertTrue(math.hypot(across,depth)<175 and -3<d[2]<71)
        self.assertGreater(first['inferred_details']['upper_side_bays'],0)
        self.assertGreater(first['inferred_details']['flying_buttresses'],0)
        self.assertGreater(first['inferred_details']['neighbour_windows'],0)
        self.assertIn('osm/relation/2449758',first['source_ids'])

    def test_belfry_front_has_real_geometric_openings(self):
        from shapely.geometry import Point,Polygon
        data=generate();frame=data['local_frame'];origin=frame['front_cm']
        mesh=next(m for m in data['objects'] if m['id']=='stone')
        points=[]
        for p in mesh['positions_cm']:
            d=[(p[i]-origin[i])/100 for i in range(3)]
            points.append((sum(d[i]*frame['across'][i] for i in range(3)),sum(d[i]*frame['depth'][i] for i in range(3)),d[2]))
        wall=[]
        for i in range(0,len(mesh['indices']),3):
            ps=[points[j] for j in mesh['indices'][i:i+3]]
            if all(abs(p[1]+.76)<.0001 for p in ps):wall.append(Polygon([(p[0],p[2]) for p in ps]))
        for x in data['belfry_voids']['front_centres']:
            self.assertFalse(any(p.covers(Point(x,55)) for p in wall),'A stone triangle seals the open belfry')
        self.assertTrue(any(p.covers(Point(15.25,55)) for p in wall),'The central structural pier is missing')


if __name__=='__main__':unittest.main()
