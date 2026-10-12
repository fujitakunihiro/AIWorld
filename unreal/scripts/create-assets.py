"""Create native UE material and texture assets plus the startup map."""
import os
import unreal

tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary
texture_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'textures'))
def import_texture(name, filename):
    path = '/Game/Textures/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    task = unreal.AssetImportTask()
    task.set_editor_properties({'filename': os.path.join(texture_dir, filename),
        'destination_path': '/Game/Textures', 'destination_name': name,
        'automated': True, 'save': True})
    tools.import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError('Could not import texture: ' + filename)
    return asset

STONE = import_texture('T_Limestone', 'limestone-wall.png')
SLATE = import_texture('T_Slate', 'slate-roof.png')
GRASS = import_texture('T_IslandGrass', 'island-grass.png')
WORLD_TEXTURE = unreal.EditorAssetLibrary.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture')
if not WORLD_TEXTURE:
    raise RuntimeError('UE WorldAlignedTexture material function was not found')

def world_texture(mat, asset, parameter, size, x, y):
    texture = lib.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, x, y)
    texture.set_editor_properties({'parameter_name': parameter, 'texture': asset})
    call = lib.create_material_expression(mat, unreal.MaterialExpressionMaterialFunctionCall, x + 220, y)
    call.set_editor_property('material_function', WORLD_TEXTURE)
    assert lib.connect_material_expressions(texture, '', call, 'TextureObject')
    tile_size = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, x, y + 150)
    tile_size.set_editor_property('r', size)
    assert lib.connect_material_expressions(tile_size, '', call, 'TextureSize')
    return call

