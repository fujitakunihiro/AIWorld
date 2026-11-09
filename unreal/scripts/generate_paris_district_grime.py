"""Source-bound cosmetic dirt, grouped into 200m tiles for distance culling."""
import hashlib,math
import numpy as np
from shapely import prepare
from shapely.geometry import shape,Point,Polygon
from shapely.ops import transform,unary_union
from generate_paris_frontages import Mesh
from paris_district_layout import district_windows
from generate_paris_luxury import Surfaces


def extend(scene,district,geo,terrain,core):
    meshes={};records=[];ox,oy=district['origin_projected_m']
    local=lambda g:transform(lambda x,y,z=None:((np.asarray(x)-ox)*100,-(np.asarray(y)-oy)*100),g)
    buildings={f['properties']['source_id']:f['properties'] for f in district['layers']['buildings']}
    footprint=local(unary_union([shape(f['geometry']) for f in district['layers']['buildings']]))
    water=local(unary_union([shape(f['geometry']) for f in district['layers']['water']]))
    prepare(footprint);prepare(water)
    existing={(w['source_mesh_id'],w['source_quad_index']) for w in core};windows,_=district_windows(scene['source_scene_sha256']);lowest={}
    def emit(role,points,normal,digest,record):
        centre=np.mean(points,axis=0).tolist();tile=tuple(math.floor(v/20000) for v in centre[:2]);key=(role,*tile)
        mesh=meshes.setdefault(key,Mesh());index=len(mesh.positions_cm)
        mesh.face(points,normal,[digest[3],180,150,255],[(0,0),(1,0),(1,1),(0,1)])
        records.append(dict(**record,anchor_cm=centre,tile=list(tile),mesh_id=role+'_'+str(tile[0])+'_'+str(tile[1]),vertex_start=index,placement_provenance='inferred_localized_grime_not_observed_staining'))
    for w in windows:
        if (w['source_mesh_id'],w['source_quad_index']) in existing:continue
        p=w['centre_cm'];n=w['normal'];t=[n[1],-n[0],0];sid=w['source_id'];key=(sid,round(p[0],1),round(p[1],1))
        if key not in lowest or p[2]<lowest[key]['centre_cm'][2]:lowest[key]=w
        digest=hashlib.sha256((sid+':grime:'+w['source_mesh_id']+':'+str(w['source_quad_index'])).encode()).digest()
        if digest[0]%3==0:continue
        width=w['width_cm']*(.65+.3*digest[1]/255);height=45+65*digest[2]/255;top=p[2]-w['height_cm']/2-25
        def point(x,z):return [p[i]+t[i]*x-n[i]*8.35+(z-p[2] if i==2 else 0) for i in range(3)]
        emit('district_streak',[point(-width/2,top),point(width/2,top),point(width/2,top-height),point(-width/2,top-height)],n,digest,dict(kind='district_window_streak',source_id=sid,source_mesh_id=w['source_mesh_id'],source_quad_index=w['source_quad_index'],top_cm=top,length_cm=height))
    for w in lowest.values():
        p=w['centre_cm'];n=w['normal'];t=[n[1],-n[0],0];sid=w['source_id'];props=buildings.get(sid)
        if not props:continue
        projected=Point(ox+(p[0]-n[0]*9)/100,oy-(p[1]-n[1]*9)/100)
        parts=[(shape(part['geometry']).distance(projected),part) for part in props['height_parts']]
        if not parts:continue
        part=min(parts,key=lambda x:x[0])[1];ground=max(part.get('ground_ngf_m',terrain.ngf((projected.x,projected.y)))-terrain.origin_ngf,terrain.local((projected.x,projected.y)))*100
        if not 50<p[2]-w['height_cm']/2-ground<700:continue
        digest=hashlib.sha256((sid+':ground:'+str(tuple(round(v,1) for v in p[:2]))).encode()).digest();width=w['width_cm']*1.35;height=35+digest[0]%24
        def point(x,z):return [p[i]+t[i]*x-n[i]*8.35+(z-p[2] if i==2 else 0) for i in range(3)]
        emit('district_base',[point(-width/2,ground+height),point(width/2,ground+height),point(width/2,ground+3),point(-width/2,ground+3)],n,digest,dict(kind='district_wall_base',source_id=sid,ground_cm=ground))
    surfaces=Surfaces(scene)
    for f in district['layers']['roads']:
        props=f['properties'];sid=props['source_id']
        if props['bridge'] or props['tunnel'] or props['layer']!=0:continue
        g=local(shape(f['geometry']));parts=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
        for part_index,poly in enumerate(parts):
            if poly.geom_type!='Polygon':continue
            edge=poly.exterior
            for sample,d in enumerate(np.arange(250,edge.length-150,480)):
                a=np.array(edge.interpolate(max(0,d-35)).coords[0]);b=np.array(edge.interpolate(min(edge.length,d+35)).coords[0]);t=b-a
                if np.linalg.norm(t)<1:continue
                t=t/np.linalg.norm(t);n=np.array([-t[1],t[0]]);p=np.array(edge.interpolate(d).coords[0]);digest=hashlib.sha256((sid+':edge:'+str(part_index)+':'+str(sample)).encode()).digest()
                if digest[0]%5==0:continue
                length=130+digest[1]*.5;width=35+digest[2]*.13
                for sign in [1,-1]:
                    c=p+n*sign*65;xy=[c-t*length/2-n*width/2,c+t*length/2-n*width/2,c+t*length/2+n*width/2,c-t*length/2+n*width/2];patch=Polygon(xy)
                    if not poly.covers(patch) or footprint.intersects(patch) or water.intersects(patch):continue
                    indices=surfaces.tree.query(patch);covered=[];excluded=False
                    for i in indices:
                        k=surfaces.kinds[i];part=surfaces.polys[i]
                        if k in ('water','bridge') and patch.intersection(part).area>1:excluded=True;break
                        if k in ('road','path','sidewalk'):covered.append(part)
                    if excluded or not covered or unary_union(covered).intersection(patch).area/patch.area<.999:continue
                    points=[]
                    for x,y in xy:
                        _,hs=surfaces.query(float(x),float(y),.5);values=[h for k,h in hs if k in ('road','path','sidewalk')]
                        if not values:break
                        points.append([float(x),float(y),max(values)+.35])
                    if len(points)!=4 or np.ptp(np.array(points)[:,2])>12:continue
                    emit('road_grime',points,[0,0,1],digest,dict(kind='road_edge_grime',source_id=sid,road_part=part_index,sample_index=sample,surface_offset_cm=.35,width_source=props['width_source']))
                    break
    objects=[]
    for (role,x,y),mesh in sorted(meshes.items()):
        name=role+'_'+str(x)+'_'+str(y);material='M_ParisWeathering'+('Streak' if role=='district_streak' else 'Base' if role=='district_base' else 'RoadGrime')
        item=mesh.item(name,material);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Weathering/SM_ParisWeathering_');objects.append(item)
    return records,objects
