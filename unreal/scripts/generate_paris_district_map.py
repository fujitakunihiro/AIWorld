"""Render a documentation map from archived geometry and decoration coordinates.

No UE screenshots are altered. Pillow is only needed for this optional PNG map;
it is not a GIS generation or runtime dependency.
"""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]


def generate():
    data=json.loads((ROOT/'unreal/AIWorld/Content/Data/paris-luxury.json').read_text(encoding='utf-8'))
    district=json.loads((ROOT/'gis/Data/Processed/ile_de_la_cite/district.json').read_text(encoding='utf-8'))
    ox,oy=district['origin_projected_m'];image=Image.new('RGB',(1200,1200),'#faf8f2');draw=ImageDraw.Draw(image)
    def font(size):return ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',size)
    def xy(p):return (100+(p[0]+40000)/80,120+(p[1]+40000)/80)
    def projected(p):return xy([(p[0]-ox)*100,-(p[1]-oy)*100])
    def polygons(g):
        if g['type']=='Polygon':return [g['coordinates']]
        if g['type']=='MultiPolygon':return g['coordinates']
        return []
    draw.text((100,24),'PARIS | DISTRICT-WIDE DECORATION',fill='#213e43',font=font(28))
    cov=data['coverage'];draw.text((100,66),f"800 x 800 m | {cov['decorated_eligible_cells']}/{cov['eligible_cells']} occupied 100 m cells decorated",fill='#54666a',font=font(20))
    for layer,color in [('water','#a4cbd5'),('parks','#d7e3c5'),('buildings','#ded5c5')]:
        for f in district['layers'].get(layer,[]):
            for rings in polygons(f['geometry']):
                for i,ring in enumerate(rings):draw.polygon([projected(p) for p in ring],fill=color if i==0 else '#faf8f2')
    for k in range(9):
        q=120+k*125;draw.line([(100,q),(1100,q)],fill='#c7cbca',width=1)
        q=100+k*125;draw.line([(q,120),(q,1120)],fill='#c7cbca',width=1)
    styles={'canopy':('#2f7098',3),'pole':('#bd8b27',3),'window':('#ad4388',2),'urn':('#438152',3)}
    garlands=[r for r in data['records'] if r['kind']=='street_garland']
    for r in garlands:draw.line([xy(p) for p in r['anchor_ends_cm']],fill='#bb453b',width=3)
    for kind,(color,radius) in styles.items():
        for r in data['records']:
            if r['kind']!=kind:continue
            x,y=xy(r['anchor_cm']);draw.ellipse([x-radius,y-radius,x+radius,y+radius],fill=color)
    draw.rectangle([100,120,1100,1120],outline='#71868b',width=2)
    counts={kind:sum(r['kind']==kind for r in data['records']) for kind in styles}
    labels={'canopy':'shops','pole':'lamp baskets','window':'window flowers','urn':'flower urns'}
    for i,(kind,(color,radius)) in enumerate(styles.items()):
        x=100+i*265;draw.ellipse([x,1146,x+12,1158],fill=color);draw.text((x+20,1138),f'{counts[kind]} {labels[kind]}',fill='#213e43',font=font(18))
    draw.text((100,1172),f'{len(garlands)} overhead garlands (red lines). Inferred decoration. GIS IDs retained. Grid: 100 m.',fill='#54666a',font=font(16))
    out=ROOT/'docs/paris-garlands-coverage.png';image.save(out);print(out)


if __name__=='__main__':generate()
