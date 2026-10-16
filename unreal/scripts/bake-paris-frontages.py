"""Create two opaque window materials and bake source-aligned facade relief."""
import hashlib
import json
import os
import unreal

assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary
tools=unreal.AssetToolsHelpers.get_asset_tools()
folder=os.path.join(unreal.Paths.project_content_dir(),'Data')
with open(os.path.join(folder,'paris-photo-frontages-source.json'),encoding='utf-8') as f:source=json.load(f)
with open(__file__,'rb') as f:signature=hashlib.sha256(f.read().replace(b'\r\n',b'\n')).hexdigest()


def node(mat,cls,**props):
    value=lib.create_material_expression(mat,cls,0,0)
    if props:value.set_editor_properties(props)
    return value


def output(mat,expression,prop,pin=''):
    if not lib.connect_material_property(expression,pin,prop):raise RuntimeError('Window material output failed')


def custom(mat,code,inputs):
    result=node(mat,unreal.MaterialExpressionCustom,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins=[]
    for name in inputs:
        pin=unreal.CustomInput();pin.set_editor_property('input_name',name);pins.append(pin)
    result.set_editor_properties(dict(inputs=pins,code=code))
    for name,(src,out) in inputs.items():
        if not lib.connect_material_expressions(src,out,result,name):raise RuntimeError('Window shader input: '+name)
    return result


for name in ['M_ParisWindowGlass','M_ParisWindowPaintedWood']:
    package='/Game/Materials/'+name
    mat=assets.load_asset(package) if assets.does_asset_exist(package) else tools.create_asset(name,'/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    if assets.get_metadata_tag(mat,'ParisTwin.FrontageRecipe')==signature:continue
    lib.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',False)
    tint=node(mat,unreal.MaterialExpressionVertexColor)
    if name.endswith('Glass'):
        uv=node(mat,unreal.MaterialExpressionTextureCoordinate,coordinate_index=0)
        normal=node(mat,unreal.MaterialExpressionVertexNormalWS)
        view=node(mat,unreal.MaterialExpressionCameraVectorWS)
        color=custom(mat,r'''
float3 N=normalize(Normal); float3 T=normalize(float3(N.y,-N.x,0));
float3 ray=float3(-dot(View,T),-View.z,max(.04,dot(View,N)));
float2 p=(UV-.5)*float2(.9,1.65); float depth=2.2;
float tx=(ray.x<0?(-1.5-p.x):(1.5-p.x))/(abs(ray.x)<.0001?.0001:ray.x);
float ty=(ray.y<0?(-.825-p.y):(.825-p.y))/(abs(ray.y)<.0001?.0001:ray.y);
float tz=depth/ray.z; float hit=min(tz,min(tx,ty));
float3 q=float3(p,0)+ray*hit;
float3 room=float3(.075,.066,.051);
if(ty<min(tx,tz)) room=q.y>0?float3(.105,.096,.075):float3(.040,.030,.022);
else if(tx<tz) room=float3(.067,.060,.046);
else {
    float picture=step(abs(q.x-.42),.40)*step(abs(q.y-.04),.34);
    room=lerp(room,float3(.022,.036,.038),picture);
    float furniture=step(q.y,-.40)*step(abs(q.x+.36),.81);
    room=lerp(room,float3(.025,.020,.016),furniture);
}
float edgeWidth=.10+.10*Seed.r;
float curtain=smoothstep(edgeWidth+.018,edgeWidth,min(UV.x,1-UV.x));
float fold=.76+.24*sin(UV.x*190+Seed.g*13);
float3 linen=float3(.25,.236,.20)*fold*(.78+.22*UV.y);
room=lerp(room,linen,curtain);
// Restrained absorption; PBR specular reflects the actual UE environment.
return room*float3(.88,.98,1.02);
''',dict(UV=(uv,''),Normal=(normal,''),View=(view,''),Seed=(tint,'')))
        output(mat,color,unreal.MaterialProperty.MP_BASE_COLOR)
        rough=.14;spec=.5
    else:
        position=node(mat,unreal.MaterialExpressionWorldPosition)
        color=custom(mat,'float grain=sin(Position.z*1.7+sin(dot(Position.xy,float2(.13,.19)))*2); return Tint*(.94+.06*grain);',dict(Position=(position,''),Tint=(tint,'')))
        output(mat,color,unreal.MaterialProperty.MP_BASE_COLOR);rough=.48;spec=.32
    for prop,value in [(unreal.MaterialProperty.MP_ROUGHNESS,rough),(unreal.MaterialProperty.MP_SPECULAR,spec),(unreal.MaterialProperty.MP_METALLIC,0.)]:
        output(mat,node(mat,unreal.MaterialExpressionConstant,r=value),prop)
    lib.recompile_material(mat)
    assets.set_metadata_tag(mat,'ParisTwin.FrontageRecipe',signature)
    assets.set_metadata_tag(mat,'ParisTwin.AppearanceProvenance',source['appearance_provenance'])
    if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot save frontage material')


def linear(byte):
    v=byte/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4


runtime={k:v for k,v in source.items() if k not in ('objects','windows')};runtime['objects']=[]
runtime['source_ids']=sorted({w['source_id'] for key in ['windows','entrances','cornices'] for w in source[key]})
for item in source['objects']:
    package=item['asset'];mesh=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if mesh and assets.get_metadata_tag(mesh,'ParisTwin.GeometrySHA256') not in ('',item['geometry_sha256']):raise RuntimeError('Frontage hash mismatch')
    if not mesh:
        assets.make_directory('/Game/ParisPhotoreal/Frontages')
        os.makedirs(os.path.realpath(os.path.join(unreal.Paths.project_content_dir(),'ParisPhotoreal','Frontages')),exist_ok=True)
        buf=unreal.GeometryScriptSimpleMeshBuffers()
        buf.set_editor_properties(dict(vertices=[unreal.Vector(*p) for p in item['positions_cm']],
            normals=[unreal.Vector(*n) for n in item['normals']],uv0=[unreal.Vector2D(*p) for p in item['uv0']],
            vertex_colors=[unreal.LinearColor(*[linear(b) for b in c[:3]],1) for c in item['colors']],
            triangles=[unreal.IntVector(*item['indices'][i:i+3]) for i in range(0,len(item['indices']),3)]))
        dynamic=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buf,material_id=0)
        options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        options.set_editor_properties(dict(enable_nanite=True,enable_collision=False,enable_recompute_normals=False,enable_recompute_tangents=False))
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,package,options)
        if not mesh:raise RuntimeError('Frontage bake failed: '+package)
    mesh.set_material(0,assets.load_asset(item['material']));mesh.set_editor_property('allow_cpu_access',True)
    mesh.set_editor_property('generate_mesh_distance_field',item['id']!='glass')
    nanite=mesh.get_editor_property('nanite_settings');nanite.set_editor_property('enabled',True)
    nanite.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
    nanite.set_editor_property('fallback_relative_error',0.);nanite.set_editor_property('fallback_percent_triangles',1.)
    mesh.set_editor_property('nanite_settings',nanite)
    assets.set_metadata_tag(mesh,'ParisTwin.GeometrySHA256',item['geometry_sha256'])
    assets.set_metadata_tag(mesh,'ParisTwin.AppearanceProvenance',source['appearance_provenance'])
    if not assets.save_loaded_asset(mesh):raise RuntimeError('Cannot save frontage mesh')
    runtime['objects'].append({k:item[k] for k in ['id','asset','material','geometry_sha256','triangles']})
with open(os.path.join(folder,'paris-photo-frontages.json'),'w',encoding='utf-8') as f:json.dump(runtime,f,indent=2)
unreal.log_warning('PARIS_PHOTO_FRONTAGES_READY '+str(source['window_count']))
