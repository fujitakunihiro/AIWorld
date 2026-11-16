"""Shop-window glazing for the inferred storefronts (illustrative interiors, not surveyed shops).

M_ParisShopWindow is an opaque, glossy pane (so Lumen reflections show the sky and street) whose
base colour / emissive come from interior mapping: a box room behind the glass with shelves of goods,
a timber floor and ceiling spots. UV must run 0..1 across each pane; PerInstanceRandom varies the shop.
"""
import unreal
a = unreal.EditorAssetLibrary
t = unreal.AssetToolsHelpers.get_asset_tools()
l = unreal.MaterialEditingLibrary
BASE = '/Game/ParisPhotoreal/Street'
RECIPE = 'paris_shop_window_v2'


def custom(mat, code, inputs, kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    c = l.create_material_expression(mat, unreal.MaterialExpressionCustom)
    c.set_editor_properties(dict(code=code, output_type=kind))
    pins = []
    for key in inputs:
        p = unreal.CustomInput(); p.set_editor_property('input_name', key); pins.append(p)
    c.set_editor_property('inputs', pins)
    for key, (src, out) in inputs.items():
        if not l.connect_material_expressions(src, out, c, key):
            raise RuntimeError('wire ' + key)
    return c


ROOM = '''float3 N=normalize(Nrm);float3 T=normalize(cross(float3(0,0,1),N));float3 B=float3(0,0,1);
float3 V=normalize(View);
float3 d=float3(-dot(V,T),-dot(V,B),min(-dot(V,N),-.06));
float2 p=float2(UV.x,1.-UV.y);
const float D=1.15;
float tx=d.x>0?(1.-p.x)/d.x:(d.x<0?-p.x/d.x:1e9);
float ty=d.y>0?(1.-p.y)/d.y:(d.y<0?-p.y/d.y:1e9);
float tz=-D/d.z;
float t=min(tz,min(tx,ty));float3 h=float3(p,0)+d*t;
float s=frac(Seed*17.31);
float3 wall=lerp(float3(.46,.38,.28),float3(.30,.36,.38),s);
float3 col;float spot=0;
if(t==tz){
  float row=floor(h.y*5.);float fy=frac(h.y*5.);float cx=h.x*9.+row*.37;float id=floor(cx)+row*13.+floor(Seed*53.);
  float3 rnd=frac(sin(float3(id*12.9898,id*78.233,id*37.719))*43758.5453);float3 goods=saturate(lerp(dot(rnd,float3(.33,.33,.33)).xxx,rnd,1.7))*.85+.05;
  float item=step(.12,frac(cx))*step(frac(cx),.88)*step(.10,fy)*step(fy,.80);
  col=lerp(wall*.72,goods,item);col=lerp(col,float3(.22,.15,.09),step(fy,.07));
}else if(t==ty){
  if(d.y>0){col=float3(.50,.48,.44);spot=(1.-smoothstep(.02,.07,abs(frac(h.x*3.)-.5)))*(1.-smoothstep(.03,.09,abs(frac(-h.z*2.5)-.5)));}
  else col=float3(.24,.16,.09)*(.85+.15*step(.5,frac(h.x*6.)));
}else col=wall*.88;
float depth=saturate(-h.z/D);
float3 room=col*lerp(1.05,.62,depth)+spot*float3(1.,.9,.7)*1.6;
'''

path = BASE + '/M_ParisShopWindow'
mat = a.load_asset(path) if a.does_asset_exist(path) else None
if mat and a.get_metadata_tag(mat, 'ParisTwin.ShopRecipe') != RECIPE:
    a.delete_asset(path); mat = None
if not mat:
    mat = t.create_asset('M_ParisShopWindow', BASE, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_properties(dict(two_sided=False, blend_mode=unreal.BlendMode.BLEND_OPAQUE,
                                   shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT))
    uv = l.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate)
    nrm = l.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS)
    view = l.create_material_expression(mat, unreal.MaterialExpressionCameraVectorWS)
    seed = l.create_material_expression(mat, unreal.MaterialExpressionPerInstanceRandom)
    nits = l.create_material_expression(mat, unreal.MaterialExpressionScalarParameter)
    nits.set_editor_properties(dict(parameter_name='InteriorNits', default_value=300.))
    ins = dict(UV=(uv, ''), Nrm=(nrm, ''), View=(view, ''), Seed=(seed, ''))
    base = custom(mat, ROOM + 'return room*.30;', ins)
    l.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
    glow = custom(mat, ROOM + 'return room*Nits;', dict(ins, Nits=(nits, '')))
    l.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    rough = l.create_material_expression(mat, unreal.MaterialExpressionConstant); rough.set_editor_property('r', .07)
    l.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    spec = l.create_material_expression(mat, unreal.MaterialExpressionConstant); spec.set_editor_property('r', .6)
    l.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
    l.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    errors = l.recompile_material(mat)
    if errors:
        raise RuntimeError('shop window shader errors ' + str(errors))
    a.set_metadata_tag(mat, 'ParisTwin.ShopRecipe', RECIPE)
    if not a.save_loaded_asset(mat, only_if_is_dirty=False):
        raise RuntimeError('save shop window')
unreal.log_warning('PARIS_SHOPFRONT_MATERIALS_READY')
