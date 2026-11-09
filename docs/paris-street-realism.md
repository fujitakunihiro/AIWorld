# 窓の奥行き・人物表示・夕景の連続性

最新の追加装飾は[派手モード v8](paris-party.md)を参照。以下はv7時点の検証記録。

`paris_street_realism_v7` は、装飾を増やす代わりに、街路から見える形状と表示の切替を改善する。GISの建物・道路・河川と既存の装飾、窓明かりは保持する。

中心部以外の15,530か所の上階窓へ、石の見切り、奥行きのある窓枠・桟・窓台、視線に応じて室内の見え方が変わるガラスを追加する。元の窓面と建物ID・四角形番号・幅・高さを利用し、既存の詳細窓がある中心部と、入口に重なる既存候補は除外する。塗装は建物ごとにセージ、ワイン、アイボリーで統一する。窓枠と室内の外観は推定であり、現地調査による詳細再現ではない。

全窓を個別の固有メッシュにせず、5種類のモデルをHISMで共有する。石材には既存の写真ベースのPBR材を使い、木部とガラスには既存の詳細窓用の材を再利用する。ガラスの共有材から一律の点灯を除き、既存の6,362か所の推定窓明かりと重複させない。昼は元の反射と奥行き、夜は窓枠の内側に暖かい灯りを表示する。追加窓には衝突を付けない。Mediumで110m、Highで160mまで表示し、Lowと表面簡略表示では追加の窓枠を隠す。

人物は既存の2種類のスケルトン付きアセットを使う。Mediumの詳細表示距離を22mから60m、Highを35mから90mへ変更する。人数上限はMedium 8人・High 16人を保ち、カメラの前方と近い人物を優先する。判定を平面距離から立体距離へ変え、上空視点で地上の人物を不要に詳細表示しない。移動経路や訪問行動、選択用カプセルは保持する。人物の種類の少なさと遠方の簡略形状は今後の課題。

夕方だけ雲の写真レイヤーを隠していた処理を修正し、保存済みHDR環境から夕景用の材を作る。上空に青み、地平線に暖色を残す。色温度と強いオレンジ色の光色を重ねる設定も改める。雨・夜・昼への切替時は対応する既存の空へ戻す。これは見た目の調整であり、パリの実際の夕空や気象の測定ではない。

## 実行と再生成

`Paris-City-Festive.cmd`または`Paris-Luxury.cmd`で起動する。`G`で昼・夕方・夜、`7`で地区巡回、`F7`で画質、`F8`で歩行、`M`で表面表示を切り替える。

```powershell
./unreal/scripts/Build-ParisLuxury.ps1
./unreal/scripts/Test-ParisLuxury.ps1
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -OutputPrefix paris-realism
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -View Sunset -OutputPrefix paris-realism
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -View Night -OutputPrefix paris-realism
```

主な変更ファイルは`generate_paris_window_relief.py`、`generate_paris_luxury.py`、`bake-paris-realism.py`、`bake-paris-luxury.py`、`ParisLuxury.cpp`、`ParisPedestrians.cpp`、`ParisPedestrians.h`、`ParisDigitalTwin.cpp`、検証コードと起動・撮影スクリプト。変更前の作業ファイルは`backups/paris-before-realism-20261107-114005`へ保存する。

## 実施した確認

C++ビルド成功、Python 10テスト成功、UE内の8テスト成功。再生成の一致、既存モデルと配置の保持、元の窓面・幅・高さへの整合、中心部との二重表示回避、衝突・表示切替を確認した。UEでは人物のスキニング・歩行・着座、人数上限、上空での詳細人物表示の抑制、夕方・雨・夜・昼の空の復帰も確認した。全体で59種類の共有モデル・66,357インスタンス。

DX12／SM6で、[昼](paris-realism-after.png)、[夕方](paris-realism-sunset.png)、[雨の夜](paris-realism-night.png)を以前と同じ通り・カメラで撮影した。窓枠・桟・窓台の厚みと影、窓の奥行き、人物の詳細表示を目視確認。夕方は赤黒い空ではなく、青みと暖色を残した空になった。[全景](paris-realism-overview-after.png)も確認した。4画面とも材料のコンパイルエラーはない。[検証記録](paris-realism-validation.json)を保存した。

1280×720・Medium・画面倍率80%の18秒計測では、通りは昼41.6fps・夕方38.1fps・雨の夜39.5fps、昼の全景は54.6fps。通りのスケルトン人物は以前の1人から5人となり、上限8人は保持する。全景のスケルトン人物は0人。60fpsは未達で、これ以上の詳細化には描画負荷の削減も必要となる。

建物の輪郭・ボリュームと、現地資料に基づく外観の再現精度は分けて扱う。今回の追加を測量済みの窓や実際の室内として扱わない。次の改善対象は実店舗ごとの資料と内装、建物ごとの形状差、遠景の人物、描画負荷の削減。
