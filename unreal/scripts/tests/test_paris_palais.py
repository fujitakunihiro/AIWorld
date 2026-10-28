"""Source traceability and reproducibility of Palais de Justice details."""
import hashlib,json,math,struct,sys,unittest
from pathlib import Path
from shapely.geometry import Point,LineString,shape
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'unreal/scripts'))
from generate_paris_palais_frontages import generate,SID,CENTRE,RADIUS
DATA=ROOT/'unreal/AIWorld/Content/Data'
class PalaisTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.layer=json.loads((DATA/'paris-palais-frontages.json').read_text(encoding='utf8'));cls.scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'));cls.blob=(DATA/'paris-digital-twin-meshes.bin').read_bytes();cls.objects={o['id']:o for o in cls.scene['objects']};cls.district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf8'));cls.ox,cls.oy=cls.district['origin_projected_m'];cls.polys={f['properties']['source_id']:shape(f['geometry']) for f in cls.district['layers']['buildings']}
 def test_each_instance_matches_a_source_quad(self):
  self.assertEqual(self.layer['source_scene_sha256'],self.scene['source_scene_sha256']);self.assertEqual(self.layer['source_id'],SID);self.assertEqual(self.layer['window_count'],len(self.layer['windows']));self.assertGreater(len(self.layer['windows']),100)
  seen=set();cache={};palace=self.polys[SID]
  for w in self.layer['windows']:
   self.assertEqual(w['source_id'],SID);self.assertLessEqual(math.dist(w['centre_cm'][:2],CENTRE),RADIUS+.01)
   obj=self.objects[w['source_mesh_id']];self.assertEqual(obj['kind'],'facade_glass');self.assertIn(SID,obj['properties']['source_ids']);spec=obj['mesh_buffer']
   if obj['id'] not in cache:
    p=spec['offset'];n=spec['vertex_count'];rows=list(struct.iter_unpack('<6f4B',self.blob[p:p+28*n]));idx=struct.unpack_from('<'+str(spec['index_count'])+'I',self.blob,p+28*n);cache[obj['id']]=(rows,idx)
   rows,idx=cache[obj['id']];k=w['source_quad_index']*6;ids=list(dict.fromkeys(idx[k:k+6]));self.assertEqual(len(ids),4)
   centre=[sum(rows[i][axis] for i in ids)/4 for axis in range(3)]
   self.assertLess(math.dist(centre,w['centre_cm']),.001);n=w['normal'];self.assertAlmostEqual(math.hypot(*n),1,places=5)
   p=Point(self.ox+(centre[0]-n[0]*9)/100,self.oy-(centre[1]-n[1]*9)/100);self.assertLess(palace.boundary.distance(p),.03)
   key=(obj['id'],k);self.assertNotIn(key,seen);seen.add(key)
 def test_camera_is_outside_buildings(self):
  e=self.layer['inspection_eye_cm'];t=self.layer['inspection_target_cm'];p=Point(self.ox+e[0]/100,self.oy-e[1]/100);line=LineString([(self.ox+t[0]/100,self.oy-t[1]/100),p.coords[0]])
  for sid,g in self.polys.items():
   self.assertFalse(g.buffer(.15).covers(p))
   if sid!=SID:self.assertFalse(g.intersects(line))
 def test_regeneration_matches(self):
  self.assertEqual(json.loads(json.dumps(generate(),allow_nan=False)),self.layer)
if __name__=='__main__':unittest.main()
