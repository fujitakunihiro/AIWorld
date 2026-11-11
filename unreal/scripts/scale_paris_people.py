"""Downscale the verified Rocketbox textures to 1024 px before import (keeps committed UE content small).

The raw sources stay untouched (their hashes are verified by bake-paris-people.py); scaled copies go to
unreal/assets/paris-people/Scaled/ with the same relative paths. Needs Pillow (system Python).
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'unreal/assets/paris-people/Raw'
OUT = ROOT / 'unreal/assets/paris-people/Scaled'
count = 0
for src in RAW.glob('Assets/Avatars/*/*/Textures/*.tga'):
    dst = OUT / src.relative_to(RAW)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        limit = 512 if ('_normal' in src.stem or '_specular' in src.stem) else 1024  # detail maps matter less at street distance
        if max(im.size) > limit:
            scale = limit / max(im.size)
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
        im.save(dst)
    count += 1
print('PARIS_PEOPLE_TEXTURES_SCALED', count)
