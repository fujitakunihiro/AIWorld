"""Bake only the original Morris advertising props and their private materials."""
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
CONTENT=ROOT/'unreal/AIWorld/Content'
source=json.loads((ROOT/'unreal/assets/paris-morris/Generated/morris.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/Morris';assets.make_directory(folder);(CONTENT/'ParisPhotoreal/Morris').mkdir(parents=True,exist_ok=True)


def save(asset):
    if not assets.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Unable to save '+asset.get_path_name())


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def output(expr,prop,pin=''):
    if not lib.connect_material_property(expr,pin,prop):raise RuntimeError('Morris material output '+str(prop))


texture_name='T_ParisMorrisOriginalPosters';texture_path=folder+'/'+texture_name
task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(ROOT/'unreal/assets/paris-morris/Source/paris-morris-posters-imagegen.png'),destination_path=folder,destination_name=texture_name,automated=True,replace_existing=True,save=True))
tools.import_asset_tasks([task]);texture=assets.load_asset(texture_path)
if not texture:raise RuntimeError('Poster texture import failed')
texture.set_editor_properties(dict(srgb=True,address_x=unreal.TextureAddress.TA_CLAMP,address_y=unreal.TextureAddress.TA_CLAMP,power_of_two_mode=unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO))
assets.set_metadata_tag(texture,'ParisTwin.OriginalFictionalPosterSHA256',source['texture_sha256']);save(texture)

for name in ['M_ParisMorrisIron','M_ParisMorrisPoster']:
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided',False)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    if name.endswith('Iron'):
        base=node(mat,unreal.MaterialExpressionVertexColor)
        output(base,unreal.MaterialProperty.MP_BASE_COLOR)
        output(node(mat,unreal.MaterialExpressionConstant,r=.55),unreal.MaterialProperty.MP_METALLIC)
        output(node(mat,unreal.MaterialExpressionConstant,r=.48),unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        uv=node(mat,unreal.MaterialExpressionTextureCoordinate)
        sample=node(mat,unreal.MaterialExpressionTextureSample,texture=texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        if not lib.connect_material_expressions(uv,'',sample,'UVs'):raise RuntimeError('Poster UV input')
        output(sample,unreal.MaterialProperty.MP_BASE_COLOR,'RGB')
        output(node(mat,unreal.MaterialExpressionConstant,r=.78),unreal.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mat)

runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[]
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        def linear(b):
            v=b/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        buffers=unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*p) for p in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(b) for b in c[:3]],1) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Morris mesh bake failed '+package)
    mat=assets.load_asset(item['material'])
    if not mat:raise RuntimeError('Morris material missing '+item['material'])
    mesh.set_material(0,mat);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',False)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mesh)
    runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')})
with (CONTENT/'Data/paris-morris.json').open('w',encoding='utf-8') as f:json.dump(runtime,f,ensure_ascii=False,indent=2)
unreal.log_warning('PARIS_MORRIS_ASSETS_READY')
