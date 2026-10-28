"""Bake the CC0 ferry and its authored 2K color textures into UE assets."""
import array, hashlib, json, struct
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'unreal/assets/paris-cruise/Generated'
src=json.loads((G/'source.json').read_text(encoding='utf-8'))
a=unreal.EditorAssetLibrary;t=unreal.AssetToolsHelpers.get_asset_tools();l=unreal.MaterialEditingLibrary
base='/Game/ParisPhotoreal/Cruise'
for d in (base,base+'/Materials',base+'/Textures'):a.make_directory(d)
def node(mat,cls,**kw):
    x=l.create_material_expression(mat,cls)
    if kw:x.set_editor_properties(kw)
    return x
def connect(x,y,pin=''):
    if not l.connect_material_property(x,pin,y):raise ValueError('material output '+str(y))
def const(m,x):return node(m,unreal.MaterialExpressionConstant,r=x)
textures=[]
for i,info in enumerate(src['textures']):
    path=G/info['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('texture hash mismatch')
    name='T_ParisCruise_%02d'%i;package=base+'/Textures/'+name
    tex=a.load_asset(package) if a.does_asset_exist(package) else None
    if not tex:
        task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=str(path),destination_path=base+'/Textures',destination_name=name,automated=True,replace_existing=True,save=True))
        t.import_asset_tasks([task]);tex=a.load_asset(package)
    if not tex:raise ValueError('texture import '+package)
    tex.set_editor_property('srgb',True);a.save_loaded_asset(tex,only_if_is_dirty=False);textures.append(tex)
materials={}
for m in src['materials']:
    i=m['id'];name='M_ParisCruise_%02d'%i;pkg=base+'/Materials/'+name
    mat=a.load_asset(pkg) if a.does_asset_exist(pkg) else t.create_asset(name,base+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    l.delete_all_material_expressions(mat)
    glass=i==6
    mat.set_editor_properties(dict(two_sided=glass,blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT if glass else unreal.BlendMode.BLEND_OPAQUE,shading_model=unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT if glass else unreal.MaterialShadingModel.MSM_DEFAULT_LIT))
    if not glass:l.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    sample=node(mat,unreal.MaterialExpressionTextureSample,texture=textures[m['texture']])
    connect(sample,unreal.MaterialProperty.MP_BASE_COLOR,'RGB')
    connect(const(mat,m['roughness']),unreal.MaterialProperty.MP_ROUGHNESS)
    connect(const(mat,m['metallic']),unreal.MaterialProperty.MP_METALLIC)
    if glass:
        mat.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        connect(const(mat,.2),unreal.MaterialProperty.MP_OPACITY)
        outputs=[x for x in l.get_material_expressions(mat) if isinstance(x,unreal.MaterialExpressionThinTranslucentMaterialOutput)]
        trans=outputs[0] if outputs else node(mat,unreal.MaterialExpressionThinTranslucentMaterialOutput)
        for x in outputs[1:]:l.delete_material_expression(mat,x)
        tint=node(mat,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.75,.86,.9,1))
        if not l.connect_material_expressions(tint,'',trans,l.get_material_expression_input_names(trans)[0]):raise ValueError('glass transmission')
    l.recompile_material(mat);a.save_loaded_asset(mat,only_if_is_dirty=False);materials[i]=mat
runtime={k:v for k,v in src.items() if k!='parts'};runtime['parts']=[]
for part in src['parts']:
    package=part['asset'];mesh=a.load_asset(package) if a.does_asset_exist(package) else None
    if not mesh:
        dynamic=unreal.DynamicMesh()
        for slot,p in enumerate(part['primitives']):
            blob=(G/p['file']).read_bytes()
            if hashlib.sha256(blob).hexdigest()!=p['sha256']:raise ValueError('geometry hash')
            magic,n,tris=struct.unpack_from('<8sII',blob)
            if magic!=b'NDSCAN01':raise ValueError('geometry header')
            f=array.array('f');f.frombytes(blob[16:16+n*32]);indices=array.array('I');indices.frombytes(blob[16+n*32:])
            if len(indices)!=tris*3:raise ValueError('geometry length')
            buf=unreal.GeometryScriptSimpleMeshBuffers();buf.set_editor_properties(dict(vertices=[unreal.Vector(*f[i*3:i*3+3]) for i in range(n)],normals=[unreal.Vector(*f[n*3+i*3:n*3+i*3+3]) for i in range(n)],uv0=[unreal.Vector2D(*f[n*6+i*2:n*6+i*2+2]) for i in range(n)],triangles=[unreal.IntVector(*indices[i:i+3]) for i in range(0,len(indices),3)]))
            unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=slot)
        opts=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();opts.set_editor_properties(dict(enable_nanite=part['id']=='body',enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=True))
        mesh,out=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,opts)
        if not mesh:raise ValueError('mesh bake '+package)
    slots=[]
    for p in part['primitives']:
        slot=unreal.StaticMaterial();slot.set_editor_properties(dict(material_interface=materials[p['material']],material_slot_name='Cruise_%02d'%p['material']));slots.append(slot)
    mesh.set_editor_property('static_materials',slots)
    ns=mesh.get_editor_property('nanite_settings');ns.set_editor_property('enabled',part['id']=='body');ns.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED);ns.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES);ns.set_editor_property('fallback_percent_triangles',.25);mesh.set_editor_property('nanite_settings',ns)
    mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',False)
    a.set_metadata_tag(mesh,'ParisTwin.SourceURL',src['source']['source_url']);a.set_metadata_tag(mesh,'ParisTwin.License',src['source']['license'])
    a.save_loaded_asset(mesh,only_if_is_dirty=False)
    runtime['parts'].append(dict(id=part['id'],asset=package,triangles=sum(p['triangles'] for p in part['primitives'])))
(Path(unreal.Paths.project_content_dir())/'Data/paris-cruise.json').write_text(json.dumps(runtime,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_CRUISE_ASSETS_READY')
