"""Bake only the additive lane study; preserve reference and source assets."""
import hashlib,json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2];CONTENT=ROOT/'unreal/AIWorld/Content'
source=json.loads((ROOT/'unreal/assets/paris-lane/Generated/lane.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/Reference';(CONTENT/'ParisPhotoreal/Reference').mkdir(parents=True,exist_ok=True)


def node(mat,cls,**props):
    result=lib.create_material_expression(mat,cls)
    if props:result.set_editor_properties(props)
    return result


def custom(mat,code,inputs,dim=3):
    result=node(mat,unreal.MaterialExpressionCustom,code=code,output_type={1:unreal.CustomMaterialOutputType.CMOT_FLOAT1,2:unreal.CustomMaterialOutputType.CMOT_FLOAT2,3:unreal.CustomMaterialOutputType.CMOT_FLOAT3}[dim]);pins=[]
    for name in inputs:
        pin=unreal.CustomInput();pin.set_editor_property('input_name',name);pins.append(pin)
    result.set_editor_property('inputs',pins)
    for name,(expression,pin) in inputs.items():
        if not lib.connect_material_expressions(expression,pin,result,name):raise RuntimeError('Lane material input '+name)
    return result


def output(mat,n,prop):
    if not lib.connect_material_property(n,'',prop):raise RuntimeError('Lane material output')


def save(asset):
    if not assets.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Lane save failed '+asset.get_path_name())


name='M_ParisLanePaving';path='/Game/Materials/'+name
mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
lib.delete_all_material_expressions(mat);mat.set_editor_properties(dict(two_sided=True,tangent_space_normal=False,shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT));lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
pos=node(mat,unreal.MaterialExpressionWorldPosition);normal=node(mat,unreal.MaterialExpressionVertexNormalWS)
collection=assets.load_asset('/Game/Weather/MPC_ParisWeather')
if not collection:raise RuntimeError('Existing weather collection missing')
wet=node(mat,unreal.MaterialExpressionCollectionParameter,collection=collection,parameter_name='Wetness')
axis=source['lane']['street_axis'];axis_hlsl='float2('+','.join(f'{v:.10f}' for v in axis)+')'
camera=source['camera'];eye=camera['eye_cm'];origin_hlsl='float2('+','.join(f'{v:.8f}' for v in eye[:2])+')'
photo_uv=custom(mat,'return P.xy/250.;',dict(P=(pos,'')),2)
def photo(role,sampler):
    tex=assets.load_asset('/Game/Textures/T_ParisPhotoPaving'+role)
    if not tex:raise RuntimeError('Existing paving photo missing '+role)
    n=node(mat,unreal.MaterialExpressionTextureSample,texture=tex,sampler_type=sampler);lib.connect_material_expressions(photo_uv,'',n,'UVs');return n
albedo=photo('Albedo',unreal.MaterialSamplerType.SAMPLERTYPE_COLOR);photo_normal=photo('Normal',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL);orm=photo('Orm',unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
pattern=f'''float2 axis={axis_hlsl};float2 uv=float2(dot(P.xy,axis),dot(P.xy,float2(-axis.y,axis.x)));
float2 delta=P.xy-{origin_hlsl};float along=dot(delta,axis);float across=dot(delta,float2(-axis.y,axis.x));float zone=(abs(across)<650.&&along>-1000.&&along<7500.)?1.:0.;
float row=floor(uv.y/100.);float parity=row-2.*floor(row*.5);float cell=floor((uv.x+parity*95.)/190.);
float2 q=float2(frac((uv.x+parity*95.)/190.)*190.-95.,frac(uv.y/100.)*100.+95.);
float radius=length(q);float band=floor(radius/10.5);float radial=frac(radius/10.5);float angular=atan2(q.x,q.y)*(band*10.5+5.25)/11.5+(band-2.*floor(band*.5))*.5;
float f=frac(angular);float edge=min(min(radial,1.-radial)*10.5,min(f,1.-f)*11.5);
float aa=max(fwidth(edge)*.55,.025);float stone=smoothstep(.11-aa,.43+aa,edge);
float seed=frac(sin(dot(float2(band+cell*17.,floor(angular)+row*13.),float2(127.1,311.7)))*43758.5453);
float grain=.96+.04*sin(P.x*2.71+sin(P.y*1.83))*cos(P.y*3.13);
float macro=.5+.5*sin(P.x*.0041)*sin(P.y*.0033);
'''
inputs=dict(P=(pos,''),W=(wet,''))
color=custom(mat,pattern+'float3 granite=lerp(float3(.065,.072,.068),float3(.12,.125,.118),seed)*grain*(.85+.3*saturate(dot(A,float3(.3,.59,.11))));float damp=lerp(1.,.68,saturate(W));float3 fan=lerp(float3(.042,.045,.041),granite,stone)*(.93+.07*macro);float3 regular=A*float3(.93,.94,.91)*(.94+.07*sin(P.x*.0008)*sin(P.y*.0011));return lerp(regular,fan,zone)*damp;',dict(**inputs,A=(albedo,'RGB')))
output(mat,color,unreal.MaterialProperty.MP_BASE_COLOR)
rough=custom(mat,pattern+'return lerp(lerp(.94,.77,stone),.32,saturate(W)*(.75+.25*macro));',inputs,1);output(mat,rough,unreal.MaterialProperty.MP_ROUGHNESS)
height=custom(mat,pattern+'return stone*.24*zone;',inputs,1)
bump=custom(mat,'float3 N=normalize(G);float3 T=normalize(float3(1,0,0)-N*N.x),B=normalize(cross(N,T));N=normalize(T*S.x*.30+B*S.y*.30+N*max(S.z,.5));float3 dx=ddx(P),dy=ddy(P),a=cross(dy,N),b=cross(N,dx);float d=dot(dx,a);if(abs(d)<1.e-6)return N;return normalize(abs(d)*N-sign(d)*(ddx(H)*a+ddy(H)*b));',dict(P=(pos,''),G=(normal,''),H=(height,''),S=(photo_normal,'RGB')))
output(mat,bump,unreal.MaterialProperty.MP_NORMAL);output(mat,node(mat,unreal.MaterialExpressionConstant,r=.3),unreal.MaterialProperty.MP_SPECULAR)
errors=lib.recompile_material(mat)
if errors:raise RuntimeError('Paving shader compile errors '+str(errors))
assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Inferred fan-set granite, metric 10-12cm stones; mapped sett street; not a survey of laying pattern');save(mat)

path='/Game/Materials/M_ParisLaneWood'
wood=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/Materials/M_ParisWood',path)
if not wood:raise RuntimeError('Existing photographic timber missing')
if assets.get_metadata_tag(wood,'ParisTwin.LaneWood')!='weathered_planter_v2':
    base=lib.get_material_property_input_node(wood,unreal.MaterialProperty.MP_BASE_COLOR);pin=lib.get_material_property_input_node_output_name(wood,unreal.MaterialProperty.MP_BASE_COLOR)
    color=custom(wood,'float grain=saturate(dot(C,float3(.3,.59,.11))*8.);return float3(.31,.23,.14)*lerp(.72,1.18,grain);',dict(C=(base,pin)));output(wood,color,unreal.MaterialProperty.MP_BASE_COLOR)
    lib.set_material_usage(wood,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES);lib.recompile_material(wood);assets.set_metadata_tag(wood,'ParisTwin.LaneWood','weathered_planter_v2');save(wood)

runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[]
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        if 'positions_cm' not in item:raise RuntimeError('Required base reference model missing '+package)
        def linear(b):
            c=b/255;return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
        buf=unreal.GeometryScriptSimpleMeshBuffers();buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(v) for v in c[:3]],c[3]/255) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,_=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Lane mesh creation failed '+package)
        material=assets.load_asset(item['material'])
        if not material:raise RuntimeError('Lane material missing '+item['material'])
        mesh.set_material(0,material);mesh.set_editor_property('allow_cpu_access',True);assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mesh)
    runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')})
(CONTENT/'Data/paris-lane.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_LANE_ASSETS_READY')
