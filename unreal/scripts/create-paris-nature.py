"""Import a real CC0 tree, normalize its appearance envelope, and build UE PBR."""
import hashlib
import json
import os
import sys
import unreal
sys.path.insert(0,os.path.dirname(__file__))
from paris_foliage import RECIPE, WIND_DISABLE_DISTANCE_CM, finish_tree_material

def main():
    root=os.path.normpath(os.path.join(os.path.dirname(__file__),'..','assets','paris-nature'))
    with open(os.path.join(root,'manifest.json'),encoding='utf-8') as f:manifest=json.load(f)
    if manifest['license']!='CC0-1.0':raise RuntimeError('Unverified nature asset license')
    for filename,record in manifest['files'].items():
        with open(os.path.join(root,filename),'rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=record['sha256']:raise RuntimeError('Nature source changed: '+filename)
    with open(os.path.join(root,manifest['asset']+'_2k.gltf'),encoding='utf-8') as f:source=json.load(f)
    bounds=[source['accessors'][p['attributes']['POSITION']] for m in source['meshes'] for p in m['primitives']]
    lo=[min(a['min'][k] for a in bounds) for k in range(3)];hi=[max(a['max'][k] for a in bounds) for k in range(3)]
    sx,sy,sz=6/(hi[0]-lo[0]),10/(hi[1]-lo[1]),6/(hi[2]-lo[2])
    source['nodes'][0]['matrix']=[sx,0,0,0,0,sy,0,0,0,0,sz,0,0,-lo[1]*sy,0,1]
    canonical=os.path.join(root,'paris_broadleaf.gltf')
    with open(canonical,'w',encoding='utf-8') as f:json.dump(source,f)
    assets=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();lib=unreal.MaterialEditingLibrary
    folder='/Game/ParisPhotoreal/Nature';package=folder+'/SM_ParisBroadleaf'
    recipe_bytes=b''.join(open(os.path.join(os.path.dirname(__file__),name),'rb').read().replace(b'\r\n',b'\n') for name in ('create-paris-nature.py','paris_foliage.py'))
    signature=hashlib.sha256(recipe_bytes+json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    cached=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if cached and assets.get_metadata_tag(cached,'ParisTwin.NatureRecipe')==signature and os.path.isfile(os.path.join(unreal.Paths.project_content_dir(),'Data','paris-nature.json')):
        unreal.log_warning('PARIS_PHOTO_NATURE_CACHED');return
    for sub in ('Materials','Textures','paris_broadleaf/StaticMeshes','paris_broadleaf/Materials','paris_broadleaf/Textures'):
        assets.make_directory(folder+'/'+sub)
    mesh=cached
    if not mesh:
        task=unreal.AssetImportTask();task.set_editor_properties(dict(filename=canonical,destination_path=folder,automated=True,replace_existing=True,save=True))
        tools.import_asset_tasks([task])
        meshes=[assets.load_asset(p) for p in task.imported_object_paths if isinstance(assets.load_asset(p),unreal.StaticMesh)]
        if len(meshes)!=1:raise RuntimeError('Expected one actual combined tree mesh')
        mesh=meshes[0]
    if mesh.get_path_name().split('.')[0]!=package:
        if not assets.rename_asset(mesh.get_path_name(),package):raise RuntimeError('Could not assign stable tree asset name')
        mesh=assets.load_asset(package)
    texture_cache={}


    def texture(filename,role):
        if filename in texture_cache:return texture_cache[filename]
        name='T_'+os.path.splitext(os.path.basename(filename))[0]
        path=folder+'/Textures/'+name
        t=assets.load_asset(path) if assets.does_asset_exist(path) else None
        if not t:
            job=unreal.AssetImportTask();job.set_editor_properties(dict(filename=os.path.join(root,filename),destination_path=folder+'/Textures',destination_name=name,automated=True,replace_existing=True,save=True));tools.import_asset_tasks([job]);t=assets.load_asset(path)
        if not t:raise RuntimeError('PBR texture missing: '+filename)
        t.set_editor_property('srgb',role=='diff')
        t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if role=='normal' else unreal.TextureCompressionSettings.TC_DEFAULT if role=='diff' else unreal.TextureCompressionSettings.TC_MASKS)
        if role=='normal':t.set_editor_property('flip_green_channel',True) # source is explicitly OpenGL
        if not assets.save_loaded_asset(t):raise RuntimeError('Could not save nature texture')
        texture_cache[filename]=t;return t


    def node(mat,cls,**kwargs):
        n=lib.create_material_expression(mat,cls,0,0)
        if kwargs:n.set_editor_properties(kwargs)
        return n


    def link(a,output,b,pin):
        if not lib.connect_material_expressions(a,output,b,pin):raise RuntimeError('Nature material pin: '+pin)


    for index,material in enumerate(source['materials']):
        leaf='leaves' in material['name'];branch='branches' in material['name'];name='M_ParisBroadleaf_'+str(index);path=folder+'/Materials/'+name
        mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,folder+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True)
        lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
        if leaf:
            mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
            mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
            mat.set_editor_property('opacity_mask_clip_value',.4)
        uv=node(mat,unreal.MaterialExpressionTextureCoordinate)
        normal_info=material['normalTexture'];transform=normal_info.get('extensions',{}).get('KHR_texture_transform',{})
        if transform:
            scale=node(mat,unreal.MaterialExpressionConstant2Vector,r=transform.get('scale',[1,1])[0],g=transform.get('scale',[1,1])[1]);mul=node(mat,unreal.MaterialExpressionMultiply);link(uv,'',mul,'A');link(scale,'',mul,'B')
            shift=node(mat,unreal.MaterialExpressionConstant2Vector,r=transform.get('offset',[0,0])[0],g=transform.get('offset',[0,0])[1]);uv=node(mat,unreal.MaterialExpressionAdd);link(mul,'',uv,'A');link(shift,'',uv,'B')
        def sample(info,role):
            filename=source['images'][source['textures'][info['index']]['source']]['uri']
            t=texture(filename,role);n=node(mat,unreal.MaterialExpressionTextureSample,texture=t,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if role=='normal' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if role=='diff' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS);link(uv,'',n,'UVs');return n
        base=sample(material['pbrMetallicRoughness']['baseColorTexture'],'diff')
        normal=sample(normal_info,'normal');arm=sample(material['pbrMetallicRoughness']['metallicRoughnessTexture'],'arm')
        finish_tree_material(mat,base,normal,arm,leaf=leaf,branch=branch,normal_scale=normal_info.get('scale',1.))
        if leaf:
            alpha=texture('textures/'+manifest['asset']+'_leaves_alpha_2k.png','alpha')
            a=node(mat,unreal.MaterialExpressionTextureSample,texture=alpha,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS);link(uv,'',a,'UVs');lib.connect_material_property(a,'R',unreal.MaterialProperty.MP_OPACITY_MASK)
        lib.recompile_material(mat)
        if not assets.save_loaded_asset(mat):raise RuntimeError('Nature PBR material save failed')
        mesh.set_material(index,mat)
    settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',True);settings.set_editor_property('shape_preservation',unreal.NaniteShapePreservation.PRESERVE_AREA);settings.set_editor_property('fallback_relative_error',.15);mesh.set_editor_property('nanite_settings',settings)
    mesh.set_editor_property('allow_cpu_access',True)
    mesh.set_editor_property('generate_mesh_distance_field',True)
    assets.set_metadata_tag(mesh,'ParisTwin.NatureRecipe',signature);assets.set_metadata_tag(mesh,'ParisTwin.License','CC0-1.0');assets.set_metadata_tag(mesh,'ParisTwin.SourceURL',manifest['source_url']);assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',manifest['appearance_provenance'])
    if not assets.save_loaded_asset(mesh):raise RuntimeError('Could not save photo tree')
    box=mesh.get_bounding_box()
    if abs((box.max.z-box.min.z)-1000)>1:raise RuntimeError('Imported tree did not preserve canonical 10m height')
    report=dict(asset=package,source_triangles=sum(source['accessors'][p['indices']]['count']//3 for m in source['meshes'] for p in m['primitives']),height_cm=box.max.z-box.min.z,materials=len(source['materials']),source_url=manifest['source_url'],license=manifest['license'],recipe=RECIPE,recipe_sha256=signature,wind_disable_distance_cm=WIND_DISABLE_DISTANCE_CM,
        appearance_provenance=manifest['appearance_provenance'],texture_resolution=manifest['maps_resolution'])
    with open(os.path.join(unreal.Paths.project_content_dir(),'Data','paris-nature.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
    with open(os.path.join(unreal.Paths.project_dir(),'Saved','paris-v3-nature-import.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
    unreal.log_warning('PARIS_PHOTO_NATURE_READY')


if __name__=='__main__':main()
