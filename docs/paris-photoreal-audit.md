# フォトリアル表現 — UE5機能と不足アセットの調査

追記：[街路の写実表現](paris-street-realism.md)で、実写由来2Kの外観用代理素材2組とHDR環境を導入しました。以下の未取得の現地資料・高詳細モデルとは区別し、地理的精度の評価は維持します。JSON監査には現在の同梱状態を反映しています。

2026-10-15。UE 5.8.3の実ファイル、現在のC++と設定、プラグインのロードログ、実GPUの機能照会を確認しました。[機械可読の監査結果](paris-rendering-audit.json) / [GPU照会](paris-gpu-capabilities.json)。

現在の表現は、独自の512px素材5組と推定した窓・屋根・装飾です。現地写真や測量に対応した外装アセットは未導入です。地理の再現レベルと外観の根拠を分け、素材や描画方式の変更で建物の再現レベルを引き上げていません。

## 利用可能な機能と現在の状態

| 機能 | 現在の状態 | 導入に必要な作業 |
| --- | --- | --- |
| Nanite | 未使用。実画面はDX11。今回の静的描画キャッシュも通常メッシュ | DX12/SM6、対応する保存Static MeshのNaniteビルド、可視化と実測。[公式仕様](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine) |
| Lumen | 未使用。GI Method=0、Reflections=2、Mesh Distance Fields無効 | ソフトウェア方式では壁・屋根などの保存メッシュ、距離フィールドとCardsを構築し、Surface Cacheの欠損・光漏れを検査。ランタイムのFastBuildだけでは準備が揃わない。[公式技術資料](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine) |
| Virtual Shadow Maps | 未使用。`r.Shadow.Virtual.Enable=0` | DX12/SM6とGPU要件、対応する形状・影のキャッシュを検証。表示距離とページ数の予算を実測。[公式資料](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine) |
| PBR Materials | 使用中。石灰岩・亜鉛・スレート・敷石・アスファルト | 現在の独自生成512pxを現地資料に対応する素材へ順次更新。既存アセットは実在し、UEの読み込み・色空間・切替テスト済み |
| PCG Framework | インストール・実行時ロードを確認。GIS配置でのGraph利用は未実装 | 地図上の登録位置を優先し、不足する小物の補完にGraphを使用。推定配置の属性を保持。[公式概要](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview) |
| World Partition | 現在のシーンは無効。ロードログの `world_partition=0` を確認 | 一括ランタイム生成から、保存された地区Actorとセルごとの表示へ移行。[公式資料](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine) |
| HLOD | 未使用。今回のキャッシュは同じ形状のコピー | World PartitionのHLOD Layer・Actorを作り、ビルダーで生成・検査。メッシュ統合と簡略化を選択。[公式資料](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine) |

設定のScalabilityログにLumenやNaniteの項目が現れても、実際に使っている証拠にはしません。現在の起動スクリプトは `-dx11` で、LumenのGIとVSMも設定で無効です。PCGはUE 5.8の標準有効プラグインとしてマウントされていますが、現在の配置はPython GISとHISMで処理しています。

## このPCでの確認

AMD Radeon(TM) Graphics、ドライバー32.0.21045.5002。D3D12デバイス作成、SM6.8照会、Wave Ops、64bit Shader演算、Typed ResourceとGroup Sharedの64bit Atomicが成功しました。Raytracing Tier 1.1とUMAも返っています。SM6.8は今回照会した上限で、GPUの絶対的な最大値という意味ではありません。

Nanite/VSMはDX12のSM6.6 Atomicなどを要求します。このGPUは照会した機能に対応していますが、UEでの有効化・アセット構築・動作速度の確認は別途必要です。現在のDX11のfpsをDX12/Lumenの性能として使いません。[UEの機能要件](https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine)。

次の検証は、100m重点範囲の保存メッシュを作り、ソフトウェアLumenを小さな範囲から試します。壁厚と閉じた形状、Cardsと距離フィールド、影の欠損を可視化してから地区を広げます。Lumenの資料では薄い面や大きな一体メッシュの問題が説明されているため、壁・床・屋根を分けた構成を採用します。[Lumenの制約](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine)。

## 不足するアセットと暫定の推奨仕様

