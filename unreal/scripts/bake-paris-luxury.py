"""Bake original street decoration without changing archived GIS assets."""
import json,runpy
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2];CONTENT=ROOT/'unreal/AIWorld/Content'
source=json.loads((ROOT/'unreal/assets/paris-luxury/Generated/luxury.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
folder='/Game/ParisPhotoreal/Luxury';assets.make_directory(folder);(CONTENT/'ParisPhotoreal/Luxury').mkdir(parents=True,exist_ok=True)
if source.get('decoration_recipe') in ('paris_street_realism_v7','paris_festival_party_v8','paris_lively_street_v9','paris_street_accents_v10'):runpy.run_path(str(ROOT/'unreal/scripts/bake-paris-realism.py'))
collection=assets.load_asset('/Game/Night/MPC_ParisNight')
if not collection:raise RuntimeError('Missing shared night collection')
parameters=list(collection.get_editor_property('scalar_parameters'))
if not any(str(p.get_editor_property('parameter_name'))=='FestivalAmount' for p in parameters):
    parameter=unreal.CollectionScalarParameter();parameter.set_editor_properties(dict(parameter_name='FestivalAmount',default_value=0.));parameters.append(parameter)
    collection.set_editor_property('scalar_parameters',parameters)
    if not assets.save_loaded_asset(collection,only_if_is_dirty=False):raise RuntimeError('Cannot save festival collection parameter')


def save(asset):
    if not assets.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Luxury asset save failed '+asset.get_path_name())


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def output(n,prop):
    if not lib.connect_material_property(n,'',prop):raise RuntimeError('Luxury material output '+str(prop))


for role,rough,metal in [('Stone',.64,0),('Metal',.33,.72),('Nature',.76,0),('Fabric',.88,0),('Marble',.27,0),('Bulb',.28,0),('FestiveGlow',.28,0),('ProxyShop',.88,0),('ProxyWindow',.76,0),('ProxyPole',.88,0),('ProxyStreet',.88,0),('NightWindow',.36,0),('PartyColor',.28,0),('PartyGold',.3,0),('MarketSolid',.6,0)]:
    name='M_ParisLuxury'+role;path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',role in ('Nature','Fabric','PartyColor','PartyGold') or role.startswith('Proxy'))
    if role=='Nature':mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    color=node(mat,unreal.MaterialExpressionVertexColor)
    if role in ('Stone','Marble','Fabric'):
        pos=node(mat,unreal.MaterialExpressionWorldPosition)
        code={'Stone':'float p=.5+.5*sin(P.x*.13+sin(P.y*.1))*sin(P.z*.17);return C.rgb*(.96+.06*p);',
              'Marble':'float w=sin(P.x*.085+P.y*.034+sin(P.y*.10)*2.+sin(P.x*.19)*.5);float v=pow(saturate(1.-abs(w)),18.);return C.rgb*(1.-v*.12);',
              'Fabric':'float weave=sin(P.x*3.)*sin(P.y*3.+P.z*2.);return C.rgb*(.98+.02*weave);'}[role]
        custom=node(mat,unreal.MaterialExpressionCustom,code=code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        pins=[]
        for key,expr in [('C',color),('P',pos)]:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        custom.set_editor_property('inputs',pins)
        for key,expr in [('C',color),('P',pos)]:
            if not lib.connect_material_expressions(expr,'',custom,key):raise RuntimeError('Luxury material input '+key)
        color=custom
    output(color,unreal.MaterialProperty.MP_BASE_COLOR)
    if role in ('PartyColor','PartyGold'):
        night=node(mat,unreal.MaterialExpressionCollectionParameter,collection=collection,parameter_name='NightAmount')
        strength='160.' if role=='PartyColor' else '384.'
        glow=node(mat,unreal.MaterialExpressionCustom,code='return C.rgb*lerp(2.,'+strength+',saturate(N));',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        pins=[]
        for key in ['C','N']:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        glow.set_editor_property('inputs',pins)
        for key,expr in [('C',color),('N',night)]:
            if not lib.connect_material_expressions(expr,'',glow,key):raise RuntimeError('Party glow input '+key)
        output(glow,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if role=='NightWindow':
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
        collection=assets.load_asset('/Game/Night/MPC_ParisNight')
        if not collection:raise RuntimeError('Missing shared night collection')
        night=node(mat,unreal.MaterialExpressionCollectionParameter,collection=collection,parameter_name='NightAmount')
        mask=node(mat,unreal.MaterialExpressionCustom,code='return step(.03,N);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        pin=unreal.CustomInput();pin.set_editor_property('input_name','N');mask.set_editor_property('inputs',[pin])
        if not lib.connect_material_expressions(night,'',mask,'N'):raise RuntimeError('Night window mask input')
        output(mask,unreal.MaterialProperty.MP_OPACITY_MASK)
        uv=node(mat,unreal.MaterialExpressionTextureCoordinate)
        festival=node(mat,unreal.MaterialExpressionCollectionParameter,collection=collection,parameter_name='FestivalAmount')
        glow=node(mat,unreal.MaterialExpressionCustom,code='float fold=.68+.32*cos(U.x*70.);float curtain=lerp(1.,fold*.65,smoothstep(.15,.28,abs(U.x-.5)));float falloff=.78+.22*U.y;float3 party=C.b>.5?float3(.05,.50,1.):C.g>.65?float3(1.,.025,.23):float3(1.,.48,.025);float f=saturate(F);return lerp(C.rgb,party,f*.85)*lerp(20.,40.,f)*saturate(N)*curtain*falloff;',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        pins=[]
        for key in ['C','U','N','F']:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        glow.set_editor_property('inputs',pins)
        for key,expr in [('C',color),('U',uv),('N',night),('F',festival)]:
            if not lib.connect_material_expressions(expr,'',glow,key):raise RuntimeError('Night window glow input '+key)
        output(glow,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if role.startswith('Proxy'):
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
        pos=node(mat,unreal.MaterialExpressionWorldPosition);camera=node(mat,unreal.MaterialExpressionCameraPositionWS)
        limit=node(mat,unreal.MaterialExpressionScalarParameter,parameter_name='NearCutCm',default_value={'ProxyShop':18000.,'ProxyWindow':7000.,'ProxyPole':9000.,'ProxyStreet':18000.}[role])
        mask=node(mat,unreal.MaterialExpressionCustom,code='return step(L,distance(P,C));',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        pins=[]
        for key,expr in [('P',pos),('C',camera),('L',limit)]:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        mask.set_editor_property('inputs',pins)
        for key,expr in [('P',pos),('C',camera),('L',limit)]:
            if not lib.connect_material_expressions(expr,'',mask,key):raise RuntimeError('Distance substitute mask input '+key)
        output(mask,unreal.MaterialProperty.MP_OPACITY_MASK)
        night=node(mat,unreal.MaterialExpressionCollectionParameter,collection=assets.load_asset('/Game/Night/MPC_ParisNight'),parameter_name='NightAmount')
        strength='256.' if role=='ProxyStreet' else '64.'
        glow=node(mat,unreal.MaterialExpressionCustom,code='return C.rgb*A*'+strength+'*saturate(N);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        pins=[]
        for key in ['C','A','N']:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        glow.set_editor_property('inputs',pins)
        for key,expr in [('C',color),('A',color),('N',night)]:
            if not lib.connect_material_expressions(expr,'A' if key=='A' else '',glow,key):raise RuntimeError('Distance substitute glow input '+key)
        output(glow,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if role=='Nature':
        scatter=node(mat,unreal.MaterialExpressionMultiply,const_b=.28)
        if not lib.connect_material_expressions(color,'',scatter,'A'):raise RuntimeError('Floral transmission input')
        output(scatter,unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        output(node(mat,unreal.MaterialExpressionConstant,r=.68),unreal.MaterialProperty.MP_OPACITY)
    if role in ('Bulb','FestiveGlow'):
        collection=assets.load_asset('/Game/Night/MPC_ParisNight')
        if not collection:raise RuntimeError('Build the existing Paris night assets before the floral lights')
        night=node(mat,unreal.MaterialExpressionCollectionParameter,collection=collection,parameter_name='NightAmount')
        strength='256.' if role=='FestiveGlow' else '64.'
        glow=node(mat,unreal.MaterialExpressionCustom,code='return float3(1.,.56,.22)*'+strength+'*saturate(N);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        pin=unreal.CustomInput();pin.set_editor_property('input_name','N');glow.set_editor_property('inputs',[pin])
        if not lib.connect_material_expressions(night,'',glow,'N'):raise RuntimeError('Festoon night control input')
        output(glow,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    output(node(mat,unreal.MaterialExpressionConstant,r=rough),unreal.MaterialProperty.MP_ROUGHNESS)
    output(node(mat,unreal.MaterialExpressionConstant,r=metal),unreal.MaterialProperty.MP_METALLIC)
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',source['appearance_provenance']);save(mat)

runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[]
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        def linear(b):
            v=b/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        buffers=unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],vertex_colors=[unreal.LinearColor(*[linear(b) for b in c[:3]],c[3]/255) for c in item['colors']],triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Luxury mesh bake failed '+package)
    mat=assets.load_asset(item['material'])
    if not mat:raise RuntimeError('Missing luxury material '+item['material'])
    mesh.set_material(0,mat);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',False)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);save(mesh)
    runtime['objects'].append({k:item[k] for k in ('id','asset','material','geometry_sha256','triangles')})
with (CONTENT/'Data/paris-luxury.json').open('w',encoding='utf-8') as f:json.dump(runtime,f,ensure_ascii=False,indent=2)
unreal.log_warning('PARIS_LUXURY_ASSETS_READY')
