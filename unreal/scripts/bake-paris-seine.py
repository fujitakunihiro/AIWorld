"""Private Seine materials and reusable GIS-attached architecture."""
import json,os,runpy,sys
from pathlib import Path
import unreal
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from paris_surface_realism import limestone, glazing, RECIPE as SURFACE_RECIPE
os.environ['PARIS_REFERENCE_SOURCE']=str(ROOT/'unreal/assets/paris-seine/Generated/seine.json')
os.environ['PARIS_REFERENCE_RUNTIME']=str(ROOT/'unreal/AIWorld/Content/Data/paris-seine.json')
runpy.run_path(str(ROOT/'unreal/scripts/bake-paris-reference.py'),run_name='__main__')
assets=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary

def copy_material(source,name,recipe,edit):
    path='/Game/Materials/'+name
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if mat and assets.get_metadata_tag(mat,'ParisTwin.SeineRecipe')!=recipe:
        # Recipes edit the source graph; start again from the source so edits never stack.
        if not assets.delete_asset(path):raise RuntimeError('Cannot replace '+name)
        mat=None
    if not mat:mat=assets.duplicate_asset(source,path)
    if not mat:raise RuntimeError('Missing material '+source)
    if assets.get_metadata_tag(mat,'ParisTwin.SeineRecipe')!=recipe:
        if isinstance(mat,unreal.MaterialInstanceConstant):
            # Grade a private copy of the parent so the shared parent stays untouched.
            parent=mat.get_editor_property('parent')
            while isinstance(parent,unreal.MaterialInstance):parent=parent.get_editor_property('parent')
            ppath='/Game/Materials/'+name+'_Base'
            if assets.does_asset_exist(ppath) and not assets.delete_asset(ppath):raise RuntimeError('Cannot replace '+ppath)
            base=assets.duplicate_asset(parent.get_path_name().split('.')[0],ppath)
            edit(base);lib.set_material_usage(base,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES);lib.set_material_usage(base,unreal.MaterialUsage.MATUSAGE_NANITE)
            errors=lib.recompile_material(base)
            if errors:raise RuntimeError('Seine shader errors '+str(errors))
            if not assets.save_loaded_asset(base,only_if_is_dirty=False):raise RuntimeError('Cannot save '+ppath)
            lib.set_material_instance_parent(mat,base);assets.set_metadata_tag(mat,'ParisTwin.SeineRecipe',recipe)
            if not assets.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('Cannot save '+name)
            return
        edit(mat)
        lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
        errors=lib.recompile_material(mat)
        if errors:raise RuntimeError('Seine shader errors '+str(errors))
        assets.set_metadata_tag(mat,'ParisTwin.SeineRecipe',recipe)
        if not assets.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('Cannot save '+name)

def water(mat):
    edits=set()
    for n in lib.get_material_expressions(mat):
        if isinstance(n,unreal.MaterialExpressionScalarParameter) and str(n.get_editor_property('parameter_name'))=='RippleStrength':n.set_editor_property('default_value',.30);edits.add('ripples')
        if not isinstance(n,unreal.MaterialExpressionCustom):continue
        code=n.get_editor_property('code')
        if 'float bank=' in code:
            n.set_editor_property('code','float bank=1.-smoothstep(60.,1500.,max(Distance,0.));float mottled=.5+.5*sin(Position.x*.0007+sin(Position.y*.0011));return lerp(float3(.026,.027,.017),float3(.040,.037,.024),bank*.55)*(.92+.14*mottled);');edits.add('color')
        if 'return .13+' in code or 'return .16+' in code:n.set_editor_property('code','return .045+(.5+.5*N.y)*.02+(1.-smoothstep(20.,160.,max(Distance,0.)))*.05;');edits.add('roughness')
    if edits!={'ripples','color','roughness'}:raise RuntimeError('Unexpected source water graph '+str(edits))

