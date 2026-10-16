"""Original inferred Paris-style lantern, in local UE centimetres.

Appearance is not a survey of the mapped lamp. The runtime keeps the original
OSM transform, source ID and collision proxy; these are rendering assets only.
"""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class Mesh:
    def __init__(self):
        self.positions=[];self.normals=[];self.indices=[]

    def face(self,points,normals):
        start=len(self.positions)
        if isinstance(normals[0],(int,float)):normals=[normals]*len(points)
        normals=[[v/math.sqrt(sum(x*x for x in n)) for v in n] for n in normals]
        self.positions.extend([[round(v*100,6) for v in p] for p in points]);self.normals.extend(normals)
        a,b,c=points[:3];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        reverse=sum(cross[i]*normals[0][i] for i in range(3))>0
        for i in range(1,len(points)-1):self.indices.extend([start,start+i+1,start+i] if reverse else [start,start+i,start+i+1])

    def lathe(self,profile,sides=32):
        for (z0,r0),(z1,r1) in zip(profile,profile[1:]):
            for j in range(sides):
                angles=[j*math.tau/sides,(j+1)*math.tau/sides]
                points=[(r*math.cos(a),r*math.sin(a),z) for z,r,a in [(z0,r0,angles[0]),(z0,r0,angles[1]),(z1,r1,angles[1]),(z1,r1,angles[0])]]
                slope=(r0-r1)/max(1.e-6,z1-z0)
                self.face(points,[(math.cos(a),math.sin(a),slope) for a in [angles[0],angles[1],angles[1],angles[0]]])

    def tube(self,points,r,sides=10):
        for a,b in zip(points,points[1:]):
            d=[b[i]-a[i] for i in range(3)];length=math.sqrt(sum(x*x for x in d))
            if length<1.e-8:continue
            d=[x/length for x in d];ref=(0,1,0) if abs(d[1])<.8 else (1,0,0)
            u=[d[1]*ref[2]-d[2]*ref[1],d[2]*ref[0]-d[0]*ref[2],d[0]*ref[1]-d[1]*ref[0]];m=math.sqrt(sum(x*x for x in u));u=[x/m for x in u]
            v=(d[1]*u[2]-d[2]*u[1],d[2]*u[0]-d[0]*u[2],d[0]*u[1]-d[1]*u[0])
            ring=[[u[k]*math.cos(j*math.tau/sides)+v[k]*math.sin(j*math.tau/sides) for k in range(3)] for j in range(sides)]
            for j in range(sides):
                k=(j+1)%sides
                self.face([[p[i]+r*ring[q][i] for i in range(3)] for p,q in [(a,j),(a,k),(b,k),(b,j)]],[ring[q] for q in [j,k,k,j]])

    def item(self,kind,color):
        data=dict(positions_cm=self.positions,normals=self.normals,indices=self.indices,color=color)
        sha=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return dict(id=kind,geometry_sha256=sha,asset='/Game/ParisPhotoreal/Street/SM_ParisLantern_'+kind+'_'+sha[:12],
                    material='/Game/Materials/M_ParisCastIron' if kind=='lamp_metal' else '/Game/Materials/M_ParisLanternGlass',
                    triangles=len(self.indices)//3,**data)


def generate():
    metal=Mesh();glass=Mesh()
    # Turned plinth, mouldings, tapered shaft, collar and lotus-shaped support.
    metal.lathe([(0,.20),(.04,.20),(.055,.225),(.10,.225),(.13,.19),(.17,.19),(.21,.15),(.29,.135),(.43,.125),(.49,.13),(.54,.13),(.57,.1),(.65,.095),(.69,.078),(3.28,.047),(3.31,.072),(3.35,.075),(3.39,.065),(3.45,.095),(3.51,.13),(3.54,.13),(3.57,.10),(3.66,.17),(3.7,.18),(3.73,.215)])
    for j in range(12):
        a=j*math.tau/12
        metal.tube([(.08*math.cos(a),.08*math.sin(a),.68),(.052*math.cos(a),.052*math.sin(a),3.27)],.006,8)
    # Six framed, sloping panes. No translucent shadow or sorting dependency.
    count=6
    for j in range(count):
        a,b=j*math.tau/count,(j+1)*math.tau/count
        corners=[(.19*math.cos(a),.19*math.sin(a),3.75),(.19*math.cos(b),.19*math.sin(b),3.75),(.28*math.cos(b),.28*math.sin(b),4.17),(.28*math.cos(a),.28*math.sin(a),4.17)]
        glass.face(corners,(math.cos((a+b)/2),math.sin((a+b)/2),-.09/.42))
        metal.tube([corners[0],corners[3]],.012,10)
        for z,r in [(3.74,.205),(4.18,.295)]:
            metal.tube([(r*math.cos(a),r*math.sin(a),z),(r*math.cos(b),r*math.sin(b),z)],.018,10)
        # Individual rivets and a restrained scroll on each face.
        mid=(a+b)/2
        for z,r in [(3.75,.19),(4.16,.28)]:
            x,y=r*math.cos(a),r*math.sin(a)
            metal.tube([(x,y,z-.012),(x,y,z+.012)],.019,12)
        scroll=[]
        for k in range(25):
            t=k/24;rr=.10+.095*t;zz=3.55+.15*t+.04*math.sin(t*math.tau)
            scroll.append((rr*math.cos(mid),rr*math.sin(mid),zz))
        metal.tube(scroll,.009,8)
    metal.lathe([(4.18,.31),(4.205,.31),(4.23,.27),(4.25,.265),(4.33,.085),(4.35,.08),(4.36,.055),(4.38,.055),(4.40,.035),(4.43,.052),(4.46,.033),(4.48,.003)],sides=24)
    return dict(format='paris_original_street_detail_v1',canonical_height_cm=448,
        appearance_provenance='Original inferred cast-iron Paris-style lantern; actual fixture design unverified. Original OSM placement, scale, source IDs and collision retained.',
        objects=[metal.item('lamp_metal','424746'),glass.item('lamp_glass','8c9a95')])


if __name__=='__main__':
    result=generate();out=ROOT/'unreal/AIWorld/Content/Data/paris-photo-street-source.json'
    out.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(meshes=len(result['objects']),triangles=sum(m['triangles'] for m in result['objects']))))
