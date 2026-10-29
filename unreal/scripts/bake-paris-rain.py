"""Build rain materials/audio; wrap existing ground PBR without replacing its textures."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'unreal/assets/paris-weather/Generated'
CONTENT = ROOT/'unreal/AIWorld/Content'
assets = unreal.EditorAssetLibrary
lib = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
assets.make_directory('/Game/Weather')
(CONTENT/'Weather').mkdir(parents=True, exist_ok=True)


def save(asset):
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Rain asset save failed: '+asset.get_path_name())


def node(mat, cls, **props):
    n = lib.create_material_expression(mat, cls)
    if props: n.set_editor_properties(props)
    return n


def custom(mat, code, inputs, dimensions=3, desc=''):
    n = node(mat, unreal.MaterialExpressionCustom, code=code, desc=desc,
             output_type={1: unreal.CustomMaterialOutputType.CMOT_FLOAT1, 3: unreal.CustomMaterialOutputType.CMOT_FLOAT3}[dimensions])
    pins = []
    for key in inputs:
        pin = unreal.CustomInput(); pin.set_editor_property('input_name', key); pins.append(pin)
    n.set_editor_property('inputs', pins)
    for key, (source, output) in inputs.items():
        if not lib.connect_material_expressions(source, output, n, key): raise RuntimeError('Rain input: '+key)
    return n


def output(n, prop):
    if not lib.connect_material_property(n, '', prop): raise RuntimeError('Rain material output: '+str(prop))


def material(name):
    path = '/Game/Weather/'+name
    m = assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name, '/Game/Weather', unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(m)
    return m


path = '/Game/Weather/MPC_ParisWeather'
collection = assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset('MPC_ParisWeather', '/Game/Weather', unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
parameters = list(collection.get_editor_property('scalar_parameters'))
for key in ('Wetness', 'RainIntensity'):
    if not any(str(p.get_editor_property('parameter_name')) == key for p in parameters):
        p = unreal.CollectionScalarParameter(); p.set_editor_properties(dict(parameter_name=key, default_value=0.)); parameters.append(p)
collection.set_editor_property('scalar_parameters', parameters)
save(collection)


def weather(mat, name):
    return node(mat, unreal.MaterialExpressionCollectionParameter, collection=collection, parameter_name=name)


for name, splash in [('M_ParisRain', False), ('M_ParisRainSplash', True)]:
    mat = material(name)
    mat.set_editor_properties(dict(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT, shading_model=unreal.MaterialShadingModel.MSM_UNLIT,
                                   two_sided=True, disable_depth_test=False))
    uv = node(mat, unreal.MaterialExpressionTextureCoordinate)
    color = node(mat, unreal.MaterialExpressionVertexColor)
    code = ('float r=length(UV-.5)*2.;return exp(-pow((r-.72)*19.,2.))*Alpha;' if splash else
            'float x=abs(UV.x-.5)*2.;float tip=saturate(sin(UV.y*3.14159265));return exp(-x*x*5.)*tip*Alpha;')
    alpha = custom(mat, code, {'UV': (uv, ''), 'Alpha': (color, 'A')}, 1)
    depth = node(mat, unreal.MaterialExpressionDepthFade, fade_distance_default=.4 if splash else 45.)
    if not lib.connect_material_expressions(alpha, '', depth, 'Opacity'): raise RuntimeError('Depth fade connection')
    output(depth, unreal.MaterialProperty.MP_OPACITY)
    # Emissive is exposed like a dim translucent highlight, never a white bar.
    pre = node(mat, unreal.MaterialExpressionEyeAdaptationInverse)
    pre_inputs = lib.get_material_expression_input_names(pre)
    light_pin = next((str(p) for p in pre_inputs if 'lightvalue' in str(p).replace(' ', '').lower()), 'LightValueInput')
    if not lib.connect_material_expressions(color, '', pre, light_pin): raise RuntimeError('Rain exposure connection: '+str(pre_inputs))
    output(pre, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat); save(mat)

mat = material('M_ParisRainSky')
mat.set_editor_properties(dict(shading_model=unreal.MaterialShadingModel.MSM_UNLIT, two_sided=True))
pos, camera = node(mat, unreal.MaterialExpressionWorldPosition), node(mat, unreal.MaterialExpressionCameraPositionWS)
brightness = node(mat, unreal.MaterialExpressionScalarParameter, parameter_name='SkyRadiance', default_value=3500.)
sky = custom(mat, 'float3 d=normalize(P-C);float cloud=.5+.22*sin(d.x*17.+sin(d.y*21.))+.16*sin(d.y*43.+d.x*31.);return lerp(float3(.48,.52,.55),float3(.23,.27,.31),smoothstep(0.,.8,d.z))*(.80+.22*cloud)*B;',
             {'P': (pos, ''), 'C': (camera, ''), 'B': (brightness, '')})
output(sky, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
lib.recompile_material(mat); save(mat)

# Each base graph is preserved and wetness=0 returns its original values.
names = ['M_ParisRoadAsphalt', 'M_ParisRoadSidewalk', 'M_ParisRoadPaving', 'M_ParisRoadKerb',
         'M_ParisPaving', 'M_ParisGroundPaving', 'M_ParisAsphaltPhotographic',
         'M_ParisQuayWet', 'M_ParisBridgeMasonry', 'M_ParisBridgeCutStone', 'M_ParisBridgePaving']
patched = []
for name in names:
    path = '/Game/Materials/'+name
    if not assets.does_asset_exist(path): continue
    mat = assets.load_asset(path)
    original = {}
    for prop in (unreal.MaterialProperty.MP_BASE_COLOR, unreal.MaterialProperty.MP_ROUGHNESS, unreal.MaterialProperty.MP_NORMAL):
        n = lib.get_material_property_input_node(mat, prop)
        if n: original[prop] = (n, lib.get_material_property_input_node_output_name(mat, prop))
    base = original.get(unreal.MaterialProperty.MP_BASE_COLOR)
    if not base: continue
    if str(base[0].get_editor_property('desc')) == 'ParisRain.Base_v1': patched.append(path); continue
    wet, rain = weather(mat, 'Wetness'), weather(mat, 'RainIntensity')
    pos, normal, time = node(mat, unreal.MaterialExpressionWorldPosition), node(mat, unreal.MaterialExpressionVertexNormalWS), node(mat, unreal.MaterialExpressionTime)
    mask = custom(mat, 'float n=.5+.25*sin(P.x*.0021+sin(P.y*.0017))+.25*sin(P.y*.0037+P.x*.0011);return saturate(W)*smoothstep(.55,.95,N.z)*(.55+.45*smoothstep(.3,.68,n));',
                  {'P': (pos, ''), 'N': (normal, ''), 'W': (wet, '')}, 1)
    output(custom(mat, 'return C*lerp(1.,.52,W);', {'C': base, 'W': (mask, '')}, desc='ParisRain.Base_v1'), unreal.MaterialProperty.MP_BASE_COLOR)
    rough = original.get(unreal.MaterialProperty.MP_ROUGHNESS)
    if rough: output(custom(mat, 'return lerp(R,max(.075,R*.18),W);', {'R': rough, 'W': (mask, '')}, 1), unreal.MaterialProperty.MP_ROUGHNESS)
    norm = original.get(unreal.MaterialProperty.MP_NORMAL)
    if norm and not mat.get_editor_property('tangent_space_normal'):
        code = '''float2 p=P.xy/85.;float2 cell=floor(p);float2 f=frac(p)-.5;
float h=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);float a=frac(T*1.7+h);
float r=length(f);float ring=exp(-pow((r-a*.7)*22.,2.))*(1.-a);
float2 ripple=f/max(r,.02)*ring*sin((r-a*.7)*90.)*.18*Rain;
return normalize(lerp(N,float3(N.xy*.35+ripple,max(N.z,.4)),W));'''
        output(custom(mat, code, {'P': (pos, ''), 'T': (time, ''), 'N': norm, 'W': (mask, ''), 'Rain': (rain, '')}), unreal.MaterialProperty.MP_NORMAL)
    lib.recompile_material(mat); save(mat); patched.append(path)

manifest = json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
for key, name in [('rain', 'A_ParisRain'), ('runoff', 'A_ParisRunoff')]:
    source = SOURCE/manifest['files'][key]['file']
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['files'][key]['sha256']: raise RuntimeError('Rain audio hash mismatch')
    path = '/Game/Weather/'+name
    sound = assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not sound or assets.get_metadata_tag(sound, 'ParisRain.SourceSHA256') != manifest['files'][key]['sha256']:
        task = unreal.AssetImportTask(); task.set_editor_properties(dict(filename=str(source), destination_path='/Game/Weather', destination_name=name, automated=True, replace_existing=True, save=True))
        tools.import_asset_tasks([task]); sound = assets.load_asset(path)
    if not sound: raise RuntimeError('Rain audio import failed')
    sound.set_editor_properties(dict(looping=True, volume=.8))
    assets.set_metadata_tag(sound, 'ParisRain.SourceSHA256', manifest['files'][key]['sha256'])
    assets.set_metadata_tag(sound, 'ParisRain.Provenance', manifest['provenance'])
    save(sound)
report = dict(recipe='paris_rain_v1', materials=patched, audio=manifest)
(CONTENT/'Data/paris-rain.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
unreal.log_warning('PARIS_RAIN_ASSETS_READY '+json.dumps(report))
