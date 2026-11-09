"""Remove covered terrain only from rendering, preserving the archived GIS.

Independent terrain/road triangulations interpolate the same DEM differently.
The original terrain sometimes protrudes a few cm through mapped roads. Cut
its display below existing surface coverage and reconcile small path-edge
height differences near Notre-Dame. Source GIS and physics are not modified.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/AIWorld/Content/Data'
KINDS={'road','sidewalk','path','park','water','bridge'}
DTYPE=np.dtype([('p','<f4',(3,)),('n','<f4',(3,)),('c','u1',(4,))])


def input_meshes(include_other_coverage=False):
    scene=json.loads((FOLDER/'paris-digital-twin-runtime.json').read_text(encoding='utf-8-sig'))
    blob=np.memmap(FOLDER/'paris-digital-twin-meshes.bin',dtype='u1',mode='r')
    def read(o):
        b=o['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ids=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        return v,ids
    source=next(o for o in scene['objects'] if o['kind']=='ground');verts,ids=read(source)
    cover=[];other_cover=[];source_ids=[]
    for o in scene['objects']:
        if o['kind'] not in KINDS:continue
        v,ix=read(o)
        for t in v['p'][ix]:
            pg=Polygon(t[:,:2])
            if pg.area>1.e-6:
                cover.append(pg)
                if o['kind']!='path':other_cover.append(pg)
        source_ids.append(o['id'])
    result=(scene,source,verts,ids,unary_union(cover),source_ids)
    return result+(unary_union(other_cover),) if include_other_coverage else result


def generate():
    scene,source,vertices,ids,coverage,source_ids,other_coverage=input_meshes(include_other_coverage=True)
    # The source path and terrain independently interpolate elevation. Reconcile
    # only small differences at path edges near Notre-Dame, for display alone.
    blob=np.memmap(FOLDER/'paris-digital-twin-meshes.bin',dtype='u1',mode='r')
    path_tris=[];path_polys=[]
    for obj in scene['objects']:
        if obj['kind']!='path':continue
        b=obj['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset'])
        ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
        for triangle in v['p'][ix]:
            poly=Polygon(triangle[:,:2])
            if poly.area>1e-6:path_tris.append(triangle.astype('f8'));path_polys.append(poly)
    tree=shapely.STRtree(path_polys);centre=np.asarray(scene['quality_centre_ue_cm'][:2]);edge_cache={}
    def edge_height(x,y,z):
        if (x-centre[0])**2+(y-centre[1])**2>20000**2:return z
        key=(round(x,4),round(y,4),round(z,3))
        if key in edge_cache:return edge_cache[key]
        p=Point(x,y);best=z;difference=20.0
        for i in tree.query(p.buffer(.1)):
            if path_polys[i].distance(p)>.1:continue
            tri=path_tris[i];u=tri[1]-tri[0];v=tri[2]-tri[0];den=u[0]*v[1]-u[1]*v[0]
            dx=x-tri[0,0];dy=y-tri[0,1];s=(dx*v[1]-dy*v[0])/den;r=(u[0]*dy-u[1]*dx)/den
            height=tri[0,2]+s*u[2]+r*v[2];diff=abs(height-z)
            if diff<difference:best=height;difference=diff
        edge_cache[key]=best;return best
    positions=[];normals=[];indices=[];original_area=0.;remaining_area=0.;restored_area=0.
    for index in ids:
        tri=vertices['p'][index].astype('f8');pg=Polygon(tri[:,:2]);original_area+=pg.area
        visible=pg.difference(coverage)
        u=tri[1]-tri[0];v=tri[2]-tri[0];den=u[0]*v[1]-u[1]*v[0]
        if abs(den)<1.e-9:continue
        # Do not remove the lower land beneath a raised path: a long vertical
        # gap is visible from eye height. Keep only overlaps with at least 30cm
        # vertical clearance, and never add land below other mapped surfaces.
        if pg.distance(Point(*centre))<20000:
            additions=[]
            for i in tree.query(pg):
                piece=pg.intersection(path_polys[i]).difference(other_coverage)
                if piece.is_empty or piece.area<.01:continue
                path=path_tris[i]; pu=path[1]-path[0];pv=path[2]-path[0];pd=pu[0]*pv[1]-pu[1]*pv[0]
                coords=shapely.get_coordinates(piece)
                dx=coords[:,0]-tri[0,0];dy=coords[:,1]-tri[0,1]
                ground_z=tri[0,2]+(dx*v[1]-dy*v[0])/den*u[2]+(u[0]*dy-u[1]*dx)/den*v[2]
                dx=coords[:,0]-path[0,0];dy=coords[:,1]-path[0,1]
                path_z=path[0,2]+(dx*pv[1]-dy*pv[0])/pd*pu[2]+(pu[0]*dy-pu[1]*dx)/pd*pv[2]
                clearance=path_z-ground_z-30
                if not len(coords) or np.max(clearance)<=0:continue
                if np.min(clearance)>0:
                    additions.append(piece);continue
                # The difference between two planes is linear. Clip to the
                # half-plane above the clearance threshold, including partial
                # triangles where the height difference changes along an edge.
                xmin,ymin,xmax,ymax=piece.bounds
                rect=[(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)]
                def value(x,y):
                    gx=x-tri[0,0];gy=y-tri[0,1]
                    g=tri[0,2]+(gx*v[1]-gy*v[0])/den*u[2]+(u[0]*gy-u[1]*gx)/den*v[2]
                    px=x-path[0,0];py=y-path[0,1]
                    h=path[0,2]+(px*pv[1]-py*pv[0])/pd*pu[2]+(pu[0]*py-pu[1]*px)/pd*pv[2]
                    return h-g-30
                clipped=[]
                for start,end in zip(rect,rect[1:]+rect[:1]):
                    av=value(*start);bv=value(*end)
                    if av>=0:clipped.append(start)
                    if (av>=0)!=(bv>=0):
                        fraction=av/(av-bv)
                        clipped.append((start[0]+fraction*(end[0]-start[0]),start[1]+fraction*(end[1]-start[1])))
                if len(clipped)>=3:
                    above=piece.intersection(Polygon(clipped))
                    if not above.is_empty and above.area>.01:additions.append(above)
            if additions:
                restored=unary_union(additions).difference(visible);restored_area+=restored.area
                visible=unary_union([visible,restored])
        remaining_area+=visible.area
        if visible.is_empty:continue
        n=vertices['n'][index[0]].astype('f8');n/=np.linalg.norm(n)
        parts=sorted(shapely.constrained_delaunay_triangles(visible).geoms,key=lambda p:p.normalize().wkb_hex)
        for t in parts:
            coords=list(t.exterior.coords)[:-1]
            if t.area<1.e-8:continue
            start=len(positions)
            for x,y in coords:
                dx,dy=x-tri[0,0],y-tri[0,1];s=(dx*v[1]-dy*v[0])/den;r=(u[0]*dy-u[1]*dx)/den
                z=float(tri[0,2]+s*u[2]+r*v[2]);z=edge_height(x,y,z)
                positions.append([round(x,6),round(y,6),round(float(z),6)]);normals.append(n.tolist())
            a,b,c=positions[-3:];cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            indices.extend([start,start+2,start+1] if cross*n[2]>0 else [start,start+1,start+2])
    color=''.join(f'{c:02x}' for c in vertices['c'][0][:3])
    mesh=dict(positions_cm=positions,normals=normals,indices=indices,color=color)
    sha=hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(format='paris_covered_terrain_display_v1',source_scene_sha256=scene['source_scene_sha256'],
        geometry_sha256=sha,asset='/Game/ParisPhotoreal/Ground/SM_ParisTerrainCut_'+sha[:12],
        source_terrain_id=source['id'],coverage_mesh_ids=source_ids,coverage_kinds=sorted(KINDS),
        original_area_m2=original_area/10000,visible_area_m2=remaining_area/10000,restored_beneath_raised_paths_m2=restored_area/10000,
        geometry_provenance='Terrain cut below surface coverage; lower terrain retained beneath raised paths with >30cm clearance near Notre-Dame. Path edges under 20cm are reconciled for display; source GIS and collision remain unchanged.',
        triangles=len(indices)//3,**mesh)


if __name__=='__main__':
    result=generate();(FOLDER/'paris-photo-ground-source.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['triangles','original_area_m2','visible_area_m2','geometry_sha256']}))
