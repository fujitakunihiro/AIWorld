"""Reference-informed door joinery and flat forged scrollwork, not a survey.

The cathedral's Sainte-Anne description documents forged hinges. The pattern
below is original inferred ornament, never a tracing of individual pentures.
All geometry stays within the existing authored portal opening and GIS frame.
"""
import math


def build_doors(face, panel, ellipsoid, x, width, portal_index):
    counts = dict(door_leaves=0, door_boards=0, forged_ribbons=0,
                  forged_leaves=0, iron_rivets=0)
    mount_offset=.035  # seat the supporting straps into the board faces

    def ribbon(points, breadth=.035, thickness=.016, taper=False):
        """Closed rectangular strip; genuine flat forged iron, not round pipe.

        Adjacent segments share averaged tangent rings, avoiding gaps at bends. Front
        normals are constant on the strap; its edges and rivets catch the sun.
        """
        rings=[]
        for j, (a,b,c) in enumerate(points):
            b+=mount_offset
            previous=points[max(0,j-1)];following=points[min(len(points)-1,j+1)]
            dx,dz=following[0]-previous[0],following[2]-previous[2]
            size=math.hypot(dx,dz)
            if size<1e-8:raise ValueError('Repeated iron-ribbon path point')
            radius=breadth*.5*(1-.65*j/(len(points)-1) if taper else 1)
            sx,sz=-dz/size*radius,dx/size*radius
            rings.append([(a-sx,b,c-sz),(a+sx,b,c+sz),
                          (a+sx,b+thickness,c+sz),(a-sx,b+thickness,c-sz)])
        for a,b in zip(rings,rings[1:]):
            for j in range(4):
                k=(j+1)%4
                normal=(0,-1,0) if j==0 else (0,1,0) if j==2 else tuple((a[1][k]-a[0][k])*(1 if j==1 else -1) if k!=1 else 0 for k in range(3))
                face('iron',[a[j],b[j],b[k],a[k]],normal)
        face('iron',list(reversed(rings[0])),tuple(points[0][i]-points[1][i] for i in range(3)))
        face('iron',rings[-1],tuple(points[-1][i]-points[-2][i] for i in range(3)))
        counts['forged_ribbons']+=1

    for side in [-1,1]:
        centre=x+side*width*.235;leaf_width=width*.455
        # A dark closed backing is behind the actual individually bevelled
        # boards. Four-millimetre gaps cannot become holes through the church.
        panel('wood',centre,.615,.12,leaf_width,4.75,.19,.018)
        boards=max(11,round(leaf_width/.27));pitch=leaf_width/boards
        for j in range(boards):
            front=.566+.004*math.sin(j*2.1+portal_index+side)
            panel('wood',centre-leaf_width/2+(j+.5)*pitch,front,.135,
                  pitch-.004,4.72,.075,.004)
            counts['door_boards']+=1
        # Shallow perimeter stiles and rails sit on the wood, never float off it.
        for sign in [-1,1]:
            panel('wood',centre+sign*(leaf_width/2-.07),.535,.14,.115,4.70,.075,.012)
        for zz in [.15,4.70]:panel('wood',centre,.529,zz,leaf_width-.08,.14,.075,.012)
        # Three load-bearing straps, with connected branching foliage/volutes.
        # Strap backs are seated at y=.572, within the board faces (.562-.570).
        for level,zz in enumerate([.85,2.30,3.80]):
            hinge=centre+side*(leaf_width/2-.16)
            tip=centre-side*(leaf_width/2-.20)
            ribbon([(hinge,.512,zz),(tip,.512,zz)],.065,.025)
            for j in range(9):
                xx=hinge+(tip-hinge)*(j+.25)/9
                ellipsoid('iron',xx,.496+mount_offset,zz,.022,.015,.022,8,5)
                counts['iron_rivets']+=1
            for branch in range(3):
                root=hinge+(tip-hinge)*(.20+branch*.25)
                for vertical in [-1,1]:
                    # A continuously tapering spiral grows out of the strap.
                    reach=leaf_width*(.11+.012*((level+branch+portal_index)%3))
                    points=[]
                    for j in range(33):
                        t=j/32;angle=t*math.pi*1.72
                        radius=reach*(1-.82*t)
                        u=reach-radius*math.cos(angle)
                        v=radius*math.sin(angle)+reach*t*.75
                        points.append((root-side*u,.510,zz+vertical*v))
                    ribbon(points,.041,.020,True)
                    # Two pointed leaves branch from the stem; explicit volume
                    # creates grazing highlights rather than painted ornaments.
                    for t in [.17,.37]:
                        p=points[round(t*32)];length=.14
                        path=[(p[0],.507,p[2]),
                              (p[0]-side*length*.45,.503,p[2]+vertical*.10),
                              (p[0]-side*length,.507,p[2]+vertical*.15)]
                        ribbon(path,.062,.015,True);counts['forged_leaves']+=1
            # The hinge knuckle is closed iron geometry at the anchored edge.
            ellipsoid('iron',hinge,.511+mount_offset,zz,.043,.042,.13,12,8)
        # Escutcheon, key hole relief and a real ring handle.
        handle=centre-side*(leaf_width/2-.34)
        panel('iron',handle,.508+mount_offset,1.58,.15,.42,.035,.022)
        ring=[]
        for j in range(49):
            t=j*math.tau/48
            ring.append((handle+.091*math.cos(t),.462-.014*math.sin(t),1.84+.12*math.sin(t)))
        ribbon(ring,.024,.022)
        ellipsoid('iron',handle,.479+mount_offset,1.95,.035,.033,.035,12,8)
        counts['door_leaves']+=1
    return counts
