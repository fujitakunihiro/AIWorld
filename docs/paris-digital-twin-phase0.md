# Paris Digital Twin — Phase 0 調査

調査日: 2026-10-14。変更前はGitコミット`6e2d297`、ローカルのbackupタグ`backup/pre-paris-digital-twin-20261014`で保持。未追跡のUE入力設定は`backups/paris-digital-twin-20261014/DefaultInput.ini`へコピー。作業ブランチは`codex/paris-digital-twin`。

## 既存構成

| 項目 | 実際に確認した状態 |
| --- | --- |
| UE | D:\Epic Games\UE_5.8 / Build.version: 5.8.3, CL 58210709 |
| C++ | Runtime module AIWorld。C++ GameMode、カメラ、住民、Slate UI、HTTP/WebSocket、ProceduralMeshComponent、HISM |
| Blueprint | ゲームロジックのBlueprintはなし。Python生成のMain.umapとマテリアル・テクスチャのuasset |
| 都市生成 | shared/world.tsが384×384×32のブロック配列・固定ランドマーク・格子街区を生成。SQLite差分を上書き |
| 道路・河川・建物 | メートル地理座標の独立地物ではなくブロック座標・Edit配列・村のHut/Bridge。実地理との対応なし |
| モデル | tools/export-unreal.tsがWebの独自モデルをmodels.jsonへ出力。既存の3種のPNG素材をUEへ取り込み |
| PCG | UE 5.8のEnabledByDefault=trueで有効。実際のMountingログも確認。プロジェクトのPCG Graph・PCGによる生成処理はなし |
| World Partition / HLOD | Main.umapをロードした実行時にworld_partition=0を確認。World Partitionの設定やHLOD生成処理なし |
| Cesium | プロジェクトに導入なし。GeoReferencingプラグインはUEに存在するが未使用 |
| Python | システム3.14.6と3.12.4。GISは3.12.4のvenvを新設し、依存を固定。UEエディタ内Pythonは3.11.8、既存アセット作成用 |
| ビルド | Build-AIWorldUE.ps1: Node/tsxモデル出力 → MSVC/UBT → UE Pythonアセット生成。日本語パスをASCII junctionで参照 |
| 起動 | AIWorld-Unreal.cmd → Start-AIWorldUE.ps1。Dockerの既存save volumeを共有、ホストlocalhost:3001でAPI公開 |
| GPU | AMD Radeon(TM) Graphics（Ryzen 7 7735HSの統合GPU）、ドライバ32.0.21045.5002。WMIのAdapterRAM報告値3.0GBは専用VRAM容量を保証しない |
| RAM | 実機28.8GB、調査時の空き4.7GB。メモリ圧迫があり、ビルドの並列数は1 |
| 既存性能 | 保存済みレポート: 1440×900、中品質54.8fps/P95 25.4ms、村の低品質95.8fps。今回の新地区の実測と混同しない |

## 採用方針

GISをPythonで取得・正規化し、版と出典のあるデータ契約をUEへ渡す。新地区の建物配置に旧格子モデル・ボクセル変換を使用しない。GISモードのC++ Scene/Camera/HUDと旧村モードは別に起動できる。旧住民AI、SQLite、Web版、セーブversion 9は維持し、GISモードから保存へ書き込まない。

世界基準はWGS84、地区投影はEPSG:2154。原点のLambert-93座標を倍精度で保持し、差分だけをcmへ変換。UEのX=東、Y=南、Z=上。Cesium変換は無効。IGNの正標高とWGS84楕円体高は混同しない。公開ソースの精度はミリメートル級ではないため、往復誤差が小さくても測量精度とは呼ばない。[IGNの2026年のRGF93/EPSGに関する説明](https://geodesie.ign.fr/actualites/evolution-venir-des-codes-epsg-du-rgf93)

## UE機能と予算

| 機能 | 今回の扱い / 次段階 |
| --- | --- |
| Nanite | 今回はProceduralMeshの形状検証。Naniteを使用したとは扱わない。後続でStaticMeshへ焼き、DX12/SM6で別途検証 |
| Lumen / VSM | 現在のDX11互換設定を継続。メモリ圧迫と統合GPUを考慮して全面的に有効化しない |
| PBR | 実在するM_Stone/M_Water等を再利用。法線・ORM・詳細ファサードが足りず、写真品質とは呼ばない |
| PCG | 位置不明の小物の補完用途を次段階で検討。初期の輪郭・道路には使わない |
| World Partition / HLOD | 地区のProjected CRS/origin/source IDをデータ契約に保存。今回の800m文脈範囲は単一Scene。地区接続・タイル焼き・HLODはPhase 7 |

NaniteのDX12/SM6要件と、Lumenの性能・対応要件は[UE 5.8公式仕様](https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine)で調査。[World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine)と[PCGとの連携](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-with-world-partition-in-unreal-engine?lang=en-US)も参照。

暫定の実機検証条件は1280×720、DX11、通常の影、目標60fps。初期地区の三角形予算20万以下、将来の描画バッチ目安200以下。今回のfeatureごとの選択用メッシュはバッチ数が多く、性能結果を見てタイル統合を判断する。高品質モードの予算はDX12で実測するまで未確定。

## 不足アセット

| 対象 | 必要な資料・推奨仕様 |
| --- | --- |
| ノートルダム、サント・シャペル、サン・ミシェルの噴水 | 利用権を確認した現地写真・測量/フォトグラメトリ。cm単位、実スケール、原点と方位の整合、L4/L5の根拠を棟別に記録 |
| 石灰岩・亜鉛板・スレート | 2K〜4KのBaseColor/Normal/ORM、実寸のタイル幅、光の焼き込みがない素材 |
| ファサード | 窓・入口・雨樋・コーニス・バルコニーを実寸モジュール化。見える面への重複貼り付けを避け、棟別の資料がない場合はL3補完属性 |
| 橋・石造護岸 | 実位置に加え桁下・アーチ・橋脚・河岸断面の資料。GISの中心線から詳細形状を断定しない |
| 地形 | 1m級DEMまたはLiDAR HDの地区切り出し、NGF-IGN69統一。今回の80m標高点は品質地形の代替にしない |

これらの詳細モデルは現在ありません。外部の有料サービスや未導入アセットを必要な依存として参照していません。
