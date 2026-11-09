# パリの照明と場所に応じた汚れ

同一の `Camera_Paris_Street` で昼・夕方・夜を撮影できる。画面のGキーで昼→夕方→夜に切り替えられる。再現用コマンドは `powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Capture-ParisLightingComparison.ps1`。

[昼](paris-lighting-comparison/Day.png) / [夕方](paris-lighting-comparison/Sunset.png) / [夜](paris-lighting-comparison/Night.png) / [調整前の夜](paris-lighting-comparison/Night-before.png)

夜のHDR環境光を40→70、露出補正を1.5→1.55とし、夕方の環境光・露出も調整。光源としての街灯・店舗灯・大聖堂の投光器、位置、プール数、品質別の影予算は保持する。中画質の比較では夜17灯・影2灯。値は景観向けの推定であり、現地で測定した照度や営業時間ではない。

窓の下460か所に雨筋、建物の根元97か所に飛沫汚れを追加。既存の推定窓の位置・向きと建物ID、建物部分の高さ・周辺地形に結び付け、入口付近は避ける。汚れは2つの表示専用メッシュにまとめ、衝突や影を作らず、低画質・平坦な材質表示・地物のデバッグ表示では隠す。石の目地には目地の内部に限る微細な汚れ、車道には既存の道路端距離と摩耗マスクによる煤を加えた。いずれも現地の汚れの測量値ではなく、位置に沿ってプロシージャルに推定した表現。

窓の近景の前後比較は `powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Capture-ParisWeatheringInspection.ps1`。再生成はプレビューを閉じて `powershell -NoProfile -ExecutionPolicy Bypass -File .\unreal\scripts\Build-ParisWeathering.ps1`。起動スクリプトは必要な2メッシュと材質の欠損を検出して再生成する。

変更前の地面修正を含む作業状態は `backups/paris-before-lighting-weather-*` に保存した。元の地理メッシュと建物・道路・窓の位置、衝突判定は変更していない。

UE 5.8 C++ Developmentビルド成功。UE内テスト8件は汚れ表示・品質切替・衝突なし、昼夕夜の環境光順序、街灯と影、視点、雨、元地形、音とミュート、PBR材質を確認した。[テストログ](paris-lighting-weathering-tests.txt)。Pythonでは同一入力の再生成と元GISバイナリ不変、窓下の位置・向きと基部の高さを確認した。

[窓下の汚れなし](paris-lighting-comparison/WeatheringBefore.png) / [汚れあり](paris-lighting-comparison/WeatheringAfter.png)。同一窓の同一視点で、追加した雨筋と壁際の汚れが実際に描画されることを目視確認した。画像はこの地区の推定窓を利用している。

同一カメラで壁の固定範囲をsRGB画像からサンプリングした平均は、調整前の夜17.8/255、調整後33.8/255。調整後の同範囲では昼59.4、夕方48.9、夜33.8だった。画像上の比較値で、実際の照度測定ではない。中画質の比較用オフスクリーン描画は昼28.9fps・夕方28.0fps・夜30.5fpsで、60fpsは未達。実際のプレイ性能は環境と視点により変わる。
