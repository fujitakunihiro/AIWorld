"""Original fictional Paris cultural posters; no real advertisements or logos.

Run with Pillow 12.3.0 and the standard Windows Georgia font. The generated PNG
is kept as an offline source asset: UE builds do not require Pillow or fonts.
"""
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'unreal/assets/paris-morris/Source/paris-morris-posters.png'
FONT = Path('C:/Windows/Fonts')


def font(size, bold=False):
    return ImageFont.truetype(str(FONT / ('georgiab.ttf' if bold else 'georgia.ttf')), size)


def centred(draw, y, text, f, fill, x=256):
    box = draw.textbbox((0, 0), text, font=f)
    draw.text((x-(box[2]-box[0])/2, y-box[1]), text, font=f, fill=fill)


def poster(draw, x, y, h, bg, ink, title, subtitle, kind):
    draw.rectangle((x+7,y+7,x+505,y+h-7), fill=bg)
    draw.rectangle((x+21,y+20,x+491,y+h-21), outline=ink, width=3)
    draw.rectangle((x+28,y+27,x+484,y+h-28), outline=ink, width=1)
    draw.line((x+50,y+110,x+462,y+110),fill=ink,width=2)
    centred(draw,y+48,title,font(48,True),ink,x+256)
    centred(draw,y+h-110,subtitle,font(24,True),ink,x+256)
    centred(draw,y+h-69,'PARIS  •  CULTURE',font(19),ink,x+256)
    cx=x+256;cy=y+h*.53
    if kind==0:
        # A cinematic sun, an arch and a river: original geometric artwork.
        draw.ellipse((cx-106,cy-150,cx+106,cy+62),fill=ink)
        draw.rectangle((cx-125,cy-6,cx+125,cy+66),fill=bg)
        draw.pieslice((cx-120,cy-78,cx+120,cy+158),180,360,fill=ink)
        draw.pieslice((cx-65,cy-38,cx+65,cy+95),180,360,fill=bg)
        for i in range(3):draw.arc((cx-150+i*10,cy+48+i*18,cx+150-i*10,cy+108+i*18),0,180,fill=ink,width=5)
    elif kind==1:
        draw.ellipse((cx-150,cy-150,cx+150,cy+150),outline=ink,width=6)
        draw.polygon([(cx,cy-125),(cx+26,cy-35),(cx+120,cy-35),(cx+46,cy+21),(cx+75,cy+115),(cx,cy+58),(cx-75,cy+115),(cx-46,cy+21),(cx-120,cy-35),(cx-26,cy-35)],fill=ink)
        draw.ellipse((cx-25,cy-25,cx+25,cy+25),fill=bg)
    elif kind==2:
        for j in range(4):
            draw.line((cx-150,cy-85+j*45,cx+150,cy-85+j*45),fill=ink,width=4)
        for dx,dy in [(-70,-100),(30,-55),(105,-10)]:
            draw.line((cx+dx,cy+dy,cx+dx,cy+dy+130),fill=ink,width=7)
            draw.ellipse((cx+dx-33,cy+dy+110,cx+dx+4,cy+dy+137),fill=ink)
    else:
        draw.ellipse((cx-125,cy-145,cx+125,cy+105),fill=ink)
        draw.ellipse((cx-81,cy-112,cx+170,cy+139),fill=bg)
        draw.polygon([(cx-130,cy+85),(cx+130,cy+85),(cx+93,cy+135),(cx-93,cy+135)],fill=ink)
        for i in range(5):draw.line((cx-145,cy+150+i*17,cx+145,cy+150+i*17),fill=ink,width=3)


def main():
    image=Image.new('RGB',(2048,2048),'#173c32');d=ImageDraw.Draw(image)
    designs=[
        ('#e8d9ae','#a9442e','CINÉMA','LE VOYAGE',0,'#1d4140','#e7cfa1','THÉÂTRE','SCÈNES DE NUIT',1),
        ('#c55b3c','#f2dfb5','MUSIQUE','LES NOTES DE PARIS',2,'#e4c998','#263f3a','EXPOSITION','SUR LES QUAIS',3),
        ('#e9d7ae','#3a3a39','THÉÂTRE','LES BELLES HEURES',1,'#315a52','#e7d9bc','CINÉMA','LA VILLE EN IMAGES',0),
        ('#d3b873','#243d39','MUSIQUE','NUITS PARISIENNES',2,'#994236','#f2dcb6','EXPOSITION','AU FIL DE L’EAU',3),
    ]
    for j,(bg,ink,title,sub,kind,bg2,ink2,title2,sub2,kind2) in enumerate(designs):
        x=j*512
        d.rectangle((x,0,x+511,219),fill='#173c32')
        d.rectangle((x+22,21,x+490,197),outline='#b99d59',width=4)
        centred(d,45,'PARIS',font(76,True),'#ddcc91',x+256)
        centred(d,139,'SPECTACLES',font(27,True),'#c8b87f',x+256)
        poster(d,x,220,902,bg,ink,title,sub,kind)
        poster(d,x,1122,926,bg2,ink2,title2,sub2,kind2)
    # Small deterministic speckles suggest aged paper without obscuring type.
    rng=random.Random(731501)
    for _ in range(12000):
        x=rng.randrange(2048);y=rng.randrange(225,2048)
        if rng.random()<.5:
            r,g,b=image.getpixel((x,y)); delta=rng.randrange(-15,9)
            d.point((x,y),fill=tuple(max(0,min(255,c+delta)) for c in (r,g,b)))
    OUT.parent.mkdir(parents=True,exist_ok=True);image.save(OUT,optimize=True)
    print(OUT)


if __name__=='__main__':main()
