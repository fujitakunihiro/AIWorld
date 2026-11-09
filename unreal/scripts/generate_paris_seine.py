"""Reproducible district-wide river presentation; archived geography is read-only."""
import hashlib,json
from pathlib import Path
from pyproj import Transformer
from generate_paris_reference import generate

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'unreal/assets/paris-seine/Generated/seine.json'

def build(reuse=False):
    cameras={
        'Cathedral':dict(name='Seine / Notre-Dame',source_id='osm/way/201611261',eye_cm=[-8000,13000,-240],target_cm=[18000,17500,2700],focal_length_mm=40,viewpoint_provenance='inferred river-level photographic viewpoint; not a walking spawn'),
        'Bridge':dict(name='Pont Saint-Michel / river arches',source_id='osm/way/20444342',eye_cm=[-8500,12500,-250],target_cm=[-18400,6600,500],focal_length_mm=32,viewpoint_provenance='inferred river-level photographic viewpoint; not a walking spawn'),
        'Aerial':dict(name='Ile de la Cite / district aerial',source_id='osm/way/201611261',eye_cm=[-26000,48000,31000],target_cm=[2500,3000,800],focal_length_mm=34,viewpoint_provenance='inferred aerial viewpoint; district acquisition boundary remains visible'),
    }
    result=json.loads(OUT.read_text(encoding='utf-8')) if reuse else generate(output=OUT,camera_region=(cameras['Cathedral'],[0,0]),radius_cm=46000)
    result['recipe']='paris_seine_vista_v1'
    result['cameras']=cameras
    result['camera']=cameras['Cathedral']
    g=result['georeference'];ox,oy=g['projected_origin_m'];to_ll=Transformer.from_crs(2154,4326,always_xy=True)
    for cam in cameras.values():
        x,y,z=cam['eye_cm'];cam['eye_wgs84']=list(to_ll.transform(ox+x/100,oy-y/100));cam['eye_elevation_ngf_m']=g['origin_elevation_ngf_m']+z/100
    # Bridge source IDs come from the existing verified reconstruction packet.
    bridges=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-bridges.json').read_text(encoding='utf-8'))
    cameras['Bridge']['source_id']=next(p for p in bridges['profiles'] if p['id']=='michel')['primary_source_id']
    water=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-water.json').read_text(encoding='utf-8'))
    result['seine']=dict(water_source_id=water['source_id'],water_level_cm=water['water_level_cm'],appearance_inferred=True,source_geometry_sha256=hashlib.sha256((ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin-meshes.bin').read_bytes()).hexdigest(),camera_names=list(cameras),preserves_source_positions=True)
    from paris_seine_banks import add_banks
    scene=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    add_banks(result,scene,ROOT/'unreal/AIWorld/Content/Data')
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('PARIS_SEINE_INPUTS_READY',result['counts'],hashlib.sha256(OUT.read_bytes()).hexdigest())
    return result

if __name__=='__main__':
    import sys
    build(reuse='--reuse-architecture' in sys.argv)
