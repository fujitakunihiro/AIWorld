"""Bake road PBR finishes and cosmetic street-edge geometry offline."""
import hashlib
import json
import os
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
CONTENT=ROOT/'unreal/AIWorld/Content'
SOURCE=ROOT/'unreal/textures/paris-roads'
data=json.loads((CONTENT/'Data/paris-road-detail-source.json').read_text(encoding='utf-8'))
lib=unreal.MaterialEditingLibrary;assets=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()


def node(mat, cls, **props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def link(a,out,b,pin):
    if not lib.connect_material_expressions(a,out,b,pin):raise RuntimeError('Road material pin: '+pin)


def custom(mat,code,inputs,dimensions=3):
    n=node(mat,unreal.MaterialExpressionCustom,code=code,
           output_type={1:unreal.CustomMaterialOutputType.CMOT_FLOAT1,2:unreal.CustomMaterialOutputType.CMOT_FLOAT2,3:unreal.CustomMaterialOutputType.CMOT_FLOAT3}[dimensions])
    pins=[]
    for key in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',key);pins.append(p)
    n.set_editor_property('inputs',pins)
    for key,(a,out) in inputs.items():link(a,out,n,key)
    return n


def output(n,prop,out=''):
    if not lib.connect_material_property(n,out,prop):raise RuntimeError('Road material output failed')


def scalar(mat,name,value):return node(mat,unreal.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)


def sample(mat,texture,uv,kind='color'):
    if not texture:raise RuntimeError('Missing verified photographic road texture')
    n=node(mat,unreal.MaterialExpressionTextureSample,texture=texture,sampler_type={
        'color':unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,'normal':unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        'mask':unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,'linear':unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR}[kind])
    link(uv,'',n,'UVs');return n


def import_mask(name,file,uncompressed=False):
    path=SOURCE/file
    if hashlib.sha256(path.read_bytes()).hexdigest()!=data['files'][file]:raise RuntimeError('Changed original road texture')
    task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(path),destination_path='/Game/Textures',destination_name=name,automated=True,replace_existing=True,save=True))
    tools.import_asset_tasks([task]);t=assets.load_asset('/Game/Textures/'+name)
    if not t:raise RuntimeError('Road texture import failed')
    t.set_editor_properties(dict(srgb=False,compression_settings=unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP if uncompressed else unreal.TextureCompressionSettings.TC_MASKS,
        address_x=unreal.TextureAddress.TA_CLAMP if uncompressed else unreal.TextureAddress.TA_WRAP,address_y=unreal.TextureAddress.TA_CLAMP if uncompressed else unreal.TextureAddress.TA_WRAP))
    assets.save_loaded_asset(t,only_if_is_dirty=False);return t


edge=import_mask('T_ParisRoadEdge','road-edge-distance.png',True)
age=import_mask('T_ParisRoadAge','road-age-mask.png')


def material(name):
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True);mat.set_editor_property('tangent_space_normal',False)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    return mat


def finish(mat):
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.RoadRecipe',data['recipe'])
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',data['appearance_provenance'])
    assets.save_loaded_asset(mat,only_if_is_dirty=False)


