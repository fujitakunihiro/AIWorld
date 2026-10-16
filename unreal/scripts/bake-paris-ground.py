"""Bake the rendering-only terrain cutout; do not create a replacement collider."""
import json
import os
import unreal

assets=unreal.EditorAssetLibrary;folder=os.path.join(unreal.Paths.project_content_dir(),'Data')
with open(os.path.join(folder,'paris-photo-ground-source.json'),encoding='utf-8') as f:data=json.load(f)
package=data['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
if not mesh:
    assets.make_directory('/Game/ParisPhotoreal/Ground')
    os.makedirs(os.path.realpath(os.path.join(unreal.Paths.project_content_dir(),'ParisPhotoreal','Ground')),exist_ok=True)
    def linear(b):
        v=b/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
    color=unreal.LinearColor(*[linear(int(data['color'][i:i+2],16)) for i in [0,2,4]],1)
    buf=unreal.GeometryScriptSimpleMeshBuffers()
    buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in data['positions_cm']],normals=[unreal.Vector(*n) for n in data['normals']],uv0=[unreal.Vector2D(0,0)]*len(data['normals']),vertex_colors=[color]*len(data['normals']),triangles=[unreal.IntVector(*data['indices'][i:i+3]) for i in range(0,len(data['indices']),3)]))
    dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
    options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.set_editor_properties(dict(enable_nanite=False,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
    mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
    if not mesh:raise RuntimeError('Ground display bake failed')
material=assets.load_asset('/Game/Materials/M_ParisGroundPaving')
if not material:raise RuntimeError('Near-field inferred ground paving material missing')
mesh.set_material(0,material);mesh.set_editor_property('allow_cpu_access',True)
for key in ['source_scene_sha256','geometry_sha256','geometry_provenance']:assets.set_metadata_tag(mesh,'ParisTwin.'+key,data[key])
if not assets.save_loaded_asset(mesh):raise RuntimeError('Ground display asset save failed')
runtime={k:v for k,v in data.items() if k not in ['positions_cm','normals','indices']}
runtime['surface_provenance']='Inferred urban paving within 100m of the west anchor, fading to source palette by 130m. Not surveyed land cover.'
with open(os.path.join(folder,'paris-photo-ground.json'),'w',encoding='utf-8') as f:json.dump(runtime,f,indent=2)
unreal.log_warning('PARIS_PHOTO_GROUND_READY')
