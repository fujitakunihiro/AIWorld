"""Bake a separate reference-look layer; keep existing GIS and festive assets."""
import hashlib,json,os,runpy
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
os.environ['PARIS_REFERENCE_NATURE']='1'
runpy.run_path(str(ROOT/'unreal/scripts/create-paris-nature.py'),run_name='__main__')
source=json.loads(Path(os.environ.get('PARIS_REFERENCE_SOURCE',ROOT/'unreal/assets/paris-reference/Generated/reference.json')).read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
path='/Game/Materials/M_ParisReferenceStone'
(ROOT/'unreal/AIWorld/Content/ParisPhotoreal/Reference').mkdir(parents=True,exist_ok=True)
mat=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Game/Materials/M_ParisLimestone',path)
if not mat:raise RuntimeError('Photographic source limestone is missing')
if assets.get_metadata_tag(mat,'ParisTwin.ReferenceRecipe')!='paris_reference_architecture_v1':
    base=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR)
    pin=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_BASE_COLOR)
    color=lib.create_material_expression(mat,unreal.MaterialExpressionCustom)
    color.set_editor_properties(dict(code='float g=dot(C.rgb,float3(.2126,.7152,.0722));return lerp(C.rgb,g.xxx,.16)*float3(1.03,1.04,1.06);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3))
    inp=unreal.CustomInput();inp.set_editor_property('input_name','C');color.set_editor_property('inputs',[inp])
    if not lib.connect_material_expressions(base,pin,color,'C'):raise RuntimeError('Reference stone input')
    if not lib.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Reference stone output')
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    assets.set_metadata_tag(mat,'ParisTwin.ReferenceRecipe','paris_reference_architecture_v1')
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Existing CC0 plaster grain and inferred limestone courses; neutral photographic tint, not sampled Paris stone')
    lib.recompile_material(mat)
    if not assets.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('Cannot save reference stone')

runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[]
sidewalk_path='/Game/Materials/M_ParisReferenceSidewalk'
sidewalk=assets.load_asset(sidewalk_path) if assets.does_asset_exist(sidewalk_path) else assets.duplicate_asset('/Game/Materials/M_ParisRoadSidewalk',sidewalk_path)
if not sidewalk:raise RuntimeError('Source photographic sidewalk missing')
if assets.get_metadata_tag(sidewalk,'ParisTwin.SafeSidewalk')!='atlas_direction_guard_v1':
    count=0
    for expression in lib.get_material_expressions(sidewalk):
        if not isinstance(expression,unreal.MaterialExpressionCustom):continue
        code=expression.get_editor_property('code');old='normalize(Packed.ba*2.-1.)'
        if old in code:
            code=code.replace(old,'(dot(Packed.ba*2.-1.,Packed.ba*2.-1.)>1.e-4?normalize(Packed.ba*2.-1.):float2(1.,0.))');expression.set_editor_property('code',code);count+=1
    if count<2:raise RuntimeError('Missing UV or normal atlas-direction guards, found '+str(count))
    errors=lib.recompile_material(sidewalk)
    if errors:raise RuntimeError('Reference sidewalk shader errors: '+str(errors))
    assets.set_metadata_tag(sidewalk,'ParisTwin.SafeSidewalk','atlas_direction_guard_v1')
    assets.set_metadata_tag(sidewalk,'ParisTwin.SafeDirectionNodes',str(count))
    if not assets.save_loaded_asset(sidewalk,only_if_is_dirty=False):raise RuntimeError('Cannot save safe sidewalk')
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if mesh and assets.get_metadata_tag(mesh,'ParisTwin.GeometrySHA256')==item['geometry_sha256'] and mesh.get_material(0) and mesh.get_material(0).get_path_name().split('.')[0]==item['material']:
        runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')});continue
    if not mesh:
        def linear(b):
            v=b/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        buffers=unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(b) for b in c[:3]],c[3]/255) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Reference mesh bake failed '+package)
    material=assets.load_asset(item['material'])
    if not material:raise RuntimeError('Reference material missing '+item['material'])
    mesh.set_material(0,material);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',False)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256'])
    assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance'])
    if not assets.save_loaded_asset(mesh,only_if_is_dirty=False):raise RuntimeError('Reference mesh save failed')
    runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')})
Path(os.environ.get('PARIS_REFERENCE_RUNTIME',ROOT/'unreal/AIWorld/Content/Data/paris-reference.json')).write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_REFERENCE_ASSETS_READY')