以下はこのプロジェクト向けの受入仕様案です。**7組すべて未導入**で、ゲームから存在しないアセットを参照していません。[状態と仕様のJSON](../unreal/assets/paris-photoreal-assets.json)では `status=missing`、`ue_asset=null` としています。

| 優先 | アセット | 推奨仕様 |
| --- | --- | --- |
| 1 | 現地資料に対応する石灰岩 | 通常2K・重点4K、照明を焼き込まないBase Color、DirectX Normal、AO/Roughness/Metallic。物理タイル寸法と摩耗の違う複数種 |
| 1 | 亜鉛板・スレート屋根 | 素材別の2K・重点4Kセット、継ぎ目・瓦の寸法、金属と表面の酸化・汚れを区別する値。実寸は資料、未測定なら推定と記録 |
| 1 | 地区に合う外壁モジュール | 壁・窓・コーニス・バルコニー・屋根窓。cm単位、UV0、位置合わせのピボット、LOD、別の衝突形状。Lumen用の壁は閉じた殻と厚みを確保 |
| 1 | ノートルダムの外装 | 西正面・塔・控壁・屋根の根拠資料、分割Static Mesh、詳細モデルと代替LOD、別の衝突。元の建物ID・基準点を維持 |
| 2 | サント・シャペルの外装 | 建物・屋根・尖塔を資料と照合し、石とガラスを分離。cm・UV・LOD・衝突を揃える |
| 2 | 護岸・橋の石造モジュール | 対応する橋ID、断面・欄干・石の資料、2K/4K、UV・LOD。河川形状、橋中心線、NGF水位を維持 |
| 3 | 街路設備・カフェ・樹木 | 現地資料と地図位置、3段階程度のLOD、Instancing対応、単純衝突。葉は透過の重なりを抑え、推定配置を識別 |

現在の表面画像は **ARH（R=AO、G=粗さ、B=高さ）** です。新規素材のORM（B=Metallic）をそのまま接続すると金属値を高さとして扱ってしまうため、別のマテリアル接続か変換工程が必要です。現在は高さの微分から法線を作っており、撮影したNormal Mapを使っているものではありません。

通常2Kを基本に、4Kは近くで見る重点範囲へ限定します。例としてBC7 Base Color＋BC5 Normal＋BC7 ORM、全ミップ保持なら2Kは約16MiB/組、4Kは約64MiB/組という概算です。実際の圧縮設定・ストリーミングの常駐量はUEで測定して決めます。

受入時には取得元URL、ライセンスと再配布条件、現地資料、寸法、色空間、チャンネル構成、元の地物IDを記録します。L4/L5の表記には相応の建物資料・測量根拠が必要です。モデルが届いたことだけで精度を昇格させません。

## 自動確認と再実行

```powershell
# GPUの読み取り専用照会（設定・ドライバー・起動中ゲームを変更しない）
.\unreal\scripts\Inspect-ParisGPU.ps1
# 実在する素材・画像SHA・チャンネル宣言・未導入状態を検査
.\gis\.venv\Scripts\python.exe unreal/scripts/audit_paris_rendering.py
.\gis\.venv\Scripts\python.exe -m unittest discover -s gis/tests -p test_render_asset_registry.py -v
```

監査はエラー0、既存5組・画像10枚とUEの素材・テクスチャファイルの存在・PNGハッシュを確認しました。ファイル検査をUEでのロード成功とは区別します。UEでの実際のロード・描画・切替は[今回の44件のネイティブ検証](paris-twin-render-test-results.json)と[実画面](screenshots/paris-twin-render-materials.png)で確認しています。

監査の新規Python5件が成功しました。存在しない現在素材、改変されたPNG、ARH/ORMの誤宣言、未検証アセットの利用可能扱い・架空パスの登録、Content外へのパスを拒否することを確認しています。[テスト結果](paris-rendering-audit-tests.txt)。

変更ファイルは `unreal/scripts/Inspect-ParisGPU.ps1`、`audit_paris_rendering.py`、`unreal/assets/paris-photoreal-assets.json`、`gis/tests/test_render_asset_registry.py` と、この報告・JSONです。

今回の完了範囲は機能調査、GPU照会、素材・不足アセットの監査、受入仕様、描画キャッシュの実装です。Nanite・Lumen・VSMの実描画、PCG Graph、World Partition/HLODの構築、高品質アセットの導入は次の実装範囲です。
