import copy
import unittest
from shapely.geometry import Polygon, mapping, Point, LineString
from paris_twin.coordinates import Georeference
from paris_twin.photo_scene import cameras, baked_visuals


class PhotoSceneTests(unittest.TestCase):
    def setUp(self):
        self.config=dict(projected_crs='EPSG:2154',origin_wgs84=[2.3471,48.8547],quality_center_wgs84=[2.3471,48.8547],core_size_m=500,context_buffer_m=150)
        self.geo=Georeference(self.config)
        self.terrain=type('Terrain',(),dict(local=lambda self,p:2.3,ngf=lambda self,p:37.3))()

    def test_cameras_preserve_source_and_stand_on_free_ground(self):
        x,y=self.geo.origin
        footprint=Polygon([(x,y),(x+120,y),(x+120,y+45),(x,y+45)])
        building=dict(geometry=mapping(footprint),properties=dict(name='Cathédrale Notre-Dame de Paris',source_id='osm/way/201611261'))
        business=dict(point_cm=[-1000,6000],properties=dict(facade_yaw_degrees=0))
        args=(self.geo,[building],Polygon(),self.terrain,[business])
        result=cameras(*args)
        self.assertEqual(result,cameras(*args))
        self.assertEqual({c['name'] for c in result},{'Camera_NotreDame_Front','Camera_NotreDame_Riverside','Camera_Paris_Street'})
        for c in result:
            self.assertEqual(c['eye_height_cm'],170)
            self.assertEqual(c['position_cm'][2],400)
            self.assertEqual(c['source_id'],building['properties']['source_id'])
            px,py=self.geo.forward.transform(*c['position_wgs84'])
            self.assertFalse(footprint.buffer(.4).covers(Point(px,py)))
            self.assertAlmostEqual(c['position_cm'][0]/100,px-x,places=4)
            self.assertAlmostEqual(c['position_cm'][1]/-100,py-y,places=4)
        self.assertEqual(cameras(self.geo,[],Polygon(),self.terrain,[]),[])
        tree=dict(kind='street_tree',point_cm=result[0]['position_cm'],properties=dict(crown_diameter_m=6))
        clear=cameras(*args,[tree])
        self.assertNotEqual(clear[0]['position_cm'][:2],result[0]['position_cm'][:2])
        lamp=dict(kind='street_lamp',point_cm=result[0]['position_cm'],properties={})
        clear=cameras(*args,[lamp])
        self.assertNotEqual(clear[0]['position_cm'][:2],result[0]['position_cm'][:2])

    def test_river_camera_uses_a_real_mapped_bridge(self):
        x,y=self.geo.origin
        footprint=Polygon([(x,y),(x+120,y),(x+120,y+45),(x,y+45)])
        building=dict(geometry=mapping(footprint),properties=dict(name='Cathédrale Notre-Dame de Paris',source_id='osm/way/201611261'))
        river=Polygon([(x-50,y-100),(x+200,y-100),(x+200,y-20),(x-50,y-20)])
        line=LineString([(x+40,y-95),(x+40,y-5)])
        bridge=dict(geometry=mapping(line),properties=dict(name='Pont au Double',bridge=True,source_id='osm/way/20444388'))
        result=cameras(self.geo,[building],river,self.terrain,[],roads=[bridge])
        camera=next(c for c in result if c['name']=='Camera_NotreDame_Riverside')
        self.assertEqual(camera['position_source_id'],'osm/way/20444388')
        self.assertEqual(camera['focal_length_mm'],28)
        point=Point(self.geo.forward.transform(*camera['position_wgs84']))
        self.assertLess(point.distance(line),.001)
        self.assertTrue(river.covers(point))

    def test_bake_cache_is_content_addressed_and_never_changes_gis(self):
        mesh=dict(id='building/near',kind='building',positions_cm=[[0,0,0],[100,0,0],[0,100,0]],normals=[[0,0,1]]*3,indices=[0,1,2],color='#fff',properties=dict(source_ids=['osm/way/1']))
        far=copy.deepcopy(mesh);far['id']='building/far';far['positions_cm']=[[p[0]+20000,*p[1:]] for p in far['positions_cm']]
        objects=[mesh,far];before=copy.deepcopy(objects)
        result=baked_visuals(objects,self.geo)
        self.assertEqual(objects,before)
        self.assertEqual(list(result),['building/near'])
        self.assertEqual(result,baked_visuals(objects,self.geo))
        self.assertEqual(result['building/near']['source_ids'],['osm/way/1'])
        mesh['positions_cm'][0][2]=1
        self.assertNotEqual(result['building/near']['asset'],baked_visuals(objects,self.geo)['building/near']['asset'])
