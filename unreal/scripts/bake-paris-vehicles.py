"""Bake the verified sedan into movable instanced meshes and automotive PBR."""
import array
import hashlib
import json
from pathlib import Path
import struct
import unreal

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'unreal/assets/paris-vehicles'
GENERATED=FOLDER/'Generated'
source=json.loads((GENERATED/'source.json').read_text(encoding='utf-8'))
assets=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools();lib=unreal.MaterialEditingLibrary
destination='/Game/ParisPhotoreal/Vehicles'
assets.make_directory(destination);assets.make_directory(destination+'/Materials')
signature=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')+json.dumps(source,sort_keys=True).encode()).hexdigest()
attribute_nodes={}


def node(mat,cls,**props):
    n=lib.create_material_expression(mat,cls)
    if props:n.set_editor_properties(props)
    return n


def output(mat,n,prop,pin=''):
    attributes=attribute_nodes.get(mat.get_path_name())
    if attributes:
        names={unreal.MaterialProperty.MP_BASE_COLOR:'BaseColor',unreal.MaterialProperty.MP_ROUGHNESS:'Roughness',unreal.MaterialProperty.MP_METALLIC:'Metallic',unreal.MaterialProperty.MP_SPECULAR:'Specular'}
        ok=lib.connect_material_expressions(n,pin,attributes,names[prop])
    else:ok=lib.connect_material_property(n,pin,prop)
    if not ok:raise ValueError('Vehicle material property '+str(prop))


def constant(mat,value):return node(mat,unreal.MaterialExpressionConstant,r=value)
def color(mat,rgb):return node(mat,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(*rgb,1))


