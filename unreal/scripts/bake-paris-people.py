"""Import the verified Rocketbox subset with original skin weights and materials."""
import hashlib
import json
import os
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'unreal/assets/paris-people'
DEST = '/Game/ParisPhotoreal/People'
assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
manifest = json.loads((SOURCE / 'sources.json').read_text())
for record in manifest['files']:
    if hashlib.sha256((SOURCE / 'Raw' / record['path']).read_bytes()).hexdigest() != record['sha256']:
        raise RuntimeError('Unverified pedestrian input: ' + record['path'])
if manifest['license'] != 'MIT':
    raise RuntimeError('Unexpected pedestrian license')

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
lib = unreal.MaterialEditingLibrary


def imported(filename, folder, name, options=None):
    os.makedirs(os.path.realpath(str(ROOT / 'unreal/AIWorld/Content' / folder[6:])), exist_ok=True)
    assets.make_directory(folder)
    path = folder + '/' + name
    if assets.does_asset_exist(path):
        existing = assets.load_asset(path)
        if not isinstance(existing, (unreal.SkeletalMesh, unreal.AnimSequence)) or existing.get_editor_property('skeleton'):
            return existing
    task = unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(filename), destination_path=folder, destination_name=name,
                                    automated=True, replace_existing=True, save=True))
    if options:
        task.set_editor_property('options', options)
        task.set_editor_property('factory', unreal.FbxFactory())
    tools.import_asset_tasks([task])
    result = assets.load_asset(path)
    if not result:
        raise RuntimeError('No imported asset: ' + path + ' outputs=' + str(task.imported_object_paths))
    return result


def node(mat, cls, **properties):
    n = lib.create_material_expression(mat, cls)
    n.set_editor_properties(properties)
    return n


