"""Small authored modules, in projected metres before the shared UE conversion."""
import math


def tube(mesh, a, b, radius, sides=8):
    """Capped arbitrary-axis pipe, in projected metres, with finite normals."""
    axis=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(v*v for v in axis))
    if length<1e-6:return
    axis=[v/length for v in axis];ref=(0,0,1) if abs(axis[2])<.9 else (0,1,0)
    u=[axis[1]*ref[2]-axis[2]*ref[1],axis[2]*ref[0]-axis[0]*ref[2],axis[0]*ref[1]-axis[1]*ref[0]]
    size=math.sqrt(sum(v*v for v in u));u=[v/size for v in u]
    v=[axis[1]*u[2]-axis[2]*u[1],axis[2]*u[0]-axis[0]*u[2],axis[0]*u[1]-axis[1]*u[0]]
    def ring(p,t):return mesh.vertex((p[0]+radius*(math.cos(t)*u[0]+math.sin(t)*v[0]),p[1]+radius*(math.cos(t)*u[1]+math.sin(t)*v[1])),p[2]+radius*(math.cos(t)*u[2]+math.sin(t)*v[2]))
    for i in range(sides):
        t,q=i*math.tau/sides,(i+1)*math.tau/sides;m=(t+q)/2
        normal=[math.cos(m)*u[j]+math.sin(m)*v[j] for j in range(3)];normal[1]*=-1
        mesh.face([ring(a,t),ring(a,q),ring(b,q),ring(b,t)],normal)
        for p,n,reverse in [(a,[-axis[0],axis[1],-axis[2]],True),(b,[axis[0],-axis[1],axis[2]],False)]:
            points=[mesh.vertex(p[:2],p[2]),ring(p,t),ring(p,q)]
            mesh.face(list(reversed(points)) if reverse else points,n)


def box(mesh, centre, along, outward, width, depth, bottom, top, offset=0):
    cx,cy=centre;dx,dy=along;nx,ny=outward
    def p(x,y,z):
        return mesh.vertex((cx+dx*x+nx*(y+offset),cy+dy*x+ny*(y+offset)),z)
    w,d=width/2,depth/2
    mesh.face([p(-w,-d,bottom),p(w,-d,bottom),p(w,-d,top),p(-w,-d,top)],(-nx,ny,0))
    mesh.face([p(w,d,bottom),p(-w,d,bottom),p(-w,d,top),p(w,d,top)],(nx,-ny,0))
    mesh.face([p(-w,d,bottom),p(-w,-d,bottom),p(-w,-d,top),p(-w,d,top)],(-dx,dy,0))
    mesh.face([p(w,-d,bottom),p(w,d,bottom),p(w,d,top),p(w,-d,top)],(dx,-dy,0))
    mesh.face([p(-w,-d,top),p(w,-d,top),p(w,d,top),p(-w,d,top)],(0,0,1))
    mesh.face([p(-w,d,bottom),p(w,d,bottom),p(w,-d,bottom),p(-w,-d,bottom)],(0,0,-1))


def cylinder(mesh, centre, radius, bottom, top, sides=10, top_radius=None):
    cx,cy=centre;upper=radius if top_radius is None else top_radius
    for i in range(sides):
        a,b=i*math.tau/sides,(i+1)*math.tau/sides
        pa=(cx+math.cos(a)*radius,cy+math.sin(a)*radius)
        pb=(cx+math.cos(b)*radius,cy+math.sin(b)*radius)
        qa=(cx+math.cos(a)*upper,cy+math.sin(a)*upper)
        qb=(cx+math.cos(b)*upper,cy+math.sin(b)*upper)
        mid=(a+b)/2
        mesh.face([mesh.vertex(pa,bottom),mesh.vertex(pb,bottom),mesh.vertex(qb,top),mesh.vertex(qa,top)],(math.cos(mid),-math.sin(mid),0))
        mesh.face([mesh.vertex((cx,cy),top),mesh.vertex(qa,top),mesh.vertex(qb,top)],(0,0,1))


def crown(mesh, centre, radii, seed=0, sides=12, rings=7):
    """Irregular smooth canopy lobes; an authored proxy, not a surveyed species."""
    cx,cy,cz=centre;rx,ry,rz=radii
    def vertex(i,j):
        phi=math.pi*i/rings;theta=math.tau*j/sides
        ripple=1+.07*math.sin(theta*3+seed)*math.sin(phi)**2
        normal=(math.sin(phi)*math.cos(theta)/rx,-math.sin(phi)*math.sin(theta)/ry,math.cos(phi)/rz)
        length=math.sqrt(sum(v*v for v in normal));normal=tuple(v/length for v in normal)
        return mesh.vertex((cx+rx*math.sin(phi)*math.cos(theta)*ripple,cy+ry*math.sin(phi)*math.sin(theta)*ripple),cz+rz*math.cos(phi)*ripple),normal
    for i in range(rings):
        for j in range(sides):
            corners=[vertex(i,j),vertex(i+1,j),vertex(i+1,j+1),vertex(i,j+1)]
            if i==0:corners=corners[:3]
            elif i==rings-1:corners=[corners[0],corners[1],corners[3]]
            mesh.face([p for p,n in corners],corners[0][1])
            mesh.normals[-len(corners):]=[list(n) for p,n in corners]
