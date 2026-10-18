"""Refresh authored cathedral details and dependent scan masks in one commandlet.

Use paths derived from __file__, not shell-encoded checkout path literals.
Acquisition and source geometry generation run separately in PowerShell/Python.
"""
from pathlib import Path
import unreal

scripts=Path(__file__).resolve().parent
steps=['create-paris-assets.py','bake-paris-architecture.py',
       'ensure-paris-nanite-materials.py']
if (Path(unreal.Paths.project_content_dir())/'Data/paris-notredame-scan-source.json').is_file():
    steps.append('bake-notredame-scan.py')
elif (Path(unreal.Paths.project_content_dir())/'Data/paris-notredame-scan.json').is_file():
    raise RuntimeError('Existing scanned facade needs its generated source before refreshing underlays; run Build-NotreDameScan.ps1')
if (Path(unreal.Paths.project_content_dir())/'Data/paris-notredame-statue-source.json').is_file():
    steps.append('bake-notredame-statue.py')
for name in steps:
    file=scripts/name
    exec(compile(file.read_text(encoding='utf-8'),str(file),'exec'),
         {'__file__':str(file),'__name__':'__main__'})
unreal.log('PARIS_CATHEDRAL_DETAILS_READY')