def material(name, vertex=False, water=False, surface=None, green_surface=False):
    path = '/Game/Materials/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mat = unreal.EditorAssetLibrary.load_asset(path)
        if unreal.EditorAssetLibrary.get_metadata_tag(mat, 'AIWorld.Generator') == '8':
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
    albedo = color
    if surface:
        source = STONE if surface == 'stone' else SLATE if surface == 'slate' else GRASS
        tile_size = 1500 if surface == 'stone' else 1250 if surface == 'slate' else 1350
        sample = world_texture(mat, source, 'SurfaceTexture', tile_size,
                               -1500, -500)
        # Reuse the configured world-aligned sample's native color output.
        surface_color = sample
        if surface in ('stone', 'slate'):
            layered = lib.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -700, -100)
            layered.set_editor_property('const_alpha', .9 if surface == 'stone' else .92)
            assert lib.connect_material_expressions(color, '', layered, 'A')
            assert lib.connect_material_expressions(surface_color, 'XYZ Texture', layered, 'B')
            albedo = layered
        else:
            r = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -800, -450)
            r.set_editor_property('r', True)
            r.set_editor_property('g', False)
            r.set_editor_property('b', False)
            assert lib.connect_material_expressions(surface_color, 'XYZ Texture', r, '')
            g = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -800, -300)
            g.set_editor_property('r', False)
            g.set_editor_property('g', True)
            g.set_editor_property('b', False)
            assert lib.connect_material_expressions(surface_color, 'XYZ Texture', g, '')
            b = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -800, -150)
            b.set_editor_property('r', False)
            b.set_editor_property('g', False)
            b.set_editor_property('b', True)
            assert lib.connect_material_expressions(surface_color, 'XYZ Texture', b, '')
            lr = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -600, -450)
            lr.set_editor_property('const_b', .2126)
            assert lib.connect_material_expressions(r, '', lr, 'A')
            lg = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -600, -300)
            lg.set_editor_property('const_b', .7152)
            assert lib.connect_material_expressions(g, '', lg, 'A')
            lb = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -600, -150)
            lb.set_editor_property('const_b', .0722)
            assert lib.connect_material_expressions(b, '', lb, 'A')
            sum_rg = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -400, -400)
            assert lib.connect_material_expressions(lr, '', sum_rg, 'A')
            assert lib.connect_material_expressions(lg, '', sum_rg, 'B')
            luminance = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -200, -300)
            assert lib.connect_material_expressions(sum_rg, '', luminance, 'A')
            assert lib.connect_material_expressions(lb, '', luminance, 'B')
            contrast = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 0, -250)
            contrast.set_editor_property('const_b', 1.05)
            assert lib.connect_material_expressions(luminance, '', contrast, 'A')
            detail = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, 200, -250)
            detail.set_editor_property('const_b', .4)
            assert lib.connect_material_expressions(contrast, '', detail, 'A')
            if green_surface:
                gr = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -1200, -100)
                gr.set_editor_property('r', False)
                gr.set_editor_property('g', True)
                assert lib.connect_material_expressions(color, '', gr, '')
                red = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -1200, 80)
                red.set_editor_property('r', True)
                red.set_editor_property('g', False)
                assert lib.connect_material_expressions(color, '', red, '')
                difference = lib.create_material_expression(mat, unreal.MaterialExpressionSubtract, -1000, -50)
                assert lib.connect_material_expressions(gr, '', difference, 'A')
                assert lib.connect_material_expressions(red, '', difference, 'B')
                strength = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -800, 50)
                strength.set_editor_property('const_b', 8.)
                assert lib.connect_material_expressions(difference, '', strength, 'A')
                green_mask = lib.create_material_expression(mat, unreal.MaterialExpressionSaturate, -600, 50)
                assert lib.connect_material_expressions(strength, '', green_mask, '')
                blend = lib.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, 420, 0)
                blend.set_editor_property('const_a', 1.0)
                assert lib.connect_material_expressions(detail, '', blend, 'B')
                assert lib.connect_material_expressions(green_mask, '', blend, 'Alpha')
                albedo = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 650, 0)
                assert lib.connect_material_expressions(color, '', albedo, 'A')
                assert lib.connect_material_expressions(blend, '', albedo, 'B')
            else:
                tiled = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 420, 0)
                assert lib.connect_material_expressions(color, '', tiled, 'A')
                assert lib.connect_material_expressions(detail, '', tiled, 'B')
                albedo = tiled
    # Use absolute world position rather than mesh UVs so the fine surface grain
    # stays continuous across the many meshes that make up the village.
    pos = lib.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -1000, 360)
    noise = lib.create_material_expression(mat, unreal.MaterialExpressionNoise, -780, 360)
    noise.set_editor_property('scale', .035 if not water else .025)
    assert lib.connect_material_expressions(pos, '', noise, 'World Position')

    grain = lib.create_material_expression(mat, unreal.MaterialExpressionSaturate, -600, 360)
    assert lib.connect_material_expressions(noise, '', grain, '')

    centered = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -560, 360)
    centered.set_editor_property('const_b', -.5)
    assert lib.connect_material_expressions(grain, '', centered, 'A')
    color_amount = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -360, 360)
    color_amount.set_editor_property('const_b', .16 if not water else .025)
    assert lib.connect_material_expressions(centered, '', color_amount, 'A')
    color_variation = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -160, 360)
    color_variation.set_editor_property('const_b', .94 if not water else 1.0)
    assert lib.connect_material_expressions(color_amount, '', color_variation, 'A')
    if water:
        sea_tint = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -120, -180)
        sea_tint.set_editor_property('constant', unreal.LinearColor(.32, .56, .64, 1))
        tinted_sea = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 80, -180)
        assert lib.connect_material_expressions(color, '', tinted_sea, 'A')
        assert lib.connect_material_expressions(sea_tint, '', tinted_sea, 'B')
        albedo = tinted_sea
    textured_color = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 280, 0)
    assert lib.connect_material_expressions(albedo, '', textured_color, 'A')
    assert lib.connect_material_expressions(color_variation, '', textured_color, 'B')
    assert lib.connect_material_property(textured_color, '', unreal.MaterialProperty.MP_BASE_COLOR)

    rough = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -360, 560)
    rough.set_editor_property('const_b', .14 if not water else .08)
    assert lib.connect_material_expressions(grain, '', rough, 'A')
    roughness = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -160, 560)
    roughness.set_editor_property('const_b', .69 if not water else .12)
    assert lib.connect_material_expressions(rough, '', roughness, 'A')
    assert lib.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
    metallic = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -160, 720)
    metallic.set_editor_property('r', .06 if water else 0.0)
    assert lib.connect_material_property(metallic, '', unreal.MaterialProperty.MP_METALLIC)
    specular = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -160, 850)
    specular.set_editor_property('r', .68 if water else .5)
    assert lib.connect_material_property(specular, '', unreal.MaterialProperty.MP_SPECULAR)
    if not vertex:
        lib.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    if water:
        wave_pos = lib.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -900, 900)
        mask = lib.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -700, 900)
        mask.set_editor_property('r', True)
        mask.set_editor_property('g', False)
        assert lib.connect_material_expressions(wave_pos, '', mask, '')
        scale = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, -550, 900)
        scale.set_editor_property('const_b', .003)
        assert lib.connect_material_expressions(mask, '', scale, 'A')
        time = lib.create_material_expression(mat, unreal.MaterialExpressionTime, -700, 550)
        add = lib.create_material_expression(mat, unreal.MaterialExpressionAdd, -350, 900)
        assert lib.connect_material_expressions(scale, '', add, 'A')
        assert lib.connect_material_expressions(time, '', add, 'B')
        sine = lib.create_material_expression(mat, unreal.MaterialExpressionSine, -180, 900)
        assert lib.connect_material_expressions(add, '', sine, '')
        direction = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -180, 600)
        direction.set_editor_property('constant', unreal.LinearColor(0, 0, 6))
        wave = lib.create_material_expression(mat, unreal.MaterialExpressionMultiply, 0, 900)
        assert lib.connect_material_expressions(sine, '', wave, 'A')
        assert lib.connect_material_expressions(direction, '', wave, 'B')
        assert lib.connect_material_property(wave, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    lib.recompile_material(mat)
    unreal.EditorAssetLibrary.set_metadata_tag(mat, 'AIWorld.Generator', '8')
    unreal.EditorAssetLibrary.save_loaded_asset(mat)

material('M_Vertex', vertex=True)
material('M_Color', surface='grass', green_surface=True)
material('M_Water', vertex=True, water=True)
material('M_Stone', vertex=True, surface='stone')
material('M_Slate', vertex=True, surface='slate')
material('M_Terrain', vertex=True, surface='grass', green_surface=True)
sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Maps/Main'):
    sub.new_level('/Game/Maps/Main')
    sub.save_current_level()
unreal.log('AIWORLD_ASSETS_READY')
