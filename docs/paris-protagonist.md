# 主人公でパリを歩く・走る

`Paris-Explore.cmd` をダブルクリックすると、UE版の実在パリ地区で主人公を操作できます。ノートルダム前の広場から、写実描画・中品質・三人称で開始します。初期配置は地面・カプセル・カメラ背後の空間を検査します。

| 操作 | 動作 |
|---|---|
| W / A / S / D | カメラの向きを基準に前後左右へ歩く |
| 左または右 Shift ＋ 移動 | 走る。離すと歩く |
| 右マウスを押しながら移動 | カメラの向きを変える |
| ホイール | 三人称のカメラ距離を調整 |
| V | 一人称／三人称を切り替え |
| F2 / F3 | 全景／飛行に戻る |
| F8 | 主人公での散策を開始。散策中は視点切替 |
| H / F10 | 操作メニュー／HUD全体の表示切替 |
| F7 | 描画品質を切り替え |

歩行は1.7m/s、走行は4.2m/s。加速・減速を設け、斜め入力は正規化します。三人称の身体は進行方向を向き、カメラは独立して回転します。一人称の眼の高さは約170cmです。街の建物・地形の衝突、重力、35cm以下の段差乗り越え、地形外への転落時の安全位置復帰を使います。水中移動や建物内部の探索は対象外です。

主人公はMicrosoft RocketboxのMITライセンス人体モデルを使い、待機・歩行・走行を別の骨格モーションからブレンドします。再生速度と切替は実際の移動速度に従い、壁に当たって停止すると待機へ戻ります。root移動は固定し、CharacterMovementが位置を管理します。素材・骨格・走行クリップが欠ける場合は既存の簡易人形へ戻ります。主人公は群衆の表示切替や近景人数枠から独立しています。

散策中は上部の大きなメニューを畳み、下部に状態・速度・操作を表示します。Hでメニューを再表示でき、F10で完全非表示にできます。

## ビルドと再生成

```powershell
./unreal/scripts/Build-ParisPeople.ps1
# ダウンロード済みの25ファイルをSHA256検証して再生成:
./unreal/scripts/Build-ParisPeople.ps1 -Offline
./unreal/scripts/Build-AIWorldUE.ps1 -SkipAssets
./unreal/scripts/Test-ParisDigitalTwin.ps1 -Photoreal
./unreal/scripts/Start-ParisDigitalTwin.ps1 -Photoreal -ThirdPerson
```

元FBX・テクスチャはコミットを固定して取得します。[出典とMITライセンス](../unreal/assets/paris-people/CREDITS.md)。走行は男女2体分を保存しますが、操作する主人公には男性モデルを使用します。

`ParisDigitalTwin.Live.ProtagonistWalkRun` は実際のW/D/左右Shift入力を注入し、歩行速度、走行速度、斜め走行、身体とカメラの方向、停止、壁衝突、スキンアニメーション、一人称での身体非表示、ズーム範囲、散策終了時の停止を検証します。従来の `WalkingAndPedestrians` は実GIS地面への着地、壁、段差、転落復帰、住民シミュレーションを検証します。

## 実画面での検証

2026-10-24、UE 5.8.3、D3D12 / Shader Model 6、写実設定・中品質、1280×720で実際の街と主人公の三人称表示を描画しました。平均41.18fps、フレーム時間95パーセンタイル27.83ms、プロセス使用メモリ約5,313MiB。実測はこのPCのAMD Radeon(TM) Graphics（共有メモリ）での1回の街区測定値で、他PCや高品質の性能値を保証しません。

実画面: [主人公の三人称表示](screenshots/paris-protagonist.png)。描画計測: [JSONレポート](paris-protagonist-medium-performance.json)。自動テストは23件成功し、主人公の検査ではWASD、左右Shift、斜め移動、速度、停止、壁衝突、視点、カメラ空間、身体アニメーションを検証しました。
