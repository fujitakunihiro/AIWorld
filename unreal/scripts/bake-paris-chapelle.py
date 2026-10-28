"""Import a verified CC0 photograph and make an exterior glass material."""
import hashlib,json
from pathlib import Path
import unreal
root=Path(__file__).resolve().parents[2];folder=root/'unreal/assets/sainte-chapelle'
meta=json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'));source=folder/'Raw/stained-glass.jpg'
if hashlib.sha256(source.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Unverified source photo')
a=unreal.EditorAssetLibrary;t=unreal.AssetToolsHelpers.get_asset_tools();l=unreal.MaterialEditingLibrary
base='/Game/ParisPhotoreal/SainteChapelle';a.make_directory(base)
name='T_SainteChapelleWindows';pkg=base+'/'+name
tex=a.load_asset(pkg) if a.does_asset_exist(pkg) else None
if not tex:
 task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(source),destination_path=base,destination_name=name,automated=True,replace_existing=True,save=True));t.import_asset_tasks([task]);tex=a.load_asset(pkg)
if not tex:raise ValueError('Photo import failed')
tex.set_editor_property('srgb',True);a.save_loaded_asset(tex,only_if_is_dirty=False)
name='M_SainteChapelleWindows';pkg=base+'/'+name
m=a.load_asset(pkg) if a.does_asset_exist(pkg) else t.create_asset(name,base,unreal.Material,unreal.MaterialFactoryNew())
l.delete_all_material_expressions(m);m.set_editor_properties(dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
s=l.create_material_expression(m,unreal.MaterialExpressionTextureSample);s.set_editor_property('texture',tex)
k=l.create_material_expression(m,unreal.MaterialExpressionConstant);k.set_editor_property('r',.3)
mul=l.create_material_expression(m,unreal.MaterialExpressionMultiply)
if not l.connect_material_expressions(s,'RGB',mul,'A') or not l.connect_material_expressions(k,'',mul,'B'):raise ValueError('Texture wiring')
l.connect_material_property(mul,'',unreal.MaterialProperty.MP_BASE_COLOR)
r=l.create_material_expression(m,unreal.MaterialExpressionConstant);r.set_editor_property('r',.32);l.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS)
l.recompile_material(m)
a.set_metadata_tag(m,'ParisTwin.SourceURL',meta['source_url']);a.set_metadata_tag(m,'ParisTwin.License',meta['license']);a.save_loaded_asset(m,only_if_is_dirty=False)
unreal.log_warning('PARIS_CHAPELLE_MATERIAL_READY')
