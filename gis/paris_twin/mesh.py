import html
import json
import math
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from .coordinates import Georeference
from .io import ROOT, paths, sha, write
from .normalize import polygonal


def polygons(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type=='Polygon':
        return [g]
    return [p for child in getattr(g,'geoms',[]) for p in polygons(child)]


def triangulate(g):
    return [t for p in polygons(g) for t in constrained_delaunay_triangles(p).geoms]


class Mesh:
    def __init__(self,geo):
        self.geo,self.positions,self.normals,self.indices = geo,[],[],[]

    def vertex(self,p,z):
        return [round((p[0]-self.geo.origin[0])*100,3),round(-(p[1]-self.geo.origin[1])*100,3),round(z*100,3)]

    def face(self,points,normal):
        start = len(self.positions)
        self.positions.extend(points);self.normals.extend([list(normal)]*len(points))
        self.indices.extend([start,start+1,start+2] if len(points)==3 else [start,start+1,start+2,start,start+2,start+3])

    def top(self,g,z):
        for t in triangulate(g):
            self.face([self.vertex(p,z) for p in list(orient(t,sign=1).exterior.coords)[:3]],(0,0,1))

    def walls(self,g,z,height):
        for p in polygons(g):
            p=orient(p,sign=1)
            for ring in [p.exterior,*p.interiors]:
                coords=list(ring.coords)
                for a,b in zip(coords,coords[1:]):
                    dx,dy=b[0]-a[0],b[1]-a[1]
                    length=math.hypot(dx,dy)
                    if length < .001:
                        continue
                    self.face([self.vertex(a,z),self.vertex(b,z),self.vertex(b,z+height),self.vertex(a,z+height)],(dy/length,dx/length,0))

    def item(self,identifier,kind,color,properties):
        return {'id':identifier,'kind':kind,'color':color,'positions_cm':self.positions,
                'normals':self.normals,'indices':self.indices,'properties':properties}


def export(config,dataset):
    geo=Georeference(config)
    layers=dataset['layers']
    river_features=[f for f in layers['water'] if f['properties']['water_role']=='river']
    water=polygonal(unary_union([shape(f['geometry']) for f in river_features]))
    building_geometries=[shape(f['geometry']) for f in layers['buildings']]
    building_union=unary_union(building_geometries)
    building_clearance=building_union.buffer(.15)
    road_buffers,foot_buffers,bridge_buffers,sidewalk_buffers=[],[],[],[]
    contributors={'road':[],'path':[],'bridge':[]}
    usable=[]
    for f in layers['roads']:
        props=f['properties']
        if props['tunnel'] or props['layer'] < 0:
            continue
        g=shape(f['geometry']).buffer(props['width_m']/2,cap_style='flat',join_style='round').intersection(geo.extent)
        g=polygonal(g.difference(building_clearance))
        if not g:
            continue
        usable.append(f)
        if props['bridge']:
            bridge_buffers.append(g)
            contributors['bridge'].append(props['source_id'])
        elif props['tags']['highway'] in ['footway','path','steps','cycleway','pedestrian']:
            foot_buffers.append(g)
            contributors['path'].append(props['source_id'])
        else:
            road_buffers.append(g)
            contributors['road'].append(props['source_id'])
            sidewalk_buffers.append(shape(f['geometry']).buffer(props['width_m']/2+1.5,cap_style='flat').intersection(geo.extent))
    square_shapes=[shape(f['geometry']) for f in layers['squares']]
    roads=polygonal(unary_union(road_buffers))
    bridges=polygonal(unary_union(bridge_buffers))
    paths_surface=polygonal(unary_union(foot_buffers+square_shapes).difference(building_clearance))
    surface_union=unary_union([g for g in [roads,bridges,paths_surface] if g is not None])
    sidewalks=polygonal(unary_union(sidewalk_buffers).difference(surface_union).difference(building_clearance))
    if water:
        roads=polygonal(roads.difference(water)) if roads else None
        paths_surface=polygonal(paths_surface.difference(water)) if paths_surface else None
        sidewalks=polygonal(sidewalks.difference(water)) if sidewalks else None
    objects=[]
    def surface(identifier,kind,g,z,color,props):
        if g is None or g.is_empty:return
        mesh=Mesh(geo);mesh.top(g,z)
        objects.append(mesh.item(identifier,kind,color,props))
    surface('terrain-preview','ground',geo.extent.difference(water) if water else geo.extent,0,'#beb39a',{'elevation_source':'preview:flat_datum; IGN samples acquired, terrain interpolation deferred'})
    surface('seine','water',water,-4,'#2e7a87',{'source_ids':[f['properties']['source_id'] for f in river_features],
            'water_level_source':'preview:visual_estimate_not_gauge','local_water_level_m':-4})
    for f in layers['water']:
        if f['properties']['water_role']!='river':
            surface(f['properties']['source_id'],'water',shape(f['geometry']),f['properties']['water_level_local_m'],'#418fa0',f['properties'])
    surface('roads','road',roads,.035,'#4c5056',{'source_ids':contributors['road'],
            'intersection_method':'union_of_OSM_width_buffers','building_conflicts':'clip_generated_surface; retain_source_geometry'})
    surface('sidewalks','sidewalk',sidewalks,.15,'#b9b5ae',{'source_ids':contributors['road'],'width_source':'estimated:1.5m','height_source':'estimated:0.15m'})
    surface('paths','path',paths_surface,.04,'#c2bbaa',{'source_ids':contributors['path']+[f['properties']['source_id'] for f in layers['squares']]})
    surface('bridges','bridge',bridges,.08,'#a9a294',{'source_ids':contributors['bridge'],
            'deck_elevation_source':'preview:estimated_flat_deck; no_arch_claim'})
    for f in layers['parks']:
        g=shape(f['geometry']).difference(building_union).difference(surface_union)
        if water:g=g.difference(water)
        surface(f['properties']['source_id'],'park',polygonal(g),.025,'#798962',f['properties'])
    footprint_seen={}
    for f in layers['buildings']:
        props=f['properties'];g=shape(f['geometry']);key=g.normalize().wkb_hex
        if key in footprint_seen:
            continue
        footprint_seen[key]=props['source_id']
        mesh=Mesh(geo);mesh.walls(g,.02,props['height_m']);mesh.top(g,props['height_m']+.02)
        objects.append(mesh.item(props['source_id'],'building','#d0c3a7',props))
    scene={'format':'paris_twin_scene_v1','generation':dataset['generation'],'district_id':config['district_id'],'georeference':{
        'wgs84_origin':config['origin_wgs84'],'projected_origin_m':list(geo.origin),'projected_crs':geo.crs.to_string(),
        'units':'cm','axes':'X=east, Y=south, Z=up','cesium_transform_applied':False,
        'vertical_mode':'relative preview; IGN NGF69 samples stored separately'},
        'extent_m':config['core_size_m']+config['context_buffer_m']*2,
        'quality_centre_ue_cm':list(geo.to_ue(*config['quality_center_wgs84'])),
        'raw_checksums':dataset['raw_checksums'],'objects':objects,
        'attribution':'OpenStreetMap contributors / Ville de Paris (ODbL); IGN RGE ALTI (Etalab 2.0)',
        'limitations':['L1 footprints; source-tag or estimated heights, not surveyed L2',
                        'flat preview terrain; elevations stored separately','No L3-L5 landmark facades',
                        'Road widths partly estimated; no walking gravity system yet']}
    dest=paths(config)['Generated']
    write(dest/'scene.json',scene)
    native=ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json'
    write(native,scene)
    road_result=[g for g in [roads,bridges,paths_surface,sidewalks] if g is not None]
    write(dest/'surface-validation.json',{'generated_road_building_overlap_m2':round(sum(g.intersection(building_union).area for g in road_result),8),
          'surface_area_m2':round(sum(g.area for g in road_result),3),'buildings':len(footprint_seen),
          'meshes':len(objects),'triangles':sum(len(o['indices'])//3 for o in objects)})
    preview(config,dataset,road_result,water)
    return {'native_file':str(native),'sha256':sha(native),'meshes':len(objects),'buildings':len(footprint_seen),
            'triangles':sum(len(o['indices'])//3 for o in objects)}


def preview(config,dataset,road_shapes,water):
    geo=Georeference(config);x0,y0,x1,y1=geo.extent.bounds;scale=1000/(x1-x0)
    def path(g):
        pieces=[]
        for p in polygons(g):
            for ring in [p.exterior,*p.interiors]:
                points=[f'{(x-x0)*scale:.2f},{(y1-y)*scale:.2f}' for x,y in ring.coords]
                pieces.append('M'+' L'.join(points)+' Z')
        return ' '.join(pieces)
    nodes=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" role="img" aria-label="Paris GIS map">','<rect width="1000" height="1000" fill="#ded7c8"/>']
    for g,color in [(water,'#72b7c0'),*[(g,'#83858c') for g in road_shapes]]:
        if g:nodes.append(f'<path d="{path(g)}" fill="{color}" fill-rule="evenodd"/>')
    for f in dataset['layers']['buildings']:
        props=f['properties'];title=html.escape(f"{props['name']} | {props['source_id']} | {props['height_m']}m ({props['height_source']}) | L1")
        nodes.append(f'<path class="building" d="{path(shape(f["geometry"]))}" fill="#c19b6b" stroke="#5d4634" stroke-width=".6" fill-rule="evenodd"><title>{title}</title></path>')
    labels=[('Notre-Dame','buildings','Cathédrale Notre-Dame de Paris'),('Sainte-Chapelle','buildings','Sainte-Chapelle'),('Saint-Michel','squares','Place Saint-Michel')]
    for label,layer,name in labels:
        feature=next((f for f in dataset['layers'][layer] if f['properties']['name']==name),None)
        if feature:
            point=shape(feature['geometry']).representative_point();x,y=point.x,point.y
            nodes.append(f'<text x="{(x-x0)*scale:.2f}" y="{(y1-y)*scale:.2f}" font-size="14" font-family="sans-serif" fill="#182e39"><title>{html.escape(feature["properties"]["source_id"])}</title>{label}</text>')
    qx,qy=geo.forward.transform(*config['quality_center_wgs84']);half=config['quality_size_m']/2
    nodes.append(f'<rect x="{(qx-half-x0)*scale}" y="{(y1-qy-half)*scale}" width="{half*2*scale}" height="{half*2*scale}" fill="none" stroke="#d63e56" stroke-width="2"/>')
    half=config['core_size_m']/2;ox,oy=geo.origin
    nodes.append(f'<rect x="{(ox-half-x0)*scale}" y="{(y1-oy-half)*scale}" width="{half*2*scale}" height="{half*2*scale}" fill="none" stroke="#314d67" stroke-dasharray="8 5" stroke-width="2"/>')
    nodes.append('</svg>');svg=''.join(nodes)
    dest=paths(config)['Generated'];(dest/'map.svg').write_text(svg,encoding='utf-8')
    text=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>Paris Digital Twin — GIS preview</title>
<style>body{{margin:24px;font-family:system-ui;background:#faf8f3;color:#25323d}}main{{max-width:1100px;margin:auto}}svg{{width:100%;max-height:85vh}}.building:hover{{fill:#e96950;stroke-width:2}}p{{line-height:1.7}}</style>
<main><h1>Île de la Cité — 実データ配置</h1><p>中央500m地区（破線）＋周辺150mの文脈範囲。赤枠は重点検証100m。建物にカーソルを置くと元ID・高さの根拠を表示します。道路面は建物輪郭で切り抜き済みです。これはL1配置検証で、写真品質の外観ではありません。</p>{svg}<p>{html.escape('OpenStreetMap contributors / Ville de Paris — ODbL. IGN RGE ALTI — Etalab Open Licence 2.0.')}</p></main></html>'''
    (dest/'map.html').write_text(text,encoding='utf-8')