def custom(mat,code,inputs,dim=3):
    n=node(mat,unreal.MaterialExpressionCustom,code=code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1 if dim==1 else unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins=[]
    for key in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',key);pins.append(p)
    n.set_editor_property('inputs',pins)
    for key,(expression,pin) in inputs.items():
        if not lib.connect_material_expressions(expression,pin,n,key):raise ValueError('Vehicle material pin '+key)
    return n


palette=[[.018,.055,.12],[.36,.40,.43],[.62,.61,.53],[.013,.017,.022],[.16,.019,.012],[.025,.085,.065]]
roles={p['role'] for part in source['parts'] for p in part['primitives']}
materials={}
for role in sorted(roles):
    name='M_ParisSedan_'+role;package=destination+'/Materials/'+name
    mat=assets.load_asset(package) if assets.does_asset_exist(package) else tools.create_asset(name,destination+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('use_material_attributes',role=='paint')
    mat.set_editor_properties(dict(two_sided=role=='glass',blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT if role=='glass' else unreal.BlendMode.BLEND_OPAQUE,shading_model=unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT if role=='glass' else unreal.MaterialShadingModel.MSM_CLEAR_COAT if role=='paint' else unreal.MaterialShadingModel.MSM_DEFAULT_LIT))
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    if role!='glass':lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    local=node(mat,unreal.MaterialExpressionPreSkinnedPosition)
    position=node(mat,unreal.MaterialExpressionVertexInterpolator)
    if not lib.connect_material_expressions(local,'',position,lib.get_material_expression_input_names(position)[0]):raise ValueError('Local position interpolator')
    uv=node(mat,unreal.MaterialExpressionTextureCoordinate)
    tint=node(mat,unreal.MaterialExpressionPerInstanceCustomData,data_index=0)
    brakes=node(mat,unreal.MaterialExpressionPerInstanceCustomData,data_index=1)
    for key in ('tint','brakes'):
        expression=locals()[key];interpolated=node(mat,unreal.MaterialExpressionVertexInterpolator)
        if not lib.connect_material_expressions(expression,'',interpolated,lib.get_material_expression_input_names(interpolated)[0]):raise ValueError('Instance data interpolator')
        if key=='tint':tint=interpolated
        else:brakes=interpolated
    metallic=0.;rough=.55;rgb=(.025,.028,.031);emission=None
    if role=='paint':
        attributes=node(mat,unreal.MaterialExpressionMakeMaterialAttributes)
        lib.connect_material_property(attributes,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
        attribute_nodes[mat.get_path_name()]=attributes
        rgb=None;metallic=.78;rough=.26
        choices=''.join('if(k==%d) C=float3(%s);'%(i,','.join(map(str,c))) for i,c in enumerate(palette))
        base=custom(mat,'int k=(int)clamp(round(Tint),0.,5.);float3 C=float3(.03,.04,.05);'+choices+'float dirt=(1.-smoothstep(18.,65.,P.z))*.12;return lerp(C,float3(.10,.085,.063),dirt);',{'Tint':(tint,''),'P':(position,'')})
        if not lib.connect_material_expressions(constant(mat,1.),'',attributes,'ClearCoat'):raise ValueError('Clear coat pin')
        if not lib.connect_material_expressions(constant(mat,.115),'',attributes,'ClearCoatRoughness'):raise ValueError('Clear coat roughness pin')
    elif role=='glass':
        rgb=(.025,.048,.056);rough=.065
        mat.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        output(mat,constant(mat,.22),unreal.MaterialProperty.MP_OPACITY)
        existing=[n for n in lib.get_material_expressions(mat) if isinstance(n,unreal.MaterialExpressionThinTranslucentMaterialOutput)]
        trans=existing[0] if existing else node(mat,unreal.MaterialExpressionThinTranslucentMaterialOutput)
        for duplicate in existing[1:]:lib.delete_material_expression(mat,duplicate)
        if not lib.connect_material_expressions(color(mat,(.72,.83,.86)),'',trans,lib.get_material_expression_input_names(trans)[0]):raise ValueError('Glass transmission input')
        unreal.log_warning('PARIS_VEHICLE_THIN_GLASS_OUTPUTS '+str(sum(isinstance(n,unreal.MaterialExpressionThinTranslucentMaterialOutput) for n in lib.get_material_expressions(mat))))
    elif role=='chrome':rgb=(.52,.55,.58);metallic=1.;rough=.17
    elif role=='alloy':rgb=(.34,.37,.40);metallic=.95;rough=.28
    elif role=='mirror':rgb=(.78,.82,.85);metallic=1.;rough=.045
    elif role=='rubber':rgb=(.012,.014,.016);rough=.85
    elif role=='plastic':rgb=(.009,.012,.014);rough=.55
    elif role=='interior':rgb=(.021,.018,.015);rough=.82
    elif role=='white':rgb=(.69,.72,.73);rough=.30
    elif role=='black':rgb=(.009,.010,.012);rough=.34
    elif role=='blue':rgb=(.018,.09,.31);rough=.32
    elif role=='caliper':rgb=(.14,.016,.012);rough=.43;metallic=.35
    elif role=='disc':rgb=(.24,.25,.26);rough=.47;metallic=.9
    elif role=='lamp_reflector':rgb=(.47,.49,.51);metallic=.95;rough=.2
    elif role=='brake':
        rgb=(.24,.003,.001);rough=.19
        emission=custom(mat,'return float3(.65,.004,.001)*(.08+clamp(B,0.,1.)*2.2);',{'B':(brakes,'')})
    elif role=='daylight':rgb=(.65,.69,.71);rough=.15;emission=color(mat,(1.5,1.42,1.25))
    elif role=='plate':
        rgb=None;rough=.44
        # Fictional registration. Vector-like strokes keep text attached to
        # the source plates without depending on an external font or texture.
        glyphs=[['01110','10001','10001','11111','10001','10001','10001'],['111','010','010','010','010','010','111'],['000','000','000','111','000','000','000'],['01110','10001','10011','10101','11001','10001','01110'],['11111','00001','00010','00100','01000','01000','01000'],['11111','10000','11110','00001','00001','10001','01110'],['000','000','000','111','000','000','000'],['11110','10001','10001','11110','10000','10000','10000'],['11110','10001','10001','10001','10001','10001','11110']]
        rows=['0'.join(g[y].center(5,'0') for g in glyphs) for y in range(7)]
        tests=[]
        for y,row in enumerate(rows):
            for x,bit in enumerate(row):
                if bit=='1':tests.append('(c.x==%d&&c.y==%d)'%(x,y))
        base=custom(mat,'float2 q=saturate(UV);if(q.x<.075||q.x>.925)return float3(.006,.026,.17);int2 c=(int2)floor((q-float2(.13,.18))*float2(72.,11.));bool ink='+'||'.join(tests)+';return ink?float3(.006,.007,.009):float3(.78,.80,.78);',{'UV':(uv,'')})
    if rgb is not None:base=color(mat,rgb)
    output(mat,base,unreal.MaterialProperty.MP_BASE_COLOR)
    if role in ('rubber','interior'):
        grain=custom(mat,'float fine=sin(P.x*23.1+P.y*14.7)*sin(P.z*31.7+P.y*22.);return clamp(R+fine*.035,.5,.95);',{'P':(position,''),'R':(constant(mat,rough),'')},1)
        output(mat,grain,unreal.MaterialProperty.MP_ROUGHNESS)
    else:output(mat,constant(mat,rough),unreal.MaterialProperty.MP_ROUGHNESS)
    output(mat,constant(mat,metallic),unreal.MaterialProperty.MP_METALLIC)
    output(mat,constant(mat,.5),unreal.MaterialProperty.MP_SPECULAR)
    if emission:output(mat,emission,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat,'ParisTwin.VehicleRecipe',signature)
    if not assets.save_loaded_asset(mat,only_if_is_dirty=False):raise ValueError('Could not save vehicle material')
    materials[role]=mat

runtime={k:v for k,v in source.items() if k!='parts'};runtime['parts']=[]
for part in source['parts']:
    package=part['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    part_materials=[materials[p['role']] for p in part['primitives']]
    dynamic=None
    if not mesh or part['id']=='body':
        dynamic=unreal.DynamicMesh()
        for material_id,primitive in enumerate(part['primitives']):
            blob=(GENERATED/primitive['file']).read_bytes()
            if hashlib.sha256(blob).hexdigest()!=primitive['sha256']:raise ValueError('Vehicle geometry hash changed')
            magic,n,t=struct.unpack_from('<8sII',blob)
            if magic!=b'NDSCAN01':raise ValueError('Vehicle binary header')
            floats=array.array('f');floats.frombytes(blob[16:16+n*32]);indices=array.array('I');indices.frombytes(blob[16+n*32:])
            if len(indices)!=3*t:raise ValueError('Incomplete vehicle triangles')
            buf=unreal.GeometryScriptSimpleMeshBuffers();buf.set_editor_properties(dict(vertices=[unreal.Vector(*floats[i*3:i*3+3]) for i in range(n)],normals=[unreal.Vector(*floats[n*3+i*3:n*3+i*3+3]) for i in range(n)],uv0=[unreal.Vector2D(*floats[n*6+i*2:n*6+i*2+2]) for i in range(n)],triangles=[unreal.IntVector(*indices[i:i+3]) for i in range(0,len(indices),3)]))
            unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=material_id)
    if not mesh:
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions();options.set_editor_properties(dict(enable_nanite=part['id']!='windows',enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=True))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise ValueError('Vehicle static mesh bake failed')
    slots=[]
    for primitive,material in zip(part['primitives'],part_materials):
        slot=unreal.StaticMaterial();slot.set_editor_properties(dict(material_interface=material,material_slot_name=primitive['role']));slots.append(slot)
    mesh.set_editor_property('static_materials',slots)
    settings=mesh.get_editor_property('nanite_settings');settings.set_editor_property('enabled',part['id']!='windows');settings.set_editor_property('generate_fallback',unreal.NaniteGenerateFallback.ENABLED);settings.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES);settings.set_editor_property('fallback_percent_triangles',.2);settings.set_editor_property('fallback_relative_error',.1)
    mesh.set_editor_property('nanite_settings',settings);mesh.set_editor_property('allow_cpu_access',True)
    mesh.set_editor_property('generate_mesh_distance_field',False) # Moving cars; Lumen uses screen traces on this hardware.
    if part['id']=='body':
        collision=unreal.GeometryScriptCollisionFromMeshOptions();collision.set_editor_properties(dict(method=unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES,max_shape_count=1,emit_transaction=False))
        unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(dynamic,mesh,collision)
    assets.set_metadata_tag(mesh,'ParisTwin.VehicleRecipe',signature);assets.set_metadata_tag(mesh,'ParisTwin.SourceURL',source['source_url']);assets.set_metadata_tag(mesh,'ParisTwin.License',source['license'])
    if not assets.save_loaded_asset(mesh,only_if_is_dirty=False):raise ValueError('Could not save vehicle mesh')
    runtime['parts'].append(dict(id=part['id'],asset=package,pivot_cm=part['pivot_cm'],triangles=sum(p['triangles'] for p in part['primitives']),materials=[p['role'] for p in part['primitives']],fallback_triangles=mesh.get_num_triangles(0)))
runtime['paint_colors_linear']=palette;runtime['bake_recipe_sha256']=signature
(Path(unreal.Paths.project_content_dir())/'Data/paris-vehicles.json').write_text(json.dumps(runtime,indent=2)+'\n',encoding='utf-8')
unreal.log_warning('PARIS_VEHICLE_ASSETS_READY 6')
