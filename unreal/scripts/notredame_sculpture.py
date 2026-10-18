"""Original inferred stone figures for the near portals, never survey assets.

Continuous surfaces replace primitive chains. Faces, drapery and poses are
authored estimates and must not be assigned the identity of an actual saint.
The imported historic facade remains a separate, attributed data layer.
"""
import math


def _unit(v):
    length=math.sqrt(sum(x*x for x in v))
    if length<1e-12:raise ValueError('Singular sculpture normal')
    return tuple(x/length for x in v)


def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))


def _surface(face, point, rows, sides, bottom_pole=False, top_pole=False):
    """Closed periodic surface with interpolated geometric vertex normals.

    Normals use the surface derivatives rather than one average per polygon.
    Caps have an explicit centre; no zero-area quads or latitude-ring slits.
    """
    p=[];n=[];eps=1e-5
    for i in range(rows+1):
        t=i/rows;pr=[];nr=[]
        for j in range(sides):
            a=j*math.tau/sides;pr.append(point(t,a))
            if i==0 and bottom_pole:nr.append((0,0,-1));continue
            if i==rows and top_pole:nr.append((0,0,1));continue
            dt=_sub(point(min(1,t+eps),a),point(max(0,t-eps),a))
            da=_sub(point(t,a+eps),point(t,a-eps))
            nr.append(_unit(_cross(_unit(da),_unit(dt))))
        p.append(pr);n.append(nr)
    def emit(points,normals):
        average=_unit(tuple(sum(v[k] for v in normals) for k in range(3)))
        face('sculpture',points,average,vertex_normals=normals)
    for i in range(rows):
        for j in range(sides):
            k=(j+1)%sides
            if i==0 and bottom_pole:emit([p[0][0],p[1][k],p[1][j]],[n[0][0],n[1][k],n[1][j]])
            elif i==rows-1 and top_pole:emit([p[i][j],p[i][k],p[-1][0]],[n[i][j],n[i][k],n[-1][0]])
            else:emit([p[i][j],p[i][k],p[i+1][k],p[i+1][j]],[n[i][j],n[i][k],n[i+1][k],n[i+1][j]])
    for row,pole in [(0,bottom_pole),(-1,top_pole)]:
        if pole:continue
        centre=tuple(sum(v[k] for v in p[row])/sides for k in range(3))
        # Outward cap direction is opposite/along the surface's longitudinal axis.
        direction=_sub(tuple(sum(v[k] for v in p[1])/sides for k in range(3)),tuple(sum(v[k] for v in p[0])/sides for k in range(3))) if row==0 else _sub(tuple(sum(v[k] for v in p[-1])/sides for k in range(3)),tuple(sum(v[k] for v in p[-2])/sides for k in range(3)))
        normal=_unit(tuple((-1 if row==0 else 1)*v for v in direction))
        for j in range(sides):face('sculpture',[centre,p[row][j],p[row][(j+1)%sides]],normal)


