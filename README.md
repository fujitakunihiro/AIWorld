# AI WORLD — Unreal Engine 5 Paris Digital Twin

現在のプレイ用クライアントはUE 5.8のWindows版です。実在するパリの地理データ、ノートルダム大聖堂の外観、住民の自律シミュレーションを表示します。旧ブラウザー画面（localhost:5173）は削除しました。

## 起動

通常の全景は、プロジェクトルートの Paris-Cathedral.cmd をダブルクリックします。

セーヌ川を見る場合は `Paris-River.cmd`。水専用の光の散乱・吸収・反射、3層の流れるさざ波、実際の河岸に沿う色の変化と濡れた護岸を表示します。`F7`の低品質や`M`の簡易表示では従来の軽い水面に戻ります。[川の描画・再生成](docs/paris-realistic-river.md)。

道路を見る場合は `Paris-Roads.cmd`。写真由来の舗装、細いひび・補修跡、道路端の汚れ、立体の縁石と排水グレーチングを、地上170cmの視点で確認できます。`F10`でHUDを隠せます。[道路の描画・再生成](docs/paris-realistic-roads.md)。

樹木を見る場合は `Paris-Trees.cmd`。中・高品質で街路樹1,108本に写真由来の樹皮と葉を使い、葉の透過光、木ごとの色の違い、近景の風による揺れを表示します。`F7`の低品質で軽い樹木に戻り、`F10`でHUDを隠せます。[樹木の描画・再生成](docs/paris-realistic-trees.md)。

橋を見る場合は `Paris-Bridges.cmd`。サン・ミシェル橋など周辺7橋に、連続した路面・歩道、石造アーチと橋脚、鋳鉄のアーチ・欄干、石材の表面と水際の染みを追加しています。`F10`でHUDを隠せます。[橋の構造・再生成](docs/paris-realistic-bridges.md)。

**主人公で街を散策する場合は `Paris-Explore.cmd` をダブルクリック。** 三人称から開始し、`WASD`で歩く、`Shift`を押しながら走る、右ドラッグでカメラ、ホイールで距離、`V`で一人称／三人称を切り替えます。`H`でメニュー、`F10`でHUD表示、`F2`で全景、`F8`で主人公に戻ります。[主人公の操作・検証](docs/paris-protagonist.md)。

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
