# 暖かい窓明かりとカーテンの陰影

このページはv6段階の記録。現在の起動ファイルは、[窓の立体感・人物表示・夕景を改善したv7](paris-street-realism.md)を使う。

`paris_warm_windows_v6` は、ガーランドと花を保持したまま、589棟・6,362か所の上階の窓に暖色の明かりを追加する。建物全体の窓候補から約40%を固定シードで選び、残りは暗いままにする。花箱の有無とは別に点灯を決め、通りに面する窓にも灯りを配る。これは推定の演出であり、実際の部屋や居住者の在宅状況を示す情報ではない。

追加するのは、元の窓面に沿った薄い表示用の面。既存のガラスと木枠の奥行きを調べ、ガラスより1cm前、木枠より奥に収める。中央の縦枠と上部の横枠の部分に隙間を設け、外側にも余白を取る。窓枠や花箱、建物の地理形状や衝突は保持する。

暖色は3種類。カーテンの縦のひだと端の陰影をマテリアルで表し、均一な明るい四角形にしない。既存の`MPC_ParisNight.NightAmount`と連動するため、昼は追加面が消え、元のガラスが見える。夕方と夜は灯りが入り、`G`の時刻切替に追従する。点光源は追加しない。

遠景の夜景でも窓の明かりが残るよう、表示上限を1,500mとする。追加モデルは3種類・計24三角形を共有する。衝突と影は付けない。`F6`で小物を隠した際や、再現レベル・問題箇所の表示中も追加面を隠す。

## 実行と検証手順

`Paris-City-Festive.cmd`または`Paris-Luxury.cmd`で起動し、`G`で昼 → 夕方 → 夜を切り替える。`7`で地区巡回、`F8`で歩行。既存の布飾り47本・電球799個、窓辺の花2,400か所、395店舗、392本の街灯、251基の鉢も表示する。

```powershell
./unreal/scripts/Build-ParisLuxury.ps1
./unreal/scripts/Test-ParisLuxury.ps1
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -OutputPrefix paris-window-lights
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -View Sunset -OutputPrefix paris-window-lights
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -View Night -OutputPrefix paris-window-lights
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 0 -View Night -OutputPrefix paris-window-lights-overview
```

主な変更は`generate_paris_window_lights.py`、統合する`generate_paris_luxury.py`、夜の表示材を作る`bake-paris-luxury.py`、描画距離と統計を更新する`ParisLuxury.cpp`、起動・撮影・検証コード。元の窓のメッシュID・四角形番号・建物ID・座標と、架空の点灯パターンであることを保存する。保存済みの同じ入力から同じ配置を生成する。

変更前は`backups/paris-before-warm-windows-20261107-110615`へ保存。前段階のモデル・配置とカメラを保持して比較する。[追加前の同じ通りの夜](paris-garlands-night.png)。

## 実施した確認

C++ビルド、Python 9テスト、UE内の6テストが成功。点灯面の元窓ID・座標・枠との隙間・架空の点灯属性・再生成の一致を確認した。前段階の全51モデルの参照・形状ハッシュ、全配置レコード、カメラの位置を保持していることも照合した。夜のモデルは3種類を加え、全体で54種類・19,767インスタンスとなった。

最初は花箱のある窓から点灯面を選んだが、通りから見える灯りが少なかった。花箱とは独立した上階の全窓候補へ選択元を広げ、最終的に589棟・6,362か所へ配置した。点灯面の形状・材料は同じで、配置だけを更新したことも照合した。

DX12／SM6で、[昼](paris-window-lights-after.png)、[夕方](paris-window-lights-sunset.png)、[雨の夜](paris-window-lights-night.png)を同じカメラで撮影した。手前の窓枠を保ったまま灯りが入り、暗い窓も残ること、昼は元のガラスになることを目視確認した。[夜の全景](paris-window-lights-overview-night.png)も撮影。4画面とも材料のコンパイルエラーはない。[検証記録](paris-window-lights-validation.json)を保存した。

1280×720・Medium・画面倍率80%の18秒計測で、通りは昼42.8fps・夕方41.5fps・雨の夜40.1fps、雨の夜の全景は51.3fps。暫定目標の60fpsには届いていない。上空数百mでは窓明かりは小さい光点になるため、広域夜景の光だまりや景観照明には改善余地がある。

実際の室内構造や部屋の用途は再現していない。布の揺れ、実店舗ごとの内装、遠景の照明の改善と60fpsに向けた最適化は次段階。
