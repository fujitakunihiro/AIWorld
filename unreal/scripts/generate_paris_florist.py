"""Original metric florist meshes, visually guided by the supplied photograph.

The photograph is a local reference, never a facade billboard or a texture.
Placement comes from existing archived florist POIs at runtime.
"""
import hashlib
import json
import math
import random
from pathlib import Path
import numpy as np
from generate_paris_frontages import Mesh

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'unreal/assets/paris-florist/Generated/display.json'
REFERENCE_SHA = '236bc83c6a46e1a773630d8cfe86adf979d9f0119923238d59781afe56a11dea'
RECIPE = 'paris_photo_reference_florist_v1'


def box(m, p, size, c):
    m.box([0, 0, 0], [1, 0, 0], [0, 1, 0], p, size, c)


def ring(m, x, y, z, rx, ry, radius, c, phase=0, segments=40):
    for i in range(segments):
        a, b = i * math.tau / segments, (i+1) * math.tau / segments
        def p(t): return [x+rx*math.cos(t), y+ry*math.sin(t), z+.3*math.sin(t*14+phase)]
        m.tube(p(a), p(b), radius, c, 5)


def lathe(m, x, y, profile, c, sides=28):
    for (z0, r0), (z1, r1) in zip(profile, profile[1:]):
        for j in range(sides):
            a, b = j*math.tau/sides, (j+1)*math.tau/sides
            n = np.array([math.cos((a+b)/2), math.sin((a+b)/2), (r0-r1)/(z1-z0) if abs(z1-z0)>.001 else 0.])
            n /= np.linalg.norm(n)
            m.face([[x+r*math.cos(t), y+r*math.sin(t), z] for r,z,t in [(r0,z0,a),(r0,z0,b),(r1,z1,b),(r1,z1,a)]], n.tolist(), c)


def basket(m, x, y, base, rx=24, ry=18, h=22):
    # Real open weave: staggered horizontal reeds, vertical stakes and a rolled lip.
    c=[177,137,83,255]
    for j in range(13):
        t=j/12;ring(m,x,y,base+2+t*h,rx*(.76+.24*t),ry*(.76+.24*t),.60,c,phase=j*math.pi)
    for j in range(28):
        a=j*math.tau/28
        for k in range(6):
            def p(t):
                r=.76+.24*t+.009*math.sin(t*math.pi*12+j*math.pi)
                return [x+rx*r*math.cos(a),y+ry*r*math.sin(a),base+2+t*h]
            m.tube(p(k/6),p((k+1)/6),.56,[145+j%4*8,109+j%4*6,65+j%4*4,255],5)
    for dz in [0,.9,1.8]:ring(m,x,y,base+h+2+dz,rx+.2,ry+.2,.7,[190,153,101,255])
    box(m,[x,y,base+2],[rx*1.45,ry*1.45,2],[88,65,39,255])


def crate(m, x, y, base, h=43):
    for side in [-1,1]:
        for z in range(7, int(h), 10):
            box(m,[x,y+side*20,base+z],[54,2.3,7],[156+z%5,123,79,255])
            box(m,[x+side*26,y,base+z],[2.3,40,7],[146,113,72,255])
        for yy in [-18,18]:box(m,[x+side*24, y+yy, base+h/2],[3,3,h],[128,96,58,255])
    for i in range(5):box(m,[x-22+i*11,y,base+h-1],[10,41,2.5],[169,136,90,255])


def leaf(m, base, tip, width, color):
    b=np.array(base);t=np.array(tip);u=t-b
    v=np.cross(u,[0,0,1]);v/=max(np.linalg.norm(v),.001);v*=width
    centre=(b+t)/2+np.array([0,0,1.2]);rim=[b,b+u*.26+v*.75,b+u*.64+v,t,b+u*.64-v,b+u*.26-v*.75]
    for i in range(6):
        a,r=centre,rim[i];s=rim[(i+1)%6];n=np.cross(r-a,s-a);n/=max(np.linalg.norm(n),.001)
        m.face([a.tolist(),r.tolist(),s.tolist()],n.tolist(),color)


def bloom(m, centre, radius, color, seed, rose=False):
    rng=random.Random(seed);centre=np.array(centre)
    normal=np.array([rng.uniform(-.35,.35),rng.uniform(.15,.55),1.]);normal/=np.linalg.norm(normal)
    u=np.cross(normal,[0,1,0]);u/=np.linalg.norm(u);v=np.cross(normal,u)
    layers=3 if rose else 1
    for layer in range(layers):
        rr=radius*(1-layer*.24);petals=7+layer*2 if rose else 5 if radius<1 else 11
        for j in range(petals):
            a=j*math.tau/petals+layer*.39;axis=u*math.cos(a)+v*math.sin(a);side=-u*math.sin(a)+v*math.cos(a)
            p=centre+axis*rr*.5+normal*(layer*.55+rr*.16)
            rim=[]
            for k in range(8):
                t=k*math.tau/8;d=rr*(.49+.49*math.cos(t));w=rr*(.28 if rose else .19)*math.sin(t)
                rim.append(centre+axis*d+side*w+normal*(layer*.55+rr*(.1+.14*math.cos(t))))
            tint=[min(255,max(0,int(s*rng.uniform(.92,1.04)))) for s in color[:3]]+[255]
            for k in range(8):
                points=[p,rim[k],rim[(k+1)%8]];n=np.cross(points[1]-p,points[2]-p);n/=max(np.linalg.norm(n),.001)
                m.face([q.tolist() for q in points],n.tolist(),tint)
    # Small faceted pollen dome instead of a painted spot.
    for j in range(10):
        a,b=j*math.tau/10,(j+1)*math.tau/10
        p=centre+normal*(1.2 if rose else .6)
        m.face([p.tolist(),(centre+(u*math.cos(a)+v*math.sin(a))*radius*.2).tolist(),(centre+(u*math.cos(b)+v*math.sin(b))*radius*.2).tolist()],normal.tolist(),[183,145,39,255])


