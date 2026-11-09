"""Reuse saved photographic assets for street glass and an evening panorama."""
import json
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[2]
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary;factory=unreal.AssetToolsHelpers.get_asset_tools()


def save(asset):
    if not assets.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Realism asset save failed '+asset.get_path_name())


def node(mat,cls,**props):
    value=lib.create_material_expression(mat,cls)
    if props:value.set_editor_properties(props)
    return value


glass=assets.load_asset('/Game/Materials/M_ParisStreetWindowGlass') if assets.does_asset_exist('/Game/Materials/M_ParisStreetWindowGlass') else None
if not glass:
    source=assets.load_asset('/Game/Materials/M_ParisWindowGlass')
    if not source:raise RuntimeError('The source-aligned core window glass is missing')
    glass=factory.duplicate_asset('M_ParisStreetWindowGlass','/Game/Materials',source)
if not glass:raise RuntimeError('Street glass copy failed')
# Reuse the existing view-dependent room/glass graph. Occupancy is rendered by
# the separately traceable warm-window layer, rather than a shared prototype seed.
lib.disconnect_material_property(glass,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
lib.set_material_usage(glass,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
assets.set_metadata_tag(glass,'ParisTwin.AppearanceProvenance','Copied core PBR/parallax glazing; inferred room appearance, no surveyed interior; separate seeded window lighting')
lib.recompile_material(glass);save(glass)

name='M_ParisEveningSky';mat=assets.load_asset('/Game/Materials/'+name) if assets.does_asset_exist('/Game/Materials/'+name) else None
if not mat:mat=factory.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
lib.delete_all_material_expressions(mat)
mat.set_editor_properties(dict(two_sided=True,is_sky=True,shading_model=unreal.MaterialShadingModel.MSM_UNLIT))
cube=assets.load_asset('/Game/Textures/T_ParisDayEnvironment')
if not cube:raise RuntimeError('The saved photographic environment is missing')
view=node(mat,unreal.MaterialExpressionCameraVectorWS);direction=node(mat,unreal.MaterialExpressionMultiply,const_b=-1.)
lib.connect_material_expressions(view,'',direction,'A')
sample=node(mat,unreal.MaterialExpressionTextureSample,texture=cube,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
lib.connect_material_expressions(direction,'',sample,'UVs')
shade=node(mat,unreal.MaterialExpressionCustom,code='float h=smoothstep(.02,.65,saturate(D.z));float3 tint=lerp(float3(1.05,.78,.60),float3(.65,.76,.98),h);return C.rgb*tint*3000.;',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
pins=[]
for key in ['C','D']:
    pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
shade.set_editor_property('inputs',pins)
for key,expr in [('C',sample),('D',direction)]:
    if not lib.connect_material_expressions(expr,'',shade,key):raise RuntimeError('Evening sky input '+key)
if not lib.connect_material_property(shade,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR):raise RuntimeError('Evening sky output')
assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Saved day HDR panorama with inferred evening radiance and directional tint; not a captured Paris sunset')
lib.recompile_material(mat);save(mat)
report=dict(recipe='paris_street_realism_v7',assets=['/Game/Materials/M_ParisStreetWindowGlass','/Game/Materials/M_ParisEveningSky'],inferred_appearance=True,geometry_unchanged=True)
(ROOT/'unreal/AIWorld/Content/Data/paris-realism.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_REALISM_ASSETS_READY')
