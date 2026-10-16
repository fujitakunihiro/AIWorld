"""Build real UE assets from the original, reproducible surface recipes."""
import hashlib
import os
import unreal

lib=unreal.MaterialEditingLibrary
assets=unreal.EditorAssetLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
world_texture=assets.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture')
if not world_texture:raise RuntimeError('WorldAlignedTexture is required')
surface_script=os.path.join(os.path.dirname(__file__),'paris_surfaces.py')
scope={'__file__':surface_script,'__name__':'paris_surfaces'}
with open(surface_script,encoding='utf-8') as source:exec(compile(source.read(),surface_script,'exec'),scope)
surface_manifest=scope['generate']()
surface_folder=os.path.normpath(os.path.join(os.path.dirname(__file__),'..','textures','paris'))
with open(__file__,'rb') as source:
    GENERATOR=hashlib.sha256(source.read().replace(b'\r\n',b'\n')+surface_manifest['generator_sha256'].encode()).hexdigest()


def import_surface(name, suffix):
    filename=f'{name}_{suffix}.png';digest=surface_manifest['files'][filename]
    asset_name=f'T_Paris{name}{suffix.title()}';path='/Game/Textures/'+asset_name
    texture=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not texture or assets.get_metadata_tag(texture,'ParisTwin.SourceSHA256')!=digest:
        task=unreal.AssetImportTask()
        task.set_editor_properties(dict(filename=os.path.join(surface_folder,filename),destination_path='/Game/Textures',
                                       destination_name=asset_name,automated=True,replace_existing=True,save=True))
        tools.import_asset_tasks([task]);texture=assets.load_asset(path)
    if not texture:raise RuntimeError('Surface texture import failed: '+filename)
    texture.set_editor_property('srgb',suffix=='basecolor')
    texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_DEFAULT if suffix=='basecolor' else unreal.TextureCompressionSettings.TC_MASKS)
    texture.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP)
    texture.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP)
    assets.set_metadata_tag(texture,'ParisTwin.SourceSHA256',digest);assets.save_loaded_asset(texture)
    return texture


def expression(mat, cls, x=0,y=0, **props):
    node=lib.create_material_expression(mat,cls,x,y)
    if props:node.set_editor_properties(props)
    return node


def connect(a,out,b,pin):
    if not lib.connect_material_expressions(a,out,b,pin):raise RuntimeError('Material pin connection failed: '+pin)


def property(node,out,prop):
    if not lib.connect_material_property(node,out,prop):raise RuntimeError('Material output connection failed')