def stone(mat):
    limestone(mat)
    base=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR);pin=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_BASE_COLOR)
    n=lib.create_material_expression(mat,unreal.MaterialExpressionCustom);n.set_editor_properties(dict(code='float g=dot(C.rgb,float3(.2126,.7152,.0722));float3 cream=float3(.84,.71,.52);float3 t=lerp(C.rgb,cream*(g/.40),.62);return saturate(t*.94);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3));inp=unreal.CustomInput();inp.set_editor_property('input_name','C');n.set_editor_property('inputs',[inp])
    if not lib.connect_material_expressions(base,pin,n,'C') or not lib.connect_material_property(n,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Seine stone graph')

def zinc_grade(mat):
    # Paris zinc/slate: weathered neutral grey, not sky-blue.
    base=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR);pin=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_BASE_COLOR)
    if not base:raise RuntimeError('Roof base colour unconnected')
    n=lib.create_material_expression(mat,unreal.MaterialExpressionCustom);n.set_editor_properties(dict(code='float g=dot(C.rgb,float3(.2126,.7152,.0722));return lerp(C.rgb,g.xxx,.75)*float3(1.03,1.01,.97)*.92;',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3));inp=unreal.CustomInput();inp.set_editor_property('input_name','C');n.set_editor_property('inputs',[inp])
    if not lib.connect_material_expressions(base,pin,n,'C') or not lib.connect_material_property(n,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Seine roof graph')
    rough=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_ROUGHNESS)
    if rough:
        rp=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_ROUGHNESS)
        r=lib.create_material_expression(mat,unreal.MaterialExpressionCustom);r.set_editor_properties(dict(code='return max(R,.55);',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1));i=unreal.CustomInput();i.set_editor_property('input_name','R');r.set_editor_property('inputs',[i])
        if not lib.connect_material_expressions(rough,rp,r,'R') or not lib.connect_material_property(r,'',unreal.MaterialProperty.MP_ROUGHNESS):raise RuntimeError('Seine roof roughness')

