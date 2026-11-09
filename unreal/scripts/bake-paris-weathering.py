"""Bake cosmetic grime without rebuilding photographic, rain or night materials."""
import json
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];CONTENT=ROOT/'unreal/AIWorld/Content'
source=json.loads((ROOT/'unreal/assets/paris-weathering/Generated/weathering.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
assets.make_directory('/Game/ParisPhotoreal/Weathering');(CONTENT/'ParisPhotoreal/Weathering').mkdir(parents=True,exist_ok=True)


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def save(a):
    if not assets.save_loaded_asset(a,only_if_is_dirty=False):raise RuntimeError('Weathering save failed '+a.get_path_name())


materials={}
for role in ('Streak','Base','RoadGrime'):
    name='M_ParisWeathering'+role;path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat);mat.set_editor_properties(dict(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT,shading_model=unreal.MaterialShadingModel.MSM_UNLIT,two_sided=True))
    uv=node(mat,unreal.MaterialExpressionTextureCoordinate);seed=node(mat,unreal.MaterialExpressionVertexColor)
    noise='''float2 p=UV;float phase=Seed.r*19.;float noise=0.;float amp=.57;
    float2 q=p*float2(8.,6.)+phase;
    [unroll]for(int j=0;j<3;j++){float2 c=floor(q);float2 f=frac(q);f=f*f*(3.-2.*f);
    float a=frac(sin(dot(c,float2(127.1,311.7)))*43758.5453);float b=frac(sin(dot(c+float2(1,0),float2(127.1,311.7)))*43758.5453);
    float c1=frac(sin(dot(c+float2(0,1),float2(127.1,311.7)))*43758.5453);float d=frac(sin(dot(c+1.,float2(127.1,311.7)))*43758.5453);
    noise+=lerp(lerp(a,b,f.x),lerp(c1,d,f.x),f.y)*amp;q=q*2.07+3.1;amp*=.5;}
    float edge=smoothstep(0.,.16,p.x)*smoothstep(0.,.16,1.-p.x);'''
    mask_code={'Streak':'''float lines=pow(saturate(sin(p.x*59.+phase+noise*2.)),12.);
    float down=smoothstep(0.,.06,p.y)*(1.-smoothstep(.32,1.,p.y));return edge*down*(lines*.25+noise*.12);''',
    'Base':'''float upward=smoothstep(.04,.82,p.y);float blotch=smoothstep(.28,.72,noise);
    return edge*upward*(.12+.24*blotch);''',
    'RoadGrime':'''float rim=1.-smoothstep(.55,1.,length((p-.5)*2.));float blotch=smoothstep(.25,.72,noise);
    return rim*(.08+.30*blotch);'''}[role]
    mask=node(mat,unreal.MaterialExpressionCustom,code=noise+mask_code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    pins=[]
    for key in ('UV','Seed'):
        pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
    mask.set_editor_property('inputs',pins)
    for expr,key in [(uv,'UV'),(seed,'Seed')]:
        if not lib.connect_material_expressions(expr,'',mask,key):raise RuntimeError('Weathering input '+key)
    black=node(mat,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(0,0,0,1))
    if not lib.connect_material_property(black,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR) or not lib.connect_material_property(mask,'',unreal.MaterialProperty.MP_OPACITY):raise RuntimeError('Weathering outputs')
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.WeatheringProvenance',source['provenance']);save(mat);materials[path]=mat

for item in source['objects']:
    mat=materials[item['material']];package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        def linear(b):
            v=b/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        buffers=unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*p) for p in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(b) for b in c[:3]],1) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Weathering mesh bake failed '+package)
    mesh.set_material(0,mat);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',False)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.WeatheringProvenance',source['provenance']);save(mesh)
runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[{k:o[k] for k in ('id','asset','material','geometry_sha256','triangles')} for o in source['objects']]
(CONTENT/'Data/paris-weathering.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
unreal.log('PARIS_WEATHERING_ASSETS_READY')
