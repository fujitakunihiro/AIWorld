"""PBR finishing for the verified CC0 tree; no geographic data is modified."""
import unreal

RECIPE = 'paris_tree_foliage_v2'
WIND_DISABLE_DISTANCE_CM = 6000


def finish_tree_material(mat, base, normal, arm, *, leaf, branch, normal_scale=1.):
    lib = unreal.MaterialEditingLibrary

    def node(cls, **properties):
        result = lib.create_material_expression(mat, cls)
        if properties:result.set_editor_properties(properties)
        return result

    def custom(code, inputs, dimensions=3):
        result = node(unreal.MaterialExpressionCustom, code=code, output_type={
            1:unreal.CustomMaterialOutputType.CMOT_FLOAT1,
            3:unreal.CustomMaterialOutputType.CMOT_FLOAT3}[dimensions])
        pins = []
        for name in inputs:
            pin = unreal.CustomInput();pin.set_editor_property('input_name', name);pins.append(pin)
        result.set_editor_property('inputs', pins)
        for name, (source, output) in inputs.items():
            if not lib.connect_material_expressions(source, output, result, name):
                raise RuntimeError('Tree material input: '+name)
        return result

    def output(source, property, pin=''):
        if not lib.connect_material_property(source, pin, property):
            raise RuntimeError('Tree material output: '+str(property))

    def scalar(name, value):
        return node(unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=value)

    local = node(unreal.MaterialExpressionPreSkinnedPosition)
    instance = node(unreal.MaterialExpressionPerInstanceRandom)
    if leaf:
        color = custom('return Color*lerp(float3(.91,1.04,.85),float3(1.10,1.01,.93),Variation)*1.10;',
            {'Color':(base,'RGB'),'Variation':(instance,'')})
    else:
        pixel_local = node(unreal.MaterialExpressionVertexInterpolator)
        pin = lib.get_material_expression_input_names(pixel_local)[0]
        if not lib.connect_material_expressions(local,'',pixel_local,pin):
            raise RuntimeError('Tree local position must be interpolated into the pixel shader')
        color = custom('float root=1.-smoothstep(8.,85.,Local.z);return Color*lerp(float3(1,1,1),float3(.64,.70,.51),root*.65)*lerp(.96,1.03,Variation);',
            {'Color':(base,'RGB'),'Local':(pixel_local,''),'Variation':(instance,'')})
    output(color, unreal.MaterialProperty.MP_BASE_COLOR)
    # Honor the source glTF normal scale (0.5 for branches). Keep UVs and the
    # photographed bark instead of replacing them with procedural stripes.
    n = custom('return normalize(float3(N.xy*Strength,N.z));',
        {'N':(normal,'RGB'),'Strength':(scalar('NormalStrength',normal_scale),'')})
    output(n, unreal.MaterialProperty.MP_NORMAL)
    rough = custom('return clamp(Roughness,Minimum,.96);',
        {'Roughness':(arm,'G'),'Minimum':(scalar('MinimumRoughness',.48 if leaf else .68),'')},1)
    output(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    ao = custom('return lerp(.38,1.,AO);', {'AO':(arm,'R')},1)
    output(ao, unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    output(scalar('Metallic',0.), unreal.MaterialProperty.MP_METALLIC)
    output(scalar('Specular',.28 if leaf else .23), unreal.MaterialProperty.MP_SPECULAR)
    if leaf:
        scatter = custom('return Color*float3(.72,.95,.46)*Strength;',
            {'Color':(color,''),'Strength':(scalar('LeafTransmission',.40),'')})
        output(scatter, unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        output(scalar('LeafThickness',.62), unreal.MaterialProperty.MP_OPACITY)
    if leaf or branch:
        position = node(unreal.MaterialExpressionWorldPosition,
            world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        # A few centimetres of crown sway. The trunk/root mesh remains rigid;
        # displacement fades before the component's 60m WPO disable distance.
        wind = custom('''
float height=smoothstep(280.,940.,Local.z);height*=height;
float fade=1.-smoothstep(2500.,5500.,length(Camera-Position));
float phase=Variation*6.283185+Position.x*.0017+Position.y*.0011;
float sway=sin(Time*.82+phase)+.24*sin(Time*1.57+phase*1.63);
float flutter=sin(Time*3.7+Local.x*.15+Local.y*.11+phase)*.45;
return float3(sway*.86,(sway*.38+flutter*.22),flutter*.12)*Amplitude*height*fade*Strength;
''', {'Local':(local,''),'Position':(position,''),
            'Camera':(node(unreal.MaterialExpressionCameraPositionWS),''),
            'Time':(node(unreal.MaterialExpressionTime),''),'Variation':(instance,''),
            'Amplitude':(scalar('CrownAmplitudeCm',3.2 if leaf else 1.05),''),
            'Strength':(scalar('WindStrength',1.),'')})
        output(wind, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        mat.set_editor_property('max_world_position_offset_displacement',6.)
    unreal.EditorAssetLibrary.set_metadata_tag(mat,'ParisTwin.FoliageRecipe',RECIPE)
