# Paris Digital Twin GIS pipeline

Python 3.12で動作する実データ取得・正規化・検証・UEプレビュー出力です。住民AIやSQLiteを変更しません。取得と生成を分離し、`Data/Raw` の固定スナップショットだけで再生成できます。

最新は[店舗・カフェと軽量読み込み](../docs/paris-digital-twin-phase7-cafes.md)です。395か所の推定店先、登録を元にした49か所の推定テラスを追加し、UE既定読み込みをメタデータ＋バイナリへ分離しました。40台の推定車両と地図上の自転車置き場・ごみ箱・信号柱を追加。NGF原点35.38mと既存の建物・装飾・街路設備を保持し、現実スケールの一人称/三人称散策とGIS由来の経路を歩く160人のシミュレーションを追加しました。人数・人物・外観は推定であり、建物全体の再現レベルはL1を維持します。

```powershell
py -3.12 -m venv gis/.venv
.\gis\.venv\Scripts\python.exe -m pip install -r gis/requirements.lock
$env:PYTHONPATH=Join-Path (Get-Location) 'gis'
.\gis\.venv\Scripts\python.exe -m paris_twin all --offline
.\gis\.venv\Scripts\python.exe -m unittest discover -s gis/tests -v
```

取得済みデータを同梱しています。オンラインで更新する場合だけ `download --refresh` を実行します。API応答を合成して補いません。取得は一時ディレクトリで完了させてから置き換えるため、途中のAPI失敗で旧キャッシュを上書きしません。キャッシュのSHA-256・取得範囲・標高点数を検証します。建物高さや道路幅の生成ポリシーは取得設定から独立し、再取得せず変更できます。

```powershell
.\gis\.venv\Scripts\python.exe -m paris_twin download --refresh
.\gis\.venv\Scripts\python.exe -m paris_twin generate --offline
.\gis\.venv\Scripts\python.exe -m paris_twin validate --offline
# 標高はNGF-IGN69の正標高。WGS84の楕円体高への変換は行いません。
.\gis\.venv\Scripts\python.exe -m paris_twin coordinates --wgs84 2.3471 48.8547 35 --origin-elevation 30
.\gis\.venv\Scripts\python.exe -m paris_twin coordinates --ue-cm 0 0 500 --origin-elevation 30
# 取得済み地形の原点を使う場合は --origin-elevation を省略
.\gis\.venv\Scripts\python.exe -m paris_twin coordinates --wgs84 2.3471 48.8547 35.38
# 地形だけを取得・更新（保存済みデータで生成するときは実行不要）
.\gis\.venv\Scripts\python.exe -m paris_twin download-terrain --refresh
```

## 構成

- `config/ile_de_la_cite.json`: 500mの検証地区＋各辺150mの文脈範囲、100mの品質確認範囲、共通基準点、推定ルール。
- `paris_twin/acquire.py`: OSM、Paris Data、IGNの取得。OSM公式APIの元XMLはgzip保存し、復元時のバイト列を保持。
- `coordinates.py`: WGS84 / EPSG:2154 / UE cmの相互変換。常にlon,lat順、UEは東=X、南=Y、上=Z。
- `normalize.py`: 不正形状の修復、河川の穴と複合輪郭、元ID、Paris建物階数との対応、未検証・推定の属性。
- `mesh.py`: 実輪郭の柱状メッシュ、道路幅の解釈、道路面の結合と建物による切り抜き、中庭を保持した三角形分割、SVG/HTML地図。
- `validate.py`: 変換、形状、重複、高さ、OSMの共有ノードによる接続、橋と川、出典、生成メッシュの検証。
- `Data/Raw/<district>`: 取得結果、URL・ライセンス・日時・SHA-256のmanifest。Gitに保存。
- `Data/Processed/<district>`: EPSG:2154の中間JSON、WGS84のGeoJSON。ローカルに保存し再生成可能。
- `Data/Generated/<district>`: UE用JSON、検証レポート、`map.html` / `map.svg`。ローカルに保存し再生成可能。

UE向けファイルは `unreal/AIWorld/Content/Data/paris-digital-twin.json` にも出力します。座標は既にcmなので、既存ボクセルの軸変換・100倍変換を適用しません。Cesiumは使っていません。

Phase 2で `diagnostics.py`、`Data/Generated/<district>/diagnostics.json`、クリック選択用source情報、輪郭メッシュ、対話式HTML地図を追加しました。地図の品質項目を選択すると関連する元IDを強調します。詳細は [Phase 2報告書](../docs/paris-digital-twin-phase2.md)。

`origin_wgs84` は全地区の共通原点、`district_center_wgs84` は個別地区の取得・表示範囲の中心です。`gis/config/saint_michel_west.json` は共通原点を保持した拡張例です。西側のRawは未取得なので、その設定を使う前に `download --config gis/config/saint_michel_west.json` が必要です。`generate` / `validate` にも同じ `--config` を渡してください。CLI座標変換は地区が変わっても同じ原点を使用します。

建物全体はL1です。OSM heightタグも測量済みとはみなさず `source_declared_unverified` とします。Parisの `h_et_max` は階数であり、メートルではありません。階数×階高や地区の既定高さは `estimated` として区別します。Phase 3で公的な軒高のある棟は複数高さに分割しますが、推定屋根・教会の尖塔を実測した外観として扱いません。