def material(name, textures, hair=False, skin=False):
    os.makedirs(os.path.realpath(str(ROOT / 'unreal/AIWorld/Content' / DEST[6:] / 'Materials')), exist_ok=True)
    assets.make_directory(DEST + '/Materials')
    path = DEST + '/Materials/' + name
    mat = assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
        name, DEST + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('used_with_skeletal_mesh', True)
    color = node(mat, unreal.MaterialExpressionTextureSample, texture=textures['color'])
    lib.connect_material_property(color, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    rough = node(mat, unreal.MaterialExpressionConstant, r=.65)
    lib.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    if hair:
        mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        mat.set_editor_property('two_sided', True)
        mat.set_editor_property('opacity_mask_clip_value', .4)
        lib.connect_material_property(color, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
    else:
        normal = node(mat, unreal.MaterialExpressionTextureSample, texture=textures['normal'],
                      sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        lib.connect_material_property(normal, 'RGB', unreal.MaterialProperty.MP_NORMAL)
        spec = node(mat, unreal.MaterialExpressionTextureSample, texture=textures['specular'],
                    sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        # Original Max specular is not a PBR roughness measurement. Keep it a
        # bounded, approximate dielectric response, never metallic skin/cloth.
        remap = node(mat, unreal.MaterialExpressionMultiply, const_b=-.35)
        lib.connect_material_expressions(spec, 'R', remap, 'A')
        add = node(mat, unreal.MaterialExpressionAdd, const_b=.78)
        lib.connect_material_expressions(remap, '', add, 'A')
        lib.connect_material_property(add, '', unreal.MaterialProperty.MP_ROUGHNESS)
        if skin:
            mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_SUBSURFACE)
            scatter = node(mat, unreal.MaterialExpressionMultiply, const_b=.18)
            lib.connect_material_expressions(color, 'RGB', scatter, 'A')
            lib.connect_material_property(scatter, '', unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
            density = node(mat, unreal.MaterialExpressionConstant, r=.75)
            lib.connect_material_property(density, '', unreal.MaterialProperty.MP_OPACITY)
    assets.set_metadata_tag(mat, 'ParisTwin.License', 'MIT')
    assets.set_metadata_tag(mat, 'ParisTwin.SourceCommit', manifest['commit'])
    lib.recompile_material(mat)
    assets.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


runtime = dict(schema_version=1, license='MIT', source_commit=manifest['commit'],
               source_url=manifest['repository'], inferred_population=True, avatars=[])
for avatar in manifest['avatars']:
    name, prefix, sex = (avatar[k] for k in ['name', 'texture_prefix', 'animation_prefix'])
    source = SOURCE / 'Raw/Assets/Avatars/Adults' / name
    textures, mats = {}, {}
    for part in ['head', 'body', 'opacity']:
        textures[part] = {}
        for channel in (['color'] if part == 'opacity' else ['color', 'normal', 'specular']):
            key = prefix + '_' + part + '_' + channel
            tex = imported(source / 'Textures' / (key + '.tga'), DEST + '/Textures', 'T_' + key)
            tex.set_editor_property('max_texture_size', 2048)
            tex.set_editor_property('srgb', channel == 'color')
            if channel == 'normal':
                tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
            assets.save_loaded_asset(tex, only_if_is_dirty=False)
            textures[part][channel] = tex
        mats[part] = material('M_' + prefix + '_' + part, textures[part], part == 'opacity', part == 'head')
    options = unreal.FbxImportUI()
    options.set_editor_properties(dict(import_as_skeletal=True, import_mesh=True, import_materials=False,
        import_textures=False, import_animations=False, automated_import_should_detect_type=False,
        mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH, create_physics_asset=False))
    options.skeletal_mesh_import_data.set_editor_properties(dict(import_uniform_scale=1., force_front_x_axis=True))
    mesh = imported(source / 'Export' / (name + '.fbx'), DEST + '/' + name, 'SK_' + name, options)
    if not isinstance(mesh, unreal.SkeletalMesh):
        raise RuntimeError('Expected a skinned human: ' + name)
    slots = mesh.get_editor_property('materials')
    slot_names = []
    for slot_index, slot in enumerate(slots):
        slot_name = str(slot.material_slot_name).lower()
        part = 'head' if 'head' in slot_name else 'opacity' if 'opac' in slot_name else 'body'
        slot.set_editor_property('material_interface', mats[part])
        # Array iteration returns a struct copy. Persist the edited entry,
        # otherwise all three saved material interfaces remain empty.
        slots[slot_index] = slot
        slot_names.append(dict(name=slot_name, surface=part))
    mesh.set_editor_property('materials', slots)
    skeleton = mesh.get_editor_property('skeleton')
    if not assets.save_loaded_asset(skeleton, only_if_is_dirty=False):
        raise RuntimeError('Could not save shared human skeleton: ' + name)
    mesh_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    if mesh_editor.get_lod_count(mesh) < 3:
        if not mesh_editor.regenerate_lod(mesh, 3):
            raise RuntimeError('Could not create skeletal LODs: ' + name)
    # Preserve the explicit bindings after any import/reduction operations.
    mesh.set_editor_property('materials', slots)
    clips = {}
    for key, kind, clip in [('walk', 'xy', 'walk_neutral_01'), ('run', 'xy', 'run_neutral_01'), ('idle', 'static', 'idle_breathe_01'), ('sit', 'static', 'sit_chair_breathe_01')]:
        options = unreal.FbxImportUI()
        options.set_editor_properties(dict(import_as_skeletal=True, import_mesh=False, import_materials=False,
            import_textures=False, import_animations=True, skeleton=skeleton,
            automated_import_should_detect_type=False, mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION))
        options.anim_sequence_import_data.set_editor_properties(dict(import_uniform_scale=1., force_front_x_axis=True,
            use_default_sample_rate=True))
        file = SOURCE / 'Raw/Assets/Animations' / ('all_animations_max_motextr_' + kind) / (sex + '_' + clip + '.max.fbx')
        anim = imported(file, DEST + '/' + name, 'A_' + name + '_' + key, options)
        if not isinstance(anim, unreal.AnimSequence):
            raise RuntimeError('Missing actual animation: ' + key)
        anim.set_editor_property('enable_root_motion', False)
        anim.set_editor_property('force_root_lock', True)
        anim.set_editor_property('root_motion_root_lock', unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
        assets.save_loaded_asset(anim, only_if_is_dirty=False)
        clips[key] = anim.get_path_name()
    assets.set_metadata_tag(mesh, 'ParisTwin.License', 'MIT')
    assets.set_metadata_tag(mesh, 'ParisTwin.SourceCommit', manifest['commit'])
    if not assets.save_loaded_asset(mesh, only_if_is_dirty=False):
        raise RuntimeError('Could not persist textured human mesh: ' + name)
    for slot in mesh.get_editor_property('materials'):
        if not slot.material_interface:
            raise RuntimeError('Human material binding is empty: ' + str(slot.material_slot_name))
    bounds = mesh.get_bounds()
    runtime['avatars'].append(dict(name=name, mesh=mesh.get_path_name(), skeleton=skeleton.get_path_name(),
        animations=clips, material_slots=slot_names, yaw_offset_degrees=0., height_cm=bounds.box_extent.z * 2,
        lod_vertices=[mesh_editor.get_num_verts(mesh, i) for i in range(mesh_editor.get_lod_count(mesh))]))

out = Path(unreal.Paths.project_content_dir()) / 'Data/paris-people.json'
out.write_text(json.dumps(runtime, indent=2) + '\n', encoding='utf-8')
unreal.log_warning('PARIS_PEOPLE_READY ' + str(len(runtime['avatars'])))
