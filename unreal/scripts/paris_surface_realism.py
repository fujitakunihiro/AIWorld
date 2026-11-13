"""Private, inferred surface finishes. No GIS positions or scanned textures change."""
import hashlib
from pathlib import Path
import unreal

SOURCE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
RECIPE = 'paris_surface_realism_v1_' + SOURCE_HASH[:12]
assets = unreal.EditorAssetLibrary
lib = unreal.MaterialEditingLibrary


def node(mat, cls, **props):
    result = lib.create_material_expression(mat, cls)
    if props:
        result.set_editor_properties(props)
    return result


def custom(mat, code, inputs, kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    result = node(mat, unreal.MaterialExpressionCustom, code=code, output_type=kind)
    pins = []
    for key in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property('input_name', key)
        pins.append(pin)
    result.set_editor_property('inputs', pins)
    for key, (src, out) in inputs.items():
        if not lib.connect_material_expressions(src, out, result, key):
            raise RuntimeError('Surface material input ' + key)
    return result


def output(mat, expression, prop):
    if not lib.connect_material_property(expression, '', prop):
        raise RuntimeError('Surface material output ' + str(prop))


def save(mat):
    lib.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    lib.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_NANITE)
    if lib.recompile_material(mat):
        raise RuntimeError('Surface shader compile ' + mat.get_name())
    assets.set_metadata_tag(mat, 'ParisTwin.SurfaceRealism', RECIPE)
    assets.set_metadata_tag(mat, 'ParisTwin.SurfaceSourceSHA256', SOURCE_HASH)
    if not assets.save_loaded_asset(mat, only_if_is_dirty=False):
        raise RuntimeError('Surface material save ' + mat.get_name())


def limestone(mat):
    # Change the underlying dry albedo, preserving the existing rain graph,
    # photographed fine normal, and local source-aligned streak/base overlays.
    count = 0
    for expression in lib.get_material_expressions(mat):
        if not isinstance(expression, unreal.MaterialExpressionCustom):
            continue
        code = expression.get_editor_property('code')
        if 'float broad=' not in code or 'float deposit=' not in code:
            continue
        core = code.split('float broad=')[0]
        expression.set_editor_property('code', core + '''
float broad=sin(dot(Position.xy,float2(.0017,.0021)))*sin(Position.z*.0018);
// Retain actual source grain while reducing the contrast of broad blotches.
float variation=.93+.13*block+.025*broad;
float deposit=(1.-stone)*(.025+.03*block);
float3 limestone=lerp(Albedo*float3(1.,.965,.90),float3(.50,.46,.39),.55)*variation;
return limestone*lerp(.76,1.,stone)*(1.-deposit);
''')
        count += 1
    if count != 1:
        raise RuntimeError('Expected one source masonry albedo, found ' + str(count))
    assets.set_metadata_tag(mat, 'ParisTwin.AppearanceProvenance',
        'Inferred pale limestone albedo with subtle block variation; existing CC0 fine normal and local weathering retained. Not surveyed stone.')


ROOM = r'''
float3 N=normalize(Normal);
float3 T=normalize(float3(N.y,-N.x,0)+float3(1e-5,0,0));
// Quantize constant per-window values before hashing. Interpolation roundoff
// amplified by sin/fract hashes otherwise makes occupied panes sparkle.
float seed=frac(floor(Instance*1024.+.5)*.754877666+dot(floor(Seed*1024.+.5),float3(.1317,.0731,.0573)));
float r=frac(sin(seed*71.39+2.17)*43758.5453);
float r2=frac(sin(seed*97.21+5.7)*23421.631);
float3 ray=float3(-dot(View,T),-View.z,max(.05,dot(View,N)));
float2 p=(UV-.5)*float2(.90,1.65);
float tx=abs(ray.x)<1e-5?1e6:((ray.x<0? -1.35:1.35)-p.x)/ray.x;
float ty=abs(ray.y)<1e-5?1e6:((ray.y<0? -.825:.825)-p.y)/ray.y;
float tz=(1.8+1.4*r)/ray.z;
float3 q=float3(p,0)+ray*min(tz,min(tx,ty));
float3 room=lerp(float3(.17,.145,.11),float3(.12,.145,.15),r2);
if(ty<min(tx,tz))room=q.y>0?float3(.23,.215,.18):float3(.055,.038,.025);
else if(tx<tz)room*=.74;
else {
    float frame=step(abs(q.x-(r-.5)),.35)*step(abs(q.y-.13),.27);
    float picture=step(abs(q.x-(r-.5)),.29)*step(abs(q.y-.13),.21);
    room=lerp(room,float3(.035,.027,.019),frame);
    room=lerp(room,float3(.08,.11,.095),picture);
    float furniture=step(q.y,-.47)*step(abs(q.x+.26),.68);
    room=lerp(room,float3(.045,.031,.021),furniture);
}
// Unequal linen panels and occasional half-lowered blinds, stable per window.
float left=.055+.20*r,right=.05+.17*r2;
float aa=max(fwidth(UV.x),.0015);
float curtain=max(1.-smoothstep(left-aa,left+aa,UV.x),smoothstep(1.-right-aa,1.-right+aa,UV.x));
float fold=.87+.13*cos(UV.x*150.+r*6.28);
float3 linen=lerp(float3(.38,.335,.25),float3(.29,.32,.30),step(.65,r2))*fold;
room=lerp(room,linen,curtain);
float blind=step(.76,r)*smoothstep(.63+.15*r2-.005,.63+.15*r2+.005,UV.y);
float slats=.90+.10*cos(UV.y*180.);
room=lerp(room,float3(.30,.275,.22)*slats,blind);
'''


