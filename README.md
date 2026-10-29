# AI WORLD — Unreal Engine 5 Paris Digital Twin

現在のプレイ用クライアントはUE 5.8のWindows版です。実在するパリの地理データ、ノートルダム大聖堂の外観、住民の自律シミュレーションを表示します。旧ブラウザー画面（localhost:5173）は削除しました。

## 起動

通常の全景は、プロジェクトルートの Paris-Cathedral.cmd をダブルクリックします。

雨の街を歩く場合は `Paris-Rain.cmd`。雨粒、水はね、濡れた路面の反射、曇り空、ステレオの雨音と水滴を表示します。`R`で晴雨、`F11`で環境音全体を切り替えます。屋根の下では雨音が弱まり、晴れに戻すと路面は徐々に乾きます。[雨の描画・音声・再生成](docs/paris-rain.md)。

夜の街は `Paris-Night.cmd`、雨の夜は `Paris-Night.cmd -Rain`。暖色の街灯、店舗の明かり、一部の窓の発光、大聖堂のライトアップを表示します。`G`で昼→夕→夜、`R`で雨／晴れを切り替えます。[夜景と照明](docs/paris-night.md)。

街の環境音は、ノートルダムの鐘、市場のざわめき、セーヌ川、船のエンジン、鳩、フランスの二音サイレン。位置と距離に合わせて鳴り、夜はざわめきと鳩が静かになります。`F11`で全体をミュート、`F12`で各音を試聴できます。[音源・配置・再生成](docs/paris-soundscape.md)。

セーヌ川を見る場合は `Paris-River.cmd`。水専用の光の散乱・吸収・反射、3層の流れるさざ波、実際の河岸に沿う色の変化と濡れた護岸を表示します。`F7`の低品質や`M`の簡易表示では従来の軽い水面に戻ります。[川の描画・再生成](docs/paris-realistic-river.md)。

道路を見る場合は `Paris-Roads.cmd`。写真由来の舗装、細いひび・補修跡、道路端の汚れ、立体の縁石と排水グレーチングを、地上170cmの視点で確認できます。`F10`でHUDを隠せます。[道路の描画・再生成](docs/paris-realistic-roads.md)。

樹木を見る場合は `Paris-Trees.cmd`。中・高品質で街路樹1,108本に写真由来の樹皮と葉を使い、葉の透過光、木ごとの色の違い、近景の風による揺れを表示します。`F7`の低品質で軽い樹木に戻り、`F10`でHUDを隠せます。[樹木の描画・再生成](docs/paris-realistic-trees.md)。

橋を見る場合は `Paris-Bridges.cmd`。サン・ミシェル橋など周辺7橋に、連続した路面・歩道、石造アーチと橋脚、鋳鉄のアーチ・欄干、石材の表面と水際の染みを追加しています。`F10`でHUDを隠せます。[橋の構造・再生成](docs/paris-realistic-bridges.md)。

車を見る場合は `Paris-Cars.cmd`。中・高品質では精細なセダンを表示し、6色のクリアコート塗装、透過ガラス、内装、回転・操舵する4輪、停止時のブレーキランプを使います。`C`で近くの車を確認、`F7`の低品質で従来モデル、`F10`でHUD表示を切り替えます。[車の描画・再生成](docs/paris-realistic-vehicles.md)。

**主人公で街を散策する場合は `Paris-Explore.cmd` をダブルクリック。** 三人称から開始し、`WASD`で歩く、`Shift`を押しながら走る、右ドラッグでカメラ、ホイールで距離、`V`で一人称／三人称を切り替えます。`H`でメニュー、`F10`でHUD表示、`F2`で全景、`F8`で主人公に戻ります。[主人公の操作・検証](docs/paris-protagonist.md)。

キーと画面上部ボタンの一覧はゲーム内の **H（操作ヘルプ）** で確認できます。詳しい説明は[パリ散策 操作ガイド](docs/paris-controls.md)を参照してください。

扉の近景は Paris-Cathedral-Doors.cmd で表示します。聖母子像の実物スキャンは、必要な個人・非商用素材をローカルで取得済みの場合のみ Paris-Cathedral-Virgin.cmd で表示できます。素材がない場合は従来の像に戻ります。NC素材本体はGitHubには含めていません。作者情報は unreal/assets/notre-dame-sculptures/CREDITS.md を確認してください。

