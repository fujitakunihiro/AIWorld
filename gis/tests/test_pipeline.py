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

CONFIG=read(ROOT/'gis/config/ile_de_la_cite.json')


class PipelineTests(unittest.TestCase):
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
        self.assertTrue(all(o['properties']['water_level_local_m']>=0 for o in scene['objects'] if o['id'] in basin_ids))


if __name__=='__main__':unittest.main()
