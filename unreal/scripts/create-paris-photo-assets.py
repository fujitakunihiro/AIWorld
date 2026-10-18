"""Import bundled CC0 originals and build actual UE material graphs offline."""
import hashlib
import json
import os
import unreal

scope = {'__file__': os.path.join(os.path.dirname(__file__), 'paris_photo_sources.py'), '__name__': 'paris_photo_sources'}
with open(scope['__file__'], encoding='utf-8') as f:
    exec(compile(f.read(), scope['__file__'], 'exec'), scope)
manifest = scope['load']()
folder = str(scope['FOLDER'])
lib = unreal.MaterialEditingLibrary
assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
world_texture = assets.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture')
world_normal = unreal.load_object(None, '/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedNormal2.WorldAlignedNormal2')
if not world_texture or not world_normal:
    raise RuntimeError('Actual engine world-aligned functions are required')
with open(__file__, 'rb') as f:
    signature = hashlib.sha256(f.read().replace(b'\r\n', b'\n')).hexdigest()
masonry_path=os.path.join(os.path.dirname(__file__),'paris_masonry.py')
masonry={'__file__':masonry_path,'__name__':'paris_masonry'}
with open(masonry_path,encoding='utf-8') as f:exec(compile(f.read(),masonry_path,'exec'),masonry)
with open(masonry_path,'rb') as f:masonry_signature=hashlib.sha256(f.read().replace(b'\r\n',b'\n')).hexdigest()
west_path=os.path.join(os.path.dirname(__file__),'notredame_west.py')
west={'__file__':west_path,'__name__':'notredame_west'}
with open(west_path,encoding='utf-8') as f:exec(compile(f.read(),west_path,'exec'),west)
with open(west_path,'rb') as f:signature+=hashlib.sha256(f.read().replace(b'\r\n',b'\n')).hexdigest()