def material(name, texture_path=None, tile_cm=400, roughness=.8, metallic=0, surface=None):
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    if assets.get_metadata_tag(mat,'ParisTwin.Generator')==GENERATOR:return
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided',True)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    color=expression(mat,unreal.MaterialExpressionVertexColor,-900,-200)
    recipe=surface_manifest['recipes'].get(surface)
    # Roads/footpaths already have real terrain grades and use a planar map.
    # Selecting the XY function output removes four unnecessary texture reads.
    projection='XY Texture' if surface in ('Paving','Asphalt') else 'XYZ Texture'
    surface_sample=None
    if texture_path or recipe:
        texture=import_surface(surface,'basecolor') if recipe else assets.load_asset(texture_path)
        if not texture:raise RuntimeError('Actual project texture missing: '+texture_path)
        if recipe:tile_cm=recipe['tile_cm'];metallic=recipe['metallic']
        tex=expression(mat,unreal.MaterialExpressionTextureObject,-1300,-500,texture=texture)
        call=expression(mat,unreal.MaterialExpressionMaterialFunctionCall,-1000,-500,material_function=world_texture)
        tile=expression(mat,unreal.MaterialExpressionConstant,-1300,-350,r=tile_cm)
        connect(tex,'',call,'TextureObject');connect(tile,'',call,'TextureSize')
        # World projection shares cm scale across roof slopes and rotated walls.
        if recipe:
            packed=expression(mat,unreal.MaterialExpressionTextureObject,-1300,150,texture=import_surface(surface,'surface'),
                              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            surface_sample=expression(mat,unreal.MaterialExpressionMaterialFunctionCall,-1000,150,material_function=world_texture)
            connect(packed,'',surface_sample,'TextureObject');connect(tile,'',surface_sample,'TextureSize')
        grey=expression(mat,unreal.MaterialExpressionComponentMask,-700,-500,r=True,g=False,b=False)
        connect(call,projection,grey,'')
        if not recipe:
            detail=expression(mat,unreal.MaterialExpressionMultiply,-500,-500,const_b=.32)
            connect(grey,'',detail,'A')
            lift=expression(mat,unreal.MaterialExpressionAdd,-300,-500,const_b=.73)
            connect(detail,'',lift,'A')
        tint=expression(mat,unreal.MaterialExpressionMultiply,-80,-200)
        connect(call,projection,tint,'A') if recipe else connect(lift,'',tint,'A')
        connect(color,'',tint,'B')
        property(tint,'',unreal.MaterialProperty.MP_BASE_COLOR)
        height=expression(mat,unreal.MaterialExpressionMultiply,-450,100,const_b=recipe['height_cm'] if recipe else .65)
        if recipe:
            relief=expression(mat,unreal.MaterialExpressionComponentMask,-700,150,r=False,g=False,b=True)
            connect(surface_sample,projection,relief,'');connect(relief,'',height,'A')
            for channel,prop in [('r',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),('g',unreal.MaterialProperty.MP_ROUGHNESS)]:
                mask=expression(mat,unreal.MaterialExpressionComponentMask,-450,600 if channel=='r' else 500,**dict(r=channel=='r',g=channel=='g',b=False))
                connect(surface_sample,projection,mask,'');property(mask,'',prop)
        else:connect(grey,'',height,'A')
        position=expression(mat,unreal.MaterialExpressionWorldPosition,-900,250)
        normal=expression(mat,unreal.MaterialExpressionVertexNormalWS,-900,400)
        bump=expression(mat,unreal.MaterialExpressionCustom,-100,200)
        bump.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        inputs=[]
        for name in ['Height','Position','Normal']:
            entry=unreal.CustomInput();entry.set_editor_property('input_name',name);inputs.append(entry)
        bump.set_editor_property('inputs',inputs)
        bump.set_editor_property('code','float3 dx=ddx(Position), dy=ddy(Position); float3 a=cross(dy,Normal), b=cross(Normal,dx); float det=dot(dx,a); if(abs(det)<1e-6) return normalize(Normal); return normalize(abs(det)*Normal-sign(det)*(ddx(Height)*a+ddy(Height)*b));')
        connect(height,'',bump,'Height');connect(position,'',bump,'Position');connect(normal,'',bump,'Normal')
        mat.set_editor_property('tangent_space_normal',False)
        property(bump,'',unreal.MaterialProperty.MP_NORMAL)
    else:property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    if not recipe:property(expression(mat,unreal.MaterialExpressionConstant,200,400,r=roughness),'',unreal.MaterialProperty.MP_ROUGHNESS)
    property(expression(mat,unreal.MaterialExpressionConstant,200,550,r=metallic),'',unreal.MaterialProperty.MP_METALLIC)
    property(expression(mat,unreal.MaterialExpressionConstant,200,700,r=.5),'',unreal.MaterialProperty.MP_SPECULAR)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat,'ParisTwin.Generator',GENERATOR)
    assets.set_metadata_tag(mat,'ParisTwin.SurfaceRecipe',surface or 'vertex-tinted original proxy')
    assets.save_loaded_asset(mat)


material('M_ParisLimestoneProcedural',surface='Limestone')
material('M_ParisSlate',surface='Slate')
material('M_ParisGlass',roughness=.22)
material('M_ParisZinc',surface='Zinc')
material('M_ParisPavingProcedural',surface='Paving')
material('M_ParisAsphalt',surface='Asphalt')
material('M_ParisIron',roughness=.53,metallic=.8)
material('M_ParisWood',roughness=.88)
material('M_ParisCutStone',roughness=.82)
material('M_ParisFoliage','/Game/Textures/T_IslandGrass',90,.92)
material('M_ParisCloth',roughness=.95)
material('M_ParisSkin',roughness=.75)
material('M_ParisVehicle',roughness=.3,metallic=.35)
photo_script=os.path.join(os.path.dirname(__file__),'create-paris-photo-assets.py')
with open(photo_script,encoding='utf-8') as source:exec(compile(source.read(),photo_script,'exec'),{'__file__':photo_script,'__name__':'__main__'})
aliases={'M_Paris_Limestone':'M_ParisLimestone','M_Paris_Roof_Zinc':'M_ParisZinc','M_Paris_Roof_Slate':'M_ParisSlatePhotographic',
         'M_Paris_Cobblestone':'M_ParisPaving','M_Paris_Asphalt':'M_ParisAsphalt','M_Paris_Iron':'M_ParisIron',
         'M_Paris_Glass':'M_ParisGlass','M_Seine_Water':'M_Water'}
for name,parent in aliases.items():
    path='/Game/Materials/'+name
    instance=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    lib.set_material_instance_parent(instance,assets.load_asset('/Game/Materials/'+parent))
    assets.set_metadata_tag(instance,'ParisTwin.ParentSurface',parent)
    if not assets.save_loaded_asset(instance):raise RuntimeError('Cannot save named Paris surface: '+name)
unreal.log('PARIS_TWIN_PBR_ASSETS_READY')
