"""Reproducible, inferred window relief for the mapped Palais de Justice.

Copies only original inferred facade quads attributed to the palace. Geometry
is instanced and does not claim surveyed joinery or modify the GIS scene.
"""
import hashlib,json,math,struct
from pathlib import Path
from shapely.geometry import Point,LineString,shape
from generate_paris_frontages import Mesh
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data';SID='osm/relation/536982';CHAPEL='osm/relation/3344870';CENTRE=(-15173.6394325,-7772.3607886);RADIUS=5000

def generate():
 scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
 district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf8'));ox,oy=district['origin_projected_m'];blob=(DATA/'paris-digital-twin-meshes.bin').read_bytes()
 polygons={f['properties']['source_id']:shape(f['geometry']) for f in district['layers']['buildings']}; palace=polygons[SID]
 windows=[];seen=set()
 for obj in scene['objects']:
  if obj['kind']!='facade_glass' or SID not in obj.get('properties',{}).get('source_ids',[]):continue
  spec=obj['mesh_buffer'];offset=spec['offset'];count=spec['vertex_count']
  rows=list(struct.iter_unpack('<6f4B',blob[offset:offset+28*count]));indices=struct.unpack_from('<'+str(spec['index_count'])+'I',blob,offset+28*count)
  for k in range(0,len(indices),6):
   ids=list(dict.fromkeys(indices[k:k+6]))
   if len(ids)!=4:continue
   points=[rows[i][:3] for i in ids];raw=rows[ids[0]][3:6];ln=math.hypot(*raw[:2])
   if ln<.99 or abs(raw[2])>.001:continue
   normal=(raw[0]/ln,raw[1]/ln);tangent=(normal[1],-normal[0]);centre=[sum(p[i] for p in points)/4 for i in range(3)]
   if math.dist(centre[:2],CENTRE)>RADIUS:continue
   extent=[(p[0]-centre[0])*tangent[0]+(p[1]-centre[1])*tangent[1] for p in points];width=max(extent)-min(extent);height=max(p[2] for p in points)-min(p[2] for p in points)
   if not (85<width<95 and 160<height<170):continue
   projected=Point(ox+(centre[0]-normal[0]*9)/100,oy-(centre[1]-normal[1]*9)/100)
   candidates=[(polygons[sid].boundary.distance(projected),sid) for sid in obj['properties']['source_ids'] if sid in polygons]
   if not candidates:continue
   distance,sid=min(candidates)
   if sid!=SID or distance>.03:continue
   key=tuple(round(v,2) for v in centre+list(normal))
   if key in seen:continue
   # If a nearby mapped building covers the relief, omit it instead of putting
   # window frames inside a neighbour's walls.
   outside=Point(ox+(centre[0]+normal[0]*35)/100,oy-(centre[1]+normal[1]*35)/100)
   if any(g.covers(outside) for other,g in polygons.items() if other!=SID):continue
   seen.add(key);windows.append(dict(source_id=SID,source_mesh_id=obj['id'],source_quad_index=k//6,centre_cm=centre,normal=normal,width_cm=width,height_cm=height,boundary_error_cm=distance*100))
 if not 20<len(windows)<3000:raise ValueError('Unexpected palace window count')
 windows.sort(key=lambda w:(w['source_mesh_id'],w['source_quad_index']))
 # Prototype at one source window centre, +X tangent / +Y outward / +Z up.
 base=[0,0,0];tan=[1,0,0];out=[0,1,0];stone=Mesh();wood=Mesh();glass=Mesh();iron=Mesh()
 c=[207,198,180,255];paint=[52,59,55,255];metal=[52,57,57,255];width=90;height=165;half=width/2;bottom=-height/2;top=height/2
 for x in (-half-7,half+7):
  stone.box(base,tan,out,(x,9,0),(14,28,height+24),c);stone.box(base,tan,out,(x+(2 if x<0 else -2),21,0),(5,6,height+10),c)
 for z,sx,sy,sz,y in [(bottom-8,width+38,42,12,12),(bottom-1,width+28,34,5,12),(top+8,width+32,27,16,8),(top+18,width+40,33,5,10)]:stone.box(base,tan,out,(0,y,z),(sx,sy,sz),c)
 for x in (-half+2,0,half-2):wood.box(base,tan,out,(x,8,0),(5,8,height),paint)
 for z in (bottom+2,top-55,top-2):wood.box(base,tan,out,(0,8,z),(width,8,5),paint)
 glass.face([[-half,5,bottom],[half,5,bottom],[half,5,top],[-half,5,top]],out,[45,66,76,255],[(0,0),(1,0),(1,1),(0,1)])
 # Small inferred handles, kept clear of the existing balcony railings.
 for x in (-7,7):
  iron.box(base,tan,out,(x,14,-5),(2,3,18),metal)
  iron.box(base,tan,out,(x,12,-13),(4,3,4),metal)
  iron.box(base,tan,out,(x,12,3),(4,3,4),metal)
 def model(name,m,material):
  item=m.item(name,material);item.pop('asset',None);item.pop('geometry_sha256',None);item.pop('triangles',None);item['material']='/Game/Materials/'+material;item['vertex_colors']=[''.join(f'{b:02x}' for b in row[:3]) for row in item.pop('colors')];item['color']='ffffff';return item
 models=[model('stone',stone,'M_Paris_Limestone'),model('wood',wood,'M_ParisWood'),model('glass',glass,'M_ParisGlass'),model('iron',iron,'M_ParisCastIron')]
 # Candidate observation window is a mapped ground-level-facing courtyard quad.
 # Match the exact UE frame and choose a camera outside ALL source buildings.
 chosen=None
 for w in sorted(windows,key=lambda x:(abs(x['centre_cm'][2]-400),math.dist(x['centre_cm'][:2],CENTRE))):
  x,y,z=w['centre_cm'];nx,ny=w['normal'];tx,ty=ny,-nx
  for lateral in (0,250,-250):
   eye=(x+nx*800+tx*lateral,y+ny*800+ty*lateral,z+120)
   p=Point(ox+eye[0]/100,oy-eye[1]/100);line=LineString([(ox+x/100,oy-y/100),p.coords[0]])
   if all(not g.buffer(.15).covers(p) and not g.intersects(line) for sid,g in polygons.items() if sid!=SID) and not palace.buffer(.15).covers(p):
    chosen=(w,eye);break
  if chosen:break
 if not chosen:raise ValueError('No source-clear camera')
 w,eye=chosen
 return dict(format='paris_palais_frontage_instances_v1',source_scene_sha256=scene['source_scene_sha256'],source_id=SID,window_count=len(windows),radius_cm=RADIUS,anchor_cm=CENTRE,models=models,windows=windows,inspection_eye_cm=eye,inspection_target_cm=w['centre_cm'],inspection_source_quad=w['source_quad_index'],appearance_provenance='Inferred window relief aligned with existing inferred source quads; not a survey or true glass openings; original GIS collision retained.')
if __name__=='__main__':
 result=generate();path=DATA/'paris-palais-frontages.json';path.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8');print(json.dumps({k:result[k] for k in ['source_id','window_count','inspection_eye_cm','inspection_target_cm']}))
