# セーヌ川の水面と護岸

`Paris-River.cmd` から写実・高品質の川を見るカメラで起動します。F10でメニューを非表示にできます。主人公の散策を含む通常の写実モードでも、中・高品質で新しい水面を使います。

- `M_SeineRiver` はUEのSingle Layer Waterを使い、光の散乱・吸収、天空と画面内の反射、屈折を描画します。金属度は0です。
- 1024pxのオリジナルのタイル可能な法線テクスチャを、異なる実寸スケールと流れる向きで3回サンプリングします。画面の遠方では細かい波を弱めます。旧水面の粗いメッシュ上下動は新素材では使いません。
- 元のOSMのセーヌ川ポリゴンから1024px・16bit相当の岸までの符号付き距離を生成し、岸際の色・粗さを変えます。距離画像は線形・非圧縮、法線は法線用圧縮で保存します。GIS範囲の切断端を河岸として扱いません。
- `M_ParisQuayWet` は既存の写真由来の石灰岩素材を複製し、水位付近の約1mに濡れ色・低い粗さ・不均一な水染みを加えます。
- 水面のポリゴン、水位、地理座標、橋の位置、歩行者の衝突は既存のデータを使います。噴水は従来素材を使います。
- 色、流れ、水の光学係数、染みは見た目の推定です。実測の水質、水深や流体シミュレーションの再現を意味しません。河川輪郭の出典と元データのSHA256は `Content/Data/paris-water.json` に記録します。

仕組みは [Epic公式のSingle Layer Water解説](https://dev.epicgames.com/documentation/en-us/unreal-engine/single-layer-water-shading-model-in-unreal-engine) に基づきます。既存の天空・照明・反射環境を利用し、ライトや川全体を映す追加カメラは増設しません。川の確認用の明示的な起動時だけ、既存の河岸カメラを川上の俯瞰位置に変更します。

## 再生成と比較

```powershell
# 元GISからオフラインで再生成。UEプレビューを閉じて実行:
./unreal/scripts/Build-ParisWater.ps1
./unreal/scripts/Build-AIWorldUE.ps1 -SkipAssets
./unreal/scripts/Start-ParisDigitalTwin.ps1 -RiverView -Quality High
# 同じ景色で従来の水面を比較:
./unreal/scripts/Start-ParisDigitalTwin.ps1 -RiverView -Quality High -LegacyWater
```

全体の写実素材生成にも川の生成工程を追加しています。起動スクリプトはGISの元データが変わった場合や素材が欠ける場合にも再生成します。川の品質はF7とMに連動します。パッケージで動的に読み込む素材も対象にするため、Materialsディレクトリをcook対象に加えました。パッケージビルドそのものは今回の検証範囲に含めません。

## 実画面

2026-10-26、UE 5.8.3 / D3D12 / SM6、1280×720・高品質で実描画を確認しました。平均43.52fps、フレーム時間95パーセンタイル25.96msです。暫定目標60fpsには未達です。計測は素材・シェーダーの準備が終わってから開始し、素材のコンパイルエラーはありませんでした。

- [改善後の水面](screenshots/paris-river-realistic.png)
- [同じカメラ位置の従来の水面](screenshots/paris-river-before.png)
- [改善後の計測結果](paris-river-high-performance.json)
- [従来の水面の計測結果](paris-river-before-performance.json)

色・光学係数はこのプロジェクトの照明環境で画面を確認して調整しています。草木・街並み自体の形状はこの変更の対象にしていません。

元GIS JSONのSHA256は `4e51a9332f3bc44aea0820ee4fcc77d339083fff9c2f73d59a66e1737f5353bb`、元メッシュblobは `fba61d4426bf6cc2fc40bda2818d48fe4a6d8e3c58bf13e025254ddc20bc97d8` で、変更前と一致しました。

既存のUE自動テスト23件がすべて成功しました。座標、衝突、橋の高さ、主人公の歩行・走行、住民、品質切替などを検証しています。水面を装飾用の非衝突メッシュと誤認しないよう、テスト側の水素材判定にもSingle Layer Waterを追加しました。
