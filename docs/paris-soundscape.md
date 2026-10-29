# パリの環境音

ノートルダムの鐘、市場のざわめき、セーヌ川、船のエンジン、鳩、フランスの二音サイレンを追加した。既存の雨・水滴も同じミュート操作にまとめている。

`Paris-Night.cmd -Rain` で雨の夜を起動。Gで昼→夕→夜、Rで晴雨、F11で環境音全体のミュート／再開。F12を押すたび、鐘→ざわめき→川→船→鳩→サイレンの順に各最大9秒の試聴ができる。試聴は位置に依存しない。通常の再生は位置と距離に依存する。

## 音源と配置

| 音 | 使用音源 | 配置と動作 |
| --- | --- | --- |
| 鐘 | ノートルダムのEmmanuelの歴史的な録音 | 大聖堂の南塔付近。初回10秒、その後4～7分おき。時刻・礼拝予定の再現ではない |
| ざわめき | パリ・バスティーユの市場録音 | OSM上の飲食店・食品店・花屋等から近い2点。夜は音量を下げる。地区内の実際の市場営業や人出の記録ではない |
| 川 | セーヌ川の録音 | 実際の河川ポリゴンの河岸に沿って、聴取者に近い水際へ音源を移す |
| 船 | オリジナルのエンジン合成音 | 既存の遊覧船に追従し、速度に応じてピッチを変える。実船の機関録音ではない |
| 鳩 | 鳩の実録音 | 地理データにあるベンチ・街路樹付近の推定位置。間欠再生し、夜・雨は控えめにする |
| サイレン | フランス警察の二音サイレンを作者が再現した音源 | 初回65秒、その後約2～4分おき。45～230m先の走行車の軌跡に追従し、接近・遠ざかりでピッチが変わる。専用の緊急車両モデルは未追加 |

常設の空間音源は7個（市場2個、他各1個）と試聴用1個に制限。音はmono 48kHzで、UEの距離減衰・建物による遮音と高域減衰を使用する。範囲外のループは停止する。サイレンは車両が再配置された際にも停止し、音源の瞬間移動を抑える。

録音元・作者・ライセンス・加工内容は [CREDITS](../unreal/assets/paris-soundscape/CREDITS.md)、ダウンロードURLとSHA-256は [sources.json](../unreal/assets/paris-soundscape/sources.json) に記録。サイレンの加工済み音声はCC BY-SA 4.0。Freesoundは公開HQプレビューを使用した。

## 実装と再生成

- `unreal/AIWorld/Source/AIWorld/ParisSoundscape.{h,cpp}`：配置、減衰、間欠イベント、昼夜・天候、船／車両追従、ミュート、試聴。
- `ParisDigitalTwin.cpp`：シーン起動、F11/F12、計測値の連携。
- `unreal/scripts/generate_paris_soundscape.py`：検証済みダウンロード、加工、合成、WAV・マニフェスト出力。
- `bake-paris-soundscape.py`：6個のSoundWaveを作成し、出典情報もアセットに保存。
- `Build-ParisSoundscape.ps1`／`Test-ParisSoundscape.ps1`：再生成とネイティブテスト。`Start-ParisDigitalTwin.ps1`は欠損音声を検出する。
- `unreal/AIWorld/Content/Soundscape/`：実際に生成した6個のSoundWave。`Content/Data/paris-soundscape.json`に加工結果を保存。

エディタ／プレビューを終了して実行する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-AIWorldUE.ps1 -SkipAssets
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-ParisSoundscape.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Test-ParisSoundscape.ps1
.\Paris-Night.cmd -Rain
```

取得済みRawと固定バージョンのPython依存関係があれば、`Build-ParisSoundscape.ps1 -Offline`でネット接続なしに再生成できる。RawとGenerated WAVはGit対象外。生成済みUEアセットを使う通常起動にはダウンロード不要。`-MuteSound`は初期状態で環境音をミュートする。

## 実際に検証した内容

UE 5.8 C++ビルド、オフライン音声生成、6音源のインポートを実行。ネイティブテストは音源の再生状態、地理ID追跡、河岸に沿う音源位置、船への追従、空間減衰・遮音設定、昼夜の音量差、固定音源数、共通ミュート、ミュート中の試聴抑止を確認した。夜景・雨・視点切替を含む4テストが成功。

同一Rawから再生成した6個のWAVのSHA-256一致、mono 48kHz、無音でないこと、クリッピングがないこと、ループの継ぎ目に突出した段差がないことも確認した。[音声検証](paris-soundscape-audio-validation.json)、[ネイティブ検証](paris-soundscape-test.json)、[テスト結果](paris-soundscape-automation.txt)を参照。

これは音声エンジンとデータの検証であり、実際のスピーカー出力を聴取して音質評価したという意味ではない。歩きながらの音量バランスはF11/F12を使って確認できる。実空間の音響測定、専用の警察車両、会話AI、実際の鐘の運行時刻は未実装。

雨・夜・三人称・1280×720・ScreenPercentage 80・Mediumで実画面を起動し、LG ULTRAWIDEの48kHz出力初期化、環境音8チャンネル、鐘の自動イベント発火、船との関連付けを確認した。25秒計測は約30.7fps（p95約38.3ms）。この値は描画を含む全体性能であり、音声処理単体の速度比較ではない。[実画面計測](paris-soundscape-performance.json)。
