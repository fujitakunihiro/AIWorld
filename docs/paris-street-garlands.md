# 通りの上空にも色と灯りを追加

このページはv5段階の記録。現在の起動ファイルは、[窓明かりを追加したv6](paris-warm-windows.md)を使う。

`paris_street_garlands_v5` は、現在の約800m四方の地区に47本の布飾りと電球列を追加する。1本につき14枚の布と17個の電球があり、合計658枚・799個。窓辺の花は1,200か所・104棟から2,400か所・573棟へ増やし、以前の1,200か所はそのまま保持する。395店舗、392本の街灯、251基の花鉢、49組のカフェテーブルも残す。

## 配置

実際のOSM道路と、両側にある建物の輪郭を基準に、幅6〜15mの区間を選ぶ。橋、トンネル、川の上、主要幹線、アクセス禁止の道路は対象から除外する。両端は実在する建物輪郭に接続し、低い建物や低い別棟を持つ複合建物を避ける。取り付け金具が既存の推定窓の開口に重ならないことも確認する。

路面の最高地点を基準に、最も低い装飾でも4.8m以上の高さを確保する。既存の地面・道路の形状を保ち、装飾側の高さを設定する。装飾には衝突を付けず、鉢や既存の歩行・車両システムの動作を保持する。

布はワイン色、青、アイボリー、緑を組み合わせる。電球は既存の昼夜設定に連動する専用の暖色発光材を使う。光源の数を増やさずに光点を追加し、布だけが影を落とす。距離が離れると簡略モデルへ切り替える。51種類の共有モデルをHISMで表示する。

装飾の外観と配置は推定で、現地の催事の再現ではない。道路と両端の建物の元ID、配置座標、幅、高さ、壁の高さ、推定属性を保存する。建物・道路・川のGIS形状は変更しない。[分布図](paris-garlands-coverage.png)はGISと配置データから描く図であり、UEの画面ではない。ガーランドは24の100m区画に分布し、従来の装飾を合わせた全体では店舗・街灯のある61区画すべてをカバーする。

## 起動と再生成

`Paris-City-Festive.cmd`と`Paris-Luxury.cmd`は、布飾りと店先が同時に見える通りから起動する。`7`で地区の巡回、`G`で昼夜、`R`で雨、`F8`で歩行、`F6`で小物表示を切り替える。今回の主視点は巡回視点の3番。

```powershell
./unreal/scripts/Build-ParisLuxury.ps1
./unreal/scripts/Test-ParisLuxury.ps1
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -OutputPrefix paris-garlands
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 3 -View Night -OutputPrefix paris-garlands
./unreal/scripts/Capture-ParisLuxury.ps1 -District -Spot 0 -OutputPrefix paris-garlands-overview
```

保存済み入力だけから再生成する。変更前の作業ファイルと実行ログは`backups/paris-before-street-garlands-20261107-104325`に保存した。

主な変更ファイルは、ガーランド生成の`generate_paris_street_garlands.py`、窓辺の分散を増やす`generate_paris_facade_gardens.py`、統合する`generate_paris_luxury.py`、発光材を作る`bake-paris-luxury.py`、区間の幅に応じた表示と統計を追加する`ParisLuxury.cpp`、起動・撮影・分布図生成スクリプト、PythonとUEの検証コード。

## 実施した確認

C++ビルド成功、Python 8テスト成功、UE内の6テスト成功。Pythonでは再生成の完全一致、元IDと座標、歩行経路との離隔、元の窓への整合、区間の両端が建物輪郭に接続すること、路面からの高さ、橋・川の回避を確認した。既存の45モデルと全配置レコードが保持されていることも照合した。UEでは51モデル・13,405インスタンス、建物間の幅に合わせた表示、装飾の衝突設定、表示切替、既存の広告柱・舗装・昼夜・雨を確認した。

DX12／SM6で、[昼の通り](paris-garlands-after.png)、[雨の夜の同じ通り](paris-garlands-night.png)、[全景](paris-garlands-overview-after.png)を実際に撮影し、マテリアルのコンパイルエラーがないことを確認した。[検証記録](paris-garlands-validation.json)を保存した。

1280×720・Medium・画面倍率80%の18秒計測で、この通りは昼41.2fps、雨の夜41.1fps、全景は55.6fps。60fpsは未達。以前とは街路の視点が異なるため、前段階の数値と単純比較しない。

布飾りは静的な形状。風で揺れる布、実店舗ごとの看板・内装・外観資料による差別化、遠景の夜景、60fpsに向けた最適化は引き続き改善対象。
