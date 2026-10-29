# 夜のパリと照明

`Paris-Night.cmd` で夜の三人称探索を起動。`Paris-Night.cmd -Rain` で雨音と濡れた路面の反射を伴う夜を表示する。
G は昼→夕方→夜、R は晴雨、F11 は環境音全体の切り替え、F12 は街の音の順番試聴。
PowerShellでは `Start-ParisDigitalTwin.ps1 -Photoreal -ThirdPerson -Night -Rain` を使える。
`-TimeOfDay Day|Sunset|Night` も使用可能。

## 実装

- アーカイブ済みOSMの街灯479か所を照明の候補として使う。既存の座標、器具のスケール、橋の表示高さを引き継ぎ、点灯のために地物を移動しない。
- 街灯のガラスを暖色で発光させ、下向きのスポットライトで地面・人・近くの壁を照らす。推定の設定は2800K・4500lm。実際の明るさや色温度を測定したものではない。
- 既存の店舗395か所から、既に推定されているファサード位置に小さな暖色照明を置く。現実の営業時間や営業中の店舗を判定する機能ではない。
- ノートルダムの既存ローカル座標を基準に、推定の投光器4候補を配置。大聖堂の立体形状を直接照らす。実際の照明設備の配置を測量したものではない。
- 既存の窓ガラス材質の昼の色・室内表現を保持し、固定シードで一部の窓に室内灯を加える。全ての窓を同じ明るさにせず、占有状況は景観上の推定として扱う。ステンドグラスにも控えめな発光を追加する。
- 晴れた夜は独自の夜空・小さな月・疎らな星、雨の夜は既存の曇天材質を使う。月光、低い環境光、ISO1600・1/45秒・露出補正1.5の夜間プリセットを設定。
- 灯具と窓の強い光に小さなブルームを設定。雨の湿潤PBR材質と組み合わせて路面に灯りが反射する。
- 昼に戻すと局所光と影を無効にし、窓・灯具の発光も0へ戻す。再現レベルや問題箇所のデバッグ表示でも照明を抑える。

## 描画予算

34灯の固定プールを使い、視点が移動しても光源コンポーネントを増やさない。0.5秒ごとに近くの候補を選び直す。街灯・店舗は80m、大聖堂の投光器は220m以内を選択対象にする。

| 画質 | 街灯 | 店舗 | 大聖堂 | 合計上限 | 動的な影の上限 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Low | 6 | 1 | 2 | 9 | 0 |
| Medium | 12 | 3 | 2 | 17 | 2 |
| High | 24 | 6 | 4 | 34 | 6 |

Highの夜だけボリューメトリックフォグを使う。`-NoShadows` では局所光の影も無効にする。
遠方の灯具の発光と、近くの面を照らす実光源の予算は別。選択範囲外の灯具は発光しても周囲を直接照らさない。

## ビルドと検証

変更前の雨を含む作業状態を `backups/paris-before-night` に保存。
材質生成時にも元の窓材質を `backups/paris-night-assets-*` に保存する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-AIWorldUE.ps1 -SkipAssets
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-ParisNight.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Test-ParisNight.ps1
.\Paris-Night.cmd -Rain
```

起動スクリプトは夜用アセットの欠損や対象窓材質の再生成を検出し、必要なら夜のレイヤーを再生成する。
`Content/Data/paris-night.json` にアセット一覧と表現の出所を保存。
既存GISデータと衝突形状は変更していない。夜景の照明は位置情報を除き推定の景観表現。

2026-10-29: UE 5.8 / AIWorldEditor Win64 Development のビルド、夜アセットの生成に成功。
`NightLightingAndDayRestoration`、既存の `PhotoEnvironmentAndCameraSwitching`、`RainLifecycleAndShelter` の3件が成功。
夜テストはGIS IDとXYの保持、重複のない灯具、実光源の点灯・暖色・単位、画質ごとの予算、雨との併用、昼の完全な消灯と発光値の復元を確認する。
[テスト値](paris-night-test.json)、[実行ログ抜粋](paris-night-automation.txt)。

夜・雨・三人称での[実画面](paris-night-preview.png)を撮影し、街灯の発光、路面の光だまりと反射、一部の窓、大聖堂の照明を確認。
実画面のUEログに夜材質のコンパイル失敗なし。
AMD Radeon(TM) Graphics、D3D12、1280×720、Medium、ScreenPercentage 80の25秒計測で平均32.15fps、P95 35.65ms。
実光源17灯、影あり2灯、プール34灯を確認。[計測結果](paris-night-performance.json)。60fpsには未達。
この値は大聖堂前の静止視点の計測であり、全地区・歩行中の性能を保証しない。

既存の昼間HDR環境を減光した間接光を使っており、現地の夜間HDR計測ではない。車のヘッドライトや実際の室内・営業時間・照明制御は未再現。
影を省く遠めの灯りでは壁越しの光の漏れを完全には防いでいない。

参照したUE仕様: [物理照明単位](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-physical-lighting-units-in-unreal-engine)、[動的光源と影のコスト](https://dev.epicgames.com/documentation/en-us/unreal-engine/movable-light-mobility-in-unreal-engine)。
