# AI WORLD — Unreal Engine 5 Paris Digital Twin

現在のプレイ用クライアントはUE 5.8のWindows版です。実在するパリの地理データ、ノートルダム大聖堂の外観、住民の自律シミュレーションを表示します。旧ブラウザー画面（localhost:5173）は削除しました。

## 起動

通常の全景は、プロジェクトルートの Paris-Cathedral.cmd をダブルクリックします。

扉の近景は Paris-Cathedral-Doors.cmd で表示します。聖母子像の実物スキャンは、必要な個人・非商用素材をローカルで取得済みの場合のみ Paris-Cathedral-Virgin.cmd で表示できます。素材がない場合は従来の像に戻ります。NC素材本体はGitHubには含めていません。作者情報は unreal/assets/notre-dame-sculptures/CREDITS.md を確認してください。

ソースから起動する場合は unreal/scripts/Start-AIWorldUE.ps1 を使います。UE 5.8、Windows向けC++ビルドツール、Node.js 22以上、Docker Desktopが必要です。[UEへの移行と操作方法](docs/unreal-migration.md)。

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
