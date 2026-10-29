# パリの雨と雨音

`Paris-Rain.cmd` でフォトリアル版の三人称探索を雨天で起動する。
通常の `Paris-Explore.cmd` では R で雨／晴れを切り替える。
F11 は雨音を含む環境音全体のミュート。F12 は街の音の順番試聴。K の駅への乗降操作は従来どおり。

## 表現

- 雨粒は毎フレーム更新。落下速度 7.2～10.2m/s、長さ18～38cmの半透明ストリーク。カメラを回しても雨の方向は世界座標で一定。
- 負の座標や長時間実行でも剰余を正規化し、雨がボリューム外へ流出する旧処理を廃止。
- 実際の衝突形状に当たる地点に短命の水はねを配置。雨粒は6m間隔の上面サンプルを使って地表・屋根より下の描画を抑える。
- 路面・敷石・護岸・橋の対応PBR材質に湿潤レイヤーを追加。元のテクスチャと乾燥時の値を保持し、濡れると暗く滑らかになり、小さな波紋が加わる。晴れに戻した後も約56秒かけて乾く。
- 曇天の空と柔らかい日光。昼／夕方／夜の既存プリセットと組み合わせられる。
- 48kHz・ステレオ・32秒の雨と水滴の2層ループ。頭上5方向の衝突照会で、遮蔽物の下では雨音の音量と高音域を下げる。晴れ／ミュート／シーン終了時は音声を停止。
- Low / Medium / High の雨粒予算は650 / 2800 / 4400、水はね予算は48 / 100 / 160。半径18mの近景に雨粒を集中させる。地理データ・歩行衝突・建物配置は変更しない。

## 再生成と検証

既存のGitコミットと `backups/paris-rain-before` にコードの変更前状態を保存。
雨のアセット生成時は既存のMaterialsを `backups/paris-rain-assets-*` にコピーする。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-AIWorldUE.ps1 -SkipAssets
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-ParisRain.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Test-ParisRain.ps1
.\Paris-Rain.cmd
```

`Start-ParisDigitalTwin.ps1 -Rain` と `-MuteSound` も使用可能。
起動時に必要な雨アセットの欠損や、対象PBR材質の再生成を検出すると雨レイヤーを再適用する。

UE自動テスト `ParisDigitalTwin.Live.RainLifecycleAndShelter` は、1分以上の降雨、座標範囲、音声素材とループ設定、実際の遮蔽物による音の遮蔽、ミュート、晴天での停止と乾燥を検証する。
既存の `ParisDigitalTwin.Live.PhotoEnvironmentAndCameraSwitching` も回帰対象。
テスト結果は `unreal/AIWorld/Saved/paris-rain-test.json` に保存される。

## 素材と実装の範囲

音声は `generate_paris_rain_audio.py` による独自の決定的な合成音。パリ現地の録音ではない。
同じシードから周期的なノイズと水滴を生成し、生成WAVのSHA-256、RMS、ピーク値を `Content/Data/paris-rain.json` に記録する。
再配布に外部の音源ライセンスは不要。生成WAVは中間成果物としてGit対象外、実際に使用するSoundWaveは `Content/Weather` に保存する。

局所的な水たまりの深さ、排水シミュレーション、屋根から流れる水の位置は未再現。
雨粒の屋根クリップは6mグリッドによる近似であり、狭い庇の縁は厳密ではない。水はねと聴取位置の遮蔽照会は実際の衝突形状を使う。
濡れの模様は景観用の推定であり、測量した水たまりではない。音量・音色の最終評価にはスピーカーまたはヘッドホンでの確認が必要。

UEの参照仕様: [Material Parameter Collections](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-material-parameter-collections-in-unreal-engine)。

## 2026-10-29 の実行結果

- UE 5.8 / AIWorldEditor / Win64 Development の最終ビルド成功。
- 雨アセット生成成功。実在する6つのWeatherアセットと11の湿潤対応PBR材質を保存。
- `RainLifecycleAndShelter` と既存の `PhotoEnvironmentAndCameraSwitching` の2件が成功。[実行ログ抜粋](paris-rain-automation.txt)、[検証値](paris-rain-test.json)。
- 雨テストでは約68秒相当を進め、雨粒の座標範囲、650粒の低画質予算、2層のステレオループ設定と再生状態、人工の遮蔽物の下でExposure=0になること、屋外への復帰、ミュート、晴天での停止と乾燥を確認。検証用のカメラ・屋根はテスト終了時に削除。
- WAVの形式・SHA-256・クリップの有無・左右の差・ループ境界が通常の過渡音より小さいことを確認。
- `Start-ParisDigitalTwin.ps1 -Photoreal -ThirdPerson -Rain` の起動を実行。GISは既存キャッシュを使用し、シーンSHA-256は変更前と同じ `4e51a9332f3bc44aea0820ee4fcc77d339083fff9c2f73d59a66e1737f5353bb`。既存GIS警告は残存。
- D3D12の実画面で雨粒、曇天、路面の反射を確認。シェーダー準備後の[スクリーンショット](paris-rain-preview.png)を保存。UEログに雨材質のコンパイル失敗なし。
- 音声出力先は `LG ULTRAWIDE (AMD High Definition Audio Device)`。音質の主観評価は未実施。
- AMD Radeon(TM) Graphics / 1280×720 / Medium / ScreenPercentage 80 / 三人称静止視点の20秒計測で平均33.28fps、P95 34.56ms。[計測結果](paris-rain-performance.json)。60fpsには未達。全地区や歩行中の性能を保証する計測ではない。

地形・舗装の既存の面の継ぎ目や傾斜は今回の天候改修では解消していない。
