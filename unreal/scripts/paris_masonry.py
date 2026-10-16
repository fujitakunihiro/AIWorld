"""Inferred dressed-stone finish, in UE centimetres; no surveyed course claim."""
COURSE_HEIGHT_CM=32.
COURSE_WIDTH_CM=88.
JOINT_HALF_CM=.14
JOINT_TRANSITION_CM=.13
RELIEF_CM=.04
MICRO_NORMAL_STRENGTH=.20


def course_hlsl():
    return f'''
float3 G=normalize(Geometric);
float3 T=float3(G.y,-G.x,0); T=length(T)>.05?normalize(T):float3(1,0,0);
float row=floor(Position.z/{COURSE_HEIGHT_CM});
float stagger=(row-2*floor(row*.5))*.5;
float u=dot(Position,T)/{COURSE_WIDTH_CM}+stagger;
float v=Position.z/{COURSE_HEIGHT_CM};
float2 cell=frac(float2(u,v));
float edge=min(min(cell.x,1-cell.x)*{COURSE_WIDTH_CM},min(cell.y,1-cell.y)*{COURSE_HEIGHT_CM});
float aa=max(fwidth(edge)*.55,.015);
float stone=smoothstep({JOINT_HALF_CM}-aa,{JOINT_HALF_CM+JOINT_TRANSITION_CM}+aa,edge);
stone=lerp(1,stone,saturate(1-abs(G.z)*4));
float block=frac(sin(dot(float2(floor(u),row),float2(127.1,311.7)))*43758.5453);
'''


def color_hlsl():
    return course_hlsl()+'''
float broad=sin(dot(Position.xy,float2(.0037,.0041)))*sin(Position.z*.0028);
float variation=.97+.06*block+.018*broad;
return Albedo*float3(1,.965,.90)*variation*lerp(.58,1,stone);
'''


def normal_hlsl():
    return course_hlsl()+f'''
float3 N=normalize(lerp(G,Photo,{MICRO_NORMAL_STRENGTH}));
float h=stone*{RELIEF_CM};
float3 dx=ddx(Position),dy=ddy(Position),a=cross(dy,N),b=cross(N,dx);
float det=dot(dx,a);
if(abs(det)<1e-6)return N;
return normalize(abs(det)*N-sign(det)*(ddx(h)*a+ddy(h)*b));
'''