def night_water(mat):
    water(mat)
    collection=assets.load_asset('/Game/Night/MPC_ParisNight')
    n=lib.create_material_expression(mat,unreal.MaterialExpressionCollectionParameter);n.set_editor_properties(dict(collection=collection,parameter_name='NightAmount'))
    def expression(code,inputs):
        c=lib.create_material_expression(mat,unreal.MaterialExpressionCustom);c.set_editor_properties(dict(code=code,output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3));pins=[]
        for key in inputs:
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        c.set_editor_property('inputs',pins)
        for key,(src,out) in inputs.items():
            if not lib.connect_material_expressions(src,out,c,key):raise RuntimeError('Night water input '+key)
        return c
    base=lib.get_material_property_input_node(mat,unreal.MaterialProperty.MP_BASE_COLOR);pin=lib.get_material_property_input_node_output_name(mat,unreal.MaterialProperty.MP_BASE_COLOR)
    shade=expression('return C*lerp(1.,.10,smoothstep(.5,1.,N));',{'C':(base,pin),'N':(n,'')})
    if not lib.connect_material_property(shade,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Night water color')
    behind=expression('return float3(.16,.17,.11)*lerp(1.,.20,smoothstep(.5,1.,N));',{'N':(n,'')})
    scatter=expression('return float3(.00006,.00007,.00004)*lerp(1.,.08,smoothstep(.5,1.,N));',{'N':(n,'')})
    for out in lib.get_material_expressions(mat):
        if not isinstance(out,unreal.MaterialExpressionSingleLayerWaterMaterialOutput):continue
        names=lib.get_material_expression_input_names(out)
        for semantic,src in [('ColorScaleBehindWater',behind),('ScatteringCoefficients',scatter)]:
            key=next(x for x in names if x.replace(' ','').lower()==semantic.lower())
            if not lib.connect_material_expressions(src,'',out,key):raise RuntimeError('Night water scattering')

def twilight(mat):
    changed=False
    for n in lib.get_material_expressions(mat):
        if isinstance(n,unreal.MaterialExpressionCustom) and 'float h=smoothstep' in n.get_editor_property('code'):
            n.set_editor_property('code','float h=smoothstep(.02,.65,saturate(D.z));float3 tint=lerp(float3(.90,.54,.46),float3(.14,.28,.65),h);return C.rgb*tint*15.;');changed=True
    if not changed:raise RuntimeError('Missing photographic evening sky graph')

QUAY_CORE='''float3 n=normalize(float3(N.xy,0.)+float3(1e-4,0,0));float2 t=float2(-n.y,n.x);float u=dot(P.xy,t);float v=P.z;
float hs[3];float joint=1.,tone=.5,course=0.;
for(int k=0;k<3;k++){float uu=u+(k==1?1.5:0.);float vv=v+(k==2?1.5:0.);
 float H=44.;float r=floor(vv/H);float hr=frac(sin(r*12.9898)*43758.5453);float L=92.+hr*58.;float x=uu+hr*173.;float b=floor(x/L);
 float fx=x-b*L,fy=vv-r*H;float m=min(min(fx,L-fx),min(fy,H-fy));float j=smoothstep(.5,2.8,m);
 float hb=frac(sin(r*78.233+b*37.719)*24634.6345);float face=.6+.4*smoothstep(0.,9.,m)+.25*hb*smoothstep(3.,12.,m);
 hs[k]=j*face;if(k==0){joint=j;tone=hb;course=hr;}}
float W=WATER;float macro=.5+.5*sin(u*.011+sin(v*.019+u*.003))*sin(u*.0041-v*.0057);
float drip=pow(saturate(.5+.5*sin(u*.083+3.*sin(u*.021))),5.)*(.5+.5*sin(u*.0071));
float wet=1.-smoothstep(W+15.,W+150.+70.*macro,v);float tide=(1.-smoothstep(W+100.,W+420.,v))*(1.-wet);
'''
def quay():
    path='/Game/Materials/M_ParisSeineQuay';recipe='ashlar_quay_v2'
    mat=assets.load_asset(path) if assets.does_asset_exist(path) else None
    if mat and assets.get_metadata_tag(mat,'ParisTwin.SeineRecipe')==recipe:return
    if mat and not assets.delete_asset(path):raise RuntimeError('Cannot replace quay')
    level=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-water.json').read_text(encoding='utf-8'))['water_level_cm']
    mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_ParisSeineQuay','/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    mat.set_editor_property('tangent_space_normal',False)
    wp=lib.create_material_expression(mat,unreal.MaterialExpressionWorldPosition);vn=lib.create_material_expression(mat,unreal.MaterialExpressionVertexNormalWS)
    core=QUAY_CORE.replace('WATER','%.1f'%level)
    outputs={
        unreal.MaterialProperty.MP_BASE_COLOR:(unreal.CustomMaterialOutputType.CMOT_FLOAT3,'float3 c=float3(.49,.43,.32)*(.91+.13*tone)*(.86+.22*macro)*(.97+.06*course);c=lerp(c*.80,c,joint);c*=1.-.22*drip*saturate(1.-(v-W)/900.);c=lerp(c,c*float3(.72,.70,.62),tide*.55);c=lerp(c,float3(.075,.072,.050),wet*.85);return c;'),
        unreal.MaterialProperty.MP_ROUGHNESS:(unreal.CustomMaterialOutputType.CMOT_FLOAT1,'return lerp(lerp(.93,.80,joint)-.05*tone,.38,wet);'),
        unreal.MaterialProperty.MP_NORMAL:(unreal.CustomMaterialOutputType.CMOT_FLOAT3,'float2 g=float2(hs[1]-hs[0],hs[2]-hs[0])/1.5;return normalize(n-1.4*(float3(t,0.)*g.x+float3(0,0,1)*g.y));'),
        unreal.MaterialProperty.MP_AMBIENT_OCCLUSION:(unreal.CustomMaterialOutputType.CMOT_FLOAT1,'return lerp(.75,1.,joint);'),
    }
    for prop,(kind,tail) in outputs.items():
        c=lib.create_material_expression(mat,unreal.MaterialExpressionCustom);c.set_editor_properties(dict(code=core+tail,output_type=kind));pins=[]
        for key in ('P','N'):
            pin=unreal.CustomInput();pin.set_editor_property('input_name',key);pins.append(pin)
        c.set_editor_property('inputs',pins)
        if not lib.connect_material_expressions(wp,'',c,'P') or not lib.connect_material_expressions(vn,'',c,'N') or not lib.connect_material_property(c,'',prop):raise RuntimeError('Quay graph')
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    lib.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_NANITE)
    errors=lib.recompile_material(mat)
    if errors:raise RuntimeError('Quay shader errors '+str(errors))
    assets.set_metadata_tag(mat,'ParisTwin.SeineRecipe',recipe)
    if not assets.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('Cannot save quay')

quay()
copy_material('/Game/Materials/M_SeineRiver','M_ParisSeineWater','murky_mirror_river_v3',night_water)
copy_material('/Game/Materials/M_ParisReferenceStone','M_ParisSeineStone',SURFACE_RECIPE+'_cream2',stone)
copy_material('/Game/Materials/M_Paris_Roof_Zinc','M_ParisSeineZinc','grey_zinc_v1',zinc_grade)
copy_material('/Game/Materials/M_Paris_Roof_Slate','M_ParisSeineSlate','grey_zinc_v1',zinc_grade)
copy_material('/Game/Materials/M_ParisEveningSky','M_ParisSeineTwilight','photographic_blue_hour_v2',twilight)
glazing()
unreal.log_warning('PARIS_SEINE_ASSETS_READY')