for kind,name in [('asphalt','M_ParisRoadAsphalt'),('sidewalk','M_ParisRoadSidewalk'),('paving','M_ParisRoadPaving'),('kerb','M_ParisRoadKerb')]:
    mat=material(name);pos=node(mat,unreal.MaterialExpressionWorldPosition);geom=node(mat,unreal.MaterialExpressionVertexNormalWS)
    b=data['atlas_bounds_cm']
    atlas_uv=custom(mat,f'return (Position.xy-float2({b[0]},{b[1]}))/float2({b[2]-b[0]},{b[3]-b[1]});',{'Position':(pos,'')},2)
    atlas=sample(mat,edge,atlas_uv,'linear')
    distance=custom(mat,'float2 m=min(UV,1.-UV);float valid=step(0.,min(m.x,m.y));return lerp(10000.,(Packed.r*65280.+Packed.g*255.)/65535.*6400.-3200.,valid);',{'Packed':(atlas,'RGBA'),'UV':(atlas_uv,'')},1)
    if kind=='sidewalk':
        uv=custom(mat,'float2 d=normalize(Packed.ba*2.-1.);return float2(dot(Position.xy,d),dot(Position.xy,float2(-d.y,d.x)))/100.;',{'Position':(pos,''),'Packed':(atlas,'RGBA')},2)
    elif kind=='kerb':
        uv=custom(mat,'float3 a=abs(N);return (a.z>.5?Position.xy:(a.x>a.y?Position.yz:Position.xz))/100.;',{'Position':(pos,''),'N':(geom,'')},2)
    else:uv=custom(mat,'return Position.xy/'+('300.' if kind=='asphalt' else '250.')+';',{'Position':(pos,'')},2)
    photo='Asphalt' if kind=='asphalt' else 'Paving' if kind=='paving' else 'Stone'
    samples={role:sample(mat,assets.load_asset('/Game/Textures/T_ParisPhoto'+photo+role.title()),uv,'normal' if role=='normal' else 'mask' if role=='orm' else 'color') for role in ('albedo','normal','orm')}
    common={'Position':(pos,''),'Albedo':(samples['albedo'],'RGB'),'Distance':(distance,''),'UV':(uv,'')}
    if kind=='asphalt':
        wear_uv=custom(mat,'return Position.xy/1200.;',{'Position':(pos,'')},2)
        wear=sample(mat,age,wear_uv,'mask');common['Wear']=(wear,'RGBA')
        # A second rotated photo breaks the obvious 3m repeat. Transform its
        # normal back to XY before combining it with the first sample.
        uv2=custom(mat,'return float2(-UV.y,UV.x)*.793+float2(.31,.67);',{'UV':(uv,'')},2)
        second={role:sample(mat,assets.load_asset('/Game/Textures/T_ParisPhotoAsphalt'+role.title()),uv2,'normal' if role=='normal' else 'mask' if role=='orm' else 'color') for role in ('albedo','normal','orm')}
        common['Second']=(second['albedo'],'RGB')
        color=custom(mat,'float m=.5+.5*sin(Position.x*.00091+sin(Position.y*.00073));float3 c=lerp(Albedo,Second,.25+.35*m);float gutter=(1.-smoothstep(8.,80.,max(Distance,0.)))*(.5+.5*Wear.b);c*=lerp(.88,1.08,Wear.b);c*=1.-Wear.r*.19;c*=1.-Wear.g*.40;c*=1.-gutter*.20;return c*float3(.93,.96,1.);',common)
        color=custom(mat,'return Color*Brightness;',{'Color':(color,''),'Brightness':(scalar(mat,'AsphaltBrightness',.62),'')})
        rough=custom(mat,'return clamp(lerp(ORM.g,Second.g,.4)*.35+.55-Wear.r*.13-Wear.a*.09,.55,.95);',{'ORM':(samples['orm'],'RGB'),'Second':(second['orm'],'RGB'),'Wear':(wear,'RGBA')},1)
        local=custom(mat,'float2 s=lerp(N.xy,float2(Second.y,-Second.x),.42)*.72;return normalize(float3(s,1.));',{'N':(samples['normal'],'RGB'),'Second':(second['normal'],'RGB')})
        relief=custom(mat,'return -Wear.g*.10-Wear.a*.055;',{'Wear':(wear,'RGBA')},1)
    elif kind=='sidewalk':
        # 60x40cm dressed slabs, 3mm joints; street-aligned in the source frame.
        joints=custom(mat,'float row=floor(UV.y/.4);float2 p=float2(UV.x+fmod(row,2.)*.3,UV.y);float2 f=frac(p/float2(.6,.4));float e=min(min(f.x,1.-f.x)*60.,min(f.y,1.-f.y)*40.);return smoothstep(.08,.43,e);',{'UV':(uv,'')},1)
        common['Joint']=(joints,'')
        color=custom(mat,'float2 cell=floor(float2(UV.x+fmod(floor(UV.y/.4),2.)*.3,UV.y)/float2(.6,.4));float r=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);float grain=dot(Albedo,float3(.3,.59,.11));float dirt=1.-smoothstep(10.,100.,abs(Distance));float3 c=float3(.30,.285,.25)*(.84+.20*r)*(.85+.35*grain);return c*lerp(.64,1.,Joint)*(1.-dirt*.12);',common)
        rough=custom(mat,'return lerp(.93,clamp(ORM.g*.3+.58,.7,.9),Joint);',{'ORM':(samples['orm'],'RGB'),'Joint':(joints,'')},1)
        local=samples['normal'];relief=custom(mat,'return Joint*.22;',{'Joint':(joints,'')},1)
    elif kind=='paving':
        color=custom(mat,'float macro=.94+.07*sin(Position.x*.0008)*sin(Position.y*.0011);return Albedo*float3(.93,.94,.91)*macro;',common)
        rough=custom(mat,'return clamp(ORM.g*.75+.2,.7,.97);',{'ORM':(samples['orm'],'RGB')},1)
        local=samples['normal'];relief=scalar(mat,'AdditionalReliefCm',0.)
    else:
        tint=node(mat,unreal.MaterialExpressionVertexColor);common['Tint']=(tint,'')
        color=custom(mat,'float grain=dot(Albedo,float3(.3,.59,.11));return Tint*float3(.43,.43,.40)*(.75+.45*grain);',common)
        rough=custom(mat,'return clamp(ORM.g*.35+.55,.72,.94);',{'ORM':(samples['orm'],'RGB')},1)
        local=samples['normal'];relief=scalar(mat,'AdditionalReliefCm',0.)
    normal_inputs={'Geometric':(geom,''),'Surface':(local,'RGB' if local==samples['normal'] else ''),'Height':(relief,''),'Position':(pos,'')}
    if kind=='kerb':
        code='float3 N=normalize(Geometric);float3 a=abs(N);float3 U=a.z>.5?float3(1,0,0):(a.x>a.y?float3(0,1,0):float3(1,0,0));float3 V=a.z>.5?float3(0,1,0):float3(0,0,1);return normalize(N*max(Surface.z,.5)+normalize(U-N*dot(N,U))*Surface.x*.4+normalize(V-N*dot(N,V))*Surface.y*.4);'
    else:
        code='float3 N=normalize(Geometric);float3 T=normalize(float3(1,0,0)-N*N.x);float3 B=normalize(cross(N,T));float3 base=normalize(T*Surface.x*.6+B*Surface.y*.6+N*max(Surface.z,.5));float3 dx=ddx(Position),dy=ddy(Position);float3 a=cross(dy,base),b=cross(base,dx);float det=dot(dx,a);if(abs(det)<1e-6)return base;return normalize(abs(det)*base-sign(det)*(ddx(Height)*a+ddy(Height)*b));'
        if kind=='sidewalk':
            normal_inputs['Packed']=(atlas,'RGBA')
            code=code.replace('float3 T=normalize(float3(1,0,0)-N*N.x);','float2 d=normalize(Packed.ba*2.-1.);float3 axis=float3(d,0.);float3 T=normalize(axis-N*dot(N,axis));')
    output(color,unreal.MaterialProperty.MP_BASE_COLOR);output(rough,unreal.MaterialProperty.MP_ROUGHNESS)
    output(custom(mat,code,normal_inputs),unreal.MaterialProperty.MP_NORMAL)
    output(scalar(mat,'Metallic',0.),unreal.MaterialProperty.MP_METALLIC)
    output(scalar(mat,'Specular',.35),unreal.MaterialProperty.MP_SPECULAR)
    output(scalar(mat,'Occlusion',1.),unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    finish(mat)

mat=material('M_ParisRoadIron');tint=node(mat,unreal.MaterialExpressionVertexColor)
color=custom(mat,'return Color*float3(.31,.29,.255);',{'Color':(tint,'')})
output(color,unreal.MaterialProperty.MP_BASE_COLOR);output(scalar(mat,'Metallic',.7),unreal.MaterialProperty.MP_METALLIC)
output(scalar(mat,'Roughness',.78),unreal.MaterialProperty.MP_ROUGHNESS);finish(mat)

runtime={k:v for k,v in data.items() if k!='objects'};runtime['objects']=[]
assets.make_directory('/Game/ParisPhotoreal/Roads')
os.makedirs(CONTENT/'ParisPhotoreal/Roads',exist_ok=True)
for item in data['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        buf=unreal.GeometryScriptSimpleMeshBuffers()
        buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],
            uv0=[unreal.Vector2D(0,0)]*len(item['normals']),vertex_colors=[unreal.LinearColor(*c) for c in item['vertex_colors']],
            triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Road detail bake failed: '+package)
    mesh.set_material(0,assets.load_asset(item['material']));mesh.set_editor_property('allow_cpu_access',True)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256'])
    assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',data['appearance_provenance'])
    assets.save_loaded_asset(mesh,only_if_is_dirty=False)
    runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')})
(CONTENT/'Data/paris-road-detail.json').write_text(json.dumps(runtime,indent=2,allow_nan=False)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_ROAD_ASSETS_READY')