def build_figure(face,x,y,z,h,seed=0):
    """Return counted components; anchor and height use the existing portal."""
    def place(p):return (x+h*p[0],y+h*p[1],z+h*p[2])
    def gaussian(v,c,s):return math.exp(-((v-c)/s)**2)
    def ellipsoid(cx,cy,cz,rx,ry,rz,sides=32,rows=18):
        def surface(t,a):
            lat=-math.pi/2+math.pi*t
            if t in (0,1):return place((cx,cy,cz+rz*(-1 if t==0 else 1)))
            return place((cx+rx*math.cos(lat)*math.sin(a),cy-ry*math.cos(lat)*math.cos(a),cz+rz*math.sin(lat)))
        _surface(face,surface,rows,sides,True,True)
    def sweep(points,r0,r1,sides=16,rows=28,folds=0):
        def centre(t):return tuple((1-t)**3*points[0][k]+3*(1-t)**2*t*points[1][k]+3*(1-t)*t*t*points[2][k]+t**3*points[3][k] for k in range(3))
        def surface(t,a):
            c=centre(t);tangent=_unit(_sub(centre(min(1,t+1e-4)),centre(max(0,t-1e-4))))
            u=_unit(_cross((0,-1,0),tangent));v=_cross(tangent,u)
            radius=(r0+(r1-r0)*t)*(1+folds*math.cos(a*7+t*3))
            return place(tuple(c[k]+radius*(u[k]*math.cos(a)+v[k]*math.sin(a)) for k in range(3)))
        _surface(face,surface,rows,sides)

    # The folds descend continuously, changing direction around the knees and
    # gathered waist. No separate rods are placed on the garment's surface.
    profile=[(.0,.136),(.22,.127),(.49,.100),(.68,.098),(.86,.124),(1.,.055)]
    def robe(t,a):
        for (t0,r0),(t1,r1) in zip(profile,profile[1:]):
            if t<=t1:
                f=(t-t0)/(t1-t0);f=f*f*(3-2*f);r=r0+(r1-r0)*f;break
        phase=a*15+.55*math.sin(t*4+seed*.6)+.22*math.cos(a*3)*t
        fold=(.055+.040*(1-t))*math.cos(phase)+.025*math.cos(phase*2+.3)
        radius=r*(1+fold)
        cx=.008*math.sin(t*3+seed*.7)*math.sin(t*math.pi)
        front_gather=.010*gaussian(t,.66,.19)*max(0,math.cos(a))*math.sin(a*4+t*14)
        return place((cx+radius*math.sin(a),-radius*.64*math.cos(a)+front_gather,.035+.79*t))
    _surface(face,robe,60,80)
    ellipsoid(0,.0,.802,.029,.029,.060)

    def head(t,a):
        lat=-math.pi/2+math.pi*t;vertical=.112*math.sin(lat)
        if t in (0,1):return place((0,-.0025,.915+vertical*.625))
        # Jaw narrows toward the chin; a rounded skull and integrated facial
        # relief create continuous eye sockets, brow, nose, lips and chin.
        jaw=1-.22*gaussian(vertical,-.072,.038)
        xx=.074*math.cos(lat)*math.sin(a)*jaw
        yy=-.068*math.cos(lat)*math.cos(a)-.004
        front=max(0,math.cos(a))**6
        nose=.019*gaussian(xx,0,.013)*gaussian(vertical,.007,.040)+.020*gaussian(xx,0,.015)*gaussian(vertical,-.015,.012)
        face_relief=nose
        for sign in [-1,1]:
            face_relief+=.006*gaussian(xx,sign*.036,.025)*gaussian(vertical,-.019,.024)
            face_relief-=.0075*gaussian(xx,sign*.030,.016)*gaussian(vertical,.023,.009)
            face_relief+=.006*gaussian(xx,sign*.030,.023)*gaussian(vertical,.037,.006)
        face_relief+=gaussian(xx,0,.027)*(.004*gaussian(vertical,-.043,.004)+.005*gaussian(vertical,-.054,.006)-.003*gaussian(vertical,-.048,.0025))
        face_relief+=.008*gaussian(xx,0,.031)*gaussian(vertical,-.075,.016)
        yy-=front*face_relief
        # Low carved hair ridges on the back and upper temples, not loose beads.
        hair=max(0,min(1,(.30-math.cos(a))*2))*max(0,min(1,(vertical+.035)*25))
        yy-=hair*.003*math.cos(a*22+lat*5)*math.cos(a)
        xx+=hair*.003*math.cos(a*22+lat*5)*math.sin(a)
        return place((xx*.625,yy*.625,.915+vertical*.625))
    _surface(face,head,44,88,True,True)
    for sign in [-1,1]:
        ellipsoid(sign*.045,.00125,.9125,.00875,.010,.01625)
        # Sleeves turn continuously through the elbow; their ends are capped.
        sweep([(sign*.104,.005,.710),(sign*.156,-.005,.620),
               (sign*.144,-.051,.548),(sign*.077,-.092,.513)],.046,.030,24,36,.045)
        ellipsoid(sign*.071,-.100,.486,.030,.024,.044)
        for finger in range(4):
            xx=sign*.071+(finger-1.5)*.013
            length=.045-.008*abs(finger-1.5)
            sweep([(xx,-.111,.486),(xx,-.120,.474),
                   (xx-sign*.004,-.122,.486-length),(xx-sign*.006,-.116,.480-length)],.0065,.0048,10,12)
        sweep([(sign*.053,-.104,.502),(sign*.035,-.122,.486),
               (sign*.035,-.130,.470),(sign*.046,-.125,.462)],.010,.0065,12,16)
        ellipsoid(sign*.046,-.030,.030,.043,.078,.025)
    return dict(near_sculptures=1,continuous_robes=1,sculpted_faces=1,
                smooth_sleeves=2,carved_hands=2)
