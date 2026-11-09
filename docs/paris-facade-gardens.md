# 上階へ広げた街の装飾

このページはv3段階の記録。現在の`Paris-Luxury.cmd`は、[通りの上空にも装飾を加えたv5](paris-street-garlands.md)を使う。

`paris_facade_gardens_v3` は、店先の花や灯りに加え、既存の窓辺と窓の間の壁にも装飾を追加する。対象は 9 棟・122 か所の窓辺、14 か所の布飾りと壁灯。既存の花箱がある 8 か所は本体を重ねず花だけを増やし、それ以外の 114 か所に新しい花箱を置く。

窓辺は既存の `paris-photo-frontages-source.json` の窓面、建物 ID、元メッシュ ID、四角形の番号、幅・高さ・法線を利用する。現地調査による窓や飾りの記録ではなく、保存済み GIS 建物に沿った既存の推定窓への推定装飾である。元のシーンとハッシュが一致する入力だけを使う。

対象は既存店舗がある建物の上階。実行用歩行面の高さを補間し、窓下端が地面から 3〜11m にある候補を選ぶ。花箱の最下部が歩道上空に十分収まることを確認する。布飾りと壁灯は、同一の壁・同一の階にある隣接窓の間を探し、他の窓面まで含めて開口部に重ならない候補に限定する。布飾りは歩道から 3m 以上の位置とする。

ワイン色・青・アイボリーの布と真鍮風の縁取り、緑の鉄製花箱、ピンク・紫・赤を含む花を組み合わせる。壁灯は既存の夜設定 `MPC_ParisNight.NightAmount` と連動して光る。追加の点光源や歩行者を妨げる衝突形状は作らない。花と布は原形を共有してインスタンス表示し、窓辺の細部は Medium で 70m まで描画する。

生成は `generate_paris_facade_gardens.py` と既存の `generate_paris_luxury.py` が担当し、共通の `paris-luxury.json` に出力する。各窓の元 ID と、既存の花箱を使うかどうか、地面からの高さ、布飾りの両隣の窓番号と壁の余白を保存する。配置とモデルは同じ入力から再生成できる。

`Paris-Luxury.cmd` は今回から上階も見える広い視点で起動する。カメラの高さは歩道から約 1.7m で、建物を見上げる。既存の寄った視点は `inspection_close_camera` として残す。

再生成・検証：

```powershell
./unreal/scripts/Build-ParisLuxury.ps1
./unreal/scripts/Test-ParisLuxury.ps1
./unreal/scripts/Capture-ParisLuxury.ps1 -View After -OutputPrefix paris-facades
./unreal/scripts/Capture-ParisLuxury.ps1 -View Night -OutputPrefix paris-facades
```

`Capture-ParisLuxury.ps1 -Close` を付けると前段階のカフェに寄った視点を使える。今回の広い視点と前段階の性能値は、見える範囲が異なるため直接比較できない。

C++ ビルド、Python 6 テスト、UE 6 テストが成功した。[検証記録](paris-facades-validation.json)、[昼の実画面](paris-facades-after.png)、[雨の夜の実画面](paris-facades-night.png) を保存する。確認視点は街路樹が前面をふさがない候補から選び、建物を正面寄りに見上げる。1280×720・Medium・画面倍率 80% で、この視点の短時間計測は昼約 33.2 fps、雨の夜約 31.4 fps。暫定目標の 60 fps は未達。
