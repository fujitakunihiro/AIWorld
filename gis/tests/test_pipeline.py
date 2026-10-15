import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from shapely.geometry import Polygon
from paris_twin.coordinates import Georeference
from paris_twin.io import ROOT,paths,read,sha
from paris_twin.mesh import export,triangulate
from paris_twin.normalize import normalize,positive_number,road_width
from paris_twin.validate import validate
from paris_twin import acquire
from paris_twin.diagnostics import road_components
from paris_twin import building_source
from paris_twin.building_heights import enrich_buildings
from paris_twin.building_mesh import roof_surfaces,gutter_at
from paris_twin.normalize import polygonal
from paris_twin.io import write
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
from paris_twin.terrain import Terrain
from paris_twin.mesh import Mesh
from paris_twin.bridges import BridgeDeck
from paris_twin import elevation_source
from paris_twin.building_mesh import generate_buildings
from paris_twin.facades import batch_bodies,generate_facades
from paris_twin import prepare
from paris_twin.io import generation_metadata

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class PipelineTests(unittest.TestCase):
    def test_fixed_ngf_origin_survives_dem_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp);write(raw/'terrain/manifest.json',dict(grid_steps=2))
            write(raw/'terrain/elevations.json',dict(origin={'z':37.},elevations=[{'z':38.}]*9))
            geo=Georeference(CONFIG)
            with patch('paris_twin.terrain.paths',return_value={'Raw':raw}):terrain=Terrain(CONFIG,geo)
            self.assertEqual(terrain.origin_ngf,35.38);self.assertEqual(terrain.measured_origin_ngf,37.)
            self.assertAlmostEqual(terrain.local(geo.origin),2.62)
            self.assertEqual(geo.to_ue(*CONFIG['origin_wgs84'],35.38,terrain.origin_ngf)[2],0)

    def test_cached_export_restores_native_and_rejects_changed_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folders={name:root/name for name in ['Raw','Processed','Generated']}
            products={}
            for key in prepare.PRODUCTS:
                folder,name=key.split('/');path=folders[folder]/name;path.parent.mkdir(exist_ok=True)
                path.write_text('unchanged source product');products[key]=sha(path)
            write(folders['Generated']/'generation-cache.json',dict(district_id=CONFIG['district_id'],generation=generation_metadata(CONFIG),
                  raw_checksums={'test.json':'123'},products=products,statistics=dict(meshes=1,buildings=1,triangles=1)))
            native=root/'unreal/AIWorld/Content/Data/paris-digital-twin.json';native.parent.mkdir(parents=True);native.write_text('other district')
            with patch.object(prepare,'paths',return_value=folders),patch.object(prepare,'ROOT',root),patch.object(prepare,'verify_cache',return_value={'files':{'test.json':{'sha256':'123'}}}):
                result=prepare.prepare(CONFIG);self.assertTrue(result['cached']);self.assertEqual(sha(native),products['Generated/scene.json'])
                with patch('paris_twin.normalize.normalize',side_effect=RuntimeError('regeneration required')):
                    with self.assertRaisesRegex(RuntimeError,'regeneration required'):prepare.prepare({**CONFIG,'default_building_height_m':16})
                    (folders['Generated']/'scene.json').write_text('damaged export')
                    with self.assertRaisesRegex(RuntimeError,'regeneration required'):prepare.prepare(CONFIG)

    def test_failed_terrain_refresh_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp);folder=raw/'terrain';folder.mkdir();(folder/'manifest.json').write_text('old');(folder/'elevations.json').write_text('old samples')
            with patch.object(elevation_source,'paths',return_value={'Raw':raw}),patch.object(elevation_source,'request',side_effect=RuntimeError('IGN unavailable')):
                with self.assertRaisesRegex(RuntimeError,'IGN unavailable'):elevation_source.download_terrain(CONFIG,refresh=True)
            self.assertEqual((folder/'manifest.json').read_text(),'old');self.assertEqual((folder/'elevations.json').read_text(),'old samples')

    def test_bilinear_terrain_and_shared_vertical_datum(self):
        terrain=Terrain.__new__(Terrain);terrain.steps=2;terrain.bounds=(0,0,20,20);terrain.spacing=10;terrain.origin_ngf=30
        terrain.samples=[{'z':30+.1*x+.2*y} for y in [0,10,20] for x in [0,10,20]]
        self.assertAlmostEqual(terrain.ngf((7,13)),33.3);self.assertAlmostEqual(terrain.local((7,13)),3.3)
        self.assertAlmostEqual(terrain.ngf((20,20)),36)
        geo=Georeference(CONFIG);x,y=geo.origin
        mesh=Mesh(geo);foot=Polygon([(x,y),(x+20,y),(x+20,y+20),(x,y+20)],holes=[[(x+5,y+5),(x+5,y+10),(x+10,y+10),(x+10,y+5)]])
        mesh.drape(foot,lambda p:(p[0]-x)*.1+(p[1]-y)*.2,5)
        for px,py,pz in mesh.positions:self.assertAlmostEqual(pz/100,(px/100)*.1-(py/100)*.2,places=4)
        for n in mesh.normals:self.assertGreater(n[2],.9)

    def test_bridge_deck_meets_banks_without_dem_river_dip(self):
        terrain=type('TestTerrain',(),dict(origin_ngf=30.,local=lambda self,p:4. if p[0]<10 or p[0]>60 else -3.))()
        deck=BridgeDeck(Polygon([(0,0),(70,0),(70,10),(0,10)]),[],terrain)
        self.assertAlmostEqual(deck.height(deck.ends[0]),4.035)
        self.assertAlmostEqual(deck.height(deck.ends[1]),4.035)
        self.assertGreater(deck.height((35,5)),4)
        self.assertGreater(deck.properties(27)['minimum_centerline_clearance_m'],7)

    def test_gutter_absolute_height_and_batch_ids_survive(self):
        geo=Georeference(CONFIG);x,y=geo.origin;g=Polygon([(x,y),(x+10,y),(x+10,y+10),(x,y+10)])
        part=dict(geometry=mapping(g),height_gutter_m=10,ground_ngf_m=35,gutter_segments_m=[],roof=dict(form='flat',rise_m=0))
        props=dict(source_id='osm/way/1',height_parts=[part],tags={},wgs84_centre=list(CONFIG['origin_wgs84']),reproduction_level_body='L2')
        features=[dict(geometry=mapping(g),properties=props)]
        terrain=type('TestTerrain',(),dict(origin_ngf=30.,local=lambda self,p:3.,ngf=lambda self,p:33.))()
        objects=generate_buildings(geo,features,Mesh,triangulate,terrain)
        roof=next(o for o in objects if o['kind']=='roof');self.assertAlmostEqual(max(p[2] for p in roof['positions_cm']),1502.)
        body=next(o for o in objects if o['kind']=='building');self.assertAlmostEqual(min(p[2] for p in body['positions_cm']),282.)
        batched=batch_bodies(objects,geo,Mesh);batch=next(o for o in batched if o['kind']=='building')
        self.assertEqual(batch['properties']['source_ids'],['osm/way/1']);self.assertEqual(batch['appearance_ranges'][0]['count'],len(body['positions_cm']))
        facades,report=generate_facades(geo,features,terrain,Mesh);self.assertGreater(report['windows'],0)
        props['tags']={'building':'cathedral'}
        self.assertEqual(generate_facades(geo,features,terrain,Mesh)[1]['windows'],0)

    def test_failed_building_refresh_preserves_height_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp);folder=raw/'heights';folder.mkdir();(folder/'manifest.json').write_text('old metadata');(folder/'buildings.json').write_text('old buildings')
            with patch.object(building_source,'paths',return_value={'Raw':raw}),patch.object(building_source,'request',side_effect=RuntimeError('WFS unavailable')):
                with self.assertRaisesRegex(RuntimeError,'WFS unavailable'):building_source.download_buildings(CONFIG,refresh=True)
            self.assertEqual((folder/'manifest.json').read_text(),'old metadata');self.assertEqual((folder/'buildings.json').read_text(),'old buildings')

    def test_ign_height_parts_keep_real_steps_and_do_not_use_church_spire_as_wall(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp);features=[]
            for identifier,left,right,height in [('a',0,10,10),('b',10,20,30)]:
                geometry={'type':'MultiPolygon','coordinates':[[[[left,0,30+height],[right,0,30+height],[right,20,30+height],[left,20,30+height],[left,0,30+height]]]]}
                features.append({'geometry':geometry,'properties':{'cleabs':identifier,'hauteur':height,'altitude_minimale_sol':30,'precision_altimetrique':1.5,'methode_d_acquisition_altimetrique':'Photogrammétrie','date_modification':'2026-01-01'}})
            write(raw/'heights/buildings.json',{'features':features})
            foot=Polygon([(0,0),(20,0),(20,20),(0,20)])
            layers={'buildings':[{'geometry':mapping(foot),'properties':{'source_id':'osm/way/1','source_url':'https://www.openstreetmap.org/way/1','height_m':75,'height_kind':'source_declared_unverified','height_source':'osm:height_tag','clipped_at_context_boundary':False,'tags':{'building':'church','height':'75','roof:shape':'flat'}}}]}
            enrich_buildings(CONFIG,raw,layers,polygonal);p=layers['buildings'][0]['properties']
            self.assertEqual(p['height_gutter_max_m'],30);self.assertEqual(p['height_m'],30)
            self.assertEqual(p['reproduction_level_body'],'L2');self.assertEqual(p['reproduction_level'],'L1')
            self.assertEqual(p['official_height_coverage'],1)
            self.assertEqual({part['height_gutter_m'] for part in p['height_parts']},{10,30})
            self.assertAlmostEqual(sum(shape(part['geometry']).area for part in p['height_parts']),foot.area)

    def test_procedural_roofs_preserve_holes_and_ridge_breaks(self):
        footprint=Polygon([(0,0),(30,0),(30,30),(0,30)],holes=[[(10,10),(10,20),(20,20),(20,10)]])
        for form in ['flat','gabled','mansard','hipped','pyramidal']:
            surfaces=list(roof_surfaces(footprint,{'form':form,'rise_m':4 if form!='flat' else 0}))
            triangles=[t for g,rise in surfaces for t in triangulate(g)]
            self.assertAlmostEqual(sum(t.area for t in triangles),footprint.area,places=5)
            self.assertTrue(all(footprint.covers(t) for t in triangles))
            for g,rise in surfaces:
                point=g.representative_point();self.assertTrue(0<=rise((point.x,point.y))<=4)
    def test_failed_online_refresh_preserves_previous_offline_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'district';raw.mkdir();(raw/'manifest.json').write_text('old manifest');(raw/'osm.json').write_text('old raw data')
            def failure(config,staging):
                (staging/'osm.json').write_text('incomplete replacement');raise RuntimeError('API unavailable')
            with patch.object(acquire,'paths',return_value={'Raw':raw}),patch.object(acquire,'_download_snapshot',side_effect=failure):
                with self.assertRaisesRegex(RuntimeError,'API unavailable'):acquire.download(CONFIG,refresh=True)
            self.assertEqual((raw/'manifest.json').read_text(),'old manifest')
            self.assertEqual((raw/'osm.json').read_text(),'old raw data')

    def test_district_id_cannot_escape_data_root(self):
        with self.assertRaises(ValueError):paths({**CONFIG,'district_id':'../../outside'})

    def test_coordinates_roundtrip_and_cm_axes(self):
        geo=Georeference(CONFIG)
        lon,lat=geo.inverse.transform(geo.origin[0]+1,geo.origin[1]+2)
        x,y,z=geo.to_ue(lon,lat,35,30)
        self.assertAlmostEqual(x,100,places=3);self.assertAlmostEqual(y,-200,places=3);self.assertEqual(z,500)
        lon2,lat2,h=geo.from_ue(x,y,z,origin_elevation=30)
        self.assertAlmostEqual(lon,lon2,places=10);self.assertAlmostEqual(lat,lat2,places=10);self.assertEqual(h,35)
        with self.assertRaises(ValueError):Georeference({**CONFIG,'projected_crs':'EPSG:4326'})

    def test_adjacent_district_uses_same_origin_and_continuous_coordinates(self):
        geo=Georeference(CONFIG)
        centre=geo.inverse.transform(geo.origin[0]+500,geo.origin[1])
        neighbor=Georeference({**CONFIG,'district_center_wgs84':centre})
        self.assertEqual(geo.origin,neighbor.origin)
        point=geo.inverse.transform(geo.origin[0]+250,geo.origin[1]+80)
        self.assertEqual(geo.to_ue(*point),neighbor.to_ue(*point))
        self.assertGreater(geo.extent.intersection(neighbor.extent).area,0)
        self.assertAlmostEqual(neighbor.centre[0]-geo.centre[0],500,places=6)

    def test_road_review_distinguishes_clipped_boundary_and_internal_paths(self):
        geo=Georeference(CONFIG);x,y=geo.origin
        def road(identifier,ids,points):
            return {'properties':{'tunnel':False,'layer':0,'source_id':identifier,'osm_node_ids':ids,'source_geometry_projected':{'coordinates':points}}}
        roads=[road('osm/way/1',[1,2,3],[(x,y),(x+50,y),(x+100,y)]),
               road('osm/way/2',[4,5],[(x,y+50),(x+20,y+50)]),
               road('osm/way/3',[6,7],[(x-450,y),(x-390,y)])]
        network,issues=road_components(roads,geo)
        self.assertEqual(network['component_sizes'],[3,2,2])
        self.assertEqual([i['classification'] for i in issues],['interior_unconnected','boundary_clipped'])
        self.assertEqual(road_components(list(reversed(roads)),geo),(network,issues))

    def test_roof_and_ground_triangulation_preserves_courtyards(self):
        g=Polygon([(0,0),(20,0),(20,20),(0,20)],holes=[[(4,4),(4,8),(8,8),(8,4)]])
        tris=triangulate(g)
        self.assertAlmostEqual(sum(t.area for t in tris),g.area,places=6)
        self.assertTrue(all(g.covers(t) for t in tris))

    def test_dimensions_are_explicit_and_estimates_labelled(self):
        self.assertEqual(positive_number('10 ft'),3.048)
        self.assertIsNone(positive_number('12;15'))
        self.assertEqual(road_width({'width':'8 m'},CONFIG),(8,'osm:width',False))
        self.assertTrue(road_width({'highway':'residential'},CONFIG)[2])

    @unittest.skipUnless((paths(CONFIG)['Raw']/'manifest.json').exists(),'requires the archived real-data snapshot')
    def test_real_snapshot_quality_and_reproducibility(self):
        acquire.verify_cache({**CONFIG,'default_building_height_m':18})
        data=normalize(CONFIG);export(CONFIG,data);a=sha(paths(CONFIG)['Generated']/'scene.json')
        data2=normalize(CONFIG);export(CONFIG,data2);b=sha(paths(CONFIG)['Generated']/'scene.json')
        self.assertEqual(a,b)
        report=validate(CONFIG)
        self.assertEqual(report['errors'],[])
        self.assertGreater(report['buildings'],20)
        self.assertGreater(report['road_network']['edges'],20)
        self.assertEqual(report['generated_surface_validation']['generated_road_building_overlap_m2'],0)
        self.assertEqual(report['untraced_ids'],[])
        scene=read(paths(CONFIG)['Generated']/'scene.json')
        river_ids=set(next(o for o in scene['objects'] if o['id']=='seine')['properties']['source_ids'])
        basin_ids={f['properties']['source_id'] for f in data['layers']['water'] if f['properties']['water_role']=='basin'}
        self.assertTrue(river_ids);self.assertTrue(basin_ids);self.assertFalse(river_ids & basin_ids)
        self.assertTrue(all(o['properties']['water_above_terrain_m']==.12 for o in scene['objects'] if o['id'] in basin_ids))
        self.assertEqual(scene['diagnostics']['building_overlaps'],report['building_overlaps'])
        self.assertEqual(len(scene['diagnostics']['issues']),len(report['building_overlaps'])+len(report['road_network']['component_sizes'])-1)
        self.assertEqual(len(scene['landmarks']),3)
        self.assertTrue(scene['footprint_mesh']['indices'])
        self.assertEqual(len(scene['pick_features']),len({f['id'] for f in scene['pick_features']}))
        self.assertGreater(report['official_height_buildings'],500)
        notre=next(f['properties'] for f in data['layers']['buildings'] if f['properties']['name']=='Cathédrale Notre-Dame de Paris')
        self.assertGreater(notre['height_gutter_max_m'],50)
        self.assertGreater(len(notre['height_reference_ids']),2)
        self.assertTrue(all(f['properties']['reproduction_level']=='L1' for f in data['layers']['buildings']))
        self.assertTrue(any(o['kind']=='roof' for o in scene['objects']))
        self.assertGreater(report['street_furniture']['rendered']['tree'],900)
        self.assertGreater(report['street_furniture']['rendered']['lamp'],400)
        self.assertGreater(report['facades']['balconies'],100)
        self.assertGreater(report['facades']['party_wall_columns_omitted'],100)
        self.assertGreater(report['instance_batches'],11)
        self.assertGreater(report['businesses']['storefronts'],20)
        self.assertGreater(report['businesses']['terraces'],0)
        self.assertLessEqual(report['runtime_packet']['max_position_error_cm'],.01)
        self.assertGreater(report['street_furniture']['rendered']['bicycle_rack'],30)
        self.assertGreater(report['traffic']['agents'],15)
        self.assertTrue(report['traffic']['inferred_traffic'])
        self.assertGreater(report['pedestrians']['routes'],100)
        self.assertGreater(report['pedestrians']['agents'],100)
        self.assertTrue(report['pedestrians']['inferred_population'])
        self.assertGreater(report['pedestrians']['visits']['destinations'],0)
        self.assertGreater(report['pedestrians']['navigation']['connectors'],100)
        self.assertLess(report['pedestrians']['navigation']['components'],500)
        from paris_twin.visits import sample
        import math
        routes={r['id']:r for r in scene['pedestrians']['routes']}
        positions=[sample(routes[a['route_id']]['points_cm'],a['progress_m']*100) for a in scene['pedestrians']['agents']]
        self.assertTrue(all(math.dist(a[:2],b[:2])>=125 for i,a in enumerate(positions) for b in positions[:i]))


if __name__=='__main__':unittest.main()
