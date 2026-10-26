"""Build Single Layer Water and wet quay assets with the existing GIS frame."""
import hashlib
import json
import os
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT/'unreal/AIWorld/Content'
SOURCE = ROOT/'unreal/textures/paris-water'
manifest = json.loads((CONTENT/'Data/paris-water.json').read_text(encoding='utf-8'))
assets = unreal.EditorAssetLibrary
lib = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def node(mat, cls, **props):
    n = lib.create_material_expression(mat, cls)
    if props:n.set_editor_properties(props)
    return n


def link(a, out, b, pin):
    if not lib.connect_material_expressions(a,out,b,pin):
        raise RuntimeError('Water material connection: '+pin+'; available '+str(lib.get_material_expression_input_names(b)))


def output(a, prop):
    if not lib.connect_material_property(a,'',prop):raise RuntimeError('Water output: '+str(prop))


def custom(mat, code, inputs, kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    n = node(mat,unreal.MaterialExpressionCustom,code=code,output_type=kind)
    pins=[]
    for key in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',key);pins.append(p)
    n.set_editor_property('inputs',pins)
    for key, (a,out) in inputs.items():link(a,out,n,key)
    return n


def scalar(mat,name,value):
    return node(mat,unreal.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)


def texture(name, filename, normal=False):
    file=SOURCE/filename
    if hashlib.sha256(file.read_bytes()).hexdigest()!=manifest['files'][filename]:raise RuntimeError('Unverified water texture')
    task=unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(file),destination_path='/Game/Textures',destination_name=name,automated=True,replace_existing=True,save=True))
    tools.import_asset_tasks([task]); t=assets.load_asset('/Game/Textures/'+name)
    if not t:raise RuntimeError('Water texture import failed')
    t.set_editor_property('srgb',False)
    t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if normal else unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    t.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP if normal else unreal.TextureAddress.TA_CLAMP)
    t.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP if normal else unreal.TextureAddress.TA_CLAMP)
    assets.save_loaded_asset(t,only_if_is_dirty=False)
    return t


