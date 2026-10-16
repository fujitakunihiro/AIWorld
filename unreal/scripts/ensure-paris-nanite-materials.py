"""Persist actual Nanite material permutations; never use the default fallback.

Loading a Nanite mesh in an unattended game can request a usage permutation
without saving it. Fix the base materials offline, including instance parents.
"""
import json
import os
import unreal

assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary
usage=unreal.MaterialUsage.MATUSAGE_NANITE
folder=os.path.join(unreal.Paths.project_content_dir(),'Data')
paths=set()
for filename in ['paris-digital-twin-runtime.json','paris-photo-architecture.json','paris-photo-street.json','paris-photo-frontages.json']:
    with open(os.path.join(folder,filename),encoding='utf-8-sig') as f:packet=json.load(f)
    if filename=='paris-digital-twin-runtime.json':
        paths.update(v['asset'] for v in packet['baked_visuals'].values())
    else:paths.update(v['asset'] for v in packet['objects'])
paths.add('/Game/ParisPhotoreal/Nature/SM_ParisBroadleaf')
materials={}


def remember(interface):
    if interface:
        base=interface.get_base_material()
        if not base or not base.get_path_name().startswith('/Game/'):raise RuntimeError('Unexpected Nanite material parent')
        materials[base.get_path_name()]=base


for path in sorted(paths):
    mesh=assets.load_asset(path)
    if not mesh:raise RuntimeError('Cannot inspect Nanite material slots: '+path)
    for slot in mesh.get_editor_property('static_materials'):remember(slot.material_interface)
# Runtime overrides used for the cathedral body and Low/procedural comparison.
for path in ['/Game/Materials/M_ParisCathedralStone','/Game/Materials/M_Vertex','/Game/Materials/M_ParisLimestoneProcedural','/Game/Materials/M_ParisSlate']:
    remember(assets.load_asset(path))
records=[]
for path,mat in sorted(materials.items()):
    changed=not lib.has_material_usage(mat,usage)
    if changed:
        lib.set_material_usage(mat,usage)
        lib.recompile_material(mat)
        if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot persist Nanite material: '+path)
    if not lib.has_material_usage(mat,usage):raise RuntimeError('Nanite permutation is still unavailable: '+path)
    records.append(dict(material=path,nanite_usage=True,changed=changed))
with open(os.path.join(unreal.Paths.project_saved_dir(),'paris-nanite-materials.json'),'w',encoding='utf-8') as f:json.dump(dict(meshes=len(paths),materials=records),f,indent=2)
unreal.log_warning('PARIS_NANITE_MATERIALS_READY '+str(len(records)))
