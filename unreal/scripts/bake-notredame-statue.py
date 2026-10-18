"""Bake the optional, explicitly licensed noncommercial Virgin scan."""
import array
import hashlib
import json
import os
import struct
import unreal

ROOT=os.path.realpath(os.path.join(os.path.dirname(__file__),'..','..'))
DATA=os.path.join(unreal.Paths.project_content_dir(),'Data')
with open(os.path.join(DATA,'paris-notredame-statue-source.json'),encoding='utf-8') as stream:source=json.load(stream)
if source['license']!='CC-BY-NC-4.0' or source['use_scope']!='personal_noncommercial':raise RuntimeError('Personal NC scope is required')
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/NotreDameStatues'
os.makedirs(os.path.realpath(os.path.join(unreal.Paths.project_content_dir(),'ParisPhotoreal','NotreDameStatues')),exist_ok=True)
assets.make_directory(folder)
with open(__file__,'rb') as stream:recipe=hashlib.sha256(stream.read().replace(b'\r\n',b'\n')).hexdigest()
def checked(filename,expected):
    with open(os.path.join(ROOT,filename),'rb') as stream:data=stream.read()
    if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError('Sculpture content hash mismatch: '+filename)
    return data
checked(source['texture']['file'],source['texture']['sha256'])
texture_path=folder+'/T_VirginMary_'+source['texture']['sha256'][:12]
texture=assets.load_asset(texture_path) if assets.does_asset_exist(texture_path) else None
if not texture:
    task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=os.path.join(ROOT,source['texture']['file']),destination_path=folder,destination_name=texture_path.rsplit('/',1)[1],automated=True,save=True))
    tools.import_asset_tasks([task]);texture=assets.load_asset(texture_path)
if not texture:raise RuntimeError('Cannot import sculpture photograph')
texture.set_editor_property('srgb',True);texture.set_editor_property('max_texture_size',1024)

identity=hashlib.sha256((recipe+json.dumps(source,sort_keys=True)).encode()).hexdigest()[:12]
material_path=folder+'/M_VirginMary_'+identity
mat=assets.load_asset(material_path) if assets.does_asset_exist(material_path) else None
if not mat:
    mat=tools.create_asset(material_path.rsplit('/',1)[1],folder,unreal.Material,unreal.MaterialFactoryNew())
    mat.set_editor_property('two_sided',True);mat.set_editor_property('tangent_space_normal',False)
    def node(cls,**properties):
        v=lib.create_material_expression(mat,cls,0,0)
        if properties:v.set_editor_properties(properties)
        return v
    sample=node(unreal.MaterialExpressionTextureSample,texture=texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    tint=node(unreal.MaterialExpressionConstant,r=source['material_calibration']['albedo_multiplier'])
    colour=node(unreal.MaterialExpressionMultiply)
    if not lib.connect_material_expressions(sample,'RGB',colour,'A') or not lib.connect_material_expressions(tint,'',colour,'B'):raise RuntimeError('Sculpture colour connection failed')
    for expression,pin,prop in [(colour,'',unreal.MaterialProperty.MP_BASE_COLOR),(node(unreal.MaterialExpressionVertexNormalWS),'',unreal.MaterialProperty.MP_NORMAL),(node(unreal.MaterialExpressionConstant,r=.85),'',unreal.MaterialProperty.MP_ROUGHNESS),(node(unreal.MaterialExpressionConstant,r=0.),'',unreal.MaterialProperty.MP_METALLIC)]:
        if not lib.connect_material_property(expression,pin,prop):raise RuntimeError('Sculpture material output failed')
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    lib.recompile_material(mat)
mesh_path=folder+'/SM_VirginMary_'+source['geometry_sha256'][:12]+'_'+recipe[:8]
mesh=assets.load_asset(mesh_path) if assets.does_asset_exist(mesh_path) else None
if not mesh:
    blob=checked(source['binary'],source['geometry_sha256']);magic,n,t=struct.unpack_from('<8sII',blob)
    if magic!=b'NDSCAN01' or len(blob)!=16+n*32+t*12:raise RuntimeError('Incomplete sculpture buffers')
    floats=array.array('f');floats.frombytes(blob[16:16+n*32]);indices=array.array('I');indices.frombytes(blob[16+n*32:])
    buf=unreal.GeometryScriptSimpleMeshBuffers()
    buf.set_editor_properties(dict(vertices=[unreal.Vector(*floats[i*3:i*3+3]) for i in range(n)],normals=[unreal.Vector(*floats[n*3+i*3:n*3+i*3+3]) for i in range(n)],uv0=[unreal.Vector2D(*floats[n*6+i*2:n*6+i*2+2]) for i in range(n)],triangles=[unreal.IntVector(*indices[i:i+3]) for i in range(0,len(indices),3)]))
    dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
    options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False,use_original_vertex_order=True))
    mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,mesh_path,options)
    if not mesh:raise RuntimeError('Scanned sculpture asset creation failed')
mesh.set_material(0,mat);mesh.set_editor_property('allow_cpu_access',True)
settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',True)
settings.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED)
settings.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
settings.set_editor_property('fallback_percent_triangles',1.);settings.set_editor_property('fallback_relative_error',0.)
mesh.set_editor_property('nanite_settings',settings)
for obj in [texture,mat,mesh]:
    for key,value in dict(SourceURL=source['source_url'],Author=source['author'],License=source['license'],UseScope=source['use_scope'],SourceSHA256=source['source_sha256'],GeometryProvenance=source['provenance']).items():assets.set_metadata_tag(obj,'ParisTwin.'+key,value)
    if not assets.save_loaded_asset(obj):raise RuntimeError('Cannot persist scanned sculpture')
runtime=dict(source,asset=mesh_path,surface_material=material_path,texture_asset=texture_path,fallback_triangles=mesh.get_num_triangles(0),bake_recipe_sha256=recipe)
with open(os.path.join(DATA,'paris-notredame-statue.json'),'w',encoding='utf-8') as stream:json.dump(runtime,stream,indent=2,ensure_ascii=False)
unreal.log_warning('PARIS_SCANNED_VIRGIN_READY '+str(runtime['triangles']))
