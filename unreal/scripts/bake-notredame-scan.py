"""Bake observed facade surface and coverage-controlled underlays. GIS stays intact."""
import array
import hashlib
import json
import os
import struct
import unreal

ROOT=os.path.realpath(os.path.join(os.path.dirname(__file__),'..','..'))
DATA=os.path.join(unreal.Paths.project_content_dir(),'Data')
with open(os.path.join(DATA,'paris-notredame-scan-source.json'),encoding='utf-8') as f:source=json.load(f)
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/NotreDameScan'
os.makedirs(os.path.realpath(os.path.join(unreal.Paths.project_content_dir(),'ParisPhotoreal','NotreDameScan')),exist_ok=True)
assets.make_directory(folder)
with open(__file__,'rb') as f:recipe=hashlib.sha256(f.read().replace(b'\r\n',b'\n')).hexdigest()
frame=source['local_frame'];xyz=lambda a:'float3('+','.join(str(v) for v in a)+')'
local=f'float3 d=(Position-{xyz(frame["front_cm"])})*.01;float x=dot(d,{xyz(frame["across"])}),y=dot(d,{xyz(frame["depth"])}),z=d.z;'


def node(mat,cls,**properties):
    v=lib.create_material_expression(mat,cls,0,0)
    if properties:v.set_editor_properties(properties)
    return v


def link(a,out,b,pin):
    if not lib.connect_material_expressions(a,out,b,pin):raise RuntimeError('Scanned facade material pin failed: '+pin)


def output(n,out,p):
    if not lib.connect_material_property(n,out,p):raise RuntimeError('Scanned facade material output failed')


def custom(mat,code,pins,kind=unreal.CustomMaterialOutputType.CMOT_FLOAT1):
    n=node(mat,unreal.MaterialExpressionCustom,code=code,output_type=kind)
    inputs=[]
    for name in pins:
        p=unreal.CustomInput();p.set_editor_property('input_name',name);inputs.append(p)
    n.set_editor_property('inputs',inputs)
    for name,(v,out) in pins.items():link(v,out,n,name)
    return n


def save(mat):
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat,'ParisTwin.SourceURL',source['source']['source_url'])
    assets.set_metadata_tag(mat,'ParisTwin.License','CC-BY-4.0')
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',source['provenance'])
    if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot persist facade material')


textures={}
for key,item in source['textures'].items():
    filename=os.path.join(ROOT,item['file'])
    with open(filename,'rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=item['sha256']:raise RuntimeError('Changed facade texture')
    name='T_NDScan_'+key+'_'+item['sha256'][:10];path=folder+'/'+name
    tex=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not tex:
        task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=filename,destination_path=folder,destination_name=name,automated=True,save=True))
        tools.import_asset_tasks([task]);tex=assets.load_asset(path)
    if not tex:raise RuntimeError('Facade texture import failed')
    tex.set_editor_property('srgb',key=='colour')
    tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if key=='normal' else unreal.TextureCompressionSettings.TC_MASKS if key=='coverage' else unreal.TextureCompressionSettings.TC_DEFAULT)
    tex.set_editor_property('max_texture_size',4096)
    if key=='normal':tex.set_editor_property('flip_green_channel',False)
    assets.set_metadata_tag(tex,'ParisTwin.License','CC-BY-4.0');assets.set_metadata_tag(tex,'ParisTwin.SourceURL',source['source']['source_url'])
    if not assets.save_loaded_asset(tex):raise RuntimeError('Cannot save facade texture')
    textures[key]=tex

