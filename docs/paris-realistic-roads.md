# パリの道路・歩道の質感

`Paris-Roads.cmd`を開くと、ノートルダム北側の実在道路 `osm/way/45518911` を歩行者の目線で中品質表示する。高品質は `Paris-Roads.cmd -Quality High`。`F10`はHUD、`F8`は主人公、`M`は簡易素材、`F7`は品質、`F6`は小物の切り替え。通常のフォトリアル起動にも新素材を適用する。

## 改善内容とデータの扱い

- アスファルト：既存の検証済み2K写真を異なる向き・大きさで重ね、繰り返しを抑える。粒状の法線、広い色むら、細いひび、補修跡、粗さの差を加えた。道路輪郭に沿う汚れは元の道路三角形から作る距離マップで制御する。
- 歩道：60×40cmの推定石板、3mmの継ぎ目、写真由来の微細な石の粒。歩行者道・広場は既存の写真由来の石畳を調整する。
- 縁石：元の歩道側に収まる幅20cmの石を1,584個生成。道路と歩道の実メッシュの高さに合わせ、面取りと目地を立体にした。
- 排水：元の車道内に44個のグレーチングを推定配置。枠と格子は立体。位置・意匠・補修模様は現地測量による再現ではない。

小物はノートルダム周辺145m以内に限定し、35バッチ・35,992三角形にまとめた。衝突・クリック・主人公・車両・歩行者は元のGIS面を使用する。追加した見た目の小物には衝突判定がない。低品質、簡易素材、デバッグ表示では隠す。

道路の位置、幅、高さ、建物・川のデータは既存データを使用する。元データに含まれる推定幅や標高の制約は引き継いでいる。既存の橋の舗装形式は変更していない。

写真は既存のPoly Haven CC0素材 `asphalt_02`、`cobblestone_pavement`、`white_plaster_02` を使う。これらはパリ現地で採取した舗装のスキャンではない。新しい距離・劣化マップと縁石・排水格子はオリジナル生成。新しい外部素材のダウンロードはない。取得元・著作者・ハッシュは `unreal/textures/paris-photo/manifest.json`、生成条件・推定属性は `Content/Data/paris-road-detail.json` に記録する。

## 再生成と比較

UEを閉じて実行する。元のGISスナップショットとPython仮想環境が必要。

```powershell
.\unreal\scripts\Build-ParisRoads.ps1
.\unreal\scripts\Build-AIWorldUE.ps1 -SkipAssets
.\unreal\scripts\Start-ParisDigitalTwin.ps1 -RoadView -Quality High
```

`generate_paris_roads.py`で元のメッシュから見た目の追加物・PNGを作り、`bake-paris-roads.py`でUEアセットにする。原点・UEのcm単位を共有し、追加の座標変換をしない。元の道路・歩道メッシュを押し出したり動かしたりしない。

旧表示は `Start-ParisDigitalTwin.ps1 -RoadView -LegacyRoads -Quality High`。素材・小物を戻しても比較カメラは共通。

```powershell
.\gis\.venv\Scripts\python.exe -m unittest discover -s unreal/scripts/tests -p test_paris_roads.py -v
.\unreal\scripts\Test-ParisDigitalTwin.ps1 -Photoreal
.\unreal\scripts\Measure-ParisDigitalTwin.ps1 -View PhotoStreet -RoadView -Photoreal -Quality High -CleanFrame -Duration 10 -CaptureAfter 8 -ReportPath docs/paris-roads-high-performance.json -ScreenshotPath docs/screenshots/paris-roads-realistic.png
```

## 実機での確認

UE 5.8.3 / D3D12 / SM6 / AMD Radeon(TM) Graphics、出力1280×720。各10秒、素材・シェーダーの準備完了後、同じカメラで測定した。Highの内部解像度は100%、Mediumは80%。

| 表示 | 平均fps | フレーム時間P95 |
| --- | ---: | ---: |
| 旧素材・小物なし / High | 25.79 | 42.02ms |
| 新素材・縁石・排水 / High | 25.50 | 44.16ms |
| 新素材・縁石・排水 / Medium | 29.27 | 38.72ms |

当該視点では60fps目標に届いていない。変更前も約26fpsであり、今回の追加だけが低fpsの原因とは言えない。短い測定のため、小さいfps差から厳密な負荷増を断定しない。

[旧表示](screenshots/paris-roads-before.png)、[新表示High](screenshots/paris-roads-realistic.png)、[新表示Medium](screenshots/paris-roads-medium.png)は実際のUE GPU描画。画像生成ではない。計測値と実行条件は `paris-roads-before-performance.json`、`paris-roads-high-performance.json`、`paris-roads-medium-performance.json`。

ネイティブビルドは成功。Python検証4件は、道路内の排水配置、元の高さとの一致、追加メッシュの範囲・法線・追跡ハッシュ、170cmカメラと元地物IDを確認した。

UEの回帰テストは24/24成功。新しい `RoadFinishAndCollision` は、高品質・低品質・簡易表示・小物表示・デバッグの切り替え、道路頂点の維持、小物が元の当たり判定や地物選択を置き換えないことを確認した。既存の主人公・歩行者・車両・座標・建物・川を含むシーンのテストも通った。ログは `unreal/AIWorld/Saved/paris-roads-regression.log`。

元のGIS JSONのSHA-256は `4e51a9332f3bc44aea0820ee4fcc77d339083fff9c2f73d59a66e1737f5353bb`、元のメッシュバイナリは `fba61d4426bf6cc2fc40bda2818d48fe4a6d8e3c58bf13e025254ddc20bc97d8` のまま。

パッケージ製品のcook・実行は今回の検証対象に含めていない。動的に読み込む道路メッシュのcook対象は `DefaultGame.ini` に追加している。

主な変更は `ParisRoadDetail.cpp` / `ParisSurfaceMaterials.cpp` の描画、`ParisPhotoEnvironment.cpp` の比較カメラ、`generate_paris_roads.py` / `bake-paris-roads.py` の生成、`ParisRoadTests.cpp` / `test_paris_roads.py` の検証、`Start-ParisDigitalTwin.ps1` / `Measure-ParisDigitalTwin.ps1` の起動・測定。起動時の既存GISパケット検査は必要な小さい属性だけをPythonで抽出し、Windows PowerShell 5.1で大量の頂点数値を展開する待ち時間を避ける。
