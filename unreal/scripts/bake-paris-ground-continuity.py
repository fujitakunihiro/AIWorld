"""Rebuild the local ground material and mesh, then reapply the rain layer."""
from pathlib import Path
import unreal

folder=Path(__file__).resolve().parent
photo=folder/'create-paris-photo-assets.py'
code=photo.read_text(encoding='utf-8').split('# Exterior stained glass')[0]
code=code.replace('for entry in entries:', "for entry in entries:\n    if entry['material'] != 'M_ParisGroundPaving':continue", 1)
exec(compile(code,str(photo),'exec'),{'__file__':str(photo),'__name__':'paris_ground_material'})
for name in ('bake-paris-ground.py','bake-paris-rain.py'):
    path=folder/name
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),{'__file__':str(path),'__name__':'paris_ground_bake'})
unreal.log('PARIS_GROUND_CONTINUITY_READY')
