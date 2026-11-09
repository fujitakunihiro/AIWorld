"""Import original photo-guided florist geometry and dedicated PBR materials."""
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
source=json.loads((ROOT/'unreal/assets/paris-florist/Generated/display.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/Florist';(ROOT/'unreal/AIWorld/Content/ParisPhotoreal/Florist').mkdir(parents=True,exist_ok=True);assets.make_directory(folder)


def save(obj):
    if not assets.save_loaded_asset(obj,only_if_is_dirty=False):raise RuntimeError('Florist save failed '+obj.get_path_name())


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def connect(mat,n,prop):
    if not lib.connect_material_property(n,'',prop):raise RuntimeError('Florist material connection failed')


materials={}
for role,rough,metal in [('wicker',.83,0),('timber',.78,0),('metal',.39,.8),('foliage',.57,0),('petals',.62,0),('paint',.53,0),('cloth',.92,0),('slates',.91,0)]:
    name='M_ParisFlorist_'+role;path=folder+'/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat);plant=role in ('foliage','petals')
    mat.set_editor_properties(dict(two_sided=plant or role=='cloth',shading_model=unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE if plant else unreal.MaterialShadingModel.MSM_DEFAULT_LIT))
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    color=node(mat,unreal.MaterialExpressionVertexColor);pos=node(mat,unreal.MaterialExpressionWorldPosition)
    detail=node(mat,unreal.MaterialExpressionCustom,code='float grain=sin(P.x*2.7+sin(P.z*1.3))*sin(P.y*3.2);return C.rgb*(.96+.04*grain);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins=[]
    for key in ['C','P']:
        pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
    detail.set_editor_property('inputs',pins)
    for key,expr in [('C',color),('P',pos)]:
        if not lib.connect_material_expressions(expr,'',detail,key):raise RuntimeError('Florist shader input')
    connect(mat,detail,unreal.MaterialProperty.MP_BASE_COLOR)
    connect(mat,node(mat,unreal.MaterialExpressionConstant,r=rough),unreal.MaterialProperty.MP_ROUGHNESS)
    connect(mat,node(mat,unreal.MaterialExpressionConstant,r=metal),unreal.MaterialProperty.MP_METALLIC)
    if plant:
        sub=node(mat,unreal.MaterialExpressionMultiply,const_b=.38 if role=='petals' else .22);lib.connect_material_expressions(color,'',sub,'A');connect(mat,sub,unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        connect(mat,node(mat,unreal.MaterialExpressionConstant,r=.55),unreal.MaterialProperty.MP_OPACITY)
    if lib.recompile_material(mat):raise RuntimeError('Florist shader compile failed '+role)
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mat);materials[role]=mat


def linear(v):
    v=v/255.;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4


runtime={k:v for k,v in source.items() if k!='models'};runtime['models']=[]
for item in source['models']:
    path=item['asset'];mesh=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not mesh:
        buf=unreal.GeometryScriptSimpleMeshBuffers();buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(v) for v in c[:3]],c[3]/255) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,_=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,path,options)
        if not mesh:raise RuntimeError('Florist mesh creation failed '+path)
    mesh.set_material(0,materials[item['id']]);mesh.set_editor_property('allow_cpu_access',True)
    assets.set_metadata_tag(mesh,'ParisTwin.ReferenceSHA256',source['reference_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mesh)
    runtime['models'].append({k:item[k] for k in ('id','asset','geometry_sha256','triangles')})
(ROOT/'unreal/AIWorld/Content/Data/paris-florist.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_FLORIST_ASSETS_READY')
