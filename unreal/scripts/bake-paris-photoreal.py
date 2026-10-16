"""Bake the existing near-field GIS geometry for SDF/Lumen/Nanite, offline."""
import json
import os
import struct
import unreal

project=unreal.Paths.project_dir()
data_dir=os.path.join(project,'Content','Data')
unreal.EditorAssetLibrary.make_directory('/Game/ParisPhotoreal/Generated')
with open(os.path.join(data_dir,'paris-digital-twin-runtime.json'),encoding='utf-8-sig') as f:scene=json.load(f)
with open(os.path.join(data_dir,'paris-digital-twin-meshes.bin'),'rb') as f:blob=f.read()
assets=unreal.EditorAssetLibrary
records=[]
RECIPE='static_gis_sdf_nanite_v3'


def linear(byte):
    value=byte/255
    return value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4


for obj in scene['objects']:
    spec=scene['baked_visuals'].get(obj['id'])
    if not spec:continue
    package=spec['asset']
    existing=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not package.startswith('/Game/ParisPhotoreal/Generated/SM_Paris_'):raise RuntimeError('Unexpected bake destination')
    if existing:
        signature=assets.get_metadata_tag(existing,'ParisTwin.GeometrySHA256')
        if signature and signature!=spec['geometry_sha256']:raise RuntimeError('Existing bake has a different geometry signature')
        if signature and assets.get_metadata_tag(existing,'ParisTwin.BakeRecipe')==RECIPE:
            records.append(dict(id=obj['id'],asset=package,cached=True));continue
    span=obj['mesh_buffer'];offset=span['offset'];vertices=span['vertex_count']
    rows=list(struct.iter_unpack('<6f4B',blob[offset:offset+vertices*28]))
    indices=struct.unpack_from('<'+str(span['index_count'])+'I',blob,offset+vertices*28)
    buffers=unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_properties(dict(vertices=[unreal.Vector(*r[:3]) for r in rows],
        normals=[unreal.Vector(*r[3:6]) for r in rows],uv0=[unreal.Vector2D(0,0)]*vertices,
        vertex_colors=[unreal.LinearColor(linear(r[6]),linear(r[7]),linear(r[8]),1) for r in rows],
        triangles=[unreal.IntVector(*indices[i:i+3]) for i in range(0,len(indices),3)]))
    dynamic=unreal.DynamicMesh()
    unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers,material_id=0)
    options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,
        enable_recompute_tangents=False,use_original_vertex_order=True))
    if existing:
        # Recover only our interrupted, content-addressed bake. GeometryScript
        # saves the mesh before the final provenance tags are written.
        if not signature and existing.get_num_triangles(0)!=spec['triangles']:raise RuntimeError('Incomplete bake has unexpected geometry')
        mesh=existing
    else:
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
    if not mesh:raise RuntimeError('Static asset bake failed: '+package)
    roof=obj['properties'].get('roof_material')
    material='/Game/Materials/'+('M_Paris_Roof_Zinc' if roof=='zinc' else 'M_Paris_Roof_Slate' if obj['kind']=='roof' else 'M_Paris_Limestone')
    surface=assets.load_asset(material)
    if not surface:raise RuntimeError('Generate Paris materials before baking: '+material)
    mesh.set_material(0,surface)
    mesh.set_editor_property('allow_cpu_access',True)
    mesh.set_editor_property('generate_mesh_distance_field',True)
    nanite=mesh.get_editor_property('nanite_settings')
    nanite.set_editor_property('enabled',True)
    nanite.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED)
    nanite.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
    nanite.set_editor_property('fallback_relative_error',0.)
    nanite.set_editor_property('fallback_percent_triangles',1.)
    mesh.set_editor_property('nanite_settings',nanite)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',spec['geometry_sha256'])
    assets.set_metadata_tag(mesh,'ParisTwin.SourceIDs',';'.join(spec['source_ids']))
    assets.set_metadata_tag(mesh,'ParisTwin.BakeRecipe',RECIPE)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometryProvenance','Unchanged GIS volume; not a surveyed decorative model')
    if not assets.save_loaded_asset(mesh):raise RuntimeError('Cannot save baked static mesh')
    # Runtime verifies exact topology and retains its exact fast-built copy for
    # roofs containing tiny/degenerate triangles removed by UE's asset builder.
    records.append(dict(id=obj['id'],asset=package,cached=False,triangles=spec['triangles'],fallback_triangles=mesh.get_num_triangles(0),exact_fallback=mesh.get_num_triangles(0)==spec['triangles']))
    del buffers,dynamic,rows,indices
    unreal.SystemLibrary.collect_garbage()
output=os.path.join(project,'Saved','paris-v2-bake-report.json')
with open(output,'w',encoding='utf-8') as f:json.dump(dict(source_scene_sha256=scene['source_scene_sha256'],bake_recipe=RECIPE,meshes=records),f,indent=2)
unreal.log_warning('PARIS_PHOTOREAL_BAKE_READY '+str(len(records)))