def imported(name, info, role):
    package = '/Game/Textures/' + name
    texture = assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not texture or assets.get_metadata_tag(texture, 'ParisTwin.SourceSHA256') != info['sha256']:
        task = unreal.AssetImportTask()
        task.set_editor_properties(dict(filename=os.path.join(folder, info['file']), destination_path='/Game/Textures',
            destination_name=name, automated=True, replace_existing=True, save=True))
        tools.import_asset_tasks([task]);texture = assets.load_asset(package)
    if not texture:
        raise RuntimeError('Photographic import failed: ' + name)
    texture.set_editor_property('srgb', role == 'albedo')
    if role != 'environment':
        texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP if role == 'normal'
            else unreal.TextureCompressionSettings.TC_MASKS if role == 'orm' else unreal.TextureCompressionSettings.TC_DEFAULT)
        texture.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property('address_y', unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property('max_texture_size', 2048)
        if role == 'normal':texture.set_editor_property('flip_green_channel', False)
    assets.set_metadata_tag(texture, 'ParisTwin.SourceSHA256', info['sha256'])
    assets.set_metadata_tag(texture, 'ParisTwin.License', 'CC0-1.0')
    if not assets.save_loaded_asset(texture):raise RuntimeError('Cannot save imported texture: ' + name)
    return texture


def node(mat, cls, x=0, y=0, **props):
    result = lib.create_material_expression(mat, cls, x, y)
    if props:result.set_editor_properties(props)
    return result


def link(a, out, b, pin):
    if not lib.connect_material_expressions(a, out, b, pin):raise RuntimeError('Photo pin failed: ' + pin + '; available: ' + str(lib.get_material_expression_input_names(b)))


def output(a, out, prop):
    if not lib.connect_material_property(a, out, prop):raise RuntimeError('Photo material output failed')


def custom(mat,code,inputs,vector=False,x=-350,y=0):
    expression=node(mat,unreal.MaterialExpressionCustom,x,y)
    expression.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3 if vector else unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    pins=[]
    for name,(source,out) in inputs.items():
        pin=unreal.CustomInput();pin.set_editor_property('input_name',name);pins.append(pin)
    expression.set_editor_property('inputs',pins);expression.set_editor_property('code',code)
    for name,(source,out) in inputs.items():link(source,out,expression,name)
    return expression


architecture={}
for filename in ['paris-photo-architecture-source.json','paris-photo-architecture.json']:
    architecture_path=os.path.join(unreal.Paths.project_content_dir(),'Data',filename)
    if os.path.isfile(architecture_path):
        with open(architecture_path,encoding='utf-8') as f:candidate=json.load(f)
        if candidate.get('local_frame'):architecture=candidate;break
frame=architecture.get('local_frame')
signature+=hashlib.sha256(json.dumps(frame,sort_keys=True).encode()).hexdigest()
entries=list(manifest['sets'])
if frame:entries.append(dict(next(e for e in entries if e['key']=='stone'),material='M_ParisCathedralStone'))
if frame:entries.append(dict(next(e for e in entries if e['key']=='stone'),material='M_ParisSculptedStone',sculpture=True))
if frame:entries.append(dict(next(e for e in entries if e['key']=='paving'),material='M_ParisGroundPaving'))


for entry in entries:
    key = entry['key'].title()
    textures = {role: imported('T_ParisPhoto' + key + role.title(), info, role) for role, info in entry['maps'].items()}
    package = '/Game/Materials/' + entry['material']
    mat = assets.load_asset(package) if assets.does_asset_exist(package) else tools.create_asset(entry['material'], '/Game/Materials', unreal.Material, unreal.MaterialFactoryNew())
    fingerprint = signature + ''.join(x['sha256'] for x in entry['maps'].values())+(masonry_signature if entry['key']=='stone' else '')
    if assets.get_metadata_tag(mat, 'ParisTwin.PhotoGenerator') == fingerprint:continue
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided', True)
    mat.set_editor_property('tangent_space_normal', False)
    lib.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    tile = node(mat, unreal.MaterialExpressionConstant, -1400, 150, r=entry['tile_cm'])
    samples = {}
    wood = entry['key']=='wood'
    planar = entry['key'] in ('paving','grass','asphalt') or wood
    if wood:
        # The photograph's grain runs along U. Align it vertically on the west
        # doors in the same geographic frame; procedural meshes have no UVs.
        if not frame:raise RuntimeError('A shared GIS frame is required for door grain')
        position=node(mat,unreal.MaterialExpressionWorldPosition,-1900,0)
        across='float3('+','.join(f'{v:.10f}' for v in frame['across'])+')'
        origin='float3('+','.join(f'{v:.10f}' for v in frame['front_cm'])+')'
        uv=node(mat,unreal.MaterialExpressionCustom,-1500,0)
        uv.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT2)
        pin=unreal.CustomInput();pin.set_editor_property('input_name','Position');uv.set_editor_property('inputs',[pin])
        uv.set_editor_property('code',f'float3 d=Position-{origin};return float2(d.z,dot(d,{across}))/200.;')
        link(position,'',uv,'Position')
    elif planar:
        position=node(mat,unreal.MaterialExpressionWorldPosition,-1900,0)
        xy=node(mat,unreal.MaterialExpressionComponentMask,-1700,0,r=True,g=True,b=False)
        uv=node(mat,unreal.MaterialExpressionDivide,-1500,0)
        link(position,'',xy,'');link(xy,'',uv,'A');link(tile,'',uv,'B')
    for i, role in enumerate(('albedo', 'orm', 'normal')):
        sampler=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if role=='normal' else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS if role=='orm' else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        if planar:
            sample=node(mat,unreal.MaterialExpressionTextureSample,-1050,i*350-300,texture=textures[role],sampler_type=sampler)
            link(uv,'',sample,'UVs');samples[role]=sample;continue
        obj = node(mat, unreal.MaterialExpressionTextureObject, -1400, i * 350 - 300, texture=textures[role],
            sampler_type=sampler)
        call = node(mat, unreal.MaterialExpressionMaterialFunctionCall, -1050, i * 350 - 300,
                    material_function=world_normal if role == 'normal' else world_texture)
        link(obj, '', call, 'TextureObject');link(tile, '', call, 'TextureSize');samples[role] = call
    projection = '' if planar else 'XYZ Texture'
    tint = node(mat, unreal.MaterialExpressionVertexColor, -800, -500)
    subtle = node(mat, unreal.MaterialExpressionLinearInterpolate, -550, -500, const_a=1., const_alpha=.08 if entry['key'] in ('grass','asphalt') else .6)
    link(tint, '', subtle, 'B')
    color = node(mat, unreal.MaterialExpressionMultiply, -250, -300)
    link(samples['albedo'], projection, color, 'A');link(subtle, '', color, 'B')
    world_position=node(mat,unreal.MaterialExpressionWorldPosition,-800,1050)
    ground_zone=None
    if entry['material']=='M_ParisGroundPaving':
        # Only unclassified exposed ground near the cathedral receives inferred
        # urban paving. Mapped road/park/water coverage has already been removed
        # from this display mesh. The source palette returns beyond 130m.
        cx,cy=frame['front_cm'][:2]
        ground_zone=custom(mat,f'return 1-smoothstep(10000,13000,length(Position.xy-float2({cx:.6f},{cy:.6f})));',dict(Position=(world_position,'')))
        blend=node(mat,unreal.MaterialExpressionLinearInterpolate)
        link(tint,'',blend,'A');link(color,'',blend,'B');link(ground_zone,'',blend,'Alpha')
        color=blend
    if entry['key']=='stone' and not entry.get('sculpture'):
        # The photograph supplies fine grain. Coursing is an explicitly
        # inferred shallow finish, not a coarse rubble photograph or geometry.
        geometric=node(mat,unreal.MaterialExpressionVertexNormalWS)
        weather=custom(mat,masonry['color_hlsl'](),
            dict(Position=(world_position,''),Albedo=(color,''),Geometric=(geometric,'')),vector=True,y=-300)
        output(weather,'',unreal.MaterialProperty.MP_BASE_COLOR)
    elif wood:
        # Subtle inferred base patina. No emissive lighting, painted shadows,
        # species identification or measured cathedral wood claim.
        weather=custom(mat,f'float z=(Position-{origin}).z*.01;float damp=1-.18*(1-smoothstep(.12,.85,z));return Albedo*damp*float3(.78,.86,.94);',
                       dict(Position=(world_position,''),Albedo=(color,'')),vector=True)
        output(weather,'',unreal.MaterialProperty.MP_BASE_COLOR)
    else:output(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    if entry['material']=='M_ParisCathedralStone':
        # Geometry and source-display cutouts share one opening specification.
        code=west['display_mask_hlsl'](frame)
        mask=custom(mat,code,dict(Position=(world_position,'')),y=1350)
        mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
        output(mask,'',unreal.MaterialProperty.MP_OPACITY_MASK)
        assets.set_metadata_tag(mat,'ParisTwin.VisualVoids','Inferred western portals, rose, windows, gallery and belfry; original GIS collision retained')
    if planar:
        # XY world UVs define a stable world-space tangent basis. Following the
        # actual road normal preserves grades without the legacy XY normal
        # function's axis convention or missing procedural UV/tangent data.
        normal=node(mat,unreal.MaterialExpressionVertexNormalWS,-650,700)
        basis=node(mat,unreal.MaterialExpressionCustom,-250,600)
        basis.set_editor_property('output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        inputs=[]
        for name in ['Surface','Geometric']:
            inp=unreal.CustomInput();inp.set_editor_property('input_name',name);inputs.append(inp)
        basis.set_editor_property('inputs',inputs)
        basis.set_editor_property('code',
            f'float3 N=normalize(Geometric);float3 axis=abs(N.z)<.95?float3(0,0,1):{across};float3 T=normalize(axis-N*dot(N,axis));float3 B=normalize(cross(N,T));return normalize(T*Surface.x*.45+B*Surface.y*.45+N*Surface.z);' if wood else
            'float3 N=normalize(Geometric); float3 T=normalize(float3(1,0,0)-N*N.x); float3 B=normalize(cross(N,T)); return normalize(T*Surface.x+B*Surface.y+N*Surface.z);')
        link(normal,'',basis,'Geometric');link(samples['normal'],'',basis,'Surface')
        if ground_zone:
            blend=node(mat,unreal.MaterialExpressionLinearInterpolate)
            link(normal,'',blend,'A');link(basis,'',blend,'B');link(ground_zone,'',blend,'Alpha');basis=blend
        output(basis,'',unreal.MaterialProperty.MP_NORMAL)
    elif entry['key']=='stone' and not entry.get('sculpture'):
        finish=custom(mat,masonry['normal_hlsl'](),dict(Position=(world_position,''),Geometric=(geometric,''),Photo=(samples['normal'],projection)),vector=True)
        output(finish,'',unreal.MaterialProperty.MP_NORMAL)
        assets.set_metadata_tag(mat,'ParisTwin.MasonryFinish','Scanned white_plaster_02 grain with inferred 32x88cm courses, shallow joints; not surveyed limestone')
    elif entry.get('sculpture'):
        # Fine plaster grain is an appearance proxy, not the figure's shape.
        # Preserve its actual smooth geometric normals at grazing angles.
        geometric=node(mat,unreal.MaterialExpressionVertexNormalWS)
        strength=node(mat,unreal.MaterialExpressionScalarParameter,parameter_name='SculptureGrainStrength',default_value=.18)
        blend=node(mat,unreal.MaterialExpressionLinearInterpolate)
        link(geometric,'',blend,'A');link(samples['normal'],projection,blend,'B');link(strength,'',blend,'Alpha')
        normalized=node(mat,unreal.MaterialExpressionNormalize)
        link(blend,'',normalized,'');output(normalized,'',unreal.MaterialProperty.MP_NORMAL)
        assets.set_metadata_tag(mat,'ParisTwin.SculptureNormalPolicy','World-space geometric normals plus subtle photographic fine grain at 0.18; not scanned sculpture detail')
    else:output(samples['normal'], projection, unreal.MaterialProperty.MP_NORMAL)
    for channel, prop in [('r',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
                          ('g',unreal.MaterialProperty.MP_ROUGHNESS),('b',unreal.MaterialProperty.MP_METALLIC)]:
        mask = node(mat, unreal.MaterialExpressionComponentMask, -450, 100 + len(channel) * 30,
                    r=channel=='r', g=channel=='g', b=channel=='b')
        link(samples['orm'], projection, mask, '')
        if wood and channel=='g':
            clamp=node(mat,unreal.MaterialExpressionClamp,min_default=.58,max_default=.92)
            link(mask,'',clamp,'');mask=clamp
        if ground_zone:
            blend=node(mat,unreal.MaterialExpressionLinearInterpolate,const_a=1. if channel=='r' else .9 if channel=='g' else 0.)
            link(mask,'',blend,'B');link(ground_zone,'',blend,'Alpha');mask=blend
        output(mask, '', prop)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat, 'ParisTwin.PhotoGenerator', fingerprint)
    assets.set_metadata_tag(mat, 'ParisTwin.SourceURL', entry['source_url'])
    assets.set_metadata_tag(mat, 'ParisTwin.SurfaceRecipe', 'photographic:' + entry['id'])
    assets.set_metadata_tag(mat, 'ParisTwin.ChannelLayout', 'ORM; DirectX normal')
    if wood:assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','CC0 dark_wood at 2m scale; vertical grain in the shared GIS frame, inferred outdoor roughness/patina; not sampled cathedral wood')
    if ground_zone:assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Inferred paving on unclassified exposed terrain within 100m of the west anchor; fades to source palette by 130m. Not surveyed land cover.')
    if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot save photographic material: ' + entry['material'])

# Exterior stained glass is opaque and dark in daylight. No emissive glow or
# photograph is used. The authored mosaic colours are encoded per vertex.
name='M_ParisStainedGlass';package='/Game/Materials/'+name
mat=assets.load_asset(package) if assets.does_asset_exist(package) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
if assets.get_metadata_tag(mat,'ParisTwin.PhotoGenerator')!=signature:
    lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True)
    color=node(mat,unreal.MaterialExpressionVertexColor)
    output(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    rough=node(mat,unreal.MaterialExpressionConstant,r=.32);output(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    metallic=node(mat,unreal.MaterialExpressionConstant,r=0.);output(metallic,'',unreal.MaterialProperty.MP_METALLIC)
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.PhotoGenerator',signature)
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Original inferred stained-glass mosaic; not a reproduction of the historical iconography')
    if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot save stained glass')

environment = imported('T_ParisDayEnvironment', manifest['environment'], 'environment')
if not isinstance(environment, unreal.TextureCube):raise RuntimeError('HDR lighting must import as a real TextureCube')
# A real HDR panorama supplies visible cloud shapes and the captured skylight.
# This is a photographic sky proxy, never an assertion about surveyed weather.
name='M_ParisPhotographicSky';sky=assets.load_asset('/Game/Materials/'+name) if assets.does_asset_exist('/Game/Materials/'+name) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
if assets.get_metadata_tag(sky,'ParisTwin.PhotoGenerator')!=signature:
    lib.delete_all_material_expressions(sky)
    sky.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    sky.set_editor_property('two_sided',True);sky.set_editor_property('is_sky',True)
    direction=node(sky,unreal.MaterialExpressionCameraVectorWS,-900,0)
    inverse=node(sky,unreal.MaterialExpressionMultiply,-700,0,const_b=-1.)
    link(direction,'',inverse,'A')
    sample=node(sky,unreal.MaterialExpressionTextureSample,-450,0,texture=environment,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    link(inverse,'',sample,'UVs')
    radiance=node(sky,unreal.MaterialExpressionMultiply,-150,0,const_b=6000.)
    link(sample,'',radiance,'A');output(radiance,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(sky);assets.set_metadata_tag(sky,'ParisTwin.PhotoGenerator',signature)
    assets.set_metadata_tag(sky,'ParisTwin.SourceURL',manifest['environment']['source_url'])
    assets.set_metadata_tag(sky,'ParisTwin.RadianceScale','6000; appearance calibration, not a measured illuminance')
    if not assets.save_loaded_asset(sky):raise RuntimeError('Cannot save photographic sky')

# Original procedural cast iron and opaque reflective lantern panes. These do
# not enable translucency or local point lights, keeping the shadow budget fixed.
for name in ['M_ParisCastIron','M_ParisLanternGlass']:
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    if assets.get_metadata_tag(mat,'ParisTwin.PhotoGenerator')==signature:continue
    lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    position=node(mat,unreal.MaterialExpressionWorldPosition)
    if name=='M_ParisCastIron':
        oxide=custom(mat,'float3 p=Position*.01; return saturate(.48+.3*sin(p.x*7.3+p.y*5.1)*sin(p.z*4.7)+.22*sin(dot(p,float3(47,39,51))));',dict(Position=(position,'')))
        color=custom(mat,'return lerp(float3(.025,.031,.029),float3(.095,.065,.039),Oxide*.55);',dict(Oxide=(oxide,'')),vector=True)
        rough=custom(mat,'return .43+.35*Oxide;',dict(Oxide=(oxide,'')))
        metal=custom(mat,'return .88-.60*Oxide;',dict(Oxide=(oxide,'')))
    else:
        color=node(mat,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(.11,.145,.135,1))
        rough=node(mat,unreal.MaterialExpressionConstant,r=.16);metal=node(mat,unreal.MaterialExpressionConstant,r=0.)
    output(color,'',unreal.MaterialProperty.MP_BASE_COLOR);output(rough,'',unreal.MaterialProperty.MP_ROUGHNESS);output(metal,'',unreal.MaterialProperty.MP_METALLIC)
    output(node(mat,unreal.MaterialExpressionConstant,r=.5),'',unreal.MaterialProperty.MP_SPECULAR)
    lib.recompile_material(mat);assets.set_metadata_tag(mat,'ParisTwin.PhotoGenerator',signature)
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance','Original inferred lantern surface; glass is opaque reflective proxy; actual fixture unverified')
    if not assets.save_loaded_asset(mat):raise RuntimeError('Lantern material save failed')
unreal.log('PARIS_PHOTOGRAPHIC_ASSETS_READY')
