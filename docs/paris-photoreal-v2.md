# Paris Digital Twin — Photorealism v2

## Phase 0：修正前の診断

2026-10-15。地理データの取得・範囲拡張を停止し、ノートルダム西正面周辺100mを優先します。修正前の状態を `backups/pre-paris-v2-20261015-212844.zip` に退避しCRCを検証しました（Git基準7c5e7c4と作業中165ファイル）。

| 項目 | 実ファイル・実行ログで確認した状態 |
| --- | --- |
| 実エンジン | UE **5.8.3**, CL58210709。起動中プロセスはUnrealEditor.exeの `-game -ParisTwin -dx11`。別のWeb版はThree.jsで、UEとは別の描画実装 |
| GPU・メモリ | AMD Radeon Graphics、ドライバ32.0.21045.5002。WMIのAdapterRAMは3GiB。D3D12照会ではUMA＝共有メモリ方式であり、3GiBを独立した専用VRAMとみなしません。使用可能なシステムRAM約28.8GiB |
| RHI・SM | 修正前はDX11 / SM5。D3D12CreateDeviceとSM6.8までの機能照会は成功。ただしこれはUEのDX12描画成功や60fpsの証明ではない |
| Lumen / Nanite / VSM | いずれも未使用。GI=0、ReflectionMethod=2、VSM=0、GenerateMeshDistanceFields=False。建物は実行中にfast-buildされ、オフラインの距離場・Lumenカード・Naniteデータを持たない |
| 都市メッシュ | GISポリゴンから壁と推定屋根を生成。100mセルの描画コピーにまとめ、元の衝突・地物選択は保持。静的生成部分466メッシュ・1,231,408三角形。これに街路設備のHISMと人物・車が加わる |
| ノートルダム | OSM `way/201611261`。本体**2,660三角形・5,382頂点**。屋根は近隣と同じバッチに含まれるため本体の数と混同しない。専用の大聖堂モデルは未導入。双塔、門、彫刻、バラ窓、飛梁の専用造形なし |
| 素材・画像 | 実写由来2Kの砂岩代理素材・敷石各3枚（albedo、DX normal、ORM）。屋根・アスファルトなどは512px独自生成ARH。窓・鉄・木・人物・樹木は単純な頂点色主体。1K HDR環境。砂岩代理はパリの現地石灰岩の測量素材ではない |
| 光・影 | Directional Light 10.3、5700K、角度(-48,-35,0)、光源角1.2°。Sky Atmosphere、指定HDRのSky Light強度0.55。影の最大解像度1024。物理カメラに対応しない露出補正9.6とAO0.6、Height Fogなし |
| 地理座標 | WGS84→EPSG:2154→共通原点からcm。東X・南Y・上Z、NGF-IGN69原点35.38m。Cesium二重変換なし。外観変更でこの基準を変えない |
| 重点範囲 | 従来はサン・ミシェル側、WGS84(2.3436,48.85325)。ノートルダム前には設定されていなかった |
| 速度 | 前回の単独UE・街路固定視点で高品質720p・内部100%が100.75fps。今回の修正前大聖堂俯瞰は51.12fpsだが、別のUEプレビューとバックアップ処理が同時に動いた診断用撮影であり、単独性能の基準値としない |

[実メッシュ診断JSON](paris-v2-diagnosis-geometry.json) / [GPU能力照会](paris-gpu-capabilities.json) / [診断用大聖堂俯瞰](screenshots/paris-v2-diagnosis-before.png)。

### 黒い天空の確認

起動中ログ `AIWorld.log` に `Set new viewmode: Unlit` の記録がありました。同じMaterials視点でUnlit撮影すると天空が黒くなりました。一方、Lit撮影では青空が描画されています。今回確認できた黒い空の原因はUnlit表示です。過去のすべての黒画面の原因が同じだとは断定しません。

