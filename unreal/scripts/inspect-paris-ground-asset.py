"""Read actual saved RenderData for independent offline coverage verification."""
import json
import os
import unreal

with open(os.path.join(unreal.Paths.project_content_dir(),'Data','paris-photo-ground.json'),encoding='utf-8') as f:data=json.load(f)
mesh=unreal.EditorAssetLibrary.load_asset(data['asset'])
if not mesh:raise RuntimeError('Saved ground asset missing')
dynamic=unreal.DynamicMesh();lod=unreal.GeometryScriptMeshReadLOD()
lod.set_editor_properties(dict(lod_type=unreal.GeometryScriptLODType.RENDER_DATA,lod_index=0))
unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(mesh,dynamic,unreal.GeometryScriptCopyMeshFromAssetOptions(),lod)
result=unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dynamic,False)
vectors=next(item for item in result if isinstance(item,unreal.GeometryScriptVectorList))
vertices=unreal.GeometryScript_List.convert_vector_list_to_array(vectors)
result=unreal.GeometryScript_MeshQueries.get_all_triangle_indices(dynamic,False)
triples=next(item for item in result if isinstance(item,unreal.GeometryScriptTriangleList))
triangles=unreal.GeometryScript_List.convert_triangle_list_to_array(triples)
report=dict(asset=data['asset'],render_triangles=mesh.get_num_triangles(0),positions_cm=[[v.x,v.y,v.z] for v in vertices],indices=[[t.x,t.y,t.z] for t in triangles])
if not report['indices']:raise RuntimeError('Ground RenderData export is empty')
with open(os.path.join(unreal.Paths.project_saved_dir(),'paris-v5-ground-render-data.json'),'w',encoding='utf-8') as f:json.dump(report,f)
unreal.log_warning('PARIS_GROUND_RENDER_DATA '+str(report['render_triangles']))
