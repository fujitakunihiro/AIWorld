import html
import json
import math
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, Point, mapping, shape
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

    def drape(self,g,height,spacing=20):
        from .terrain import cells
        for cell in cells(g,self.geo,spacing):
            for t in triangulate(cell):
                xy=list(orient(t,sign=1).exterior.coords)[:3]
                points=[self.vertex(p,height(p)) for p in xy]
                u=[points[1][i]-points[0][i] for i in range(3)];v=[points[2][i]-points[0][i] for i in range(3)]
                normal=[v[1]*u[2]-v[2]*u[1],v[2]*u[0]-v[0]*u[2],v[0]*u[1]-v[1]*u[0]]
                size=math.sqrt(sum(n*n for n in normal));normal=[n/max(size,1e-9) for n in normal]
                self.face(points,normal)

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
    from .terrain import Terrain
    from .bridges import decks
    terrain=Terrain(config,geo)
    layers=dataset['layers']
    river_features=[f for f in layers['water'] if f['properties']['water_role']=='river']
    water=polygonal(unary_union([shape(f['geometry']) for f in river_features]))
    building_geometries=[shape(f['geometry']) for f in layers['buildings']]
    building_union=unary_union(building_geometries)
    building_clearance=building_union.buffer(.35)
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
    # Close narrow gaps between a bridge roadway and parallel footways so all
    # lanes share one deck height. Width is still an OSM/estimated footprint.
    bridges=polygonal(unary_union(bridge_buffers).buffer(1.5,join_style='mitre').buffer(-1.5,join_style='mitre').difference(building_clearance))
    paths_surface=polygonal(unary_union(foot_buffers+square_shapes).difference(building_clearance))
    surface_union=unary_union([g for g in [roads,bridges,paths_surface] if g is not None])
    sidewalks=polygonal(unary_union(sidewalk_buffers).difference(surface_union).difference(building_clearance))
    if water:
        roads=polygonal(roads.difference(water)) if roads else None
        paths_surface=polygonal(paths_surface.difference(water)) if paths_surface else None
        sidewalks=polygonal(sidewalks.difference(water)) if sidewalks else None
    objects=[]
    water_ngf,water_samples=terrain.water_level(water,bridges)
    bridge_decks=decks(bridges,[f for f in usable if f['properties']['bridge']],terrain)
    def surface(identifier,kind,g,z,color,props):
        if g is None or g.is_empty:return
        mesh=Mesh(geo);mesh.drape(g,z if callable(z) else lambda p:z,10 if kind=='water' else 20)
        objects.append(mesh.item(identifier,kind,color,props))
    surface('terrain-ign','ground',geo.extent.difference(water) if water else geo.extent,terrain.local,'#beb39a',terrain.metadata())
    surface('seine','water',water,water_ngf-terrain.origin_ngf,'#357f86',{'source_ids':[f['properties']['source_id'] for f in river_features],
            'water_level_source':'estimated:median IGN river DEM samples excluding bridge footprints; not a hydrometric gauge',
            'water_level_ngf_m':water_ngf,'dem_samples_used':water_samples,'source_snapshot':terrain.snapshot})
    for f in layers['water']:
        if f['properties']['water_role']!='river':
            point=shape(f['geometry']).representative_point()
            basin_props={**f['properties'],'water_above_terrain_m':.12,
                'water_level_local_m':round(terrain.local((point.x,point.y))+.12,3),
                'water_level_ngf_m':round(terrain.ngf((point.x,point.y))+.12,3),
                'water_level_source':'estimated:terrain + 0.12m fountain surface'}
            surface(f['properties']['source_id'],'water',shape(f['geometry']),terrain.local((point.x,point.y))+.12,'#418fa0',basin_props)
    surface('roads','road',roads,lambda p:terrain.local(p)+.035,'#4c5056',{'source_ids':contributors['road'],
            'intersection_method':'union_of_OSM_width_buffers','building_conflicts':'clip_generated_surface; retain_source_geometry'})
    surface('sidewalks','sidewalk',sidewalks,lambda p:terrain.local(p)+.15,'#b9b5ae',{'source_ids':contributors['road'],'width_source':'estimated:1.5m','height_source':'estimated:0.15m'})
    surface('paths','path',paths_surface,lambda p:terrain.local(p)+.04,'#c2bbaa',{'source_ids':contributors['path']+[f['properties']['source_id'] for f in layers['squares']]})
    bridge_reports=[]
    for index,deck in enumerate(bridge_decks):
        props=deck.properties(water_ngf);bridge_reports.append(props)
        mesh=Mesh(geo);mesh.drape(deck.geometry,deck.height,5)
        for ring in lines(deck.geometry.segmentize(5)):
            for a,b in zip(ring,ring[1:]):
                dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
                if length<.001:continue
                za,zb=deck.height(a),deck.height(b)
                mesh.face([mesh.vertex(a,za-.7),mesh.vertex(b,zb-.7),mesh.vertex(b,zb),mesh.vertex(a,za)],(dy/length,dx/length,0))
        objects.append(mesh.item('bridge-deck/'+str(index),'bridge','#a9a294',props))
    quay=Mesh(geo);quay_count=0
    for ring in lines(water.segmentize(5)):
        for a,b in zip(ring,ring[1:]):
            mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2)
            if geo.extent.boundary.distance(mid)<.01 or (bridges and bridges.buffer(.2).covers(mid)):continue
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            if length<.001:continue
            bottom=water_ngf-terrain.origin_ngf-.5
            za,zb=max(bottom+.1,terrain.local(a)),max(bottom+.1,terrain.local(b))
            quay.face([quay.vertex(a,bottom),quay.vertex(b,bottom),quay.vertex(b,zb),quay.vertex(a,za)],(dy/length,dx/length,0));quay_count+=1
    objects.append(quay.item('seine-quays','quay','#b6aa91',{'source_ids':[f['properties']['source_id'] for f in river_features],
        'bank_geometry_source':'OSM river polygon boundary','height_source':'IGN terrain to estimated river water level',
        'construction_source':'procedural limestone wall; not surveyed quay masonry'}))
    for f in layers['parks']:
        g=shape(f['geometry']).difference(building_union).difference(surface_union)
        if water:g=g.difference(water)
        surface(f['properties']['source_id'],'park',polygonal(g),lambda p:terrain.local(p)+.025,'#798962',f['properties'])
    footprint_seen={}
    for f in layers['buildings']:
        props=f['properties'];g=shape(f['geometry']);key=g.normalize().wkb_hex
        if key in footprint_seen:
            continue
        footprint_seen[key]=props['source_id']
    from .building_mesh import generate_buildings
    objects.extend(generate_buildings(geo,layers['buildings'],Mesh,triangulate,terrain))
    from .facades import batch_bodies,generate_facades
    objects=batch_bodies(objects,geo,Mesh)
    facade_objects,facade_report=generate_facades(geo,layers['buildings'],terrain,Mesh)
    objects.extend(facade_objects)
    from .street_furniture import model_meshes,generate_street_objects
    instance_batches,street_features,street_report=generate_street_objects(geo,layers['street_objects'],terrain,water,building_union,layers['roads'],sidewalks,paths_surface,bridge_decks)
    scene={'format':'paris_twin_scene_v1','generation':dataset['generation'],'district_id':config['district_id'],'georeference':{
        'wgs84_origin':config['origin_wgs84'],'projected_origin_m':list(geo.origin),'projected_crs':geo.crs.to_string(),
        'units':'cm','axes':'X=east, Y=south, Z=up','cesium_transform_applied':False,
        'reference_id':config.get('georeference_id','paris_lambert93_shared_v1'),
        'vertical_mode':'orthometric NGF-IGN69 minus shared origin; no ellipsoidal conversion',
        'origin_elevation_ngf_m':terrain.origin_ngf,'vertical_datum':'NGF-IGN69'},
        'terrain':terrain.metadata(),'bridge_profiles':bridge_reports,'facades':facade_report,
        'instance_models':model_meshes(geo,Mesh),'instance_batches':instance_batches,'street_furniture':street_report,
        'extent_m':config['core_size_m']+config['context_buffer_m']*2,
        'scene_centre_ue_cm':list(geo.to_ue(*config.get('district_center_wgs84',config['origin_wgs84']),terrain.ngf(geo.centre),terrain.origin_ngf)),
        'quality_centre_ue_cm':list(geo.to_ue(*config['quality_center_wgs84'],terrain.ngf(geo.forward.transform(*config['quality_center_wgs84'])),terrain.origin_ngf)),
        'raw_checksums':dataset['raw_checksums'],'objects':objects,
        'attribution':'OpenStreetMap contributors / Ville de Paris (ODbL); IGN BD TOPO + RGE ALTI (Etalab 2.0)',
        'limitations':['Overall L1; body L2 only with near-complete official gutter coverage; roofs remain inferred',
                        'Sampled/interpolated terrain; water level and bridge cross sections estimated','No L3-L5 landmark facades',
                        'Road widths partly estimated; no walking gravity system yet']}
    review = analyse(dataset, geo)
    scene['diagnostics'] = {k:v for k,v in review.items() if k != 'issues'}
    scene['diagnostics']['issues'] = []
    for issue in review['issues']:
        item = {k:v for k,v in issue.items() if k != 'geometry'}
        item['polylines_cm'] = [[Mesh(geo).vertex(p, terrain.local(p)+.35) for p in line] for line in lines(shape(issue['geometry']))]
        scene['diagnostics']['issues'].append(item)
    scene['pick_features'] = []
    for layer, kind in [('buildings','building'),('roads','road'),('water','water'),('parks','park'),('squares','path')]:
        for feature in layers[layer]:
            if layer == 'roads' and (feature['properties']['tunnel'] or feature['properties']['layer'] < 0):
                continue
            picked=source_feature(feature,'bridge' if layer == 'roads' and feature['properties']['bridge'] else kind,geo)
            if layer=='water':
                props=picked['properties'];point=shape(feature['geometry']).representative_point()
                props['water_level_ngf_m']=water_ngf if props['water_role']=='river' else round(terrain.ngf((point.x,point.y))+.12,3)
                props['water_level_source']='estimated:river DEM median; no gauge' if props['water_role']=='river' else 'estimated:terrain + 0.12m fountain surface'
                props.pop('water_level_local_m',None)
            scene['pick_features'].append(picked)
    scene['pick_features'].extend(street_features)
    scene['landmarks'] = []
    for label, layer, name in [('Notre-Dame','buildings','Cathédrale Notre-Dame de Paris'),('Sainte-Chapelle','buildings','Sainte-Chapelle'),('Saint-Michel','squares','Place Saint-Michel')]:
        feature = next((f for f in layers[layer] if f['properties']['name']==name),None)
        if feature:
            g = shape(feature['geometry']); point = g.representative_point()
            scene['landmarks'].append({'name':label,'source_id':feature['properties']['source_id'],
                'ue_cm':Mesh(geo).vertex((point.x,point.y),terrain.local((point.x,point.y))),'radius_cm':max(8000,max(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])*150)})
    scene['coordinate_checks'] = []
    for e,n in [geo.origin,*[(x,y) for x in [geo.extent.bounds[0],geo.extent.bounds[2]] for y in [geo.extent.bounds[1],geo.extent.bounds[3]]]]:
        ll = geo.inverse.transform(e,n)
        height=terrain.ngf((e,n))
        scene['coordinate_checks'].append({'wgs84':list(ll),'height_ngf_m':height,'ue_cm':list(geo.to_ue(*ll,height,terrain.origin_ngf))})
    # A single optional footprint mesh, rather than hundreds of debug components.
    outline = unary_union([g.boundary.buffer(.35,cap_style='flat',join_style='mitre') for g in building_geometries])
    mesh = Mesh(geo); colours=[]
    for f,g in zip(layers['buildings'],building_geometries):
        start=len(mesh.positions);mesh.drape(g,lambda p:terrain.local(p)+.2)
        shade=sum(f['properties']['source_id'].encode('utf-8'))%4
        colours.extend([['#b89465','#c5a277','#ceae86','#d7b88f'][shade]]*(len(mesh.positions)-start))
    start=len(mesh.positions);mesh.drape(outline,lambda p:terrain.local(p)+.25);colours.extend(['#42627b']*(len(mesh.positions)-start))
    scene['footprint_mesh'] = mesh.item('building-footprints','footprint','#218db5',{'source_ids':[f['properties']['source_id'] for f in layers['buildings']]})
    scene['footprint_mesh']['vertex_colors']=colours
    dest=paths(config)['Generated']
    write(dest/'scene.json',scene)
    write(dest/'diagnostics.json',review)
    write(dest/'street-placement.json',{'report':street_report,'features':street_features})
    native=ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json'
    write(native,scene)
    road_result=[g for g in [roads,bridges,paths_surface,sidewalks] if g is not None]
    write(dest/'surface-validation.json',{'generated_road_building_overlap_m2':round(sum(g.intersection(building_union).area for g in road_result),8),
          'surface_area_m2':round(sum(g.area for g in road_result),3),'buildings':len(footprint_seen),
          'meshes':len(objects),'triangles':sum(len(o['indices'])//3 for o in objects),
          'terrain':terrain.metadata(),'river_water_ngf_m':water_ngf,'river_dem_samples':water_samples,
          'quay_segments':quay_count,'bridge_decks':bridge_reports,'facades':facade_report,'street_furniture':street_report,
          'instance_models':len(scene['instance_models']),'rendered_instances':sum(len(b['instances']) for b in instance_batches)})
    preview(config,dataset,road_result,water,review)
    from .prepare import PRODUCTS
    folders=paths(config)
    products={key:sha(folders[key.split('/')[0]]/key.split('/')[1]) for key in PRODUCTS}
    write(dest/'generation-cache.json',{'format':1,'district_id':config['district_id'],
          'generation':dataset['generation'],'raw_checksums':dataset['raw_checksums'],'products':products,
          'statistics':{'meshes':len(objects),'buildings':len(footprint_seen),'triangles':sum(len(o['indices'])//3 for o in objects)}})
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
    text=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>Paris Digital Twin — Phase 4 / 5</title>
<style>body{{margin:20px;font-family:system-ui;background:#faf8f3;color:#25323d}}main{{max-width:1400px;margin:auto}}section{{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}}svg{{width:100%;max-height:80vh}}.building:hover,.building.selected{{fill:#e96950;stroke-width:2}}.issue.selected{{stroke:#9b00ff;stroke-width:6}}button{{display:block;width:100%;text-align:left;padding:10px;margin-bottom:6px;cursor:pointer}}small{{display:block;overflow-wrap:anywhere}}aside{{max-height:78vh;overflow:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media(max-width:800px){{section{{display:block}}}}</style>
<main><h1>Île de la Cité — Phase 4 / 5 配置確認</h1><p>建物クリックで元ID、IGN軒高、対応率と屋根の推定を確認。本体L2と建物全体L1を区別します。UE表示では20m間隔のIGN標高を反映し、推定の窓・窓枠を追加しています。右の問題を選ぶと該当する建物と道路を強調します。赤線は建物sourceの重なり、橙線は最大道路ネットワークから分かれた成分です。孤立は不具合と断定せず、境界切断と内部の独立経路を区別しています。</p>
<section><div>{svg}<p id="coordinate">地図をクリックするとLambert-93とUE座標を表示。</p><pre id="selection">建物または品質項目を選択してください。</pre></div><aside><h2>品質レビュー ({len(review['issues'])})</h2>{issue_items}</aside></section><p>500m中核は破線、100m重点確認は赤枠。L1輪郭表示。OpenStreetMap contributors / Ville de Paris — ODbL. IGN — Etalab 2.0.</p></main>
<script id="data" type="application/json">{payload}</script><script>
const data=JSON.parse(document.querySelector('#data').textContent),svg=document.querySelector('svg'),out=document.querySelector('#selection');
function select(id,issue=false){{document.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));const item=issue?data.issues.find(x=>x.id===id):data.features[id];if(!item)return;out.textContent=JSON.stringify(item,null,2);for(const element of document.querySelectorAll('[data-id],[data-issue]')){{if((issue&&element.dataset.issue===id)||(item.source_ids||[id]).includes(element.dataset.id))element.classList.add('selected');}}}}
document.addEventListener('click',event=>{{const i=event.target.closest('[data-issue]'),f=event.target.closest('[data-id]');if(i)select(i.dataset.issue,true);else if(f)select(f.dataset.id);}});
svg.addEventListener('click',event=>{{let p=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse()),e=data.bounds[0]+p.x/1000*(data.bounds[2]-data.bounds[0]),n=data.bounds[3]-p.y/1000*(data.bounds[3]-data.bounds[1]);document.querySelector('#coordinate').textContent=`EPSG:2154 E=${{e.toFixed(3)}}m N=${{n.toFixed(3)}}m | UE X=${{((e-data.origin[0])*100).toFixed(1)}}cm Y=${{(-(n-data.origin[1])*100).toFixed(1)}}cm`;}});
</script></html>'''
    (dest/'map.html').write_text(text,encoding='utf-8')