[Unlitで再現した黒い空](screenshots/paris-v2-sky-unlit.png) / [Litの空](screenshots/paris-street-realism-materials.png)。Unlitは照明を評価しない検査表示で、写実画像の比較には使いません。

### 外部モデル候補

| 候補 | 提供者の仕様 | 取得・不足点 |
| --- | --- | --- |
| [Notre-Dame de Paris — francois.bouille](https://sketchfab.com/3d-models/notre-dame-de-paris-b5808186c49a451bbf815fbccdb727a3) | API実測303,751面・371,457頂点。CC BY 4.0、無料ダウンロード可。説明は20M→300K、16K→8K | メタデータAPIは200、匿名download APIは401。モデル本体・UV・法線/粗さ・全建築要素の有無は未検査。取得後に検証する候補 |
| [Notre-Dame De Paris — ZhengJie / Fab](https://www.fab.com/listings/4e2cf2ab-ac8c-4798-860c-00d06b1ff7e7) | 58,300三角形、4素材・2K画像、FBX/GLB/glTF | 購入用掲載。価格と契約は未取得。購入・導入していない。近景造形とPBRの中身を検査する必要あり |
| [Cathedral Notre-Dame façade — Nicolas Diolez / Fab](https://www.fab.com/listings/55f872f2-0cfc-4f97-9176-8875c0813163) | 2024復元後の西正面写真測量。614,510三角形、albedo/normal各8K。高詳細版も同梱と記載 | 購入用、西正面のみ。後陣・飛梁・屋根の全体モデルの代わりにはならない。未購入・未導入 |
| [Myles Zhang — inside and out](https://sketchfab.com/3d-models/notre-dame-of-paris-inside-and-out-ead7ec4c9a594de2906116cb04d75441) | 2.7M三角形、内外を含む。DAE/SKP/KMZと記載 | 再利用条件は作者への確認が必要と記載。権利未確定のまま使わない |

[匿名APIの実際の応答](paris-v2-model-access.json)。外部への問い合わせや購入は実行していません。ログインや本体ファイルが必要な候補を、存在しないモデルパスに置き換えて完成扱いにしません。

### 技術上の修正方針

天空のLit起動、重複しないライト・霧・Post Process、自然な露出、約1.7mの固定比較カメラを先に整えます。対応GPUではDX12/SM6によるLumen/VSMを実描画で検証します。Lumenは設定フラグだけでなく、静的メッシュの距離場とカードも必要です。[UEのLumen技術資料](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine) / [UE5.8の描画機能要件](https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine)。

モデルの輸入・メッシュ作成・素材構築は、既存のUE Python commandletで自動化できます。購入、Sketchfabへのログイン、モデルの美術・建築上の承認を自動で済ませたとは扱いません。


## Phase 1：描画環境の実装

`ParisPhotoEnvironment.cpp`に環境構築を分離しました。同じ種類のActorを再利用し、太陽・大気・Sky Light・Height Fog・無限Post Processを重複生成しません。通常起動をLitへそろえ、太陽50,000lux、5,600K、光源角0.8度、ISO100・1/125秒・F8、露出補正+0.5EVの手動物理露出としました。現在の太陽角は美術上の設定で、日時とパリの天文学的な一致は未実装です。

通常環境光は太陽とSky AtmosphereをSky Lightで取得し、近景の日陰を確認して強度2へ調整しました（美術調整であり照度の現地測定ではありません）。従来の低輝度HDRは物理露出との明るさが整合しなかったため、`-ParisTwinLegacyLighting`の診断用に限定しました。Lumenのキャッシュ露出は実際の警告に合わせ、UE5.8のソースで確認したEVオフセット8に設定しています。薄いHeight Fogを追加し、重いVolumetric Fogは使用していません。

`Config/Custom/ParisPhotoreal/DefaultEngine.ini`にDX12・SM6・ソフトウェアLumen GI/反射・VSM・距離場の専用プロファイルを追加しました。既定のDX11起動も維持します。最初のDX12描画とSM6起動は成功しました。起動時の距離場・カード・Naniteの実データ数は計測JSONに記録し、設定フラグだけで有効と判断しません。

元のGISメッシュの近景21個をGeometry Scriptで静的アセット化します。位置・原点・元の衝突・クリック判定は保持し、描画コピーのみ置き換えます。これは簡易的な建物形状そのものを高詳細モデルに変換する処理ではありません。

## Phase 2：取得した実モデルと採用判定

公開された[Objaverseデータセット](https://huggingface.co/datasets/allenai/objaverse)に同じSketchfab UIDが存在することを確認し、作者名・個別ライセンス・埋込クレジットを照合してGLBを取得しました。ログインが必要な元サービスの非公開データを取得したものではありません。

- 作者：francois.bouille。個別モデルはCC BY 4.0。データベースのODC-Byと区別します。
- SHA256：`1edc3e67d32b3a223591625a9322a9155ab271fb0591a1465eb22a2fa409d3c7`、35,120,084bytes。
- 建築部分302,855三角形、別の地面876三角形。UV0・法線あり。
- 配布ファイルの実画像は16枚すべて**1024×1024**。素材16個がUnlitで、Normal/Roughness画像はありません。元掲載の8Kと同等とは扱いません。
- UE5 Interchangeによる実インポート成功：49アセット。専用の候補フォルダに隔離し、採否未確定のメタデータと著作権表示を保存しました。
- 実寸・建物方向・西正面双塔・飛梁・屋根の建築的検証、PBR再構築は未完了です。取得物の高さ約32.6単位に対し長さ約115単位であり、GISの高さ包絡66mへ一律スケールを掛けることはしません。

**高品質モデルの置換は未完了です。** 現在のGIS輪郭と簡易本体を基準として保持し、候補を完成モデルとして街へ配置していません。高品質の西正面だけならNicolas DiolezのFab掲載が候補ですが、全体の屋根・飛梁は別途必要です。購入や外部への問い合わせは実行していません。

検査・来歴・クレジットは `unreal/assets/notre-dame/{manifest,inspection,source-metadata}.json` と `CREDITS.md`、再取得は `fetch_notredame.py --download`。生GLBはGit対象外です。UE候補アセットの再生成は `Build-ParisPhotoreal.ps1 -ImportCandidate` で実行できます。

## Phase 3：周辺建築

外観の重点100m範囲をサン・ミシェルからノートルダムの西端へ移しました。近景4棟、立体窓枠131、丸みのあるバルコニー38、プランター26。既存の実体形状を持つ装飾生成をこの地区へ適用しています。建物本体・高さ・向き・地物IDは変更していません。

玄関・窓枠・鉄柵・庇・店舗・煙突などはプロシージャルな推定外観です。現地調査済みのL4/L5とは扱いません。建物壁に実際の窓穴を開ける処理、現地の個別ファサード採寸、高詳細の植生・人物・車両は未実装です。

## Phase 4：素材

指定された8名称のMaterial Instanceを実生成して描画へ接続しました。既存PBR素材の親を共有するため、重複したシェーダー実装を増やしません。

| アセット | 実装と制限 |
| --- | --- |
| M_Paris_Limestone | CC0の実写2K砂岩代理。Base Color・DX Normal・ORM、ワールド座標の実寸投影。現地のパリ石灰岩を計測した素材ではない |
| M_Paris_Roof_Zinc / M_Paris_Roof_Slate | 512pxの再生成可能なオリジナル。ARHからAO・Roughness・微細な凹凸を算出 |
| M_Paris_Cobblestone | CC0実写2K敷石、Base Color・DX Normal・ORM、地面に合わせた実寸投影 |
| M_Paris_Asphalt | 独自512px、ARHとワールドスケール |
| M_Paris_Iron | 金属度・粗さ・頂点色。個別の鍛鉄装飾の撮影テクスチャは未導入 |
| M_Paris_Glass | 低い粗さの窓面。実体のある店舗内部・透過多層ガラスは未実装 |
| M_Seine_Water | 既存水面素材を共有。河川ポリゴン・水位を保持。現地水面の物理的な測定再現ではない |

近景の実写表面は既存素材に含まれる経年変化を使います。個別建物の雨染みや汚れの現地再現、完全な繰返し除去は未実装です。遠景の輪郭だけを増やして写真品質として報告しません。

## Phase 5：カメラ

`Camera_NotreDame_Front` / `Camera_NotreDame_Riverside` / `Camera_Paris_Street`を生成しました。共通GIS原点、実際に歩ける道路・地形の衝突面から170cm、35mm相当・F8、実距離に焦点を合わせます。カメラWGS84と元の大聖堂IDを中間データに保存します。現地の特定の写真と一致させた測量カメラではなく、比較用に推定した撮影地点です。

建物・水面の内部と、推定された街路樹の樹冠直下を除外します。4/5/6で切替、WASDまたは右ドラッグで自由視点に戻ります。過度な浅い被写界深度やミニチュア効果は追加していません。

**構図の品質調整は未完了です。** 実際の撮影画像では、正面は護岸付近の地形で下部が遮られ、川沿いは前方の樹木が大聖堂を隠します。撮影地点の建物・水面・樹冠直下の除外だけでは、視線全体の地形・植生の遮蔽を解決できていません。樹木を消したり地形を変形したりして撮影成功として扱っていません。街路には暗い面と簡易的な外観も残ります。高品質モデル導入時に、橋上や広場の上段など、実際の地面に立てる地点で構図を再調整する必要があります。


追加調査で、[3dtrustの全体モデル（CGTrader）](https://www.cgtrader.com/3d-models/exterior/landmark/notre-dame-cathedral-ultra-high-detail-8k-pbr-textures-3d-model)も候補に挙がりました。販売側表示は3,977,597ポリゴン・8K PBR・FBX/glTF、Royalty Freeです。高詳細の全体モデル候補ですが、実物ファイルの寸法・建築要素・GPU負荷は未検査で、購入・導入していません。販売画像だけから完成品質を保証しません。

[Autodeskの文化財BIM資料](https://adsknews.autodesk.com/en/media-resources/notre-dame-assets/)は公開されていますが、今回確認したページのダウンロードは説明用の画像で、自由に再利用できるUE用の全体PBRモデルとは確認できませんでした。


## 最終描画検証

2026-10-15、AMD Radeon Graphics (Ryzen 7 7735HS)、UE 5.8.3 Development Editor `-game`。1280×720、Highは内部100%、Mediumは80%、各20秒・準備5秒、別UEプロセスなし。正面DX12はGPUプロファイル表示あり。初回のshader/SDF/card構築中の値は別のwarmupレポートとして残し、次の表には含めません。

| 視点・設定 | 平均fps | P95 frame ms | 実キャプチャ |
| --- | ---: | ---: | --- |
| DX12 正面 / High | 51.91 | 22.78 | [画像](screenshots/paris-v2-front-high.png) / [計測JSON](paris-v2-front-high-performance.json) |
| DX12 川沿い / Medium | 57.32 | 21.81 | [画像](screenshots/paris-v2-riverside-medium.png) / [計測JSON](paris-v2-riverside-medium-performance.json) |
| DX12 街路 / Medium | 43.28 | 27.97 | [画像](screenshots/paris-v2-street-medium.png) / [計測JSON](paris-v2-street-medium-performance.json) |
| DX11 正面 / High | 89.45 | 12.71 | [画像](screenshots/paris-v2-front-dx11.png) / [計測JSON](paris-v2-front-dx11-performance.json) |

DX12の目標60fpsは未達です。DX12ではGI=1、Reflections=1、VSM=1、SM6と、近景21個すべての距離場・Lumenカード・Naniteデータを実行中に確認しました。描画コピーの外形誤差0cm、サンプリングした頂点色の不一致0件。元の当たり判定と地物IDを引き続き使います。近景以外の実行時fast-buildメッシュは、距離場やカードがそろった状態ではありません。

[GPUプロファイル](paris-v2-front-high-performance.gpu.log)の単発観測では、LumenScreenProbeGather約9.86ms、LumenSceneLighting約2.49ms、BasePass約3.82ms、ShadowDepths約3.55msでした。非同期computeとgraphicsを含み、これらを単純加算して総GPU時間にはしません。撮影時のstat unitではGame約8.4ms、Draw約17.7ms、GPU約15.5ms。LumenのGPUコストに加え、描画スレッドも60fpsの16.7ms予算を超えています。UMAの帯域不足を直接計測したものではありません。今後は重点100m以外の簡略化と装飾バッチの見直し、Lumen品質予算の調整が必要です。

**これらは実際のUE画面であり、実写品質の達成例ではありません。** 大聖堂の建築詳細、植生、小物、地形と護岸の段差、撮影構図に未解決の点が残っています。

## 実行手順

エディタを閉じて、リポジトリ直下のPowerShellから実行します。

```powershell
# 現在の取得済み地理データだけで再生成（新規取得なし）
$env:PYTHONPATH = Join-Path (Get-Location) 'gis'
& gis/.venv/Scripts/python.exe -m paris_twin prepare --offline
& gis/.venv/Scripts/python.exe -m paris_twin validate --offline

# ネイティブと素材、近景の静的メッシュを生成
./unreal/scripts/Build-AIWorldUE.ps1
./unreal/scripts/Build-ParisPhotoreal.ps1

# DX12品質モード。DX11は -Photoreal を外す
./unreal/scripts/Start-ParisDigitalTwin.ps1 -Photoreal -PhotoCamera Front -Quality High
```

日常の起動は `Paris-NotreDame.cmd`。4/5/6が固定カメラ、WASDと右ドラッグが自由移動、F8が歩行です。既存の村とDX11表示も維持しています。

```powershell
# 外部候補の再取得・検査・隔離インポート（街には配置しない）
& gis/.venv/Scripts/python.exe unreal/scripts/fetch_notredame.py --download
& gis/.venv/Scripts/python.exe unreal/scripts/inspect_notredame.py
./unreal/scripts/Build-ParisPhotoreal.ps1 -ImportCandidate

# 回帰テスト
./unreal/scripts/Test-ParisDigitalTwin.ps1
./unreal/scripts/Test-ParisDigitalTwin.ps1 -LegacyJSON
./unreal/scripts/Test-AIWorldUE.ps1
```

エディタでの手動作業を必須にせず、実際にcommandletで生成・インポート・ビルドしました。候補を目視確認する場合はContent Browserの `ParisPhotoreal/NotreDameCandidate` を開きます。採用前に塔・門・バラ窓・飛梁・屋根・UV・単位・方位を確認し、元の `osm/way/201611261` 輪郭と照合します。未採用モデルを街の完成品として配置する自動処理はありません。

## 変更ファイル

- `gis/config/ile_de_la_cite.json`：重点範囲のみ変更。取得範囲・共通原点は維持。
- `gis/paris_twin/photo_scene.py`、`mesh.py`、`gis/tests/test_photo_scene.py`：撮影地点・来歴・静的描画キャッシュ指定。
- `unreal/AIWorld/Source/AIWorld/ParisPhotoEnvironment.*`、`ParisPhotoTests.cpp`：環境・物理露出・固定カメラ・切替と回帰テスト。
- `ParisDigitalTwin.cpp`、`ParisRenderCache.*`、`ParisSurfaceTests.cpp`、`AIWorld.Build.cs`：描画経路・素材接続・RHI診断。既存AIや保存処理は変更していません。
- `unreal/AIWorld/AIWorld.uproject`、`Config/Custom/ParisPhotoreal/DefaultEngine.ini`：Editor用Geometry ScriptとDX12品質プロファイル。
- `unreal/scripts/{Start,Measure,Test}-ParisDigitalTwin.ps1`、`Build-ParisPhotoreal.ps1`、`bake-paris-photoreal.py`、`create-paris-assets.py`、`Paris-NotreDame.cmd`。
- `diagnose_paris_scene.py`、`fetch_notredame.py`、`inspect_notredame.py`、`import-notredame-candidate.py`、`unreal/assets/notre-dame/*`：実測診断・正規公開モデルの取得・検査・隔離インポートとクレジット。
- `Content/Materials`の指定8名称、`Content/ParisPhotoreal/Generated`の21メッシュ、`Content/ParisPhotoreal/NotreDameCandidate`の候補49アセット。存在するアセットを生成・ロードして確認しています。
- `docs/paris-v2-*`、`docs/screenshots/paris-v2-*`：診断・実行結果・実画像。

既存のDocker構成、Web版、住民AI、建築と保存ロジックを改修する作業は行っていません。修正前の作業内容は冒頭のバックアップに保持しています。

## 次に必要なアセット・作業

| 優先 | 必要なもの | 推奨する検収条件 |
| --- | --- | --- |
| 1 | 実在ノートルダムの全体モデル | 双塔・門・バラ窓・飛梁・屋根を含む実寸モデル。UVと法線、Base Color/Normal/Roughness、明確な利用・再配布条件。高解像度原本を保持し、このUMA機では4K以下の表示セットも用意 |
| 2 | 近景の石灰岩・亜鉛・スレート | 実寸2〜4mの写真由来PBR、4K原本、DX Normalと正しい線形マスク。現地素材か代理かを記録 |
| 3 | ファサード部材・植生 | 実体のある玄関、窓、鍛鉄、店舗と現実的な樹木。反復部材はHISM/LOD、素材・寸法・推定配置を記録 |
| 4 | 構図・接地・明るさの再調整 | 橋・広場上段の実際に歩ける地点で、地形と樹木を含む視線を確認。100m品質地区を先に仕上げる |

現段階でPhase 2の完成モデル採用と、地区全体のフォトリアル完成を宣言しません。都市範囲の拡大は引き続き停止します。


## 最終ビルド・自動検証の結果

- UE5.8.3のDevelopment Editorビルド成功。最終DLLを4つの描画計測と回帰テストで使用しました。
- UE自動テスト：compact 15件、従来JSON 15件、既存村/プロトコル5件、合計**35件成功**。歩行・衝突・元の地物選択・人物/交通・保存/地形・固定カメラ切替・ライト再設定の重複防止を含みます。
- GIS検証：**エラー0**、座標往復最大誤差2.79×10⁻⁹m。既存の輪郭重複、362棟の実測高さの被覆不足、道路の分断、範囲端の橋2断片の警告は残ります。
- 元の非ファサード形状・地物メタデータのハッシュは変更前と一致：`7ad69c15c2e697908b321b49e0b456c240cd83f59714330371847107003fd1e8`。739棟・4,799地物・191コアメッシュを保持。
- Python一括71件は、最終カメラ・照明調整前に成功しました。その後のカメラ調整には、決定性・接地高さメタデータ・樹冠回避・キャッシュの内容依存キーを確認する写真シーン2件を再実行して成功しています。一括71件を最終調整後に再実行したという意味ではありません。
- PowerShell4スクリプトの構文検証成功。新しい外部モデルはUEへ実インポート済みですが、建築要素とPBRの採用検査は未完了です。

[検証結果と各テスト名](paris-v2-validation.json)。高品質モデルの未採用と写真品質の未達を、テスト成功と混同しません。
