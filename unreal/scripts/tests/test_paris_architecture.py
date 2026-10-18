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
        self.assertEqual(first['west_details']['near_sculptures'],21)
        self.assertEqual(first['west_details']['carved_hands'],42)
        self.assertIn('No surveyed shape',first['near_sculpture_provenance'])
        self.assertEqual({m['id'] for m in first['objects']},{'stone','wood','glass','iron','sculpture','stained','virgin_fallback'})
        fallback=next(m for m in first['objects'] if m['id']=='virgin_fallback')
        self.assertGreater(fallback['triangles'],10000)
        import numpy as np
        f=first['local_frame'];relative=(np.array(fallback['positions_cm'])-f['front_cm'])/100
        self.assertTrue(np.all((relative@f['across']>13)&(relative@f['across']<15)),'Fallback must match the northern/left entrance')
        camera=(np.array(first['virgin_camera']['target_cm'])-f['front_cm'])/100
        self.assertAlmostEqual(camera@f['across'],14,places=4)
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

    def test_forged_doors_have_finite_solid_detail_behind_stone(self):
        import numpy as np
        frame=self.data['local_frame'];origin=np.array(frame['front_cm'])
        counts=self.data['west_details']
        self.assertEqual(counts['door_leaves'],6)
        self.assertGreater(counts['door_boards'],70)
        self.assertEqual(counts['iron_rivets'],162)
        self.assertGreater(counts['forged_ribbons'],300)
        self.assertIn('not a traced or measured',self.data['door_provenance'])
        surfaces={}
        for kind in ['wood','iron']:
            m=next(m for m in self.data['objects'] if m['id']==kind)
            p=(np.array(m['positions_cm'])-origin)/100
            local=np.column_stack([p@frame['across'],p@frame['depth'],p[:,2]])
            t=local[np.array(m['indices']).reshape(-1,3)]
            portal=t[np.all((t[:,:,2]>.10)&(t[:,:,2]<4.90)&(abs(t[:,:,0])<20)&(abs(t[:,:,1])<1),axis=1)]
            self.assertGreater(len(portal),1500 if kind=='wood' else 15000)
            area=np.linalg.norm(np.cross(portal[:,1]-portal[:,0],portal[:,2]-portal[:,0]),axis=1)
            self.assertGreater(area.min(),1e-9,'A door detail contains a degenerate triangle')
            self.assertGreater(portal[:,:,1].min(),.40,'Iron must contact recessed doors, not float outside the facade')
            self.assertLess(portal[:,:,1].max(),.82)
            surfaces[kind]=portal
        # Cast through an actual strap and its board. An ornament may stand
        # proud of the wood, but its supporting strap cannot float in space.
        def depths(triangles,x,z):
            a=triangles[:,0][:,[0,2]];u=triangles[:,1][:,[0,2]]-a;v=triangles[:,2][:,[0,2]]-a
            det=u[:,0]*v[:,1]-u[:,1]*v[:,0];valid=abs(det)>1e-10
            a,u,v,det,triangles=a[valid],u[valid],v[valid],det[valid],triangles[valid]
            p=np.array([x,z])-a
            s=(p[:,0]*v[:,1]-p[:,1]*v[:,0])/det
            t=(u[:,0]*p[:,1]-u[:,1]*p[:,0])/det
            hit=(s>=-1e-7)&(t>=-1e-7)&(s+t<=1+1e-7)
            return (triangles[:,0,1]+s*(triangles[:,1,1]-triangles[:,0,1])+t*(triangles[:,2,1]-triangles[:,0,1]))[hit]
        from notredame_west import PORTALS
        for x,w in PORTALS:
            for side in [-1,1]:
                xx=x+side*w*.235+.03
                timber=depths(surfaces['wood'],xx,.85);metal=depths(surfaces['iron'],xx,.85)
                self.assertTrue(len(timber) and len(metal))
                self.assertLessEqual(timber.min()-metal.max(),.001,'Supporting iron is detached from the timber')
        # The separate low eye-level camera actually includes the side doors.
        d=(np.array(self.data['door_camera']['position_cm'])-origin)/100
        target=(np.array(self.data['door_camera']['target_cm'])-origin)/100
        self.assertAlmostEqual(d[2],1.7,places=4)
        self.assertGreater(d@frame['across'],14)
        self.assertLess(d@frame['depth'],-10)
        self.assertAlmostEqual(target@frame['across'],14,places=4)
        self.assertAlmostEqual(target[2],3.2,places=4)


if __name__=='__main__':unittest.main()
