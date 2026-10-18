"""Reference-informed western elevation; sculpture and depths are authored estimates.

Official dimensions and architectural elements are cited in the generated manifest.
This does not claim photogrammetry, surveyed sculpture, or a finished L4/L5 asset.
The same opening descriptions drive geometry and the source-display cutout.
"""
import math

REVISION = 12
PORTALS = [(-14., 8.1), (0., 9.5), (14., 8.1)]
ROSE = dict(x=0., z=28.1, radius=4.85)
GALLERY = [(-20.9, -9.25), (-7.75, 7.75), (9.25, 20.9)]


def opening_spec():
    return dict(portals=[dict(x=x, width=w, bottom=0., spring=5.5, top=13.) for x, w in PORTALS],
                rose=ROSE, windows=[dict(x=x+d, width=3.3, bottom=23.5, spring=28., top=32.)
                                   for x in [-15.2, 15.2] for d in [-2.7, 2.7]],
                gallery=[dict(left=a, right=b, bottom=36., top=43.6) for a,b in GALLERY],
                depth_min=-3., depth_max=2.)


def display_mask_hlsl(frame):
    """Only the display changes; colliders and source vertices remain untouched."""
    xyz=lambda p:'float3('+','.join(f'{x:.10f}' for x in p)+')'
    code=f'float3 d=(Position-{xyz(frame["front_cm"])})*.01; float x=dot(d,{xyz(frame["across"])}), y=dot(d,{xyz(frame["depth"])}), z=d.z; float hole=0; '
    code+='if(y>=-3&&y<=2){'
    spec=opening_spec()
    for p in spec['portals']+spec['windows']:
        half=p['width']/2;rise=p['top']-p['spring'];offset=(rise*rise-half*half)/(2*half);radius=half+offset
        code+=f'{{float a=abs(x-({p["x"]}));hole=max(hole,(a<{half}&&z>={p["bottom"]}&&z<={p["spring"]}+sqrt(max(0,{radius*radius} - ({offset}+a)*({offset}+a))))?1:0);}}'
    code+='hole=max(hole,length(float2(x,z-28.1))<4.85?1:0);'
    for a,b in GALLERY:code+=f'hole=max(hole,(x>{a}&&x<{b}&&z>36&&z<43.6)?1:0);'
    code+='} if(z>=48&&z<=64.7&&y>=-2&&y<=16){float o=(6.7*6.7-2.3*2.3)/(2*2.3), r=2.3+o;'
    for cx in [-17.95,-12.55,12.55,17.95]:code+=f'{{float a=abs(x-({cx}));hole=max(hole,(a<2.3&&z<58+sqrt(max(0,r*r-(o+a)*(o+a))))?1:0);}}'
    code+='if(abs(abs(x)-15.25)<6.5){'
    for cy in [4.8,10.2]:code+=f'{{float a=abs(y-{cy});hole=max(hole,(a<2.3&&z<58+sqrt(max(0,r*r-(o+a)*(o+a))))?1:0);}}'
    return code+'}} return 1-hole;'


