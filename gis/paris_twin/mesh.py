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
from .diagnostics import analyse


def polygons(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type=='Polygon':
        return [g]
    return [p for child in getattr(g,'geoms',[]) for p in polygons(child)]


def triangulate(g):
    return [t for p in polygons(g) for t in constrained_delaunay_triangles(p).geoms]


def lines(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [list(r.coords) for r in [g.exterior, *g.interiors]]
    if g.geom_type in ['LineString', 'LinearRing']:
        return [list(g.coords)]
    return [line for child in getattr(g, 'geoms', []) for line in lines(child)]


def source_feature(feature, kind, geo):
    g = shape(feature['geometry']); p = feature['properties']
    props = {k:v for k,v in p.items() if k not in ['source_geometry_projected', 'osm_node_ids', 'tags', 'height_parts']}
    mesh = Mesh(geo)
    result = {'id': p['source_id'], 'kind': kind, 'properties': props}
    if kind in ['road', 'bridge']:
        result['polylines_cm'] = [[mesh.vertex(xy, 0) for xy in line] for line in lines(g)]
    else:
        result['polygons_cm'] = [[[mesh.vertex(xy, 0) for xy in ring] for ring in lines(polygon)] for polygon in polygons(g)]
    return result


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
    from .building_mesh import generate_buildings
    objects.extend(generate_buildings(geo,layers['buildings'],Mesh,triangulate))
    scene={'format':'paris_twin_scene_v1','generation':dataset['generation'],'district_id':config['district_id'],'georeference':{
        'wgs84_origin':config['origin_wgs84'],'projected_origin_m':list(geo.origin),'projected_crs':geo.crs.to_string(),
        'units':'cm','axes':'X=east, Y=south, Z=up','cesium_transform_applied':False,
        'reference_id':config.get('georeference_id','paris_lambert93_shared_v1'),
        'vertical_mode':'relative preview; IGN NGF69 samples stored separately'},
        'extent_m':config['core_size_m']+config['context_buffer_m']*2,
        'scene_centre_ue_cm':list(geo.to_ue(*config.get('district_center_wgs84',config['origin_wgs84']))),
        'quality_centre_ue_cm':list(geo.to_ue(*config['quality_center_wgs84'])),
        'raw_checksums':dataset['raw_checksums'],'objects':objects,
        'attribution':'OpenStreetMap contributors / Ville de Paris (ODbL); IGN BD TOPO + RGE ALTI (Etalab 2.0)',
        'limitations':['Overall L1; body L2 only with near-complete official gutter coverage; roofs remain inferred',
                        'flat preview terrain; elevations stored separately','No L3-L5 landmark facades',
                        'Road widths partly estimated; no walking gravity system yet']}
    review = analyse(dataset, geo)
    scene['diagnostics'] = {k:v for k,v in review.items() if k != 'issues'}
    scene['diagnostics']['issues'] = []
    for issue in review['issues']:
        item = {k:v for k,v in issue.items() if k != 'geometry'}
        item['polylines_cm'] = [[Mesh(geo).vertex(p, .35) for p in line] for line in lines(shape(issue['geometry']))]
        scene['diagnostics']['issues'].append(item)
    scene['pick_features'] = []
    for layer, kind in [('buildings','building'),('roads','road'),('water','water'),('parks','park'),('squares','path')]:
        for feature in layers[layer]:
            if layer == 'roads' and (feature['properties']['tunnel'] or feature['properties']['layer'] < 0):
                continue
            scene['pick_features'].append(source_feature(feature,'bridge' if layer == 'roads' and feature['properties']['bridge'] else kind,geo))
    scene['landmarks'] = []
    for label, layer, name in [('Notre-Dame','buildings','Cathédrale Notre-Dame de Paris'),('Sainte-Chapelle','buildings','Sainte-Chapelle'),('Saint-Michel','squares','Place Saint-Michel')]:
        feature = next((f for f in layers[layer] if f['properties']['name']==name),None)
        if feature:
            g = shape(feature['geometry']); point = g.representative_point()
            scene['landmarks'].append({'name':label,'source_id':feature['properties']['source_id'],
                'ue_cm':Mesh(geo).vertex((point.x,point.y),0),'radius_cm':max(8000,max(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])*150)})
    scene['coordinate_checks'] = []
    for e,n in [geo.origin,*[(x,y) for x in [geo.extent.bounds[0],geo.extent.bounds[2]] for y in [geo.extent.bounds[1],geo.extent.bounds[3]]]]:
        ll = geo.inverse.transform(e,n)
        scene['coordinate_checks'].append({'wgs84':list(ll),'ue_cm':list(geo.to_ue(*ll))})
    # A single optional footprint mesh, rather than hundreds of debug components.
    outline = unary_union([g.boundary.buffer(.35,cap_style='flat',join_style='mitre') for g in building_geometries])
    mesh = Mesh(geo); colours=[]
    for f,g in zip(layers['buildings'],building_geometries):
        start=len(mesh.positions);mesh.top(g,.2)
        shade=sum(f['properties']['source_id'].encode('utf-8'))%4
        colours.extend([['#b89465','#c5a277','#ceae86','#d7b88f'][shade]]*(len(mesh.positions)-start))
    start=len(mesh.positions);mesh.top(outline,.25);colours.extend(['#42627b']*(len(mesh.positions)-start))
    scene['footprint_mesh'] = mesh.item('building-footprints','footprint','#218db5',{'source_ids':[f['properties']['source_id'] for f in layers['buildings']]})
    scene['footprint_mesh']['vertex_colors']=colours
    dest=paths(config)['Generated']
    write(dest/'scene.json',scene)
    write(dest/'diagnostics.json',review)
    native=ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json'
    write(native,scene)
    road_result=[g for g in [roads,bridges,paths_surface,sidewalks] if g is not None]
    write(dest/'surface-validation.json',{'generated_road_building_overlap_m2':round(sum(g.intersection(building_union).area for g in road_result),8),
          'surface_area_m2':round(sum(g.area for g in road_result),3),'buildings':len(footprint_seen),
          'meshes':len(objects),'triangles':sum(len(o['indices'])//3 for o in objects)})
    preview(config,dataset,road_result,water,review)
    return {'native_file':str(native),'sha256':sha(native),'meshes':len(objects),'buildings':len(footprint_seen),
            'triangles':sum(len(o['indices'])//3 for o in objects)}


def preview(config,dataset,road_shapes,water,review):
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
        props=f['properties'];title=html.escape(f"{props['name']} | {props['source_id']} | gutter {props['height_gutter_min_m']}-{props['height_gutter_max_m']}m | inferred roof envelope {props['height_m']}m | body {props['reproduction_level_body']} / overall L1")
        nodes.append(f'<path class="building feature" data-id="{html.escape(props["source_id"])}" d="{path(shape(f["geometry"]))}" fill="#c19b6b" stroke="#5d4634" stroke-width=".6" fill-rule="evenodd"><title>{title}</title></path>')
    labels=[('Notre-Dame','buildings','Cathédrale Notre-Dame de Paris'),('Sainte-Chapelle','buildings','Sainte-Chapelle'),('Saint-Michel','squares','Place Saint-Michel')]
    for label,layer,name in labels:
        feature=next((f for f in dataset['layers'][layer] if f['properties']['name']==name),None)
        if feature:
            point=shape(feature['geometry']).representative_point();x,y=point.x,point.y
            nodes.append(f'<text x="{(x-x0)*scale:.2f}" y="{(y1-y)*scale:.2f}" font-size="14" font-family="sans-serif" fill="#182e39"><title>{html.escape(feature["properties"]["source_id"])}</title>{label}</text>')
    qx,qy=geo.forward.transform(*config['quality_center_wgs84']);half=config['quality_size_m']/2
    nodes.append(f'<rect x="{(qx-half-x0)*scale}" y="{(y1-qy-half)*scale}" width="{half*2*scale}" height="{half*2*scale}" fill="none" stroke="#d63e56" stroke-width="2"/>')
    half=config['core_size_m']/2;ox,oy=geo.centre
    nodes.append(f'<rect x="{(ox-half-x0)*scale}" y="{(y1-oy-half)*scale}" width="{half*2*scale}" height="{half*2*scale}" fill="none" stroke="#314d67" stroke-dasharray="8 5" stroke-width="2"/>')
    for issue in review['issues']:
        g=shape(issue['geometry']);colour='#e04d59' if issue['kind']=='building_overlap' else '#d98920'
        d=path(g) if polygons(g) else ' '.join('M'+' L'.join(f'{(x-x0)*scale:.2f},{(y1-y)*scale:.2f}' for x,y in line) for line in lines(g))
        nodes.append(f'<path class="issue" data-issue="{html.escape(issue["id"])}" d="{d}" fill="none" stroke="{colour}" stroke-width="3"><title>{html.escape(issue["id"]+" | "+issue["classification"])}</title></path>')
    nodes.append('</svg>');svg=''.join(nodes)
    dest=paths(config)['Generated'];(dest/'map.svg').write_text(svg,encoding='utf-8')
    details={f['properties']['source_id']:{k:v for k,v in f['properties'].items() if k in ['source_id','name','height_m','height_source','source_url','wgs84_centre','reproduction_level','reproduction_level_body','official_height_coverage','height_gutter_min_m','height_gutter_max_m','height_reference_ids','height_precision_max_m','height_data_dates','roof_form_source']} for f in dataset['layers']['buildings']}
    issue_items=''.join(f'<button data-issue="{html.escape(i["id"])}">{html.escape(i["kind"]+" · "+i["classification"])}<small>{html.escape(", ".join(i["source_ids"]))}</small></button>' for i in review['issues'])
    # Embedded JSON is escaped for an HTML script context, including untrusted OSM names.
    payload=json.dumps({'features':details,'issues':review['issues'],'bounds':[x0,y0,x1,y1],'origin':geo.origin},ensure_ascii=False).replace('<','\\u003c')
    text=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>Paris Digital Twin — Phase 3</title>
<style>body{{margin:20px;font-family:system-ui;background:#faf8f3;color:#25323d}}main{{max-width:1400px;margin:auto}}section{{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}}svg{{width:100%;max-height:80vh}}.building:hover,.building.selected{{fill:#e96950;stroke-width:2}}.issue.selected{{stroke:#9b00ff;stroke-width:6}}button{{display:block;width:100%;text-align:left;padding:10px;margin-bottom:6px;cursor:pointer}}small{{display:block;overflow-wrap:anywhere}}aside{{max-height:78vh;overflow:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media(max-width:800px){{section{{display:block}}}}</style>
<main><h1>Île de la Cité — Phase 3 高さ・配置確認</h1><p>建物クリックで元ID、IGN軒高、対応率と屋根の推定を確認。本体L2と建物全体L1を区別します。右の問題を選ぶと該当する建物と道路を強調します。赤線は建物sourceの重なり、橙線は最大道路ネットワークから分かれた成分です。孤立は不具合と断定せず、境界切断と内部の独立経路を区別しています。</p>
<section><div>{svg}<p id="coordinate">地図をクリックするとLambert-93とUE座標を表示。</p><pre id="selection">建物または品質項目を選択してください。</pre></div><aside><h2>品質レビュー ({len(review['issues'])})</h2>{issue_items}</aside></section><p>500m中核は破線、100m重点確認は赤枠。L1輪郭表示。OpenStreetMap contributors / Ville de Paris — ODbL. IGN — Etalab 2.0.</p></main>
<script id="data" type="application/json">{payload}</script><script>
const data=JSON.parse(document.querySelector('#data').textContent),svg=document.querySelector('svg'),out=document.querySelector('#selection');
function select(id,issue=false){{document.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));const item=issue?data.issues.find(x=>x.id===id):data.features[id];if(!item)return;out.textContent=JSON.stringify(item,null,2);for(const element of document.querySelectorAll('[data-id],[data-issue]')){{if((issue&&element.dataset.issue===id)||(item.source_ids||[id]).includes(element.dataset.id))element.classList.add('selected');}}}}
document.addEventListener('click',event=>{{const i=event.target.closest('[data-issue]'),f=event.target.closest('[data-id]');if(i)select(i.dataset.issue,true);else if(f)select(f.dataset.id);}});
svg.addEventListener('click',event=>{{let p=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse()),e=data.bounds[0]+p.x/1000*(data.bounds[2]-data.bounds[0]),n=data.bounds[3]-p.y/1000*(data.bounds[3]-data.bounds[1]);document.querySelector('#coordinate').textContent=`EPSG:2154 E=${{e.toFixed(3)}}m N=${{n.toFixed(3)}}m | UE X=${{((e-data.origin[0])*100).toFixed(1)}}cm Y=${{(-(n-data.origin[1])*100).toFixed(1)}}cm`;}});
</script></html>'''
    (dest/'map.html').write_text(text,encoding='utf-8')
