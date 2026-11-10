"""Materials for the Sainte-Chapelle upper-chapel interior (illustrative, not scanned)."""
import unreal
a=unreal.EditorAssetLibrary;t=unreal.AssetToolsHelpers.get_asset_tools();l=unreal.MaterialEditingLibrary
base='/Game/ParisPhotoreal/SainteChapelle'
RECIPE='sainte_chapelle_interior_v13'

def fresh(name):
    pkg=base+'/'+name
    if a.does_asset_exist(pkg):
        m=a.load_asset(pkg)
        if a.get_metadata_tag(m,'ParisTwin.InteriorRecipe')==RECIPE:return None
        a.delete_asset(pkg)
    return t.create_asset(name,base,unreal.Material,unreal.MaterialFactoryNew())

def custom(mat,code,inputs,kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    c=l.create_material_expression(mat,unreal.MaterialExpressionCustom);c.set_editor_properties(dict(code=code,output_type=kind));pins=[]
    for key in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',key);pins.append(p)
    c.set_editor_property('inputs',pins)
    for key,(src,out) in inputs.items():
        if not l.connect_material_expressions(src,out,c,key):raise RuntimeError('wire '+key)
    return c

def finish(mat,name):
    l.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE) if False else None
    errors=l.recompile_material(mat)
    if errors:raise RuntimeError(name+' shader errors '+str(errors))
    a.set_metadata_tag(mat,'ParisTwin.InteriorRecipe',RECIPE)
    if not a.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('save '+name)

# 1. Stone, gilding and floor: base colour from vertex RGB, roughness from vertex alpha.
m=fresh('M_SainteChapelleInterior')
if m:
    m.set_editor_properties(dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
    vc=l.create_material_expression(m,unreal.MaterialExpressionVertexColor)
    l.connect_material_property(vc,'RGB',unreal.MaterialProperty.MP_BASE_COLOR)
    rough=custom(m,'return max(A,.25);',{'A':(vc,'A')},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    l.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    glow=custom(m,'return A<.03?V*45.:V*26.;',{'V':(vc,''),'A':(vc,'A')})
    l.connect_material_property(glow,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(m,'interior')

# 2. Stained glass: the existing CC0 interior photograph, emitted as a backlit window.
m=fresh('M_SainteChapelleInnerGlass')
if m:
    tex=a.load_asset(base+'/T_SainteChapelleWindows')
    if not tex:raise RuntimeError('Run Build-ParisChapelle.ps1 first: window photo missing')
    m.set_editor_properties(dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_UNLIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
    s=l.create_material_expression(m,unreal.MaterialExpressionTextureSample);s.set_editor_property('texture',tex)
    gain=l.create_material_expression(m,unreal.MaterialExpressionScalarParameter);gain.set_editor_properties(dict(parameter_name='GlassGain',default_value=150.))
    glow=custom(m,'float3 c=pow(saturate(C),1.25);float lum=dot(c,float3(.3,.59,.11));c=lerp(lum.xxx,c,1.45);return c*G;',{'C':(s,'RGB'),'G':(gain,'')})
    l.connect_material_property(glow,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(m,'glass')

# 3. Vault: deep ultramarine webs with a lattice of gold stars / fleurs-de-lis.
m=fresh('M_SainteChapelleVault')
if m:
    m.set_editor_properties(dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_UNLIT,blend_mode=unreal.BlendMode.BLEND_OPAQUE))
    wp=l.create_material_expression(m,unreal.MaterialExpressionWorldPosition)
    code='''float2 q=float2(P.x+P.y*.5,P.z+P.y*.35)/70.;float2 cell=frac(q)-.5;float2 id=floor(q);
float odd=fmod(id.x+id.y,2.);cell+=odd*float2(.0,.0);
float r=length(cell);float ang=atan2(cell.y,cell.x);float star=smoothstep(.20+.12*cos(ang*5.),.12+.12*cos(ang*5.),r);
float dot=1.-smoothstep(.05,.09,r);float mark=saturate(star*.9+dot);
float shade=.85+.15*sin(P.x*.004+P.z*.003);
float3 blue=float3(.010,.022,.20)*shade;float3 gold=float3(.78,.52,.10);'''
    col=custom(m,code+'return lerp(blue,gold,mark);',{'P':(wp,'')})
    em=custom(m,code+'return gold*mark*56.+blue*120.;',{'P':(wp,'')})
    l.connect_material_property(em,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(m,'vault')
# 4. Light shafts, floor pools and glitter motes: additive, unlit; vertex RGB = colour, vertex A = gain,
#    UV.x = along the shaft (or -1..1 across a pool/mote), UV.y = across.
m=fresh('M_SainteChapelleBeam')
if m:
    m.set_editor_properties(dict(two_sided=True,shading_model=unreal.MaterialShadingModel.MSM_UNLIT,blend_mode=unreal.BlendMode.BLEND_ADDITIVE))
    vc=l.create_material_expression(m,unreal.MaterialExpressionVertexColor)
    tc=l.create_material_expression(m,unreal.MaterialExpressionTextureCoordinate)
    wp=l.create_material_expression(m,unreal.MaterialExpressionWorldPosition)
    tm=l.create_material_expression(m,unreal.MaterialExpressionTime)
    code='''float f=pow(saturate(1.-abs(UV.x)),1.3);float e=pow(saturate(sin(3.14159*saturate(UV.y))),1.5);
float n=frac(sin(dot(floor(P*.05),float3(12.9898,78.233,37.719)))*43758.5453);
float tw=pow(saturate(sin(T*2.5+n*40.)),10.)*step(.55,n)*step(.9,A);
float3 d=float3(.55,.5,.4)*f*e*.15;
return V*A*40.*f*e*(1.+tw*9.)+d*A*.8;'''
    glow=custom(m,code,{'V':(vc,''),'A':(vc,'A'),'UV':(tc,''),'P':(wp,''),'T':(tm,'')})
    l.connect_material_property(glow,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(m,'beam')
unreal.log_warning('PARIS_CHAPELLE_INTERIOR_MATERIALS_READY')