signature=hashlib.sha256((recipe+json.dumps(source,sort_keys=True)).encode()).hexdigest()[:12]
name='M_NDScan_Surface_'+signature;surface=assets.load_asset(folder+'/'+name) if assets.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
lib.delete_all_material_expressions(surface);surface.set_editor_property('two_sided',True);surface.set_editor_property('tangent_space_normal',False)
colour=node(surface,unreal.MaterialExpressionTextureSample,texture=textures['colour'],sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
# The photographs carry their original illumination. This explicit art
# calibration matches the existing stone; it is not a measured albedo recovery.
tint=node(surface,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.72,.64,.52,1))
matched=node(surface,unreal.MaterialExpressionMultiply);link(colour,'RGB',matched,'A');link(tint,'',matched,'B')
output(matched,'',unreal.MaterialProperty.MP_BASE_COLOR)
normal=node(surface,unreal.MaterialExpressionTextureSample,texture=textures['normal'],sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
worldnormal=custom(surface,f'return normalize(.35*N.x*{xyz(frame["across"])}-.35*N.y*float3(0,0,1)-N.z*{xyz(frame["depth"])});',{'N':(normal,'RGB')},unreal.CustomMaterialOutputType.CMOT_FLOAT3)
output(worldnormal,'',unreal.MaterialProperty.MP_NORMAL)
output(node(surface,unreal.MaterialExpressionConstant,r=.82),'',unreal.MaterialProperty.MP_ROUGHNESS)
output(node(surface,unreal.MaterialExpressionConstant,r=0.),'',unreal.MaterialProperty.MP_METALLIC)
save(surface)

underlays={}
bases=dict(stone='M_ParisLimestone',wood='M_ParisWood',glass='M_ParisGlass',iron='M_ParisIron',sculpture='M_ParisSculptedStone',stained='M_ParisStainedGlass',body='M_ParisCathedralStone')
for key,base in bases.items():
    original=assets.load_asset('/Game/Materials/'+base)
    if not original:raise RuntimeError('Underlying material is missing: '+base)
    mask_code=local+'return (abs(x)<21.75&&z>=0&&z<45&&y>-5&&y<8)?1-Active*(Coverage>.85?1:0):1;'
    identity=hashlib.sha256((mask_code+source['textures']['coverage']['sha256']+base+assets.get_metadata_tag(original,'ParisTwin.PhotoGenerator')).encode()).hexdigest()[:12]
    path=folder+'/M_NDScan_Underlay_'+key+'_'+identity
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/Materials/'+base,path)
    if not mat:raise RuntimeError('Cannot preserve underlying material graph')
    if assets.get_metadata_tag(mat,'ParisTwin.ScanUnderlay')!=identity:
        position=node(mat,unreal.MaterialExpressionWorldPosition)
        uv=custom(mat,local+'return float2((x+21.75)/43.5,1-z/45);',{'Position':(position,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
        coverage=node(mat,unreal.MaterialExpressionTextureSample,texture=textures['coverage'],sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        link(uv,'',coverage,'UVs')
        active=node(mat,unreal.MaterialExpressionScalarParameter,parameter_name='NDScanActive',default_value=1. if key=='body' else 0.)
        mask=custom(mat,mask_code,{'Position':(position,''),'Coverage':(coverage,'R'),'Active':(active,'')})
        if key=='body':
            westpath=os.path.join(os.path.dirname(__file__),'notredame_west.py');scope={'__name__':'notredame_west','__file__':westpath}
            with open(westpath,encoding='utf-8') as f:exec(compile(f.read(),westpath,'exec'),scope)
            original_mask=custom(mat,scope['display_mask_hlsl'](frame),{'Position':(position,'')})
            multiply=node(mat,unreal.MaterialExpressionMultiply);link(mask,'',multiply,'A');link(original_mask,'',multiply,'B');mask=multiply
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED);output(mask,'',unreal.MaterialProperty.MP_OPACITY_MASK)
        assets.set_metadata_tag(mat,'ParisTwin.ScanUnderlay',identity);save(mat)
    underlays[key]=path

mesh=assets.load_asset(source['asset']) if assets.does_asset_exist(source['asset']) else None
if not mesh:
    with open(os.path.join(ROOT,source['binary']),'rb') as f:blob=f.read()
    if hashlib.sha256(blob).hexdigest()!=source['geometry_sha256']:raise RuntimeError('Facade surface binary changed')
    magic,n,t=struct.unpack_from('<8sII',blob)
    if magic!=b'NDSCAN01':raise RuntimeError('Unrecognized scan binary')
    floats=array.array('f');floats.frombytes(blob[16:16+n*32]);indices=array.array('I');indices.frombytes(blob[16+n*32:])
    if len(indices)!=t*3:raise RuntimeError('Incomplete surface indices')
    buf=unreal.GeometryScriptSimpleMeshBuffers()
    buf.set_editor_properties(dict(vertices=[unreal.Vector(*floats[i*3:i*3+3]) for i in range(n)],
        normals=[unreal.Vector(*floats[n*3+i*3:n*3+i*3+3]) for i in range(n)],
        uv0=[unreal.Vector2D(*floats[n*6+i*2:n*6+i*2+2]) for i in range(n)],
        triangles=[unreal.IntVector(*indices[i:i+3]) for i in range(0,len(indices),3)]))
    dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
    opts=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    opts.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=True,use_original_vertex_order=True))
    mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,source['asset'],opts)
    if not mesh:raise RuntimeError('Cannot create the observed facade surface')
mesh.set_material(0,surface)
settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',True)
settings.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED)
settings.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
settings.set_editor_property('fallback_percent_triangles',1.);settings.set_editor_property('fallback_relative_error',0.)
mesh.set_editor_property('nanite_settings',settings);mesh.set_editor_property('allow_cpu_access',True)
for key,value in dict(SourceURL=source['source']['source_url'],License='CC-BY-4.0',Author=source['source']['author'],SourceID=source['source_id'],GeometryProvenance=source['provenance']).items():assets.set_metadata_tag(mesh,'ParisTwin.'+key,value)
if not assets.save_loaded_asset(mesh):raise RuntimeError('Cannot save the real observed facade mesh')
runtime=dict(source,underlays=underlays,surface_material=surface.get_path_name(),fallback_triangles=mesh.get_num_triangles(0),
    material_calibration=dict(albedo_multiplier_linear=[.72,.64,.52],normal_strength=.35,estimated_roughness=.82,
        note='Visual matching to existing stone. Original photographed illumination remains; not calibrated survey albedo.'))
with open(os.path.join(DATA,'paris-notredame-scan.json'),'w',encoding='utf-8') as f:json.dump(runtime,f,indent=2)
unreal.log_warning('PARIS_SCANNED_FACADE_READY '+str(runtime['triangles']))
