"""Import the licensed real candidate in an isolated folder, without placing it."""
import hashlib
import json
import os
import unreal

folder=os.path.normpath(os.path.join(os.path.dirname(__file__),'..','assets','notre-dame'))
with open(os.path.join(folder,'manifest.json'),encoding='utf-8') as f:source=json.load(f)
filename=os.path.join(folder,source['file'])
with open(filename,'rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
if digest!=source['sha256'] or source['license']!='CC-BY-4.0':raise RuntimeError('Unverified source model')
for sub in ('Textures','Materials','StaticMeshes','Meshes'):
    unreal.EditorAssetLibrary.make_directory('/Game/ParisPhotoreal/NotreDameCandidate/notre-dame/'+sub)
task=unreal.AssetImportTask()
task.set_editor_properties(dict(filename=filename,destination_path='/Game/ParisPhotoreal/NotreDameCandidate',automated=True,replace_existing=True,save=True))
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
records=[]
assets=unreal.EditorAssetLibrary
for path in task.imported_object_paths:
    asset=assets.load_asset(path)
    if not asset:raise RuntimeError('Imported asset is missing: '+path)
    assets.set_metadata_tag(asset,'ParisTwin.SourceURL',source['original_url'])
    assets.set_metadata_tag(asset,'ParisTwin.License','CC-BY-4.0')
    assets.set_metadata_tag(asset,'ParisTwin.Author',source['author'])
    assets.set_metadata_tag(asset,'ParisTwin.Acceptance','Candidate only: source Unlit / 1K colour; required PBR incomplete')
    if not assets.save_loaded_asset(asset):raise RuntimeError('Could not save candidate: '+path)
    record=dict(path=path,asset_class=asset.get_class().get_name())
    if isinstance(asset,unreal.StaticMesh):
        bounds=asset.get_bounding_box()
        record.update(triangles=asset.get_num_triangles(0),bounds_min=[bounds.min.x,bounds.min.y,bounds.min.z],bounds_max=[bounds.max.x,bounds.max.y,bounds.max.z])
    records.append(record)
if not any(x['asset_class']=='StaticMesh' for x in records):raise RuntimeError('No actual static meshes imported')
with open(os.path.join(unreal.Paths.project_dir(),'Saved','paris-v2-candidate-import.json'),'w',encoding='utf-8') as f:
    json.dump(dict(status='imported_not_accepted_not_placed',source_sha256=digest,assets=records),f,indent=2)
unreal.log_warning('PARIS_NOTREDAME_CANDIDATE_IMPORTED '+str(len(records)))
