# Paris Digital Twin GIS pipeline

Python 3.12で動作する実データ取得・正規化・検証・UEプレビュー出力です。住民AIやSQLiteを変更しません。取得と生成を分離し、`Data/Raw` の固定スナップショットだけで再生成できます。

最新は[Phase 4・5基盤](../docs/paris-digital-twin-phase45.md)です。20m間隔のIGN標高を地形・道路・建物へ反映し、NGF原点35.38mを共通使用します。窓・窓枠は推定、建物全体の再現レベルはL1を維持します。

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

出力の再現性は固定した入力、設定、依存ライブラリに対して確認します。元データの測量精度は、変換の往復誤差と別です。LOD・Nanite用のStaticMesh化、World Partition・HLOD、現地写真に合う外観は後続Phaseで実装します。

## 固定依存関係

| ライブラリ | バージョン | 用途 | ライセンス / 取得元 |
| --- | --- | --- | --- |
| NumPy | 2.2.6 | Shapelyの配列基盤 | BSD-3-Clause / https://pypi.org/project/numpy/2.2.6/ |
| Shapely | 2.1.2 | 形状修復・バッファ・三角形分割 | BSD-3-Clause / https://pypi.org/project/shapely/2.1.2/ |
| pyproj | 3.7.2 | PROJ座標変換 | MIT / https://pypi.org/project/pyproj/3.7.2/ |
| certifi | 2025.10.5 | pyprojの依存 | MPL-2.0 / https://pypi.org/project/certifi/2025.10.5/ |

osmnx・GeoPandas・rasterio・trimeshは今回は導入していません。取得と小地区のベクトル処理を最小の構成で実装しました。DEMラスタと広域GISを扱うPhaseで追加・固定します。
