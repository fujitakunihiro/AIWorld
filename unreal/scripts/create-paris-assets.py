"""PBR materials using only the project's existing, authored textures."""
import unreal

lib=unreal.MaterialEditingLibrary
assets=unreal.EditorAssetLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
world_texture=assets.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture')
if not world_texture:raise RuntimeError('WorldAlignedTexture is required')


def expression(mat, cls, x=0,y=0, **props):
    node=lib.create_material_expression(mat,cls,x,y)
    if props:node.set_editor_properties(props)
    return node


def connect(a,out,b,pin):
    if not lib.connect_material_expressions(a,out,b,pin):raise RuntimeError('Material pin connection failed: '+pin)


def property(node,out,prop):
    if not lib.connect_material_property(node,out,prop):raise RuntimeError('Material output connection failed')


def material(name, texture_path=None, tile_cm=400, roughness=.8, metallic=0):
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    if assets.get_metadata_tag(mat,'ParisTwin.Generator')=='2':return
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided',True)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    color=expression(mat,unreal.MaterialExpressionVertexColor,-900,-200)
    if texture_path:
        texture=assets.load_asset(texture_path)
        if not texture:raise RuntimeError('Actual project texture missing: '+texture_path)
        tex=expression(mat,unreal.MaterialExpressionTextureObject,-1300,-500,texture=texture)
        call=expression(mat,unreal.MaterialExpressionMaterialFunctionCall,-1000,-500,material_function=world_texture)
        tile=expression(mat,unreal.MaterialExpressionConstant,-1300,-350,r=tile_cm)
        connect(tex,'',call,'TextureObject');connect(tile,'',call,'TextureSize')
        # Keep tint variation visible and avoid over-saturated, giant stone blocks.
        grey=expression(mat,unreal.MaterialExpressionComponentMask,-700,-500,r=True,g=False,b=False)
        connect(call,'XYZ Texture',grey,'')
        detail=expression(mat,unreal.MaterialExpressionMultiply,-500,-500,const_b=.32)
        connect(grey,'',detail,'A')
        lift=expression(mat,unreal.MaterialExpressionAdd,-300,-500,const_b=.73)
        connect(detail,'',lift,'A')
        tint=expression(mat,unreal.MaterialExpressionMultiply,-80,-200)
        connect(lift,'',tint,'A');connect(color,'',tint,'B')
        property(tint,'',unreal.MaterialProperty.MP_BASE_COLOR)
        height=expression(mat,unreal.MaterialExpressionMultiply,-450,100,const_b=.65)
        connect(grey,'',height,'A')
        position=expression(mat,unreal.MaterialExpressionWorldPosition,-900,250)
        normal=expression(mat,unreal.MaterialExpressionVertexNormalWS,-900,400)
        bump=expression(mat,unreal.MaterialExpressionCustom,-100,200)
        bump.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        inputs=[]
        for name in ['Height','Position','Normal']:
            entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
        bump.set_editor_property('inputs',inputs)
        bump.set_editor_property('code','float3 dx=ddx(Position), dy=ddy(Position); float3 a=cross(dy,Normal), b=cross(Normal,dx); float det=dot(dx,a); return normalize(abs(det)*Normal-sign(det)*(ddx(Height)*a+ddy(Height)*b));')
        connect(height,'',bump,'Height');connect(position,'',bump,'Position');connect(normal,'',bump,'Normal')
        mat.set_editor_property('tangent_space_normal',False)
        property(bump,'',unreal.MaterialProperty.MP_NORMAL)
    else:property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    property(expression(mat,unreal.MaterialExpressionConstant,200,400,r=roughness),'',unreal.MaterialProperty.MP_ROUGHNESS)
    property(expression(mat,unreal.MaterialExpressionConstant,200,550,r=metallic),'',unreal.MaterialProperty.MP_METALLIC)
    property(expression(mat,unreal.MaterialExpressionConstant,200,700,r=.5),'',unreal.MaterialProperty.MP_SPECULAR)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat,'ParisTwin.Generator','2');assets.save_loaded_asset(mat)


material('M_ParisLimestone','/Game/Textures/T_Limestone',400,.83)
material('M_ParisSlate','/Game/Textures/T_Slate',300,.55)
material('M_ParisGlass',roughness=.22)
material('M_ParisZinc',roughness=.48,metallic=.72)
material('M_ParisIron',roughness=.53,metallic=.8)
material('M_ParisWood',roughness=.88)
material('M_ParisFoliage','/Game/Textures/T_IslandGrass',90,.92)
material('M_ParisCloth',roughness=.95)
material('M_ParisSkin',roughness=.75)
material('M_ParisVehicle',roughness=.3,metallic=.35)
unreal.log('PARIS_TWIN_PBR_ASSETS_READY')
