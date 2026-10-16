"""Fixed photographic comparisons anchored to the unchanged cathedral footprint."""
import hashlib
import json
import math
from shapely.geometry import Point,LineString,shape
from shapely.ops import unary_union


def cameras(geo,buildings,water,terrain,businesses,street_features=(),roads=()):
    church=next((f for f in buildings if f['properties'].get('name')=='Cathédrale Notre-Dame de Paris'),None)
    if not church:return []
    g=shape(church['geometry']);rect=list(g.minimum_rotated_rectangle.exterior.coords)
    a,b=max(zip(rect,rect[1:]),key=lambda edge:math.dist(*edge));length=math.dist(a,b)
    dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
    if dx<0:dx,dy=-dx,-dy
    c=g.centroid;low=min((x-c.x)*dx+(y-c.y)*dy for x,y in g.exterior.coords)
    front=(c.x+dx*low,c.y+dy*low);occupied=unary_union([shape(f['geometry']) for f in buildings])
    tree_clearance=[]
    for f in street_features:
        if f['kind'] not in ('street_tree','street_lamp'):continue
        q=f['point_cm'];props=f['properties']
        radius=8 if f['kind']=='street_lamp' else props.get('crown_diameter_m',6)*.7+1
        tree_clearance.append((Point(geo.origin[0]+q[0]/100,geo.origin[1]-q[1]/100),radius))
    blocked=occupied.buffer(.4);wet=water.buffer(.5);extent=geo.extent.buffer(-1)
    def free(point):
        p=Point(point)
        return not blocked.covers(p) and not wet.covers(p) and extent.covers(p) and all(p.distance(tree)>radius for tree,radius in tree_clearance)
    other_buildings=unary_union([shape(f['geometry']) for f in buildings if f is not church]).buffer(.3)
    def choose(options,aim=None):
        return next((p for p in options if free(p) and (aim is None or not other_buildings.intersects(LineString([p,aim])))),None)
    result=[]
    def add(name,point,target,z=26,lens=28,position_source=None):
        if point is None:return
        ground=terrain.local(point);target_ground=terrain.local(target)
        def ue(p,height):return [round((p[0]-geo.origin[0])*100,3),round(-(p[1]-geo.origin[1])*100,3),round(height*100,3)]
        result.append(dict(name=name,position_cm=ue(point,ground+1.7),target_cm=ue(target,target_ground+z),
            ground_ngf_m=terrain.ngf(point),eye_height_cm=170,focal_length_mm=lens,aperture=8,iso=100,shutter_reciprocal=125,
            source_id=church['properties']['source_id'],position_wgs84=list(geo.inverse.transform(*point)),
            position_source_id=position_source,
            pose_source='inferred photographic viewpoint; source footprint and terrain retained; UE collision trace resolves eye height'))
    p=choose([(front[0]-dx*d-dy*side,front[1]-dy*d+dx*side) for d in [130,120,110,140,150] for side in [0,-8,8,-16,16,-24,24,-40,40]],front)
    add('Camera_NotreDame_Front',p,front,33)
    south=(dy,-dx)
    p=choose([(c.x-dx*along+south[0]*away,c.y-dy*along+south[1]*away) for away in [180,165,150,135,120] for along in [20,0,40,-20,60,-40]],(c.x,c.y))
    bridge=next((f for f in roads if f['properties'].get('name')=='Pont au Double' and f['properties'].get('bridge') and shape(f['geometry']).geom_type=='LineString'),None)
    if bridge:
        line=shape(bridge['geometry'])
        candidate=next((line.interpolate(t,normalized=True) for t in [.5,.35,.65] if not blocked.covers(line.interpolate(t,normalized=True))),None)
        if candidate is not None:p=(candidate.x,candidate.y)
    add('Camera_NotreDame_Riverside',p,(c.x,c.y),30,position_source=bridge['properties']['source_id'] if bridge else None)
    for item in sorted(businesses,key=lambda f:math.dist(f['point_cm'][:2],[(front[0]-geo.origin[0])*100,-(front[1]-geo.origin[1])*100])):
        q=item['point_cm'];yaw=math.radians(item['properties']['facade_yaw_degrees'])
        along=(math.cos(yaw),-math.sin(yaw));out=(-math.sin(yaw),-math.cos(yaw))
        shop=(geo.origin[0]+q[0]/100,geo.origin[1]-q[1]/100)
        if math.dist(shop,front)>100:continue
        p=choose([(shop[0]+out[0]*distance,shop[1]+out[1]*distance) for distance in [8,6,4]])
        if p:
            add('Camera_Paris_Street',p,(p[0]+along[0]*15,p[1]+along[1]*15),2.1,lens=35);break
    return result


def baked_visuals(objects,geo):
    qx,qy=geo.forward.transform(*geo.config['quality_center_wgs84']);q=[(qx-geo.origin[0])*100,-(qy-geo.origin[1])*100]
    result={}
    for obj in objects:
        if obj['kind'] not in ('building','roof'):continue
        points=obj['positions_cm']
        if not points or max(p[0] for p in points)<q[0]-8000 or min(p[0] for p in points)>q[0]+8000 or max(p[1] for p in points)<q[1]-8000 or min(p[1] for p in points)>q[1]+8000:continue
        digest=hashlib.sha256(json.dumps({k:obj.get(k) for k in ['positions_cm','normals','indices','vertex_colors','color']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        name='SM_Paris_'+obj['kind'].title()+'_'+digest[:16]
        result[obj['id']]=dict(asset='/Game/ParisPhotoreal/Generated/'+name,geometry_sha256=digest,
            triangles=len(obj['indices'])//3,source_ids=obj['properties'].get('source_ids',[]))
    return result