def glazing():
    path = '/Game/Materials/M_ParisSeineWindow'
    mat = assets.load_asset(path) if assets.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'M_ParisSeineWindow', '/Game/Materials', unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        raise RuntimeError('Cannot create private window material')
    if (assets.get_metadata_tag(mat, 'ParisTwin.SurfaceSourceSHA256') == SOURCE_HASH
            and assets.does_asset_exist('/Game/Materials/MI_ParisSeineCoreWindow')):
        return
    lib.delete_all_material_expressions(mat)
    mat.set_editor_properties(dict(two_sided=False, tangent_space_normal=False,
        blend_mode=unreal.BlendMode.BLEND_OPAQUE, shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT))
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate)
    normal = node(mat, unreal.MaterialExpressionVertexNormalWS)
    view = node(mat, unreal.MaterialExpressionCameraVectorWS)
    seed = node(mat, unreal.MaterialExpressionVertexColor)
    instance = node(mat, unreal.MaterialExpressionPerInstanceRandom)
    inputs = dict(UV=(uv, ''), Normal=(normal, ''), View=(view, ''), Seed=(seed, ''), Instance=(instance, ''))
    room = custom(mat, ROOM + 'return room*float3(.96,.99,1.);', inputs)
    output(mat, room, unreal.MaterialProperty.MP_BASE_COLOR)
    rough = custom(mat, '''float edge=min(min(UV.x,1.-UV.x),min(UV.y,1.-UV.y));
return .16+.018*Instance+.08*(1.-smoothstep(.015,.07,edge));''',
        dict(UV=(uv, ''), Instance=(instance, '')), unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    output(mat, rough, unreal.MaterialProperty.MP_ROUGHNESS)
    # Slight old-pane waviness changes the actual environment reflection.
    ripple = custom(mat, '''float3 N=normalize(Normal);float3 T=normalize(float3(N.y,-N.x,0)+float3(1e-5,0,0));
float2 wave=float2(sin(UV.x*13.+Instance*6.),sin(UV.y*11.+Instance*5.));
return normalize(N+T*wave.x*.0008+float3(0,0,1)*wave.y*.0006);''',
        dict(UV=(uv, ''), Normal=(normal, ''), Instance=(instance, '')))
    output(mat, ripple, unreal.MaterialProperty.MP_NORMAL)
    for prop, value in [(unreal.MaterialProperty.MP_SPECULAR,.5),(unreal.MaterialProperty.MP_METALLIC,0.)]:
        output(mat,node(mat,unreal.MaterialExpressionConstant,r=value),prop)
    # Core windows previously had a night contribution. Preserve it here;
    # district relief already has a separately seeded warm-window layer.
    collection = assets.load_asset('/Game/Night/MPC_ParisNight')
    if not collection:
        raise RuntimeError('Night collection missing')
    night = node(mat, unreal.MaterialExpressionCollectionParameter, collection=collection, parameter_name='NightAmount')
    glow = custom(mat, '''float r=frac(sin(dot(floor(Seed*1024.+.5),float3(12.17,31.7,8.3)))*43758.5453);
return C*float3(1.,.70,.40)*115.*Night*step(.72,r)*Core;''',
        dict(C=(room,''),Seed=(seed,''),Night=(night,''),Core=(node(mat,unreal.MaterialExpressionScalarParameter,parameter_name='CoreNightEmission',default_value=0.),'')))
    output(mat, glow, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',
        'Inferred view-dependent rooms, per-instance linen/blinds and dielectric glazing. Actual UE environment reflections; no photographed/surveyed interiors.')
    save(mat)
    # An instance restores only core-window emission, without double lighting
    # the district's separate occupancy layer.
    path='/Game/Materials/MI_ParisSeineCoreWindow'
    core=assets.load_asset(path) if assets.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'MI_ParisSeineCoreWindow','/Game/Materials',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    lib.set_material_instance_parent(core,mat)
    lib.set_material_instance_scalar_parameter_value(core,'CoreNightEmission',1.)
    if not assets.save_loaded_asset(core,only_if_is_dirty=False):
        raise RuntimeError('Cannot save core glass instance')

