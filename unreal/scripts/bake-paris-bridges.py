"""Bake original bridge meshes and photographic PBR materials into real assets."""
import hashlib
import json
import os
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2];CONTENT=ROOT/'unreal/AIWorld/Content'
source=json.loads((CONTENT/'Data/paris-bridges-source.json').read_text(encoding='utf-8'))
texture_folder=ROOT/'unreal/textures/paris-bridges';manifest=json.loads((texture_folder/'manifest.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def custom(mat,code,inputs,dimensions=3):
    n=node(mat,unreal.MaterialExpressionCustom,code=code,output_type={1:unreal.CustomMaterialOutputType.CMOT_FLOAT1,3:unreal.CustomMaterialOutputType.CMOT_FLOAT3}[dimensions]);pins=[]
    for key in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',key);pins.append(p)
    n.set_editor_property('inputs',pins)
    for key,(a,out) in inputs.items():
        if not lib.connect_material_expressions(a,out,n,key):raise RuntimeError('Bridge material pin '+key)
    return n


def output(mat,n,prop,pin=''):
    if not lib.connect_material_property(n,pin,prop):raise RuntimeError('Bridge material output')


def constant(mat,name,value):return node(mat,unreal.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)


photos={}
for role,info in manifest['maps'].items():
    path=texture_folder/info['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise RuntimeError('Unverified bridge stone')
    name='T_ParisBridgeStone_'+role;task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(path),destination_path='/Game/Textures',destination_name=name,automated=True,replace_existing=True,save=True));tools.import_asset_tasks([task]);t=assets.load_asset('/Game/Textures/'+name)
    if not t:raise RuntimeError('Bridge texture import failed')
    t.set_editor_properties(dict(srgb=role=='albedo',compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP if role=='normal' else unreal.TextureCompressionSettings.TC_MASKS if role=='orm' else unreal.TextureCompressionSettings.TC_DEFAULT))
    assets.save_loaded_asset(t,only_if_is_dirty=False);photos[role]=t


def sample(mat,t,uv,kind):
    n=node(mat,unreal.MaterialExpressionTextureSample,texture=t,sampler_type={'normal':unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,'albedo':unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,'orm':unreal.MaterialSamplerType.SAMPLERTYPE_MASKS}[kind])
    if not lib.connect_material_expressions(uv,'',n,'UVs'):raise RuntimeError('Bridge UV input')
    return n


for kind,name in [('masonry','M_ParisBridgeMasonry'),('cutstone','M_ParisBridgeCutStone'),('paving','M_ParisBridgePaving'),('iron','M_ParisBridgeIron'),('copper','M_ParisBridgeCopper')]:
    path='/Game/Materials/'+name;mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat);mat.set_editor_properties(dict(two_sided=True,tangent_space_normal=False))
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    pos=node(mat,unreal.MaterialExpressionWorldPosition);geom=node(mat,unreal.MaterialExpressionVertexNormalWS);uv=node(mat,unreal.MaterialExpressionTextureCoordinate);tint=node(mat,unreal.MaterialExpressionVertexColor)
    if kind in ('masonry','cutstone','paving'):
        tiles=photos if kind=='masonry' else {r:assets.load_asset('/Game/Textures/T_ParisPhoto'+('Stone' if kind=='cutstone' else 'Paving')+r.title()) for r in ('albedo','normal','orm')}
        if any(v is None for v in tiles.values()):raise RuntimeError('Existing photographic bridge finish is missing')
        scale=node(mat,unreal.MaterialExpressionMultiply,const_b=3. if kind=='cutstone' else 1.2 if kind=='paving' else 1.)
        lib.connect_material_expressions(uv,'',scale,'A');maps={r:sample(mat,t,scale,r) for r,t in tiles.items()}
        water=source['profiles'][0]['water_level_cm']
        color=custom(mat,f'''float wet=1.-smoothstep({water+15:.4f},{water+150:.4f},P.z+sin(P.x*.023)*8.+sin(P.y*.019)*9.);float age=.5+.5*sin(P.x*.009+sin(P.y*.021))*sin(P.z*.005);return Color*Tint*float3(.95,.96,.94)*lerp(.94,1.03,age)*lerp(float3(1,1,1),float3(.40,.46,.37),wet*.8);''',{'Color':(maps['albedo'],'RGB'),'Tint':(tint,''),'P':(pos,'')})
        rough=custom(mat,'return clamp(R*.6+.31,.58,.96);',{'R':(maps['orm'],'G')},1)
        normal=custom(mat,'''float3 N=normalize(G);float3 a=ddx(P),b=ddy(P);float2 u=ddx(UV),v=ddy(UV);float det=u.x*v.y-u.y*v.x;if(abs(det)<1e-8)return N;float3 T=normalize((a*v.y-b*u.y)/det);float3 B=normalize((-a*v.x+b*u.x)/det);return normalize(N*max(Photo.z,.55)+T*Photo.x*Strength+B*Photo.y*Strength);''',{'G':(geom,''),'P':(pos,''),'UV':(scale,''),'Photo':(maps['normal'],'RGB'),'Strength':(constant(mat,'NormalStrength',.64 if kind=='masonry' else .22),'')})
        output(mat,normal,unreal.MaterialProperty.MP_NORMAL)
        output(mat,maps['orm'],unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,'R');metallic=0.
    else:
        rgb='float3(.115,.051,.021)' if kind=='copper' else 'float3(.032,.053,.047)'
        color=custom(mat,f'float age=.5+.5*sin(P.x*.041+sin(P.y*.029))*sin(P.z*.033);return lerp({rgb},float3(.048,.092,.067),pow(age,6.)*.42)*Tint;',{'P':(pos,''),'Tint':(tint,'')})
        rough=constant(mat,'Roughness',.58);metallic=.72
    output(mat,color,unreal.MaterialProperty.MP_BASE_COLOR);output(mat,rough,unreal.MaterialProperty.MP_ROUGHNESS)
    output(mat,constant(mat,'Metallic',metallic),unreal.MaterialProperty.MP_METALLIC);output(mat,constant(mat,'Specular',.32),unreal.MaterialProperty.MP_SPECULAR)
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.BridgeRecipe',source['recipe']);assets.save_loaded_asset(mat,only_if_is_dirty=False)

runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[];runtime['collisions']=[]
for item in source['objects']:
    if item['collision_only']:
        runtime['collisions'].append({k:v for k,v in item.items() if k in ('id','bridge_id','positions_cm','normals','indices')});continue
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        folder='/Game/ParisPhotoreal/Bridges';assets.make_directory(folder);os.makedirs(CONTENT/'ParisPhotoreal/Bridges',exist_ok=True)
        buf=unreal.GeometryScriptSimpleMeshBuffers();buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*c) for c in item['vertex_colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Bridge static mesh creation failed')
    material=assets.load_asset(item['material'])
    if not material:raise RuntimeError('Missing bridge material '+item['material'])
    lib.set_material_usage(material,unreal.MaterialUsage.MATUSAGE_NANITE);assets.save_loaded_asset(material)
    mesh.set_material(0,material);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',True)
    settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',True)
    settings.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED)
    settings.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
    settings.set_editor_property('fallback_percent_triangles',1.);settings.set_editor_property('fallback_relative_error',0.)
    mesh.set_editor_property('nanite_settings',settings)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.BridgeRecipe',source['recipe']);assets.save_loaded_asset(mesh,only_if_is_dirty=False)
    runtime['objects'].append({k:item[k] for k in ('id','bridge_id','asset','material','triangles')})
(CONTENT/'Data/paris-bridges.json').write_text(json.dumps(runtime,indent=2,allow_nan=False)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_BRIDGE_ASSETS_READY')