ripple=texture('T_SeineRippleNormal','seine-ripple-normal.png',True)
shore=texture('T_SeineShoreDistance','seine-shore-distance.png')
path='/Game/Materials/M_SeineRiver'
mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset('M_SeineRiver','/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
lib.delete_all_material_expressions(mat)
water_model=next((getattr(unreal.MaterialShadingModel,n) for n in dir(unreal.MaterialShadingModel) if 'SINGLE' in n and 'WATER' in n),None)
if water_model is None:raise RuntimeError('Installed UE does not expose Single Layer Water')
mat.set_editor_property('shading_model',water_model)
mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
mat.set_editor_property('two_sided',True)
mat.set_editor_property('tangent_space_normal',False)
position=node(mat,unreal.MaterialExpressionWorldPosition)
time=node(mat,unreal.MaterialExpressionTime)
speed=scalar(mat,'FlowSpeed',1.)
strength=scalar(mat,'RippleStrength',1.)
b=manifest['world_bounds_cm']
uv=custom(mat,f'return (Position.xy-float2({b[0]:.6f},{b[1]:.6f}))/float2({b[2]-b[0]:.6f},{b[3]-b[1]:.6f});',{'Position':(position,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
shore_sample=node(mat,unreal.MaterialExpressionTextureSample,texture=shore,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
link(uv,'',shore_sample,'UVs')
distance=custom(mat,'return (Packed.r*65280.+Packed.g*255.)/65535.*12800.-6400.;',{'Packed':(shore_sample,'RGB')},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
samples=[]
for tile,flow in [(480.,(.075,.018)),(1630.,(-.012,.025)),(71.,(.021,-.049))]:
    coords=custom(mat,f'return Position.xy/{tile}+Time*Speed*float2({flow[0]},{flow[1]});',{'Position':(position,''),'Time':(time,''),'Speed':(speed,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    sample=node(mat,unreal.MaterialExpressionTextureSample,texture=ripple,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    link(coords,'',sample,'UVs');samples.append(sample)
normal=custom(mat,'float fade=saturate(1.-length(CameraPosition-Position)/16000.);float2 slope=(N0.xy*.78+N1.xy*.55+N2.xy*.24*fade)*Strength;return normalize(float3(slope,1.));',
    {'N0':(samples[0],'RGB'),'N1':(samples[1],'RGB'),'N2':(samples[2],'RGB'),'Strength':(strength,''),'Position':(position,''),'CameraPosition':(node(mat,unreal.MaterialExpressionCameraPositionWS),'')})
output(normal,unreal.MaterialProperty.MP_NORMAL)
color=custom(mat,'float bank=1.-smoothstep(60.,1500.,max(Distance,0.));float mottled=.5+.5*sin(Position.x*.0017+sin(Position.y*.0021));return lerp(float3(.025,.040,.022),float3(.041,.060,.038),bank*.55)*( .91+.16*mottled);',{'Distance':(distance,''),'Position':(position,'')})
output(color,unreal.MaterialProperty.MP_BASE_COLOR)
rough=custom(mat,'return .13+(.5+.5*N.y)*.035+(1.-smoothstep(20.,160.,max(Distance,0.)))*.065;',{'N':(samples[0],'RGB'),'Distance':(distance,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
output(rough,unreal.MaterialProperty.MP_ROUGHNESS)
output(scalar(mat,'Metallic',0.),unreal.MaterialProperty.MP_METALLIC)
output(scalar(mat,'Specular',.255),unreal.MaterialProperty.MP_SPECULAR)
output(scalar(mat,'SurfaceCoverage',.28),unreal.MaterialProperty.MP_OPACITY)
water=node(mat,unreal.MaterialExpressionSingleLayerWaterMaterialOutput)
for pin,value in [('Scattering Coefficients',(.00005,.000095,.00007)),('Absorption Coefficients',(.011,.0045,.012)),('Color Scale Behind Water',(.46,.58,.48))]:
    n=node(mat,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(*value,1))
    names=lib.get_material_expression_input_names(water)
    name=next((s for s in names if s.replace(' ','').lower()==pin.replace(' ','').lower()),pin)
    link(n,'',water,name)
names=lib.get_material_expression_input_names(water)
link(scalar(mat,'ScatteringPhase',.15),'',water,next((s for s in names if s.replace(' ','').lower()=='phaseg'),'PhaseG'))
# Pixel normals carry the waves; retain surveyed shoreline geometry and picking.
lib.recompile_material(mat)
assets.set_metadata_tag(mat,'ParisTwin.WaterRecipe',manifest['recipe'])
assets.save_loaded_asset(mat,only_if_is_dirty=False)

wet_path='/Game/Materials/M_ParisQuayWet'
if assets.does_asset_exist(wet_path):assets.delete_asset(wet_path)
wet=assets.duplicate_asset('/Game/Materials/M_ParisLimestone',wet_path)
if not wet:raise RuntimeError('Cannot preserve photographic limestone for quays')
base=lib.get_material_property_input_node(wet,unreal.MaterialProperty.MP_BASE_COLOR)
base_pin=lib.get_material_property_input_node_output_name(wet,unreal.MaterialProperty.MP_BASE_COLOR)
old_rough=lib.get_material_property_input_node(wet,unreal.MaterialProperty.MP_ROUGHNESS)
old_rough_pin=lib.get_material_property_input_node_output_name(wet,unreal.MaterialProperty.MP_ROUGHNESS)
pos=node(wet,unreal.MaterialExpressionWorldPosition)
level=scalar(wet,'WaterLevelCm',manifest['water_level_cm'])
stain=custom(wet,'float edge=sin(Position.x*.023)*4.+sin(Position.y*.011)*7.;return 1.-smoothstep(12.,105.,Position.z-Level+edge);',{'Position':(pos,''),'Level':(level,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
base=custom(wet,'return Color*lerp(float3(1,1,1),float3(.43,.49,.40),Wet);',{'Color':(base,base_pin),'Wet':(stain,'')})
output(base,unreal.MaterialProperty.MP_BASE_COLOR)
rough=custom(wet,'return lerp(Roughness,.27,Wet);',{'Roughness':(old_rough,old_rough_pin),'Wet':(stain,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
output(rough,unreal.MaterialProperty.MP_ROUGHNESS)
lib.recompile_material(wet)
assets.set_metadata_tag(wet,'ParisTwin.WaterRecipe',manifest['recipe'])
assets.save_loaded_asset(wet,only_if_is_dirty=False)
unreal.log_warning('PARIS_WATER_ASSETS_READY')
