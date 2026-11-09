"""Shared source-aligned window depth outside the original detailed core."""
import hashlib,json,math
from pathlib import Path
from generate_paris_frontages import Mesh

ROOT=Path(__file__).resolve().parents[2]


def make_models():
    result=[];stone=Mesh(bevel_cm=.35);wood=Mesh(bevel_cm=.15);glass=Mesh()
    def add(name,mesh,material):
        item=mesh.item(name,material);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    ivory=[220,210,187,255]
    for x in [-52,52]:
        stone.box([0,0,0],[1,0,0],[0,1,0],[x,4,0],[14,28,189],ivory)
        stone.box([0,0,0],[1,0,0],[0,1,0],[x+(2 if x<0 else -2),17,0],[5,6,175],ivory)
    stone.box([0,0,0],[1,0,0],[0,1,0],[0,7,91],[122,30,14],ivory)
    stone.box([0,0,0],[1,0,0],[0,1,0],[0,10,101],[130,36,5],ivory)
    stone.box([0,0,0],[1,0,0],[0,1,0],[0,8,-90],[126,38,12],ivory)
    add('relief_stone',stone,'M_ParisLimestone')
    for theme,color in [('sage',[60,77,67,255]),('wine',[96,46,49,255]),('ivory',[201,191,164,255])]:
        mesh=Mesh(bevel_cm=.15)
        for x in [-43,0,43]:mesh.box([0,0,0],[1,0,0],[0,1,0],[x,8,0],[5,8,165],color)
        for z in [-80.5,27.5,80.5]:mesh.box([0,0,0],[1,0,0],[0,1,0],[0,8,z],[90,8,5],color)
        add('relief_wood_'+theme,mesh,'M_ParisWindowPaintedWood')
    glass.face([[-45,5,-82.5],[45,5,-82.5],[45,5,82.5],[-45,5,82.5]],[0,1,0],[94,111,128,255],[(0,0),(1,0),(1,1),(0,1)])
    add('relief_glass',glass,'M_ParisStreetWindowGlass')
    return result


def make_placements(windows,geo):
    source=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-photo-frontages-source.json').read_text(encoding='utf-8'))
    core={(w['source_mesh_id'],w['source_quad_index']) for w in source['windows']}
    occluded={(w['source_mesh_id'],w['source_quad_index']) for w in source.get('occluded_source_windows',[])}
    records=[];excluded=core|occluded
    for w in windows:
        if (w['source_mesh_id'],w['source_quad_index']) in excluded:continue
        p=w['centre_cm'];n=w['normal'];seed=int(hashlib.sha256(w['source_id'].encode()).hexdigest()[:8],16);ll=geo.from_ue(*p)
        records.append(dict(kind='facade_relief',source_id=w['source_id'],building_source_id=w['source_id'],source_window_mesh=w['source_mesh_id'],source_window_quad=w['source_quad_index'],source_window_centre_cm=p,source_window_normal=n,source_window_width_cm=w['width_cm'],source_window_height_cm=w['height_cm'],placement_provenance='inferred_stone_joinery_and_glazing_depth_at_existing_inferred_window',anchor_cm=p,yaw_degrees=math.degrees(math.atan2(-n[0],n[1])),scale_xyz=[w['width_cm']/90,1,w['height_cm']/165],wgs84_placement=list(ll[:2]),models=['relief_stone','relief_wood_'+['sage','wine','ivory'][seed%3],'relief_glass']))
    return records
