# 写真を参考にした花屋の店先

2026-11-08に提供された街路写真から、籐籠にあふれる切り花、段積み木箱、亜鉛色のバケツ、濃緑の店構えと布庇を立体モデルとして追加した。既存のOSM花屋4店舗の位置・向き・地面高を利用する。元の建物・道路・歩行者経路・店舗の選択IDを変更しない。写真の撮影場所をこれらの店舗と同定したものではなく、店先の外観は参考写真からの推定制作。

籠は横糸と縦の芯、巻き縁をメッシュで作り、木箱は隙間のある板、バケツは口縁を持つ。8組の花束には352本の茎と立体の葉、白・黄・ピンク・紫の花弁を使う。植生には両面の透過光、金属には金属度と粗さ、籠・木部・庇には細かな色変化を持つ専用PBR材を割り当てる。

8種類・155,394三角形のモデルを4店舗で共有する。HISMで描画し、50–75mでカリング。中央の幅1m・高さ2mに陳列を置かず、追加の衝突は付けない。既存庇の外側を緑の布で覆い、元の衝突は保持する。旧3鉢の表示と重複させず、素材未生成時や`-ParisTwinSimpleFlorists`指定時は旧表示へ戻る。F6、Low、GIS診断表示でも他の店舗小物と一緒に隠れる。

## 開き方

`Paris-Florist.cmd`をダブルクリックする。通常の写実モードでは **Z** で花屋に移動できる。**F8**で歩行、**F10**でHUD、**F6**で小物、**F7**で画質を切り替える。

専用起動では既存の祭り飾りを隠す。花屋の視点は左右の陳列への視線を確認し、街灯や木で花束が隠れる候補を避ける。カメラを壁から5m以上離して、庇と地面の籠まで画面に収める。

```powershell
./unreal/scripts/Build-ParisFlorist.ps1
./unreal/scripts/Capture-ParisFlorist.ps1 -View Before
./unreal/scripts/Capture-ParisFlorist.ps1 -View After
./gis/.venv/Scripts/python.exe -m unittest discover -s unreal/scripts/tests -p test_paris_florist.py -v
./unreal/scripts/Test-ParisFlorist.ps1
```

元写真は`unreal/assets/paris-florist/Raw/reference.png`にそのまま保存し、SHA256と使用範囲を`reference.json`に記録する。写真の人物・店名・画像ピクセルを3D材へ転写していない。Raw画像と再生成可能な大きな中間JSONはGitの対象外。今回追加の形状・マテリアルはオリジナル制作で、有料素材や外部APIを使わない。

写真は430×286pxの単一方向の参考画像であり、測量・フォトグラメトリによる実店舗の完全再現ではない。周辺建物や歩行者の写実品質は既存シーンの品質に依存する。

## 検証

UE 5.8.3のEditorターゲットをビルドし、形状の3テスト、UE内の新表示・旧表示の2回の店舗テストを実行した。モデルの再生成一致、有限座標、単位法線、三角形の面積と向き、入口の空き、共有モデルのロード、店舗位置の一致、衝突を付けないこと、F6での非表示、旧表示への復帰が成功。[UE内の検証記録](paris-florist-validation.json)。

DX12／SM6・High・1280×720・画面倍率100%で[変更後](paris-florist-after.png)と[変更前](paris-florist-before.png)を同じカメラで撮影する。比較では人物・車を非表示にし、素材と形状の表示を確認する。ベンチマーク値は各`paris-florist-*-performance.json`に記録し、通常の人物・車付きプレイの性能とは区別する。

AMD Radeon内蔵GPUでの18秒計測は変更前38.1fps、変更後36.6fps（P95 31.1ms）。短い計測の参考値であり、目標60fpsには届いていない。最終画像で籠の編み目、板の隙間、花と葉の密度、地面との接地、旧庇が表に出ないことを確認した。人物と車は比較撮影時のみ非表示で、通常起動では既存のシミュレーションが動く。

主な変更は`ParisShopfrontSigns.cpp`、花屋のカメラ候補を調整する`ParisDigitalTwin.cpp`、配置を登録する`AIWorld.Build.cs`、`Start-ParisDigitalTwin.ps1`、新しい生成・取り込み・検証・撮影スクリプト、`Content/ParisPhotoreal/Florist`の16アセット、`Content/Data/paris-florist.json`。変更前の作業ファイルは`backups/paris-before-florist-20261108-213826`に保存した。
