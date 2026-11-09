"""Spatial selection and source window extraction for the full loaded district."""
import json,math
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import numpy as np
from shapely.geometry import Point,LineString,shape
from shapely.strtree import STRtree

ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'unreal/AIWorld/Content/Data'
DTYPE=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])


def cell(point,size=10000):
    return tuple(math.floor(float(v)/size) for v in point[:2])


def spread(items,point,key=lambda v:str(v)):
    buckets=defaultdict(list)
    for item in items:buckets[cell(point(item))].append(item)
    for values in buckets.values():values.sort(key=key)
    ordered=[];depth=0
    while True:
        layer=[buckets[c][depth] for c in sorted(buckets) if len(buckets[c])>depth]
        if not layer:break
        ordered.extend(layer);depth+=1
    return ordered


@lru_cache(maxsize=2)
def district_windows(source_hash):
    scene=json.loads((DATA/'paris-digital-twin-runtime.json').read_text(encoding='utf-8'))
    if scene['source_scene_sha256']!=source_hash:raise RuntimeError('Source scene changed during window extraction')
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    allowed=[];geometries=[];source_ids=[]
    excluded={'osm/way/201611261','osm/relation/2449758'}
    for f in district['layers']['buildings']:
        p=f['properties'];tags=p.get('tags',{});sid=p['source_id']
        if sid in excluded or tags.get('building') in ('church','cathedral','chapel','tower','public') or tags.get('historic') in ('castle','monument'):continue
        allowed.append(sid);geometries.append(shape(f['geometry']));source_ids.append(sid)
    tree=STRtree(geometries);ox,oy=district['origin_projected_m'];blob=np.memmap(DATA/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');windows=[];seen=set()
    for o in scene['objects']:
        if o['kind']!='facade_glass':continue
        permitted=set(o['properties']['source_ids']);b=o['mesh_buffer'];verts=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count'])
        for k in range(0,len(ix),6):
            ids=np.unique(ix[k:k+6])
            if len(ids)!=4:continue
            pts=verts['p'][ids].astype('f8');n=verts['n'][ids[0]].astype('f8');length=math.hypot(n[0],n[1])
            if length<.99 or abs(n[2])>.001:continue
            n=np.array([n[0]/length,n[1]/length,0]);t=np.array([n[1],-n[0],0]);p=pts.mean(axis=0);width=float(np.ptp((pts-p)@t));height=float(np.ptp(pts[:,2]))
            if not 85<width<95 or not 160<height<170:continue
            unique=tuple(round(v,2) for v in list(p)+list(n))
            if unique in seen:continue
            point=Point(ox+(p[0]-n[0]*9)/100,oy-(p[1]-n[1]*9)/100)
            candidates=[(geometries[i].boundary.distance(point),source_ids[i]) for i in tree.query(point.buffer(.05)) if source_ids[i] in permitted]
            if not candidates:continue
            distance,sid=min(candidates)
            if distance>.04:continue
            seen.add(unique);windows.append(dict(source_id=sid,source_mesh_id=o['id'],source_quad_index=k//6,centre_cm=p.tolist(),normal=n.tolist(),width_cm=width,height_cm=height))
    # Keep the authoritative detailed core records byte-for-byte where present.
    core=json.loads((DATA/'paris-photo-frontages-source.json').read_text(encoding='utf-8'))
    combined={(w['source_mesh_id'],w['source_quad_index']):w for w in windows}
    for w in core['windows']:combined[(w['source_mesh_id'],w['source_quad_index'])]=w
    return tuple(combined.values()),frozenset(allowed)


def coverage_report(scene,records):
    eligible={cell(f['point_cm']) for f in scene['pick_features'] if f['kind'] in ('business','street_lamp')}
    counts=defaultdict(lambda:defaultdict(int))
    for r in records:counts[cell(r['anchor_cm'])][r['kind']]+=1
    decorated=set(counts);points=[r['anchor_cm'] for r in records]
    return dict(extent_m=scene['extent_m'],cell_size_m=100,eligible_cells=len(eligible),decorated_eligible_cells=len(eligible&decorated),decorated_cells=len(decorated),bounds_cm=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)],cells=[dict(x=c[0],y=c[1],counts=dict(counts[c])) for c in sorted(counts)])


def inspection_views(scene,shops,surfaces,buildings,water,occupied,trees,upper,records):
    counts=defaultdict(int)
    for r in upper:
        if r['kind']=='window':counts[r['source_id']]+=1
    views=[dict(name='District overview',eye_cm=[0,65000,60000],target_cm=[0,0,500])]
    flower_shops={r['source_id'] for r in records if r['kind']=='canopy' and r['hanging_baskets']}
    for sx,sy,name in [(-1,-1,'North west'),(1,-1,'North east'),(-1,1,'South west'),(1,1,'South east')]:
        candidates=[f for f in shops if f['point_cm'][0]*sx>5000 and f['point_cm'][1]*sy>5000]
        candidates.sort(key=lambda f:(f['id'] not in flower_shops,-counts[f['properties']['building_source_id']],math.dist(f['point_cm'][:2],[sx*23000,sy*23000]),f['id']))
        found=None
        for f in candidates:
            p=f['point_cm'];a=math.radians(f['properties']['facade_yaw_degrees']);t=[math.cos(a),math.sin(a)];n=[-t[1],t[0]]
            for distance,side in [(1400,0),(1200,400),(1200,-400),(1000,0),(800,400),(800,-400),(650,0)]:
                x=p[0]+n[0]*distance+t[0]*side;y=p[1]+n[1]*distance+t[1]*side;point=Point(x,y);target=[p[0]+n[0]*80,p[1]+n[1]*80,p[2]+350];ray=LineString([(x,y),target[:2]])
                if point.distance(buildings)<50 or point.distance(water)<50 or point.distance(occupied)<40 or ray.intersects(buildings):continue
                if point.distance(trees)<220 or ray.distance(trees)<130:continue
                cover,hs=surfaces.query(x,y,35)
                if max(cover.get('path',0),cover.get('sidewalk',0))<.9 or cover.get('road',0)>.01:continue
                z=max([h for k,h in hs if k in ('path','sidewalk','ground')] or [p[2]])+170
                found=dict(name=name,source_id=f['id'],eye_cm=[x,y,z],target_cm=target);break
            if found:break
        if found:views.append(found)
    river=next((c for c in scene['photo_cameras'] if c['name']=='Camera_NotreDame_Riverside'),None)
    if river:views.append(dict(name='Riverside',eye_cm=river['position_cm'],target_cm=river['target_cm']))
    return views