def build(face, box, tube, ellipsoid, ogive, opening, pierced_wall):
    from notredame_portal_doors import build_doors
    counts=dict(portals=3, gallery_figures=28, archivolt_figures=0, carved_capitals=0,
                rose_glass_cells=0, pierced_balustrade_panels=0)

    def circle(x,z,r,y,n=64):
        return [(x+r*math.cos(i*math.tau/n),y,z+r*math.sin(i*math.tau/n)) for i in range(n+1)]

    def panel(kind,x,y,z,w,h,depth,bevel=.035):
        """Closed frame with a sloping arris; y is the exposed/front surface."""
        b=min(bevel,w*.2,h*.2,depth*.4)
        outer=[(x-w/2,z),(x+w/2,z),(x+w/2,z+h),(x-w/2,z+h)]
        inner=[(x-w/2+b,z+b),(x+w/2-b,z+b),(x+w/2-b,z+h-b),(x-w/2+b,z+h-b)]
        face(kind,[(a,y,c) for a,c in inner],(0,-1,0))
        face(kind,[(a,y+depth,c) for a,c in reversed(outer)],(0,1,0))
        for i in range(4):
            j=(i+1)%4;a,c=outer[i];b0,d=outer[j];u,v=inner[i];s,t=inner[j]
            length=math.hypot(b0-a,d-c);out=((d-c)/length,(a-b0)/length)
            n=(out[0],-1,out[1])
            face(kind,[(a,y+bevel,c),(b0,y+bevel,d),(s,y,t),(u,y,v)],n)
            face(kind,[(a,y+bevel,c),(a,y+depth,c),(b0,y+depth,d),(b0,y+bevel,d)],(out[0],0,out[1]))

    def capital(x,y,z,r=.22):
        panel('stone',x,y-r,z,r*2.7,.16,r*2.4,.025)
        for i in range(6):
            a=i*math.tau/6
            ellipsoid('sculpture',x+r*.8*math.cos(a),y+r*.55*math.sin(a),z-.12,r*.38,r*.38,.22,8,5)
        counts['carved_capitals']+=1

    def person(x,y,z,h,seed=0,royal=False,angel=False,lean=0.):
        """Carved faces and fluted drapery; no identification of real sculpture."""
        if h>=3:
            from notredame_sculpture import build_figure
            is_virgin_anchor=abs(x-14)<.001 and abs(y+.30)<.001 and abs(h-3.4)<.001
            def statue_face(kind,*args,**kwargs):
                return face('virgin_fallback' if is_virgin_anchor else kind,*args,**kwargs)
            for key,value in build_figure(statue_face,x,y,z,h,seed).items():counts[key]=counts.get(key,0)+value
            panel('virgin_fallback' if is_virgin_anchor else 'stone',x,y-h*.14,z,h*.38,h*.055,h*.30,.02)
            return
        # The robe is a closed taper with varied fold directions and a hem.
        rings=[];sides=16
        for row in range(8):
            t=row/7;radius=h*(.15-.035*t+.012*math.sin(t*math.pi))
            rings.append([(x+lean*h*t+radius*(1+.13*math.cos(j*math.tau/4+seed*.4+t))*math.cos(j*math.tau/sides),
                           y+radius*.66*(1+.12*math.cos(j*math.tau/4+seed*.4+t))*math.sin(j*math.tau/sides),z+h*(.04+t*.68)) for j in range(sides)])
        for a,b in zip(rings,rings[1:]):
            for j in range(sides):
                k=(j+1)%sides;n=(a[j][0]+a[k][0]-2*x,a[j][1]+a[k][1]-2*y,0)
                face('sculpture',[a[j],a[k],b[k],b[j]],n)
        face('sculpture',list(reversed(rings[0])),(0,0,-1));face('sculpture',rings[-1],(0,0,1))
        hx=x+lean*h*.8;hz=z+h*.87
        ellipsoid('sculpture',hx,y,hz,h*.081,h*.072,h*.108,16,10)
        # Nose, brows, cheeks, chin and hair remain stone relief, not a skin material.
        ellipsoid('sculpture',hx,y-h*.071,hz-h*.012,h*.019,h*.035,h*.035,10,6)
        for side in [-1,1]:
            tube('sculpture',[(hx+side*h*.013,y-h*.065,hz+h*.025),(hx+side*h*.047,y-h*.064,hz+h*.018)],h*.009,6)
            ellipsoid('sculpture',hx+side*h*.05,y-h*.051,hz-h*.021,h*.025,h*.018,h*.032,8,5)
            tube('sculpture',[(x+side*h*.12,y,z+h*.68),(x+side*h*.20,y-h*.02,z+h*(.53 if seed%2 else .64)),(hx+side*h*.07,y-h*.13,z+h*.49)],h*.043,10)
            ellipsoid('sculpture',hx+side*h*.07,y-h*.14,z+h*.49,h*.03,h*.035,h*.042,8,5)
            for j in range(4):
                tube('sculpture',[(hx+side*h*.067+(j-1.5)*h*.011,y-h*.171,z+h*.485),(hx+side*h*.067+(j-1.5)*h*.011,y-h*.171,z+h*.45)],h*.004,5)
        tube('sculpture',[(hx-h*.024,y-h*.067,hz-h*.053),(hx,y-h*.074,hz-h*.058),(hx+h*.024,y-h*.067,hz-h*.053)],h*.006,6)
        for j in range(7):
            a=math.pi*(.05+j*.15)
            ellipsoid('sculpture',hx+h*.074*math.cos(a),y+.012*h,hz+h*.10*math.sin(a),h*.026,h*.074,h*.028,8,5)
        if seed%3:
            for j in range(5):
                tube('sculpture',[(hx+(j-2)*h*.015,y-h*.069,hz-h*.04),(hx+(j-2)*h*.009,y-h*.064,hz-h*.12)],h*.008,6)
        if royal:
            for j in range(8):
                a=j*math.tau/8
                ellipsoid('sculpture',hx+h*.078*math.cos(a),y+h*.071*math.sin(a),hz+h*.10,h*.019,h*.019,h*(.035+.012*(j%2)),8,5)
            panel('sculpture',hx+h*.065,y-h*.18,z+h*.40,h*.12,h*.19,h*.035,.008)
        if angel:
            for side in [-1,1]:
                for j in range(5):
                    tube('sculpture',[(x+side*h*.11,y+h*.04,z+h*.68),(x+side*h*(.18+.027*j),y+h*.06,z+h*(.84-.075*j))],h*.022,7)
        panel('stone',x,y-h*.14,z,h*.38,h*.055,h*.30,.02)

    spec=opening_spec()
    holes=[opening(p['x'],p['spring'],p['width'],p['top'],p['bottom']) for p in spec['portals']+spec['windows']]
    holes.append([(p[0],p[2]) for p in circle(0,28.1,4.85,0,128)[:-1]])
    holes.extend([[(a,36),(b,36),(b,43.6),(a,43.6)] for a,b in GALLERY])
    pierced_wall(-21.75,21.75,0,45,-.80,1.65,holes)
    # Actual architectural depth: the closed door is behind the exposed stone.
    for index,(x,w) in enumerate(PORTALS):
        # Stone tympanum and horizontal lintels sit inside the reveal.
        profile=ogive(x,5.5,w*.98,12.9,.62)
        face('stone',[(x-w*.49,.62,4.95),(x+w*.49,.62,4.95),*reversed(profile)],(0,-1,0))
        for zz in [4.95,7.5,9.5]:panel('stone',x,.27,zz,w*.97,.22,.40,.045)
        for key,value in build_doors(face,panel,ellipsoid,x,w,index).items():
            counts[key]=counts.get(key,0)+value
        panel('stone',x,-.03,0,.48,4.96,.68,.06)
        person(x,-.30,.72,3.40,index,royal=False)
        # Nested voussoirs with figured archivolts; every loop has a masonry core.
        for ring in range(6):
            offset=ring*.31
            curve=ogive(x,5.5,w+offset*2,13+offset,-.94-ring*.17,72)
            for delta,radius in [(0,.13),(-.11,.055),(.10,.05)]:tube('stone',[(a,b+delta,c) for a,b,c in curve],radius,12)
            for side in [-1,1]:
                xx=x+side*(w/2+offset)
                tube('stone',[(xx,-.94-ring*.17,.15),(xx,-.94-ring*.17,5.5)],.13,12)
                capital(xx,-.94-ring*.17,5.28,.18)
            if ring in [1,3,5]:
                for j in range(2,71,5):
                    a,b,c=curve[j];person(a,b-.16,c-.20,.58+(ring%3)*.07,j+index,angel=True)
                    counts['archivolt_figures']+=1
        for row,(zz,n,h) in enumerate([(5.24,9,1.80),(7.80,7,1.43),(9.85,3,1.55)]):
            for i in range(n):person(x+(i-(n-1)/2)*w*.086,.20,zz,h,index*11+i+row,angel=row==2)
        for side in [-1,1]:
            for k in range(3):
                xx=x+side*(w/2+.38+k*.42)
                person(xx,-1.14,.62,3.63,k+index)
                capital(xx,-1.14,4.45,.20)
        # Recessed carved medallions on the base of the splays.
        for side in [-1,1]:
            for j in range(4):
                xx=x+side*(w/2+.34+j*.34)
                tube('sculpture',circle(xx,.47,.13,-1.65,20),.022,6)

    # Four strong piers, stepped ledges and capitals preserve the elevation's rhythm.
    for x in [-21.7,-8.5,8.5,21.7]:
        panel('stone',x,-1.65,0,1.18,45,1.45,.055)
        for z in [3,9,16,21,33,39,44]:panel('stone',x,-1.90,z,1.65,.35,1.72,.045)
        for z in [22.5,34.7,45.4,66.2]:
            for step in range(3):panel('stone',x,-1.95+step*.08,z+step*.14,1.75-step*.12,.18,1.35,.03)

    for z,w in [(17,44.6),(22.1,44.6),(34.5,44),(45,44)]:
        for step in range(4):panel('stone',0,-1.15-step*.16,z+step*.16,w+step*.2,.18,1.4+step*.2,.035)
    # Gallery of the twenty-eight kings. Individual relief remains an estimate.
    for i in range(28):
        x=(i-13.5)*1.45
        panel('stone',x,-.95,17.55,1.38,3.72,.28,.025)
        for side in [-1,1]:
            tube('stone',[(x+side*.65,-1.53,17.6),(x+side*.65,-1.53,20.7)],.10,12)
            capital(x+side*.65,-1.53,20.65,.14)
        tube('stone',ogive(x,20.2,1.3,21.45,-1.52),.10,12)
        person(x,-1.31,17.85,2.55,i,royal=True,lean=(i%3-1)*.016)

    # Western rose: 9.70 m envelope, three-dimensional tracery and dark glass.
    palette=['233943','34384d','40363f','4c4140','293f48','3f3444','35463f','51483e']
    for ring in range(16):
        r0=4.82*ring/16;r1=4.82*(ring+1)/16
        for j in range(96):
            a=j*math.tau/96;b=(j+1)*math.tau/96
            if ring==0:
                points=[(0,.38,28.1),(r1*math.cos(a),.38,28.1+r1*math.sin(a)),(r1*math.cos(b),.38,28.1+r1*math.sin(b))]
            else:points=[(r0*math.cos(a),.38,28.1+r0*math.sin(a)),(r1*math.cos(a),.38,28.1+r1*math.sin(a)),(r1*math.cos(b),.38,28.1+r1*math.sin(b)),(r0*math.cos(b),.38,28.1+r0*math.sin(b))]
            face('stained',points,(0,-1,0),palette[(j//2+ring*3+(j*ring)%5)%len(palette)])
            counts['rose_glass_cells']+=1
    for r,thickness in [(4.9,.20),(5.13,.16),(5.35,.12),(.64,.13),(2.12,.13)]:tube('stone',circle(0,28.1,r,-.97,128),thickness,14)
    for i in range(24):
        a=i*math.tau/24
        tube('stone',[(.65*math.cos(a),-.99,28.1+.65*math.sin(a)),(4.8*math.cos(a),-.99,28.1+4.8*math.sin(a))],.070,12)
        cx,cz=3.5*math.cos(a),28.1+3.5*math.sin(a)
        # Petal rim and internal leadwork are physical geometry, with zero glow.
        points=[]
        for j in range(49):
            t=j*math.tau/48;rr=.70*math.cos(t);tt=.37*math.sin(t)
            points.append((cx+rr*math.cos(a)-tt*math.sin(a),-1.01,cz+rr*math.sin(a)+tt*math.cos(a)))
        tube('stone',points,.045,8)
        for r in [1.1,1.55,2.65,3.15,3.85,4.4]:
            aa=[a+j*math.tau/24/6 for j in range(7)]
            tube('iron',[(r*math.cos(t),.32,28.1+r*math.sin(t)) for t in aa],.012,5)
    # Paired pointed windows and deep open gallery, with real backing surfaces.
    for p in spec['windows']:
        x=p['x'];profile=ogive(x,28,3.3,32,.53)
        face('glass',[(x-1.65,.53,23.5),(x+1.65,.53,23.5),*reversed(profile)],(0,-1,0))
        tube('stone',ogive(x,28,3.3,32,-1.1),.19,12)
        for d in [-1.65,0,1.65]:tube('stone',[(x+d,-1.10,23.5),(x+d,-1.10,28)],.105,12)
    for a,b in GALLERY:
        box('stone',(a+b)/2,1.10,36,b-a,.30,7.6)
        count=round((b-a)/1.13)
        for i in range(count+1):
            x=a+(b-a)*i/count
            tube('stone',[(x,-1.35,36),(x,-1.35,42.05)],.12,14);capital(x,-1.35,41.92,.19)
            if i<count:tube('stone',ogive(x+(b-a)/count/2,42.05,(b-a)/count,43.55,-1.35),.09,12)
    # Pierced stone quatrefoils replace the previous plain bars.
    for z,ranges in [(35.1,[(-21.7,21.7)]),(45.6,[(-21.7,21.7)]),(69.05,[(-21.7,-8.7),(8.7,21.7)])]:
        for lo,hi in ranges:
            for zz in [z,z+1.12]:panel('stone',(lo+hi)/2,-1.73,zz,hi-lo,.16,.46,.025)
            n=round((hi-lo)/.88)
            for i in range(n):
                x=lo+(i+.5)*(hi-lo)/n
                panel('stone',x-(hi-lo)/n/2,-1.65,z+.12,.12,1.,.30,.015)
                for j in range(4):
                    a=j*math.pi/2
                    tube('stone',circle(x+.15*math.cos(a),z+.64+.15*math.sin(a),.18,-1.66,20),.036,7)
                counts['pierced_balustrade_panels']+=1
    # Upper towers retain the same official 69 m envelope and real openings.
    for x in [-15.25,15.25]:
        holes=[opening(cx,58,4.6,64.7,48) for cx in [x-2.7,x+2.7]]
        pierced_wall(x-6.5,x+6.5,45,69,-.76,1.,holes)
        for sx in [x-6.5,x+6.5]:
            sideholes=[opening(cy,58,4.6,64.7,48) for cy in [4.8,10.2]]
            pierced_wall(.7,15,45,69,0,.7,sideholes,side=sx)
            for cy in [4.8,10.2]:
                tube('stone',[(sx+(-.14 if sx<0 else .14),p[0],p[2]) for p in ogive(cy,58,4.6,64.7,0)],.2,12)
        for cx in [x-2.7,x+2.7]:
            tube('stone',ogive(cx,58,4.6,64.7,-1.16),.22,14)
            for side in [-1,1]:
                tube('stone',[(cx+side*2.3,-1.16,48),(cx+side*2.3,-1.16,58)],.19,12)
                capital(cx+side*2.3,-1.16,57.85,.26)
            # Dense recessed louvres have believable spacing, rather than nine bars.
            for j in range(36):panel('wood',cx,.20,48.35+j*.27,4.32,.16,.36,.018)
        for z in [46,65.5,68.6]:panel('stone',x,-1.18,z,13.8,.42,1.50,.045)
        box('stone',x,7.3,68.5,13.4,15.8,.45)
        for sx in [x-6.5,x+6.5]:
            for z in [47,52,57,62,67]:panel('stone',sx,-1.18,z,.92,.14,.62,.025)
    return counts