def models():
    wicker=Mesh();timber=Mesh(bevel_cm=.22);metal=Mesh();foliage=Mesh();petals=Mesh();paint=Mesh(bevel_cm=.22);cloth=Mesh();slates=Mesh(bevel_cm=.12)
    groups=[('wicker',wicker),('timber',timber),('metal',metal),('foliage',foliage),('petals',petals),('paint',paint),('cloth',cloth),('slates',slates)]
    # Two narrow display banks leave the middle 120cm clear for the entrance.
    containers=[]
    for side in [-1,1]:
        x=side*113
        crate(timber,x,24,0,43);crate(timber,x,24,43,36)
        basket(wicker,x,70,1,27,21,23);containers.append((x,70,28,25,16,24))
        basket(wicker,x,24,81,24,17,20);containers.append((x,24,104,21,13,31))
        bx=side*80
        lathe(metal,bx,44,[(1,10),(3,11),(43,15),(44,15.8),(46,15.8),(46.5,14.5)],[129,139,138,255])
        ring(metal,bx,44,45,15.5,15.5,.65,[187,190,180,255],segments=32)
        containers.append((bx,44,48,12,12,40))
    for side in [-1,1]:
        x=side*151
        lathe(timber,x,57,[(1,9),(3,9.5),(23,12),(24,13),(27,13),(28,11.5)],[159,102,69,255],24)
        containers.append((x,57,28,10,10,23))
    rng=random.Random(84021)
    palettes=[[239,217,164,255],[234,183,201,255],[225,185,224,255],[239,203,55,255],[235,233,213,255],[171,70,114,255]]
    for ci,(x,y,z,rx,ry,h) in enumerate(containers):
        for j in range(44):
            a=j*2.399963;d=math.sqrt((j+.5)/44)
            head=[x+rx*d*math.cos(a),y+ry*d*math.sin(a),z+h*(.82+.27*rng.random())-d*6]
            root=[x+rx*d*.25*math.cos(a),y+ry*d*.25*math.sin(a),z-2]
            foliage.tube(root,head,.24,[48,83,34,255],5)
            for k in range(3):
                aa=a+k*2.3;zz=z+h*(.2+k*.17);p=[root[0]+(head[0]-root[0])*(.25+k*.18),root[1]+(head[1]-root[1])*(.25+k*.18),zz]
                ll=rng.uniform(6,10);leaf(foliage,p,[p[0]+ll*math.cos(aa),p[1]+ll*math.sin(aa),p[2]+rng.uniform(-2,3)],ll*.24,[[40,77,38,255],[63,102,43,255],[77,116,53,255]][j%3])
            bloom(petals,head,rng.uniform(2.8,4.1),palettes[ci%len(palettes)],ci*100+j,rose=ci in [1,5,7])
            if j%3==0:
                # Baby's breath, distinct tiny white blooms at the bouquet edge.
                for k in range(3):bloom(petals,[head[0]+k*2-2,head[1]+2,head[2]+4],.7,[240,238,215,255],ci*700+j*3+k)
        box(slates,[x+7,y+ry+1,z+9],[9,1,7],[27,39,36,255]);metal.tube([x+7,y+ry,z-5],[x+7,y+ry,z+8],.32,[144,147,133,255],5)
        for dz,w in [(10,4.5),(8,3)]:box(slates,[x+7,y+ry+1.6,z+dz],[w,.25,.35],[216,213,184,255])
    dark=[32,65,51,255]
    for x in [-163,163]:box(paint,[x,34,151],[7,8,302],dark)
    for x in [-107,107]:box(paint,[x,33,16],[88,7,30],dark)
    box(paint,[0,34,296],[333,8,12],dark)
    # Original green canvas canopy, with a hanging scalloped valance.
    # Enclose the original 344 x 114cm canopy, retaining its existing collider.
    cloth.face([[-176,3,305],[176,3,305],[176,119,277],[-176,119,277]],[0,.23464,.97208],[35,76,56,255],[(0,0),(3,0),(3,1),(0,1)])
    for i in range(32):
        x=-176+i*11;bottom=237+1.4*math.cos(i*math.pi)
        cloth.face([[x,119,277],[x+11,119,277],[x+11,119,bottom],[x,119,bottom]],[0,1,0],[31,67,49,255],[(0,0),(1,0),(1,1),(0,1)])
    for side in [-1,1]:cloth.face([[side*176,3,305],[side*176,119,277],[side*176,119,237],[side*176,3,290]],[side,0,0],[31,67,49,255])
    for x in [-166,166]:metal.tube([x,12,300],[x,117,277],.8,[42,48,43,255],8)
    out=[]
    for name,m in groups:
        item=m.item(name,'M_ParisFlorist_'+name);item['asset']='/Game/ParisPhotoreal/Florist/SM_ParisFlorist_'+name+'_'+item['geometry_sha256'][:12]
        out.append(item)
    return out


def generate():
    return dict(format='paris_florist_display_v1',recipe=RECIPE,reference_sha256=REFERENCE_SHA,
        appearance_provenance='Original inferred 3D display guided by the user photograph; not a scan or a verified real shop exterior',
        reference_usage='Local visual reference only. No photographed people, brands or pixels are baked into the models.',
        local_units='cm; X along facade, +Y toward street, Z above existing shop ground',
        entrance_clear_width_cm=100,display_max_depth_cm=93,models=models())


if __name__=='__main__':
    data=generate();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(dict(recipe=RECIPE,models=len(data['models']),triangles=sum(m['triangles'] for m in data['models']))))