Phase 3でIGN BD TOPOの追加高さキャッシュを同梱しました。`download-buildings` で取得し、`heights/` の867記録を `building_heights.py` で既存輪郭へ対応付け、`building_mesh.py` で高さ別の壁と推定屋根を生成します。生成はAPIを呼びません。建物全体はL1、本体の条件を満たす部分は `reproduction_level_body=L2`、屋根は推定L1です。詳しい値・手順・制限は [Phase 3報告書](../docs/paris-digital-twin-phase3.md)。

Phase 4の `elevation_source.py` は `terrain/` に1,681点と共通原点の標高、要求内容、URL、ライセンス、チェックサムを保存します。元の121点スナップショットは変更しません。`terrain.py` は正標高を補間、`bridges.py` はOSM橋の道路・並行歩道を同じ推定桁高へ合わせます。点間隔20mはDEMの原解像度・精度ではありません。川の水位は橋を除いたDEM点の中央値からの推定で、量水標の観測値ではありません。

Phase 5の `facades.py` は元の建物IDを保持して壁を100mごとにまとめ、推定窓・窓枠・桟・張り出し窓台を生成します。装飾は300mを超える距離で省略します。教会・特異な記念建築の外観は専用資料が必要なので、この窓生成から除外します。隣接地区は原点を変更せず `download` と `download-terrain` の両方で取得範囲を準備してください。

Phase 5続きでは隣接建物で塞がれる壁の窓を省略し、推定入口・バルコニー・コーニス・屋根窓を追加しました。元ID・輪郭・高さ・L1/L2の区別は維持します。薄い鉄柵は両面の面形状を用いた描画用代理モデルです。

Phase 6の `street_furniture.py` は、既存の `osm-map.xml.gz` から街路設備ノードを読み取ります。Overpassを使う新規取得では `osm.json` のノードを使用します。新しい取得は不要です。点を黙って移動せず、建物との干渉・河川上の橋なし・壁付け灯などを `Generated/street-placement.json` に理由付きで保存します。UEでは11種の自作StaticMeshをHISMで使い回し、クリックしたインスタンスから元ノード・座標・推定寸法を確認できます。F6で設備表示、F7で低・中・高の描画距離を切り替えます。`Start-ParisDigitalTwin.ps1 -Quality Low` でも設定できます。

再計測は `Measure-ParisDigitalTwin.ps1 -View Overview` または `-View Street`。事前に生成とビルドを済ませてください。隠した補助プロセスでDX11のオフスクリーン描画を測定し、JSONと画像をdocsへ保存します。ウィンドウ表示時の計測とは条件が異なるため、以前のFPSとの厳密な比較には使いません。

`pedestrians.py` は実在道路・歩行面から安全な経路を切り出し、建物・水面・設備を避けた `Generated/pedestrian-network.json` を生成します。経路の分割点だけでなく補間した線分全体を検査します。経路IDは元道路・元の分割線・左右歩道・切り抜き後の区間を区別し、重複を検出。人物と初期状態は同じ入力から再生成する推定値です。UEではPで表示、F8で散策、Vで一人称/三人称に切替。歩行用の重力・衝突はUE標準Character Movementを使用します。

散策の計測は `Measure-ParisDigitalTwin.ps1 -View WalkFirst` / `-View WalkThird`。要求した散策モードに入らなかった場合は測定失敗として扱います。

出力の再現性は固定した入力、設定、依存ライブラリに対して確認します。元データの測量精度は、変換の往復誤差と別です。LOD・Nanite用のStaticMesh化、World Partition・HLOD、現地写真に合う外観は後続Phaseで実装します。

## 固定依存関係

| ライブラリ | バージョン | 用途 | ライセンス / 取得元 |
| --- | --- | --- | --- |
| NumPy | 2.2.6 | Shapelyの配列基盤 | BSD-3-Clause / https://pypi.org/project/numpy/2.2.6/ |
| Shapely | 2.1.2 | 形状修復・バッファ・三角形分割 | BSD-3-Clause / https://pypi.org/project/shapely/2.1.2/ |
| pyproj | 3.7.2 | PROJ座標変換 | MIT / https://pypi.org/project/pyproj/3.7.2/ |
| certifi | 2025.10.5 | pyprojの依存 | MPL-2.0 / https://pypi.org/project/certifi/2025.10.5/ |

osmnx・GeoPandas・rasterio・trimeshは今回は導入していません。取得と小地区のベクトル処理を最小の構成で実装しました。DEMラスタと広域GISを扱うPhaseで追加・固定します。

`traffic.py` は元道路から方向・通行制限を解釈し、車体全体が道路内に収まる独立経路を生成します。`Generated/traffic-network.json` の安全領域と元道路IDを自動検証し、車両・交通量・駐輪の占有状態が推定であることを記録します。人物と車両のシミュレーション数は描画予算から独立しています。

`businesses.py` は元の店舗POIを保持し、歩行空間に向く外壁と屋外席だけを補完します。`runtime.py` は完全な `scene.json` を監査用に残し、`runtime.json` / `runtime-meshes.bin` を決定的に生成します。CRC32、バイト範囲、インデックス、色、頂点座標誤差を検証し、既定のUE読み込みで数百万個のJSON数値の展開を避けます。旧方式は `Start-ParisDigitalTwin.ps1 -LegacyJSON` で比較できます。
