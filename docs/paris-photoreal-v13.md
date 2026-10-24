# Paris Photoreal v13 — 写真スキャン面のPBRディテール

2026-10-18。都市範囲とGIS配置はそのままに、ノートルダム西正面の写真由来スキャン面を仕上げた。

## 変更

- 写真スキャン由来の色と形状法線を保持し、CC0のwhite_plaster_02法線とORM粗さを1mの正面基準スケールで重ねた。
- 微細法線の寄与は0.16、粗さの寄与は0.38。視差や高さ変位は追加せず、元の位置・衝突判定・開口マスク・歩行データを変更しない。
- 素材を実際にUE5で生成し、元データからの再生成時にも同じ設定を使用する。
- テクスチャは砂岩そのものの測定ではなく、細粒石肌のCC0見た目素材。スキャンに焼き込まれた撮影照明は残るため、物理的なアルベド復元とは扱わない。

## 実行した検証

- Pythonのスキャン・座標・ライセンス・再現性テスト：9件成功。
- UE5.8.3のアセットベイク：成功、0エラー、3警告。2件は既存APIの非推奨警告。
- 写実モードのUE自動テスト：21件成功。スキャン表示・fallback、GIS、衝突、環境切替を確認。
- AMD Radeon Graphics搭載PC、DX12/SM6、Lumen、High、1920×1080で撮影。正面表示は平均21.56fps、P95 53.79ms。60fps目標には未達。

正面画像：[paris-v13-front-high.png](screenshots/paris-v13-front-high.png)。実機スクリーンショットで、描画負荷を含む測定値は[計測JSON](paris-v13-front-high-performance.json)。

## 再生成

```powershell
./unreal/scripts/Build-NotreDameScan.ps1 -EngineRoot 'D:\Epic Games\UE_5.8'
./unreal/scripts/Test-ParisDigitalTwin.ps1 -EngineRoot 'D:\Epic Games\UE_5.8' -Photoreal -VirginDetail
```

## まだ写真相当ではない点

現行シーンは正面の一部を2019年の写真点群から作った2.5D面で覆い、残りは推定形状で補完している。塔・屋根・側面を含む全周の実測写真測量モデルではなく、モデル全体の色には旧写真の照明が残る。プロジェクト内の別候補は約30万三角形、1Kカラー、アンリット素材であり、置き換えには採用していない。測量済み全周モデル、現地に一致するPBR素材、スキャン位置合わせが写真相当の品質に必要。
