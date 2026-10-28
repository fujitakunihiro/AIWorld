"""Trace station points to the checked-in OSM node references and CRS."""
import json, math, unittest
from pathlib import Path
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[3]
class MetroGeography(unittest.TestCase):
    def test_station_coordinates_and_shared_scene(self):
        data=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-metro.json').read_text(encoding='utf8'))
        scene=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(data['source_scene_sha256'],scene['source_scene_sha256'])
        self.assertEqual([s['source_id'] for s in data['stations']],['osm/node/264514896','osm/node/264515098'])
        self.assertEqual([s['entrance_source_id'] for s in data['stations']],['osm/node/677104485','osm/node/257628954'])
        project=Transformer.from_crs(4326,2154,always_xy=True);inverse=Transformer.from_crs(2154,4326,always_xy=True)
        coords=[]
        for station in data['stations']:
            lon,lat=station['wgs84'];x,y=project.transform(lon,lat);lon2,lat2=inverse.transform(x,y)
            self.assertAlmostEqual(lon,lon2,places=7);self.assertAlmostEqual(lat,lat2,places=7)
            elon,elat=station['entrance_wgs84'];ex,ey=project.transform(elon,elat)
            self.assertLess(math.hypot(x-ex,y-ey),100);coords.append((x,y))
        self.assertTrue(200<math.dist(*coords)<600)
if __name__=='__main__':unittest.main()