ソースから起動する場合は unreal/scripts/Start-AIWorldUE.ps1 を使います。UE 5.8、Windows向けC++ビルドツール、Node.js 22以上、Docker Desktopが必要です。[UEへの移行と操作方法](docs/unreal-migration.md)。

写実モードの中・高品質では、近くの歩行者に肌・髪・衣服のテクスチャと骨格アニメーションを持つ男女の人体モデルを使います。`Paris-People.cmd`で街路カメラから起動できます。`F7`で品質、`P`で人物の表示、`F10`でHUDを切り替えられます。素材を再生成する場合は `unreal/scripts/Build-ParisPeople.ps1`、取得済み素材だけで再生成する場合は `-Offline` を付けます。[素材とMITライセンス](unreal/assets/paris-people/CREDITS.md)。

## シミュレーションと保存

住民AI、行動、資源、建築、会話、SQLite保存はローカルのNode.js backendが担当します。Docker Composeはbackendサービスだけを起動し、ホストの127.0.0.1:3001でUEと通信します。5173番ポートのWeb画面はありません。

セーブデータはai-world_world-data Docker volumeに保持されます。通常の停止・再ビルドでは消えません。docker compose down -v はこのボリュームを削除するため実行しないでください。

## 構成

- unreal/AIWorld: UEの地形・建物・住民・描画・操作
- backend/ と shared/: 住民シミュレーション、API、保存データ形式
- presentation/src/renderer: UE用の建築・人物メッシュと地形の表示計画。Webアプリではなく、UEへデータを渡すモデル生成コード
- tools/export-unreal.ts: モデルをUE用バッファへ出力
- gis/: パリの地理データ取得・変換

## ビルド・確認

UEのC++ビルドは unreal/scripts/Build-AIWorldUE.ps1、UE側の確認は unreal/scripts/Test-AIWorldUE.ps1 を使います。Node.js側は npm run typecheck と npm test で確認できます。

ノートルダムの最新の実装・実画面・検証結果は [v12レポート](docs/paris-photoreal-v12.md)、入口の扉は [v11レポート](docs/paris-photoreal-v11.md) を参照してください。全体写真相当の再現はまだ未完成です。

### セーヌ川クルーズ船

`Paris-Cruise.cmd` で船を追いかける写実モードを起動できます。通常画面では **U** で船の追従表示、もう一度 **U** または **F2** で元の視点に戻ります。**F10** で表示を隠せます。船は実際のセーヌ川の輪郭から算出した区間を自動で往復し、橋の手前で減速・旋回します。船自体や航路は実在の交通状況を示すものではありません。詳細と素材の出典は [クルーズ船の説明](docs/paris-realistic-cruise.md) を参照してください。

### メトロ4号線（試作）

`Paris-Metro.cmd` で地下ホームから開始します。通常の街画面でも **K** で最寄りの駅のホームへ入り、**L** で列車に乗ってもう一方の駅へ移動できます。到着後に **L** で降車し、**K** で地上へ戻ります。ホームでは **WASD** で歩けます。駅の実位置はOpenStreetMapを参照し、地下の構造や線路、車両は推定の試作です。実際の時刻や運行状況には連動しません。詳細は [メトロ試作の説明](docs/paris-metro-prototype.md) を参照してください。

### サント・シャペル

`Paris-Sainte-Chapelle.cmd` で建物の専用視点を開けます。街の画面では **J** で切替、**F2** で全体表示に戻ります。控え壁、尖塔、尖頭窓の外観は資料に基づく推定モデルです。元の建物と当たり判定を保持しており、内部はまだ再現していません。出典と制約は [サント・シャペルの説明](docs/paris-sainte-chapelle.md) に記載しています。

### 旧司法宮の外壁

`Paris-Palais.cmd` でサント・シャペル近くの旧司法宮の窓を確認できます。**O** は専用視点、**J** はサント・シャペル、**F2** は全体表示です。立体的な窓枠は元の地理データの窓に合わせた推定モデルで、建物の当たり判定や内部は変更していません。[出典と詳細](docs/paris-palais-detail.md)
