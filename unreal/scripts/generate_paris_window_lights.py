"""Inferred evening occupancy at existing source-aligned upper windows."""
import hashlib,math
from generate_paris_frontages import Mesh


def make_models():
    result=[]
    for variant,color in enumerate([[255,218,158,255],[255,236,197,255],[255,201,139,255]]):
        mesh=Mesh()
        # Glazing relief is 5cm ahead of the source glass. The night overlay
        # sits at 6cm, behind the timber profiles (front at 12cm), with gaps
        # for the central mullion and the upper transom.
        for x0,x1 in [(-38,-4),(4,38)]:
            for z0,z1 in [(-74,24),(31,74)]:
                points=[[x0,6,z0],[x1,6,z0],[x1,6,z1],[x0,6,z1]]
                mesh.face(points,[0,1,0],color,[((p[0]+45)/90,(p[2]+82.5)/165) for p in points])
        item=mesh.item('night_window_'+str(variant),'M_ParisLuxuryNightWindow')
        item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    return result


def make_placements(windows,geo):
    result=[]
    for w in windows:
        seed=int(hashlib.sha256((w['source_id']+w['source_mesh_id']+str(w['source_quad_index'])+'evening').encode()).hexdigest()[:8],16)
        if seed%5>=2:continue
        p=w['centre_cm'];n=w['normal'];ll=geo.from_ue(*p)
        result.append(dict(kind='night_window',source_id=w['source_id'],building_source_id=w['source_id'],source_window_mesh=w['source_mesh_id'],source_window_quad=w['source_quad_index'],source_window_centre_cm=p,source_window_normal=n,source_window_width_cm=w['width_cm'],source_window_height_cm=w['height_cm'],placement_provenance='inferred_warm_window_and_curtain_at_existing_inferred_source_window',occupancy_provenance='fictional_lighting_pattern_not_observed_occupancy',anchor_cm=p,yaw_degrees=math.degrees(math.atan2(-n[0],n[1])),wgs84_placement=list(ll[:2]),day_visibility='masked_out_by_shared_night_collection',models=['night_window_'+str(seed%3)]))
    return result
