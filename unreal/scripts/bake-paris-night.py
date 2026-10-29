"""Original night sky / lantern shader and nondestructive window emission layer."""
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT/'unreal/AIWorld/Content'
assets, lib = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
assets.make_directory('/Game/Night'); (CONTENT/'Night').mkdir(parents=True, exist_ok=True)


def save(asset):
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False): raise RuntimeError('Night asset save failed: '+asset.get_path_name())


def node(mat, cls, **props):
    n = lib.create_material_expression(mat, cls)
    if props: n.set_editor_properties(props)
    return n


def custom(mat, code, inputs, desc=''):
    n = node(mat, unreal.MaterialExpressionCustom, code=code, desc=desc, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for name in inputs:
        p = unreal.CustomInput(); p.set_editor_property('input_name', name); pins.append(p)
    n.set_editor_property('inputs', pins)
    for name, (value, pin) in inputs.items():
        if not lib.connect_material_expressions(value, pin, n, name): raise RuntimeError('Night shader input: '+name)
    return n


def output(n, prop):
    if not lib.connect_material_property(n, '', prop): raise RuntimeError('Night shader output: '+str(prop))


def material(name):
    path = '/Game/Night/'+name
    mat = assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name, '/Game/Night', unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat); return mat


path = '/Game/Night/MPC_ParisNight'
collection = assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset('MPC_ParisNight', '/Game/Night', unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
parameters = list(collection.get_editor_property('scalar_parameters'))
if not parameters:
    p = unreal.CollectionScalarParameter(); p.set_editor_properties(dict(parameter_name='NightAmount', default_value=0.)); parameters.append(p)
collection.set_editor_property('scalar_parameters', parameters); save(collection)


def night(mat): return node(mat, unreal.MaterialExpressionCollectionParameter, collection=collection, parameter_name='NightAmount')


mat = material('M_ParisNightLantern')
mat.set_editor_properties(dict(two_sided=True))
lib.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
base = node(mat, unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(.11, .145, .135, 1))
output(base, unreal.MaterialProperty.MP_BASE_COLOR)
output(node(mat, unreal.MaterialExpressionConstant, r=.16), unreal.MaterialProperty.MP_ROUGHNESS)
glow = custom(mat, 'return float3(1.,.60,.26)*72.*N;', {'N': (night(mat), '')})
output(glow, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
lib.recompile_material(mat); save(mat)

mat = material('M_ParisNightSky')
mat.set_editor_properties(dict(two_sided=True, is_sky=True, shading_model=unreal.MaterialShadingModel.MSM_UNLIT))
pos, camera = node(mat, unreal.MaterialExpressionWorldPosition), node(mat, unreal.MaterialExpressionCameraPositionWS)
code = '''float3 d=normalize(P-C);float h=saturate(d.z);
float3 sky=lerp(float3(.22,.25,.32),float3(.018,.032,.067),pow(h,.45));
float2 uv=float2(atan2(d.y,d.x)/6.2831853+.5,asin(clamp(d.z,-1.,1.))/3.14159265+.5);
float2 cell=floor(uv*float2(1600.,800.));float2 f=frac(uv*float2(1600.,800.))-.5;
float seed=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);
float star=step(.9985,seed)*exp(-dot(f,f)*150.)*smoothstep(.10,.45,h)*4.;
float moonDot=dot(d,normalize(float3(-.333,.714,.616)));
float moon=smoothstep(.999985,.999994,moonDot)*145.;
float halo=exp((moonDot-1.)*1200.)*.7;
return sky+star*float3(.8,.88,1.)+(moon+halo)*float3(.8,.88,1.);'''
output(custom(mat, code, {'P': (pos, ''), 'C': (camera, '')}), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
lib.recompile_material(mat); save(mat)

patched = []
for name in ('M_ParisWindowGlass', 'M_ParisStainedGlass'):
    path = '/Game/Materials/'+name
    if not assets.does_asset_exist(path): continue
    mat = assets.load_asset(path)
    old = lib.get_material_property_input_node(mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if old and str(old.get_editor_property('desc')) == 'ParisNight.Emission_v1': patched.append(path); continue
    base = lib.get_material_property_input_node(mat, unreal.MaterialProperty.MP_BASE_COLOR)
    if not base: raise RuntimeError('Night window has no base graph: '+path)
    pin = lib.get_material_property_input_node_output_name(mat, unreal.MaterialProperty.MP_BASE_COLOR)
    seed = node(mat, unreal.MaterialExpressionVertexColor)
    if name == 'M_ParisWindowGlass':
        code = 'float r=frac(sin(dot(Seed,float3(127.1,311.7,83.3)))*43758.5453);float occupied=step(.62,r);return Base*float3(1.,.70,.40)*115.*N*occupied;'
    else:
        code = 'return Base*18.*N;'
    glow = custom(mat, code, {'Base': (base, pin), 'Seed': (seed, ''), 'N': (night(mat), '')}, 'ParisNight.Emission_v1')
    if old:
        old_pin = lib.get_material_property_input_node_output_name(mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        glow = custom(mat, 'return Old+Night;', {'Old': (old, old_pin), 'Night': (glow, '')}, 'ParisNight.Emission_v1')
    output(glow, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat); save(mat); patched.append(path)

report = dict(recipe='paris_night_v1', patched_materials=patched, assets=['/Game/Night/MPC_ParisNight', '/Game/Night/M_ParisNightLantern', '/Game/Night/M_ParisNightSky'],
              provenance='Original inferred lighting; archived OSM lamp positions retained. Intensities, temperatures, occupied windows, store opening state and cathedral floods are artistic estimates, not current observations.')
(CONTENT/'Data/paris-night.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
unreal.log('PARIS_NIGHT_ASSETS_READY '+json.dumps(report))
