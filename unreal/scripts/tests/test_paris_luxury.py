import importlib.util,json,math,sys,unittest
from pathlib import Path
from shapely.geometry import Point,LineString,shape
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('paris_luxury',ROOT/'unreal/scripts/generate_paris_luxury.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)


class LuxuryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=m.generate();cls.scene=m.read(m.DATA/'paris-digital-twin-runtime.json')

    def test_same_archived_inputs_reproduce_same_decoration(self):
        self.assertEqual(self.data,m.generate())
        self.assertEqual(self.data['source_scene_sha256'],self.scene['source_scene_sha256'])

    def test_storefront_and_seating_traceability(self):
        features={f['id']:f for f in self.scene['pick_features'] if f['kind']=='business'}
        fixtures={f['id']:f for f in self.scene['pick_features'] if f['kind'] in ('street_lamp','street_bench')}
        roads={f['properties']['source_id']:f for f in m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')['layers']['roads']}
        for r in self.data['records']:
            if r['kind'] in ('street_accent','street_hanging_accent'):
                self.assertIn(r['source_id'],{f['id'] for f in self.scene['pick_features']});continue
            if r['kind'] in ('street_display','terrace_parasol'):
                self.assertIn(r['source_id'],features);self.assertEqual(r['building_source_id'],features[r['source_id']]['properties']['building_source_id']);continue
            if r['kind'].startswith('party_'):
                self.assertEqual(r['feature_layer'],'festival');self.assertEqual(r['placement_provenance'],'fictional_festival_illumination_on_existing_inferred_decoration');continue
            self.assertTrue(r['placement_provenance'].startswith('inferred'))
            if r['kind']=='street_garland':
                self.assertEqual(r['source_wgs84'],roads[r['source_id']]['properties']['wgs84_centre']);self.assertIsNone(r['building_source_id']);continue
            if r['kind'] in ('window','facade_banner','night_window','facade_relief'):
                self.assertEqual(r['source_id'],r['building_source_id']);continue
            if r['kind']=='pole' or r.get('anchor_source_kind')=='street_bench':
                f=fixtures[r['source_id']];self.assertEqual(r['source_wgs84'],f['properties']['wgs84_centre'])
                self.assertIsNone(r['building_source_id'])
                if r['kind']=='pole':
                    self.assertEqual(r['anchor_cm'],f['point_cm']);self.assertGreaterEqual(r['minimum_clearance_cm'],205);self.assertGreaterEqual(r['path_coverage'],.98)
                continue
            f=features[r['source_id']];p=f['properties']
            self.assertEqual(r['building_source_id'],p['building_source_id'])
            self.assertTrue(r['placement_provenance'].startswith('inferred'))
            if r['kind']=='table':
                self.assertEqual(p['outdoor_seating_tag'],'yes');self.assertEqual(r['anchor_cm'],p['terrace_cm'])
            if r['kind']=='canopy':self.assertEqual(r['anchor_cm'],f['point_cm'])
        self.assertEqual(sum(r['kind']=='table' for r in self.data['records']),49)
        self.assertEqual({r['source_id'] for r in self.data['records'] if r['kind']=='canopy'},set(features))

    def test_urns_keep_entrances_and_existing_routes_clear(self):
        routes=unary_union([LineString(r['points_cm']).buffer(50) for r in self.scene['pedestrians']['routes'] if len(r['points_cm'])>1])
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'))
        district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json');buildings=unary_union([shape(f['geometry']) for f in district['layers']['buildings']])
        urns=[r for r in self.data['records'] if r['kind']=='urn'];self.assertGreaterEqual(len(urns),200)
        for r in urns:
            self.assertGreaterEqual(r['path_coverage'],.98);self.assertGreaterEqual(r['clearance_coverage'],.85)
            x,y,z=r['anchor_cm'];self.assertFalse(Point(x,y).buffer(40).intersects(routes))
            lon,lat,_=geo.from_ue(x,y,z);self.assertLess(math.dist((lon,lat),r['wgs84_placement']),1e-8)
            projected=Point(geo.forward.transform(lon,lat));self.assertGreaterEqual(buildings.distance(projected),.4)

    def test_model_buffers_have_valid_indices_and_unit_normals(self):
        models={o['id'] for o in self.data['objects']};self.assertEqual(len(models),89)
        for r in self.data['records']:self.assertTrue(set(r['models'])<=models)
        for o in self.data['objects']:
            self.assertEqual(len(o['positions_cm']),len(o['normals']))
            self.assertLess(max(o['indices']),len(o['positions_cm']))
            self.assertTrue(all(math.isfinite(v) for p in o['positions_cm'] for v in p))
            self.assertTrue(all(abs(sum(v*v for v in n)-1)<.002 for n in o['normals']))

    def test_shop_displays_preserve_routes_entrances_and_real_terraces(self):
        import numpy as np
        from shapely.ops import transform
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'));district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
        buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
        water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
        routes=unary_union([LineString(r['points_cm']).buffer(62) for r in self.scene['pedestrians']['routes'] if len(r['points_cm'])>1])
        shops={f['id']:f for f in self.scene['pick_features'] if f['kind']=='business'}
        rows=[r for r in self.data['records'] if r['kind']=='street_display'];self.assertGreater(len(rows),40)
        self.assertTrue({'menu','books','flowers'}<={r['display_type'] for r in rows})
        for r in rows:
            foot=Point(r['anchor_cm'][:2]).buffer(r['footprint_radius_cm']);self.assertFalse(foot.intersects(buildings));self.assertFalse(foot.intersects(water));self.assertFalse(foot.intersects(routes));self.assertGreaterEqual(r['path_coverage'],.98)
            self.assertLess(math.dist(geo.from_ue(*r['anchor_cm'])[:2],r['wgs84_placement']),1e-8)
            for f in shops.values():
                p=f['point_cm'];a=math.radians(f['properties']['facade_yaw_degrees']);door=LineString([p[:2],[p[0]-math.sin(a)*300,p[1]+math.cos(a)*300]]).buffer(78);self.assertFalse(door.intersects(foot))
        self.assertGreater(sum(r['kind']=='terrace_parasol' for r in self.data['records']),5)
        for r in self.data['records']:
            if r['kind']!='terrace_parasol':continue
            props=shops[r['source_id']]['properties'];self.assertTrue(props['terrace_placed']);self.assertEqual(r['anchor_cm'],props['terrace_cm']);self.assertGreaterEqual(r['minimum_clearance_cm'],210)
            self.assertFalse(Point(r['anchor_cm'][:2]).buffer(112).intersects(buildings))
            a=math.radians(r['yaw_degrees']);p=r['anchor_cm'];foot=Point(p[0]+math.cos(a)*125+math.sin(a)*25,p[1]+math.sin(a)*125-math.cos(a)*25).buffer(24)
            self.assertFalse(foot.intersects(buildings));self.assertFalse(foot.intersects(routes));self.assertFalse(foot.intersects(water))

    def test_extra_objects_keep_the_existing_street_and_walkways_clear(self):
        import numpy as np
        from shapely.ops import transform
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'));district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
        buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
        water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
        routes=unary_union([LineString(r['points_cm']).buffer(62) for r in self.scene['pedestrians']['routes'] if len(r['points_cm'])>1])
        rows=[r for r in self.data['records'] if r['kind']=='street_accent'];self.assertGreater(len(rows),100)
        self.assertTrue({'bread','wine','cart','bicycle','orrery','topiary'}<={r['accent_type'] for r in rows})
        for r in rows:
            foot=Point(r['anchor_cm'][:2]).buffer(r['footprint_radius_cm']);self.assertFalse(foot.intersects(buildings));self.assertFalse(foot.intersects(water));self.assertFalse(foot.intersects(routes));self.assertGreaterEqual(r['path_coverage'],.98)
            self.assertLess(math.dist(geo.from_ue(*r['anchor_cm'])[:2],r['wgs84_placement']),1e-8)
            for b in r['collision_boxes']:self.assertLessEqual(math.hypot(*b['size_cm'][:2])/2,r['footprint_radius_cm'])
        for i,r in enumerate(rows):
            for other in rows[i+1:]:self.assertGreaterEqual(math.dist(r['anchor_cm'][:2],other['anchor_cm'][:2]),r['footprint_radius_cm']+other['footprint_radius_cm']+27.99)

    def test_hanging_bouquets_follow_mapped_lamps_with_safe_headroom(self):
        poles={r['source_id']:r for r in self.data['records'] if r['kind']=='pole'}
        rows=[r for r in self.data['records'] if r['kind']=='street_hanging_accent'];self.assertGreater(len(rows),20)
        for r in rows:
            self.assertEqual(r['anchor_cm'],poles[r['source_id']]['anchor_cm']);self.assertEqual(r['yaw_degrees'],poles[r['source_id']]['yaw_degrees']);self.assertEqual(r['collision_boxes'],[]);self.assertGreaterEqual(r['minimum_clearance_cm'],210)
        for o in self.data['objects']:
            if o['id'].startswith('market_extra_hanging_'):self.assertGreaterEqual(min(p[2] for p in o['positions_cm']),260)

    def test_extra_object_camera_is_on_open_walkable_ground(self):
        import numpy as np
        from shapely.ops import transform
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'));district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json');camera=self.data['extra_objects_camera'];eye=camera['eye_cm'];target=camera['target_cm']
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
        buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
        self.assertGreater(Point(eye[:2]).distance(buildings),70);self.assertFalse(LineString([eye[:2],target[:2]]).intersects(buildings))
        surfaces=m.Surfaces(self.scene);cover,hs=surfaces.query(*eye[:2],40);self.assertGreaterEqual(max(cover.get('path',0),cover.get('sidewalk',0)),.9);self.assertLessEqual(max(cover.get(k,0) for k in ('road','water','bridge')),.001)
        self.assertAlmostEqual(eye[2]-max(h for k,h in hs if k in ('path','sidewalk')),170,delta=.002);self.assertTrue(camera['visible_accent_types'])

    def test_hanging_flowers_preserve_headroom_and_night_recipe(self):
        self.assertEqual(self.data['decoration_recipe'],'paris_street_accents_v10')
        canopies=[r for r in self.data['records'] if r['kind']=='canopy']
        self.assertGreaterEqual(sum(r['hanging_baskets'] for r in canopies),500)
        self.assertLessEqual(sum(r['hanging_baskets'] for r in canopies),790)
        self.assertEqual(sum(r['bulbs'] for r in canopies),4740)
        for r in canopies:
            if r['hanging_baskets']:
                self.assertGreaterEqual(r['minimum_hanging_clearance_cm'],205)
                self.assertGreaterEqual(r['hanging_walk_coverage'],.98)
            else:self.assertTrue(r['hanging_not_placed_reason'])
        for o in self.data['objects']:
            if o['id'].startswith(('floral_','festoon_')):
                self.assertGreaterEqual(min(p[2] for p in o['positions_cm']),205)
                self.assertLessEqual(max(abs(p[0]) for p in o['positions_cm']),173.5)
        self.assertGreaterEqual(len({tuple(c[:3]) for o in self.data['objects'] if o['id'].startswith('urn_flowers_') for c in o['colors'] if c[0]>150 and c[1]<180}),6)

    def test_upper_decorations_follow_source_windows_without_covering_openings(self):
        from paris_district_layout import district_windows
        source,_=district_windows(self.scene['source_scene_sha256']);windows={(w['source_mesh_id'],w['source_quad_index']):w for w in source}
        boxes=[r for r in self.data['records'] if r['kind']=='window'];self.assertGreaterEqual(len(boxes),2200)
        for r in boxes:
            w=windows[(r['source_window_mesh'],r['source_window_quad'])]
            self.assertEqual(r['source_id'],w['source_id']);self.assertLess(abs(r['anchor_cm'][2]-(w['centre_cm'][2]-w['height_cm']/2)),.001)
            self.assertGreaterEqual(r['minimum_clearance_cm'],260)
            if r['uses_existing_planter']:self.assertNotIn('window_box',r['models'])
        banners=[r for r in self.data['records'] if r['kind']=='facade_banner'];self.assertGreaterEqual(len(banners),10)
        for r in banners:
            self.assertGreater(r['window_gap_cm'],90);self.assertGreater(r['minimum_clearance_cm'],300)
            for quad in r['adjacent_window_quads']:self.assertEqual(windows[(r['source_window_mesh'],quad)]['source_id'],r['source_id'])
        self.assertNotEqual(self.data['inspection_camera']['eye_cm'],self.data['inspection_close_camera']['eye_cm'])

    def test_decoration_covers_the_loaded_district_and_has_safe_tour_views(self):
        c=self.data['coverage'];self.assertEqual(c['extent_m'],800)
        self.assertGreaterEqual(c['decorated_eligible_cells']/c['eligible_cells'],.95)
        self.assertGreater(c['bounds_cm'][2]-c['bounds_cm'][0],70000)
        self.assertGreater(c['bounds_cm'][3]-c['bounds_cm'][1],70000)
        self.assertGreater(len({r['source_id'] for r in self.data['records'] if r['kind']=='window'}),250)
        self.assertGreater(sum(r['kind']=='pole' for r in self.data['records']),300)
        views=self.data['district_views'];self.assertGreaterEqual(len(views),5)
        surfaces=m.Surfaces(self.scene)
        for view in views[1:5]:
            x,y,z=view['eye_cm'];cover,hs=surfaces.query(x,y,35)
            self.assertGreaterEqual(max(cover.get('path',0),cover.get('sidewalk',0)),.9)
            floor=max(h for k,h in hs if k in ('path','sidewalk','ground'))
            self.assertAlmostEqual(z-floor,170,places=3)
        for r in self.data['records']:
            if r['kind']=='canopy':self.assertTrue(any(model.startswith('proxy_shop_') for model in r['models']))
            if r['kind']=='window':self.assertTrue(any(model.startswith('proxy_window_') for model in r['models']))
            if r['kind']=='pole':self.assertTrue(any(model.startswith('proxy_pole_') for model in r['models']))

    def test_overhead_spans_anchor_to_real_walls_and_keep_traffic_headroom(self):
        from shapely.ops import transform
        import numpy as np
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'));district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
        footprints={f['properties']['source_id']:local(shape(f['geometry'])) for f in district['layers']['buildings']}
        buildings=unary_union(list(footprints.values()));water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
        roads={f['properties']['source_id']:f['properties'] for f in district['layers']['roads']};surfaces=m.Surfaces(self.scene)
        garlands=[r for r in self.data['records'] if r['kind']=='street_garland'];self.assertGreaterEqual(len(garlands),30)
        self.assertGreater(len({(int(r['anchor_cm'][0]//10000),int(r['anchor_cm'][1]//10000)) for r in garlands}),8)
        for r in garlands:
            road=roads[r['source_id']];self.assertFalse(road['bridge']);self.assertFalse(road['tunnel']);self.assertEqual(road['layer'],0)
            ends=r['anchor_ends_cm'];span=LineString([p[:2] for p in ends]);self.assertLess(span.intersection(buildings).length,2.01);self.assertFalse(span.intersects(water))
            self.assertAlmostEqual(span.length,r['span_cm'],places=4);self.assertAlmostEqual(r['scale_xyz'][0]*1000,span.length,places=4)
            self.assertGreaterEqual(r['minimum_clearance_cm'],450);self.assertEqual(r['scale_xyz'][1:],[1,1])
            for i,(end,sid) in enumerate(zip(ends,r['anchor_building_source_ids'])):
                self.assertLess(footprints[sid].boundary.distance(Point(end[:2])),.02)
                self.assertLessEqual(end[2],r['anchor_wall_ground_cm'][i]+r['anchor_wall_height_m'][i]*100-50+.01)
            for t in np.linspace(.02,.98,11):
                p=span.interpolate(t,normalized=True);cover,hs=surfaces.query(p.x,p.y,12)
                self.assertLess(max(cover.get('water',0),cover.get('bridge',0)),.0011)
                self.assertLessEqual(max(h for k,h in hs if k in ('ground','road','path','sidewalk')),r['maximum_ground_cm']+.02)
        for o in self.data['objects']:
            if o['id'].startswith('street_festoon_'):self.assertGreaterEqual(min(p[2] for p in o['positions_cm']),480)

    def test_party_attachments_preserve_anchors_and_clear_buildings(self):
        from shapely.ops import transform
        import numpy as np
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'));district=m.read(ROOT/'gis/Data/Processed/ile_de_la_cite/district.json')
        local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-geo.origin[0])*100,-(np.asarray(y)-geo.origin[1])*100),g)
        buildings=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
        water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
        parents={(r['kind'],r['source_id'],tuple(r['anchor_cm'])):r for r in self.data['records'] if not r['kind'].startswith('party_')}
        party=[r for r in self.data['records'] if r['kind'].startswith('party_')]
        self.assertEqual(sum(r['kind']=='party_shop' for r in party),395);self.assertEqual(sum(r['kind']=='party_banner' for r in party),150)
        self.assertGreaterEqual(sum(r['kind']=='party_canopy' for r in party),20)
        for r in party:
            parent=parents[(r['source_record_kind'],r['source_id'],tuple(r['anchor_cm']))]
            self.assertEqual(r['yaw_degrees'],parent['yaw_degrees']);self.assertEqual(r.get('scale_xyz'),parent.get('scale_xyz'))
            self.assertEqual(r['building_source_id'],parent['building_source_id']);self.assertEqual(r['feature_layer'],'festival')
            if r['kind']!='party_canopy':continue
            self.assertGreaterEqual(r['minimum_clearance_cm'],450);a=math.radians(r['yaw_degrees']);cs=math.cos(a);sn=math.sin(a);p=r['anchor_cm'];scale=r['scale_xyz'][0]
            for offset in [-160,160]:
                points=[]
                for x in np.linspace(-500,500,33):
                    y=offset*(1-(x/500)**2);points.append([p[0]+cs*x*scale-sn*y,p[1]+sn*x*scale+cs*y])
                curve=LineString(points);self.assertLessEqual(curve.intersection(buildings).length,5);self.assertFalse(curve.intersects(water))
        for o in self.data['objects']:
            if o['id'].startswith('festival_canopy_'):self.assertGreaterEqual(min(p[2] for p in o['positions_cm']),470)
        colors={tuple(c) for o in self.data['objects'] if o['id'].startswith('festival_canopy_color_') for c in o['colors']};self.assertGreaterEqual(len(colors),5)

    def test_warm_windows_preserve_frames_and_label_fictional_occupancy(self):
        geo=m.Georeference(m.read(ROOT/'gis/config/ile_de_la_cite.json'))
        from paris_district_layout import district_windows
        catalog,_=district_windows(self.scene['source_scene_sha256']);source={(r['source_mesh_id'],r['source_quad_index']):r for r in catalog}
        lights=[r for r in self.data['records'] if r['kind']=='night_window']
        self.assertGreater(len(lights),2000);self.assertLess(len(lights),15000)
        self.assertGreater(len({r['source_id'] for r in lights}),200)
        for r in lights:
            w=source[(r['source_window_mesh'],r['source_window_quad'])]
            self.assertEqual(r['anchor_cm'],w['centre_cm']);self.assertEqual(r['source_id'],w['source_id'])
            self.assertEqual(r['occupancy_provenance'],'fictional_lighting_pattern_not_observed_occupancy')
            self.assertEqual(r['day_visibility'],'masked_out_by_shared_night_collection')
            self.assertLess(math.dist(geo.from_ue(*r['anchor_cm'])[:2],r['wgs84_placement']),1e-8)
        for model in self.data['objects']:
            if not model['id'].startswith('night_window_'):continue
            for x,y,z in model['positions_cm']:
                self.assertLess(abs(x),40);self.assertGreaterEqual(abs(x),4)
                self.assertEqual(y,6);self.assertLessEqual(abs(z),74)
                self.assertFalse(24<z<31)

    def test_window_relief_uses_original_panes_and_does_not_duplicate_core(self):
        from paris_district_layout import district_windows
        catalog,_=district_windows(self.scene['source_scene_sha256']);source={(w['source_mesh_id'],w['source_quad_index']):w for w in catalog}
        core=m.read(m.DATA/'paris-photo-frontages-source.json');excluded={(w['source_mesh_id'],w['source_quad_index']) for w in core['windows']+core.get('occluded_source_windows',[])}
        rows=[r for r in self.data['records'] if r['kind']=='facade_relief'];self.assertGreater(len(rows),10000)
        self.assertEqual(len(rows),len({(r['source_window_mesh'],r['source_window_quad']) for r in rows}))
        for r in rows:
            key=(r['source_window_mesh'],r['source_window_quad']);self.assertNotIn(key,excluded);w=source[key]
            self.assertEqual(r['anchor_cm'],w['centre_cm']);self.assertEqual(r['source_id'],w['source_id'])
            self.assertAlmostEqual(r['scale_xyz'][0]*90,w['width_cm'],places=4);self.assertAlmostEqual(r['scale_xyz'][2]*165,w['height_cm'],places=4)
            self.assertIn('relief_glass',r['models']);self.assertIn('relief_stone',r['models'])


if __name__=='__main__':unittest.main()
