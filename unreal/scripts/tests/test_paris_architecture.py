import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generate_paris_architecture import ROOT,generate


class ArchitectureStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=generate()

    def test_deterministic_read_only_geographic_art_layer(self):
        source=ROOT/'gis/Data/Processed/ile_de_la_cite/district.json'
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        first=self.data;second=generate()
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
        self.assertEqual(first['west_details']['gallery_figures'],28)
        self.assertGreater(first['west_details']['archivolt_figures'],100)
        self.assertGreater(first['west_details']['rose_glass_cells'],1000)
        self.assertEqual({m['id'] for m in first['objects']},{'stone','wood','glass','iron','sculpture','stained'})
        self.assertGreater(first['inferred_details']['upper_side_bays'],0)
        self.assertGreater(first['inferred_details']['flying_buttresses'],0)
        self.assertGreater(first['inferred_details']['neighbour_windows'],0)
        self.assertIn('osm/relation/2449758',first['source_ids'])

    def test_belfry_front_has_real_geometric_openings(self):
        from shapely.geometry import Point,Polygon
        data=self.data;frame=data['local_frame'];origin=frame['front_cm']
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

    def test_western_holes_and_recessed_doors_are_real_geometry(self):
        import numpy as np
        from shapely.geometry import Point,Polygon
        data=self.data;frame=data['local_frame'];origin=np.array(frame['front_cm'])
        mesh=next(m for m in data['objects'] if m['id']=='stone')
        p=(np.array(mesh['positions_cm'])-origin)/100
        local=np.column_stack([p@frame['across'],p@frame['depth'],p[:,2]])
        triangles=local[np.array(mesh['indices']).reshape(-1,3)]
        front=triangles[np.all(abs(triangles[:,:,1]+.80)<1e-5,axis=1)]
        polygons=[Polygon(t[:,[0,2]]) for t in front]
        for x,z in [(0,2),(-14,8),(14,8),(0,28.1),(17.9,27),(0,40)]:
            self.assertFalse(any(t.covers(Point(x,z)) for t in polygons),f'Stone closes a western aperture at {x},{z}')
        self.assertTrue(any(t.covers(Point(8.5,30)) for t in polygons),'Structural wall between apertures must remain')
        wood=next(m for m in data['objects'] if m['id']=='wood')
        p=(np.array(wood['positions_cm'])-origin)/100
        local=np.column_stack([p@frame['across'],p@frame['depth'],p[:,2]])
        door=local[(abs(local[:,0])<4.5)&(abs(local[:,1])<3)&(local[:,2]<4.9)]
        self.assertGreater(len(door),100)
        self.assertGreater(door[:,1].min(),.3,'Door must remain behind the stone face, not a flat card on the front')

    def test_stained_glass_envelope_and_capture_camera(self):
        import numpy as np
        from shapely.geometry import Point,shape
        frame=self.data['local_frame'];mesh=next(m for m in self.data['objects'] if m['id']=='stained')
        p=(np.array(mesh['positions_cm'])-frame['front_cm'])/100
        across=p@frame['across'];depth=p@frame['depth']
        self.assertLess(np.hypot(across,p[:,2]-28.1).max(),4.851)
        self.assertTrue(np.allclose(depth,.38,atol=1e-5))
        self.assertEqual(len(mesh['colors_srgb']),len(p))
        self.assertGreater(len(set(mesh['colors_srgb'])),5)
        camera=self.data['detail_camera'];d=(np.array(camera['position_cm'])-frame['front_cm'])/100
        self.assertAlmostEqual(d[2],1.7,places=4)
        self.assertLess(d@frame['depth'],-20)
        source=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
        # A portal closeup must stay outside the cathedral's actual footprint.
        from paris_twin.coordinates import Georeference
        config=json.loads((ROOT/'gis/config/ile_de_la_cite.json').read_text(encoding='utf-8'))
        geo=Georeference(config)
        xy=(geo.origin[0]+camera['position_cm'][0]/100,geo.origin[1]-camera['position_cm'][1]/100)
        building=next(f for f in source['layers']['buildings'] if f['properties']['source_id']==self.data['source_id'])
        self.assertFalse(shape(building['geometry']).covers(Point(xy)))


if __name__=='__main__':unittest.main()
