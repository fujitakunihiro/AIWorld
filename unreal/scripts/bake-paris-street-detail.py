"""Bake two original shared lantern meshes. Source colliders remain in runtime."""
import json
import os
import unreal

assets=unreal.EditorAssetLibrary
folder=os.path.join(unreal.Paths.project_content_dir(),'Data')
with open(os.path.join(folder,'paris-photo-street-source.json'),encoding='utf-8') as f:source=json.load(f)
runtime={k:v for k,v in source.items() if k!='objects'};runtime['objects']=[]
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not mesh:
        # UE can remove empty content directories between commandlets. Create
        # the physical destination in this process immediately before saving.
        assets.make_directory('/Game/ParisPhotoreal/Street')
        os.makedirs(os.path.realpath(os.path.join(unreal.Paths.project_content_dir(),'ParisPhotoreal','Street')),exist_ok=True)
        def linear(byte):
            v=byte/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        color=unreal.LinearColor(*[linear(int(item['color'][i:i+2],16)) for i in [0,2,4]],1)
        buf=unreal.GeometryScriptSimpleMeshBuffers()
        buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(0,0)]*len(item['normals']),vertex_colors=[color]*len(item['normals']),triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        options.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Lantern bake failed: '+package)
    material=assets.load_asset(item['material'])
    if not material:raise RuntimeError('Lantern material missing: '+item['material'])
    mesh.set_material(0,material);mesh.set_editor_property('allow_cpu_access',True);mesh.set_editor_property('generate_mesh_distance_field',True)
    settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',True);settings.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES);settings.set_editor_property('fallback_percent_triangles',1.);settings.set_editor_property('fallback_relative_error',0.);mesh.set_editor_property('nanite_settings',settings)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256']);assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance'])
    if not assets.save_loaded_asset(mesh):raise RuntimeError('Lantern asset save failed')
    runtime['objects'].append({k:item[k] for k in ['id','asset','geometry_sha256','triangles']})
with open(os.path.join(folder,'paris-photo-street.json'),'w',encoding='utf-8') as f:json.dump(runtime,f,indent=2)
unreal.log_warning('PARIS_PHOTO_STREET_READY')
