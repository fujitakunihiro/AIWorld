"""Record actual build/test logs and fresh UE screenshots for the surface pass."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
CONTENT = ROOT / 'unreal/AIWorld/Content'
backup = Path((ROOT / 'backups/current-surface-realism-backup.txt').read_text(encoding='utf-8-sig').strip())
baseline = (backup / 'commit.txt').read_text(encoding='utf-8-sig').strip()
subprocess.run(['git', 'diff', '--quiet', baseline, '--', 'unreal/AIWorld/Content/Data', 'gis/Data'], cwd=ROOT, check=True)

build = (ROOT / 'backups/surface-realism-build.log').read_text(encoding='utf-8-sig', errors='replace')
bake = (ROOT / 'backups/surface-realism-bake.log').read_text(encoding='utf-8-sig', errors='replace')
native = (ROOT / 'unreal/AIWorld/Saved/paris-surface-realism-automation.log').read_text(encoding='utf-8-sig', errors='replace')
assert 'Result: Succeeded' in build
assert 'Success - 0 error(s)' in bake and 'PARIS_SEINE_ASSETS_READY' in bake
tests = re.findall(r'Result=\{Success\} Name=\{([^}]+)\}', native)
assert set(tests) == {'ReferenceArchitectureAndRestoration', 'RainLifecycleAndShelter'}
assert 'Result={Fail}' not in native
assets = [CONTENT / 'Materials' / (name + '.uasset') for name in
          ('M_ParisSeineStone', 'M_ParisSeineWindow', 'MI_ParisSeineCoreWindow')]
latest_material = max(path.stat().st_mtime for path in assets)

captures = {}
for view, time in [('windows','day'), ('street','day'), ('windows','night'), ('street','rain')]:
    name = f'paris-surface-after-{view}-{time}'
    shot = DOCS / (name + '.png')
    stats = json.loads((DOCS / (name + '-performance.json')).read_text(encoding='utf-8-sig'))
    assert shot.stat().st_mtime > latest_material, f'Stale final screenshot: {name}'
    assert stats['seine_look'] and stats['reference_models'] >= 86
    log = (ROOT / 'unreal/AIWorld/Saved' / (name + '.log')).read_text(encoding='utf-8-sig', errors='replace')
    assert not re.search(r'Fatal error|Failed to compile Material|LogMaterial: Error|LogShaderCompilers: Error', log)
    if time == 'day':
        before = json.loads((DOCS / f'paris-surface-before-{view}-day-performance.json').read_text(encoding='utf-8-sig'))
        for key in ('active_photo_camera', 'camera_pitch_degrees', 'camera_elevation_ngf_m'):
            assert stats[key] == before[key], f'Camera changed: {view}/{key}'
    captures[f'{view}-{time}'] = dict(image=shot.name, fps=stats['fps'], frame_p95_ms=stats['frame_p95_ms'],
        captured_at=datetime.fromtimestamp(shot.stat().st_mtime, timezone.utc).isoformat())

report = dict(created_utc=datetime.now(timezone.utc).isoformat(), baseline_commit=baseline, backup=str(backup),
    source_data_unchanged=True, build_succeeded=True, asset_bake_errors=0, native_tests=tests,
    native_note='Material bindings and state transitions tested before final shader-only seed stabilization; final shaders verified in DX12 captures.',
    captures=captures, assets={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in assets},
    source_recipe_sha256=hashlib.sha256((ROOT/'unreal/scripts/paris_surface_realism.py').read_bytes()).hexdigest(),
    geometry_added=False, surveyed_interiors=False, reference_photo_parity_achieved=False, target_60fps_achieved=False)
(DOCS/'paris-surface-realism-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

rows=[]
for view,label in [('windows','窓の近景'),('street','カフェ前')]:
    before=json.loads((DOCS/f'paris-surface-before-{view}-day-performance.json').read_text(encoding='utf-8-sig'))
    after=captures[view+'-day']
    rows.append(f"| {label} | [変更前](paris-surface-before-{view}-day.png) {before['fps']:.2f}fps | [変更後]({after['image']}) {after['fps']:.2f}fps |")
section='''UE 5.8のC++ビルド、素材保存、自動検証2件が成功。新しい窓素材の実メッシュへの適用、昼夜・詳細表示切替後の復元、雨の継続・屋根下・乾燥を検証した。最終の素材だけの調整は、DX12/SM6で描画して確認した。元のGISと中間データは開始時のGitコミットと差分なし。

比較は1280×720、High、描画100%、人物・車の移動を止めたUE実画像。窓とカフェはそれぞれ同じカメラで比較している。夜の粒状ノイズが消えたことも実画像で確認。AMD Radeon内蔵GPU環境では60fps未達。通常起動のMedium・80%とは条件が異なる。

| 昼の比較 | 変更前 | 変更後 |
| --- | --- | --- |
'''+ '\n'.join(rows)+f"\n\n[夜の窓]({captures['windows-night']['image']})：{captures['windows-night']['fps']:.2f}fps。[雨のカフェ前]({captures['street-rain']['image']})：{captures['street-rain']['fps']:.2f}fps。\n\n[機械可読の実行記録](paris-surface-realism-validation.json)\n\n![最終版の昼の窓](paris-surface-after-windows-day.png)"
doc=DOCS/'paris-surface-realism.md'
text=doc.read_text(encoding='utf-8')
start=text.index('## 実行結果')
end=text.index('## 残る差と次の改善',start)
doc.write_text(text[:start]+'## 実行結果\n\n'+section+'\n\n'+text[end:],encoding='utf-8')
print(json.dumps(dict(native_tests=len(tests),fresh_final_captures=len(captures),source_data_unchanged=True)))
