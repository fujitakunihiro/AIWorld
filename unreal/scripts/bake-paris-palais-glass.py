"""Create an instanced glass variant without altering the existing frontage material."""
import os,sys,hashlib
from pathlib import Path
import unreal
A=unreal.EditorAssetLibrary; L=unreal.MaterialEditingLibrary
source='/Game/Materials/M_ParisWindowGlass';folder='/Game/ParisPhotoreal/Palais';dest=folder+'/M_PalaisReflectiveGlass'
disk=Path(os.path.realpath(unreal.Paths.project_content_dir()))/'ParisPhotoreal'/'Palais';disk.mkdir(parents=True,exist_ok=True)
sentinel=disk/'.build-in-progress';sentinel.write_text('building',encoding='ascii')
A.make_directory(folder)
if not A.does_asset_exist(source):raise RuntimeError('Existing Paris window material is unavailable')
if not A.does_asset_exist(dest):
    if not A.duplicate_asset(source,dest):raise RuntimeError('Window material copy failed')
m=A.load_asset(dest)
if not m:raise RuntimeError('Palais glass material unavailable')
signature=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
if A.get_metadata_tag(m,'ParisTwin.RecipeSHA256')==signature:
    sentinel.unlink(missing_ok=True);unreal.log_warning('PARIS_PALAIS_GLASS_READY');sys.exit(0)
# Remove prior generated seed nodes before rebuilding to avoid accumulated graphs.
for n in list(L.get_material_expressions(m)):
    if isinstance(n,(unreal.MaterialExpressionPerInstanceCustomData,unreal.MaterialExpressionVertexInterpolator,unreal.MaterialExpressionAppendVector)):
        L.delete_material_expression(m,n)
L.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
customs=[n for n in L.get_material_expressions(m) if isinstance(n,unreal.MaterialExpressionCustom) and 'float3 N=normalize(Normal)' in n.get_editor_property('code')]
if len(customs)!=1:raise RuntimeError('Expected one window interior shader')
# Instance data is explicitly carried from vertex to pixel shading. The seed
# changes curtain placement; all rooms and glass are a visual approximation.
existing=[n for n in L.get_material_expressions(m) if isinstance(n,unreal.MaterialExpressionPerInstanceCustomData)]
seed=existing[0] if existing else L.create_material_expression(m,unreal.MaterialExpressionPerInstanceCustomData)
seed.set_editor_property('data_index',0)
inter=L.create_material_expression(m,unreal.MaterialExpressionVertexInterpolator)
if not L.connect_material_expressions(seed,'',inter,L.get_material_expression_input_names(inter)[0]):raise RuntimeError('Seed interpolator')
a=L.create_material_expression(m,unreal.MaterialExpressionAppendVector);b=L.create_material_expression(m,unreal.MaterialExpressionAppendVector)
for node,pin in [(a,'A'),(a,'B'),(b,'B')]:
    if not L.connect_material_expressions(inter,'',node,pin):raise RuntimeError('Seed vector')
if not L.connect_material_expressions(a,'',b,'A') or not L.connect_material_expressions(b,'',customs[0],'Seed'):raise RuntimeError('Seed to glass shader')
L.recompile_material(m)
A.set_metadata_tag(m,'ParisTwin.RecipeSHA256',signature)
A.set_metadata_tag(m,'ParisTwin.AppearanceProvenance','Derived procedural room illusion and reflective glass; not a photo, no actual interior.')
if not A.save_loaded_asset(m,only_if_is_dirty=False):raise RuntimeError('Cannot save Palais glass')
sentinel.unlink(missing_ok=True)
unreal.log_warning('PARIS_PALAIS_GLASS_READY')
