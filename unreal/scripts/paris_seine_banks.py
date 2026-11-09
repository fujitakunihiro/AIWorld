"""Close unbacked water and shoreline voids with explicitly inferred surfaces."""
import math,json
import numpy as np
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from generate_paris_frontages import Mesh
from generate_paris_reference import item
from generate_paris_luxury import Surfaces
from paris_district_layout import DTYPE

LOWER_W=600;LOWER_DECK=200;TREE_SPACING=900;TREE_INSET=230

def add_banks(result,scene,data):
    result['objects']=[o for o in result['objects'] if not o['id'].startswith('seine_')]
    result['records']=[r for r in result['records'] if not r['kind'].startswith('seine_')]
    water=next(o for o in scene['objects'] if o['id']=='seine');blob=np.memmap(data/'paris-digital-twin-meshes.bin',dtype='u1',mode='r');b=water['mesh_buffer'];v=np.frombuffer(blob,dtype=DTYPE,count=b['vertex_count'],offset=b['offset']);ix=np.frombuffer(blob,dtype='<u4',count=b['index_count'],offset=b['offset']+28*b['vertex_count']).reshape(-1,3)
    bed=Mesh();level=result['seine']['water_level_cm'];bottom=level-450
    for ids in ix:
        bed.face([[float(v['p'][i,0]),float(v['p'][i,1]),bottom] for i in ids],[0,0,1],[38,43,34,255])
    feature=next(f for f in scene['pick_features'] if f['id']==result['seine']['water_source_id']);river=unary_union([Polygon(p[0],p[1:]) for p in feature['polygons_cm']]);walls=Mesh();caps=Mesh();cache={};cx,cy=scene['scene_centre_ue_cm'][:2];radius=scene['extent_m']*50
    landings=[];decks=[]
    for bridge in json.loads((data/'paris-bridges.json').read_text())['profiles']:
        centre=np.array(bridge['centre_cm'][:2]);direction=np.array(bridge['direction'])
        decks.append(LineString([centre-direction*bridge['length_cm']*.6,centre+direction*bridge['length_cm']*.6]).buffer(bridge['width_cm']/2+450))
        for i,sign in enumerate((-1,1)):landings.append((centre+direction*sign*bridge['length_cm']/2,bridge['endpoint_z_cm'][i]+110))
    def height(p,n):
        key=(round(p[0],4),round(p[1],4))
        if key not in cache:
            # Smooth the inferred upper-bank/parapet height between archived
            # bridge landings. DEM samples at the waterline create sharp spikes.
            nearest=sorted((float(np.linalg.norm(p-xy)),z) for xy,z in landings)[:4]
            weights=[1/max(distance,1800)**2 for distance,z in nearest]
            cache[key]=max(level+300,min(300,sum(w*z for w,(_,z) in zip(weights,nearest))/sum(weights)))
        return cache[key]
    terrace=Mesh();trees=[];deck=level+LOWER_DECK;run=0.;next_tree=TREE_SPACING/2
    def hash_xy(p):return int(abs(math.sin(p[0]*12.9898+p[1]*78.233))*43758.5453*1000)
    for poly in getattr(river,'geoms',[river]):
        for ring in [poly.exterior,*poly.interiors]:
            coords=list(ring.coords);prev=None
            for a,b in zip(coords,coords[1:]):
                if any(abs(a[k]-edge)<1 and abs(b[k]-edge)<1 for k,edge in ((0,cx-radius),(0,cx+radius),(1,cy-radius),(1,cy+radius))):prev=None;continue
                delta=np.array(b[:2])-a[:2];length=np.linalg.norm(delta)
                if length<1:continue
                t=delta/length;n=np.array([-t[1],t[0]]);mid=(np.array(a[:2])+b[:2])*.5
                if river.contains(Point(*(mid+n*80))):n=-n
                pieces=max(1,math.ceil(length/350))
                for i in range(pieces):
                    p=np.array(a[:2])+delta*i/pieces;q=np.array(a[:2])+delta*(i+1)/pieces;z0=height(p,n);z1=height(q,n)
                    walls.face([[*p,bottom],[*q,bottom],[*q,z1],[*p,z0]],[-n[0],-n[1],0],[190,183,165,255])
                    # Narrow coping follows the upper bank.
                    caps.face([[*p,z0+4],[*q,z1+4],[*(q+n*60),z1+4],[*(p+n*60),z0+4]],[0,0,1],[208,201,181,255])
                    # Inferred bas-port: a paved lower quay just above the water, inside the mapped river edge.
                    pi,qi=p-n*LOWER_W,q-n*LOWER_W
                    terrace.face([[*p,deck],[*q,deck],[*qi,deck],[*pi,deck]],[0,0,1],[150,140,120,255],[tuple(p/100),tuple(q/100),tuple(qi/100),tuple(pi/100)])
                    walls.face([[*pi,bottom],[*qi,bottom],[*qi,deck],[*pi,deck]],[-n[0],-n[1],0],[190,183,165,255])
                    caps.face([[*pi,deck+6],[*qi,deck+6],[*(qi+n*45),deck+6],[*(pi+n*45),deck+6]],[0,0,1],[208,201,181,255])
                    walls.face([[*pi,deck],[*qi,deck],[*qi,deck+6],[*pi,deck+6]],[-n[0],-n[1],0],[190,183,165,255])
                    if prev is not None and np.dot(prev,n)<.999:
                        # Close the wedge left between consecutive segment offsets at bends.
                        terrace.face([[*p,deck],[*(p-prev*LOWER_W),deck],[*pi,deck]],[0,0,1],[150,140,120,255],[tuple(p/100),tuple((p-prev*LOWER_W)/100),tuple(pi/100)])
                        walls.face([[*(p-prev*LOWER_W),bottom],[*pi,bottom],[*pi,deck+6],[*(p-prev*LOWER_W),deck+6]],[-(prev[0]+n[0])/2,-(prev[1]+n[1])/2,0],[190,183,165,255])
                    prev=n
                    run+=float(np.linalg.norm(q-p))
                    while run>=next_tree:
                        spot=q-t*(run-next_tree)-n*TREE_INSET;next_tree+=TREE_SPACING
                        if any(d.contains(Point(*spot)) for d in decks) or not river.contains(Point(*spot)):continue
                        rng=(hash_xy(spot)%1000)/1000
                        trees.append(dict(anchor_cm=[round(float(spot[0]),1),round(float(spot[1]),1),deck],yaw_degrees=round(rng*360,1),scale=round(.82+.18*rng,3)))
    for mesh,name,material in ((bed,'seine_bed','M_ParisLuxuryMarketSolid'),(walls,'seine_bank_closure','M_ParisQuayWet'),(caps,'seine_bank_coping','M_ParisBridgeCutStone'),(terrace,'seine_lower_quay','M_ParisBridgePaving')):
        result['objects'].append(item(mesh,name,material));result['records'].append(dict(kind=name,models=[name],anchor_cm=[0,0,0],scale_xyz=[1,1,1],yaw_degrees=0,source_id=feature['id'],placement_provenance='mapped shoreline; closure height interpolated from archived bridge landings plus inferred 110cm parapet / 4.5m river depth / 60cm coping; no measured bathymetry'))
    result['quay_trees']=trees
    result['seine']['inferred_lower_quay']=dict(width_cm=LOWER_W,deck_above_water_cm=LOWER_DECK,trees=len(trees),tree_spacing_cm=TREE_SPACING,provenance='inferred continuous bas-port along mapped banks; not surveyed quay extents; trees use the existing avenue tree asset')
    result['seine']['inferred_bed_depth_cm']=450
    result['seine']['bank_closure_triangles']=len(walls.indices)//3
