"""Collect actual captures, tests and immutable input checks into one report."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'unreal/AIWorld/Content/Data';DOCS=ROOT/'docs';SAVED=ROOT/'unreal/AIWorld/Saved'
p=json.loads((DATA/'paris-seine.json').read_text(encoding='utf-8'))
backup=Path((ROOT/'backups/current-seine-backup.txt').read_text(encoding='utf-8-sig').strip())
preserved={name:(DATA/name).read_bytes()==(backup/'unreal/AIWorld/Content/Data'/name).read_bytes() for name in ('paris-reference.json','paris-lane.json')}
assert all(preserved.values())
regen=json.loads((ROOT/'backups/seine-regeneration.json').read_text())
assert regen['byte_identical_regeneration']
current=hashlib.sha256((ROOT/'unreal/assets/paris-seine/Generated/seine.json').read_bytes()).hexdigest();assert current==regen['sha256']
tests={}
for group in ('seine','environment','reference','lane'):
    text=(SAVED/f'paris-seine-{group}-automation.log').read_text(encoding='utf-8-sig')
    assert 'Result={Fail}' not in text
    names=re.findall(r'Result=\{Success\}.*?Name=\{([^}]+)\}',text)
    assert names,group
    tests[group]=names
captures={}
for file in sorted(DOCS.glob('paris-seine-*-performance.json')):
    d=json.loads(file.read_text(encoding='utf-8-sig'));shot=file.with_name(file.name.replace('-performance.json','.png'));assert shot.is_file()
    captures[shot.name]=dict(fps=d['fps'],quality=d['detail_quality'],rhi=d['rhi'],feature_level=d['shader_feature_level'],camera=d.get('seine_camera'),seine_look=d['seine_look'])
assert len(captures)>=4
matching=[captures[f'paris-seine-cathedral-{view}.png']['camera'] for view in ('after','day','night')]
assert all(camera==matching[0] for camera in matching),'Day, sunset and night must use the same saved camera'
digest=hashlib.sha256((DATA/'paris-digital-twin-meshes.bin').read_bytes()).hexdigest();assert digest==p['seine']['source_geometry_sha256']=='fba61d4426bf6cc2fc40bda2818d48fe4a6d8e3c58bf13e025254ddc20bc97d8'
report=dict(date='2026-11-09',recipe=p['recipe'],source_scene_sha256=p['source_scene_sha256'],source_geometry_sha256=digest,source_geometry_unchanged=True,previous_mode_packets_preserved=preserved,counts=p['counts'],models=len(p['objects']),regeneration=regen,native_tests=tests,python_tests=3,captures=captures,backup=str(backup),photo_parity_achieved=False,appearance_inferred=True,fps_target_60_achieved=False,limitations=['800m acquired district only','inferred architectural exterior and lighting','existing terrain crossfall and source geometry warnings remain'])
(DOCS/'paris-seine-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(models=report['models'],native_tests=sum(map(len,tests.values())),captures=len(captures),geometry_unchanged=True),ensure_ascii=False))
doc=DOCS/'paris-seine-vistas.md';marker='\n<!-- execution-results -->\n';body=doc.read_text(encoding='utf-8').split(marker)[0]
rows=['| 実画面 | fps |','| --- | ---: |']
labels={'paris-seine-cathedral-after.png':'大聖堂・夕方','paris-seine-cathedral-day.png':'大聖堂・昼','paris-seine-cathedral-night.png':'大聖堂・夜','paris-seine-bridge-day.png':'サン・ミシェル橋・昼','paris-seine-aerial-after.png':'上空・夕方'}
for name,c in captures.items():rows.append(f'| [{labels.get(name,name)}]({name}) | {c["fps"]:.2f} |')
results='\n実行済み：UE 5.8のC++ビルドとアセット保存に成功。地理検証3件とUE内検証5件が成功し、最終データでの水面素材の適用も再確認した。元のGISメッシュと従来の2表示用データは変更前と一致。最初からの再生成も同一ハッシュになった。\n\n大聖堂の昼・夕・夜は同じ位置・画角で撮影。全て1280×720、High、描画100%、DX12/SM6、人物・車の移動を止めた未加工のUE実画像。AMD Radeon(TM) Graphicsの環境で60fpsには未達。通常起動はMedium・80%・人物と交通ありで条件が異なる。\n\n'+'\n'.join(rows)+'\n\n![夕景のUE実画面](paris-seine-cathedral-after.png)\n'
doc.write_text(body+marker+results,encoding='utf-8')
