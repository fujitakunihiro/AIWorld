"""Create native UE material assets and the startup map; no external assets required."""
import unreal

tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary
def material(name, vertex=False, water=False):
    path = '/Game/Materials/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mat = unreal.EditorAssetLibrary.load_asset(path)
        if unreal.EditorAssetLibrary.get_metadata_tag(mat, 'AIWorld.Generator') == '2':
            return
        lib.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(name, '/Game/Materials', unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property('two_sided', True)
    if vertex:
        color = lib.create_material_expression(mat, unreal.MaterialExpressionVertexColor, -400, 0)
    else:
        color = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
        color.set_editor_property('parameter_name', 'Tint')
        color.set_editor_property('default_value', unreal.LinearColor(.5, .5, .5, 1))
    assert lib.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    rough = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 140)
    rough.set_editor_property('r', .2 if water else .85)
    assert lib.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    if not vertex:
        lib.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    if water:
        pos = lib.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -900, 400)
        mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -700, 400)
        mask.set_editor_property('r', True)
        mask.set_editor_property('g', False)
        assert lib.connect_material_expressions(pos, '', mask, '')
        scale = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -550, 400)
        scale.set_editor_property('const_b', .003)
        assert lib.connect_material_expressions(mask, '', scale, 'A')
        time = lib.create_material_expression(mat, unreal.MaterialExpressionTime, -700, 550)
        add = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -350, 400)
        assert lib.connect_material_expressions(scale, '', add, 'A')
        assert lib.connect_material_expressions(time, '', add, 'B')
        sine = lib.create_material_expression(mat, unreal.MaterialExpressionSine, -180, 400)
        assert lib.connect_material_expressions(add, '', sine, '')
        direction = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -180, 600)
        direction.set_editor_property('constant', unreal.LinearColor(0, 0, 3))
        wave = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 0, 400)
        assert lib.connect_material_expressions(sine, '', wave, 'A')
        assert lib.connect_material_expressions(direction, '', wave, 'B')
        assert lib.connect_material_property(wave, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    lib.recompile_material(mat)
    unreal.EditorAssetLibrary.set_metadata_tag(mat, 'AIWorld.Generator', '2')
    unreal.EditorAssetLibrary.save_loaded_asset(mat)

material('M_Vertex', vertex=True)
material('M_Color')
material('M_Water', vertex=True, water=True)
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Maps/Main'):
    sub.new_level('/Game/Maps/Main')
    sub.save_current_level()
unreal.log('AIWORLD_ASSETS_READY')
