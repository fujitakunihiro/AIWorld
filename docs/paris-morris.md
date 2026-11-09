# パリの広告塔と街頭掲示板

フォトリアル版に、緑色のモリス広告塔と両面の街頭掲示板を追加する。保存済み OpenStreetMap スナップショットの `advertising=column` 7 地点と `advertising=poster_box` / `support=ground` 1 地点を利用する。初期の 500m 四方だけでなく、既存シーンの周辺範囲も含む。

各物体の位置は OSM のノード座標であり、[OpenStreetMap contributors / ODbL 1.0](https://www.openstreetmap.org/copyright) に由来する。例えば広告塔の一つは [node/9693401739](https://www.openstreetmap.org/node/9693401739)。地点の `lit` 等のタグは記録するが、広告の内容や塔の実測寸法を意味しない。形状、寸法、模様は写真を参考にした独自の推定デザイン、掲示物は AI 生成のイメージで、実物の外観や現在の広告を測量したものではない。

生成時に既存シーンの歩道・歩行面の三角形を検査し、塔の円形接地範囲の 98% 以上が歩行面に入り、周囲 1m を加えた円の 90% 以上も歩行面であり、車道・水面・橋と重ならず、建物・水辺・他の街路設備と所定の距離が取れる地点だけを採用する。足元の高さは歩行面の三角形から補間する。ノードの XY 座標は動かさず、安全条件を満たさない地点は拒否する。大型の物体なのでカプセル状の当たり判定を持つが、歩行者経路そのものは再生成しない。

元ノード ID、WGS84、UE 座標、元タグ、歩行面の被覆率と拒否理由は `unreal/AIWorld/Content/Data/paris-morris.json` に保存する。広告塔や掲示板をクリックすると ID、座標、位置と外観の出典区分が表示される。F6 で街路設備を隠すと表示と当たり判定が一緒に消える。

`Paris-Morris.cmd` をダブルクリックすると確認視点で起動する。PowerShell からは：

```powershell
./unreal/scripts/Start-ParisDigitalTwin.ps1 -MorrisView
```

再生成は `./unreal/scripts/Build-ParisMorris.ps1`、GIS と UE の確認は `./unreal/scripts/Test-ParisMorris.ps1`。オンライン API は不要だが、既存の OSM スナップショット、地形・実行用シーン、UE 5.8、固定済み GIS Python 環境と、保存済みポスター画像が必要。変更されたシーンとはハッシュを照合し、不一致の場合は表示を見合わせる。ポスター画像は保存済みの入力として扱うため、同じ入力からオフライン再生成できる。

ポスター画像は imagegen で制作した AI 生成イメージで、実在の広告の記録ではない。元画像 `unreal/assets/paris-morris/Source/paris-morris-posters-imagegen.png` を保存し、ハッシュを記録する。`generate_paris_morris_art.py` と `paris-morris-posters.png` は別の簡易な自作図案であり、現在の表示には使用していない。

目線の高さで撮影した[昼の実画面](paris-morris-preview.png)と[雨の夜の実画面](paris-morris-night-preview.png)。1280×720、Medium、画面倍率 80% の同視点での暫定計測は昼約 35 fps、雨の夜約 33〜36 fps で、目標の 60 fps は未達。数値はこの環境・視点での参考値であり、広告塔追加前との比較ではない。
