"""Optional fictional festival lighting attached to existing decoration anchors."""
import hashlib,math
from shapely.geometry import LineString
from generate_paris_frontages import Mesh

PALETTE=[[255,16,91,255],[18,157,255,255],[255,163,13,255],[151,29,255,255],[12,237,188,255]]


def star(mesh,x,y,z,r,color):
    points=[]
    for i in range(10):
        angle=math.pi/2+i*math.tau/10;rr=r if i%2==0 else r*.43
        points.append([x+rr*math.cos(angle),y,z+rr*math.sin(angle)])
    for a,b in zip(points,points[1:]+points[:1]):mesh.face([[x,y,z],a,b],[0,1,0],color)


def make_models(lathe_at):
    result=[];metal=Mesh();gold=Mesh();bronze=[151,117,54,255];cream=[255,213,130,255]
    def add(name,mesh,role):
        item=mesh.item(name,'M_ParisLuxury'+role);item['asset']=item['asset'].replace('/Frontages/SM_ParisFrontage_','/Luxury/SM_ParisLuxury_');result.append(item)
    # Five fans meet at the already validated wall hooks, forming a light canopy.
    for offset in [-160,-80,0,80,160]:
        def p(x):
            f=1-(x/500)**2;return [x,offset*f,620-30*f]
        for j in range(32):metal.tube(p(-500+j*1000/32),p(-500+(j+1)*1000/32),.4,bronze,5)
        for j in range(15):
            x=-460+j*920/14;px,py,z=p(x)
            lathe_at(gold,[(z-5,0),(z-4,2.4),(z-1,2.7),(z+1,0)],px,py,cream,8)
    star(gold,0,-8,540,32,cream);metal.tube([0,0,590],[0,-8,570],.6,bronze,6)
    for j in range(9):
        x=-420+j*840/8;h=560-35*(1-(x/500)**2)-4
        metal.tube([x,0,620-30*(1-(x/500)**2)],[x,0,h],.65,bronze,6)
        for low,high,r in [(h-44,h-39,6),(h-3,h+1,5)]:lathe_at(metal,[(low,r),(high,r)],x,0,bronze,12)
        profile=[(h-42,2),(h-38,9),(h-30,16),(h-20,19),(h-10,15),(h-3,9),(h,2)]
        for a in [k*math.tau/6 for k in range(6)]:
            points=[[x+r*math.cos(a),r*math.sin(a),z] for z,r in profile]
            for u,v in zip(points,points[1:]):metal.tube(u,v,.45,bronze,5)
    add('festival_canopy_metal',metal,'Metal');add('festival_canopy_gold',gold,'PartyGold')
    for theme in range(2):
        mesh=Mesh()
        for j in range(9):
            x=-420+j*840/8;h=560-35*(1-(x/500)**2)-4
            profile=[(h-42,2),(h-38,9),(h-30,16),(h-20,19),(h-10,15),(h-3,9),(h,2)]
            lathe_at(mesh,profile,x,0,PALETTE[(j+theme*2)%len(PALETTE)],20)
        add('festival_canopy_color_'+str(theme),mesh,'PartyColor')
    support=Mesh();badge=Mesh();star(badge,0,24,30,22,cream)
    for j in range(32):
        a=j*math.tau/32;b=(j+1)*math.tau/32
        badge.tube([29*math.cos(a),24,30+29*math.sin(a)],[29*math.cos(b),24,30+29*math.sin(b)],.7,cream,6)
    for x in [-27,27]:
        support.tube([x,14,-76],[x,24,-76],.6,bronze,5);support.tube([x,24,-76],[x,24,89],.45,bronze,5)
        for z in range(-70,90,20):
            lathe_at(badge,[(z-2,0),(z,1.8),(z+2,0)],x,25,cream,8)
    add('festival_banner_metal',support,'Metal');add('festival_banner_gold',badge,'PartyGold')
    for variant,color in enumerate([PALETTE[0],PALETTE[1],PALETTE[2]]):
        mesh=Mesh();mesh.tube([-172,119,266],[172,119,266],1.1,color,8)
        for j in range(84):
            def p(x):return [x,119,244-7*abs(math.sin((x+173.5)*math.pi/(347/14)))]
            mesh.tube(p(-172+j*344/84),p(-172+(j+1)*344/84),.8,color,8)
        add('festival_shop_glow_'+str(variant),mesh,'PartyColor')
    return result


def make_placements(records,buildings,water):
    result=[];rejected=[]
    for r in records:
        kind=r['kind']
        if kind not in ('street_garland','facade_banner','canopy'):continue
        seed=int(hashlib.sha256((r['source_id']+'party').encode()).hexdigest()[:8],16)
        common=dict(source_id=r['source_id'],building_source_id=r.get('building_source_id'),source_record_kind=kind,anchor_cm=r['anchor_cm'],yaw_degrees=r['yaw_degrees'],placement_provenance='fictional_festival_illumination_on_existing_inferred_decoration',feature_layer='festival')
        if 'scale_xyz' in r:common['scale_xyz']=r['scale_xyz']
        if kind=='street_garland':
            angle=math.radians(r['yaw_degrees']);cs=math.cos(angle);sn=math.sin(angle);p=r['anchor_cm'];scale=r['scale_xyz'][0];safe=True
            for offset in [-160,160]:
                points=[]
                for j in range(33):
                    x=-500+j*1000/32;y=offset*(1-(x/500)**2);points.append([p[0]+cs*x*scale-sn*y,p[1]+sn*x*scale+cs*y])
                curve=LineString(points)
                if curve.intersection(buildings).length>5 or curve.intersects(water):safe=False;break
            if not safe:
                rejected.append(dict(source_id=r['source_id'],kind='party_canopy',reason='Keep the expanded light canopy outside mapped building interiors and water'));continue
            result.append(dict(**common,kind='party_canopy',anchor_building_source_ids=r['anchor_building_source_ids'],minimum_clearance_cm=470,lanterns=9,fairy_lights=75,models=['festival_canopy_metal','festival_canopy_gold','festival_canopy_color_'+str(seed%2)]))
        elif kind=='facade_banner':result.append(dict(**common,kind='party_banner',models=['festival_banner_metal','festival_banner_gold']))
        else:result.append(dict(**common,kind='party_shop',models=['festival_shop_glow_'+str(seed%3)]))
    return result,rejected
