# 地区全体へ広げた花と灯り

このページはv4段階の記録。現在の起動ファイルは、[ガーランドと窓辺を追加したv5](paris-street-garlands.md)を使う。

`paris_district_festival_v4` は、現在生成済みのパリ約800m四方を対象に、395店舗すべてのひさし、1,200か所・104棟の窓辺、392本の街灯、150か所の壁の布飾りと灯りへ装飾を広げる。足元の花鉢は251基、そのうち11基は店舗から離れた既存ベンチのそば。既存の49組のカフェテーブルも維持する。店舗の吊り花籠は692個、店舗の電球は4,740個、街灯の装飾電球は1,176個。

店舗・街灯が存在する100m区画は61区画あり、そのすべてに装飾がある。装飾の配置は東西約797m、南北約799mに広がる。[分布図](paris-district-coverage.png)は保存済みGIS座標から描いた検証用の図で、UEの画面ではない。パリ全市への拡張ではなく、現在ロードされる地区全域が対象。

## 起動と操作

`Paris-City-Festive.cmd` または `Paris-Luxury.cmd` で地区南西の花のある街角から起動する。`7`キーで保存した視点を順送りする。視点の並びは全景 → 北西 → 北東 → 南西 → 南東 → 河岸 → 全景。地上の四方向の視点は実行用歩道面から1.7m。`F8`で歩行、`G`で時刻変更、`R`で雨、`F6`で街路小物の表示を切り替える。地下鉄の既存の`K`・`L`操作も保持する。

```powershell
./unreal/scripts/Start-ParisDigitalTwin.ps1 -DistrictView -Quality Medium
./unreal/scripts/Start-ParisDigitalTwin.ps1 -DistrictView -DistrictSpot 2 -Night
```

以前の寄ったカフェ視点は`Capture-ParisLuxury.ps1 -Close`、上階を見上げる視点は`Start-ParisDigitalTwin.ps1 -LuxuryView`で利用できる。

## 配置と描画

建物・道路・河川の位置と形状は変更しない。花・布・装飾灯の外観と配置は推定であり、現地に実在する飾りや催事の再現ではない。店舗・街灯・ベンチの元データID、建物ID、窓の元メッシュと四角形番号、座標、推定属性を保存する。窓の元面そのものも既存の推定外観であり、実測された開口部ではない。教会や大聖堂などは窓辺装飾の対象から除外する。

100m区画ごとの候補を順に選び、中央だけへ集中しないようにする。街灯の花籠は元の街灯の位置を基準に8方向を検討し、道路・川・橋と重ならず、歩行面から205cm以上の高さを確保できる向きだけを使う。花鉢は建物、川、店舗の入口、既存歩行経路、街路設備、ほかの鉢を避ける。安全な配置ができない候補は理由とともに除外する。

45種類のモデルをHISMで共有する。Mediumでは店舗のひさし180m、窓辺70m、その他90mまで細かい形状を表示し、それより遠くは小さな色面と電球面のモデルへ切り替える。遠景モデルの描画上限は1,500m。画質変更時は切替距離も連動する。電球の色面だけが夜設定に応じて発光する。遠景モデルには衝突と影を付けず、新しい点光源も追加しない。

## 再生成・検証

変更前の作業ファイルは`backups/paris-before-district-festival-20261107-095644`へ保存した。

```powershell
./unreal/scripts/Build-ParisLuxury.ps1
./unreal/scripts/Test-ParisLuxury.ps1
./unreal/scripts/Capture-ParisLuxury.ps1 -District -OutputPrefix paris-district
./unreal/scripts/Capture-ParisLuxury.ps1 -District -View Night -OutputPrefix paris-district
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 1 -OutputPrefix paris-district-northwest
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -OutputPrefix paris-district-southwest
```

データ生成はGIS仮想環境の固定済み依存関係を使い、保存済み入力だけで実行できる。任意の分布図生成`generate_paris_district_map.py`だけはPillowを使う。今回の図はPillow 13.0.0で生成した。実行時の依存関係には含めない。

中心となる変更ファイルは`generate_paris_luxury.py`、`generate_paris_facade_gardens.py`、`paris_district_layout.py`、`generate_paris_district_decor.py`、`bake-paris-luxury.py`、`ParisLuxury.cpp`、入力操作を追加した`ParisDigitalTwin.cpp`、起動・撮影スクリプト、Python・UEの検証コード。

## 実施した確認と現在の限界

C++ビルド成功、Python 7テスト成功、UE内の6テスト成功。Pythonでは同じ入力からの完全一致、元ID・座標の追跡、鉢と歩行経路・建物との離隔、花籠の高さ、元の窓面への整合、地区全体への分布、巡回視点の歩道からの高さを確認した。UEでは全45モデルの読み込み、9,618インスタンス、花鉢の衝突、F6非表示時の衝突解除、巡回カメラ、既存の広告柱・舗装・昼夜・雨・素材を確認した。最後の巡回視点の変更時は、モデルの全ハッシュと配置レコードが同一で、カメラだけが変わったことも照合した。

DX12／SM6で5画面を実際に描画し、マテリアルのコンパイルエラーがないことを確認した。[検証記録](paris-district-validation.json)、[南西の通り](paris-district-southwest-after.png)、[北西の通り](paris-district-northwest-after.png)、[北西の夜](paris-district-northwest-night.png)、[全景](paris-district-after.png)、[夜の全景](paris-district-night.png)を保存した。

1280×720・Medium・画面倍率80%の18秒計測で、全景は昼53.0／雨の夜48.7fps、北西の通りは昼44.7／雨の夜42.4fps、南西の通りは昼43.9fps。60fpsは未達。視点が違う以前の性能値との直接比較はしない。

装飾は現地資料に基づく詳細再現ではない。数百m上空の全景では小さな装飾の灯りが目立ちにくく、遠景の夜間表現も今後の改善対象とする。

次の改善候補は、実店舗ごとの外観資料を使った差別化と、統合GPUで60fpsを目指す描画負荷の削減。装飾の数だけでフォトリアル完成とはしない。
