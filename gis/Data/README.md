# Data provenance and licensing

Rawのmanifestに、各ファイルの取得元URL、取得日時、SHA-256、ライセンスを記録しています。

- OpenStreetMap: © OpenStreetMap contributors, ODbL 1.0. https://www.openstreetmap.org/copyright
- Paris Volumes bâtis: Direction de l'Urbanisme – Ville de Paris, ODbL（取得したdataset metadataの値）。https://opendata.paris.fr/explore/dataset/volumesbatisparis/
- IGN RGE ALTI: IGN, Licence Ouverte / Open Licence Etalab 2.0. https://www.etalab.gouv.fr/licence-ouverte-open-licence/
- IGN BD TOPO bâtiments: IGN, Licence Ouverte / Etalab 2.0。`heights/` に867件の3D輪郭と高さ、WFSページ、XSD、取得URL・SHA-256を保存。https://www.data.gouv.fr/datasets/bd-topo-r

OSMとParis Dataに基づく正規化・派生データベースはODbL条件を引き継ぎます。このデータ条件は、プログラムコードのライセンスとは別です。サービスAPIと情報取得の日時はデータの測量日時を意味しません。

`osm-map.xml.gz`と各relation XMLのgzipは、解凍すれば取得時のXMLバイト列に戻ります。`osm.json`はこれをID・タグ・緯度経度・relation member geometryを保持してJSONへ読み直したものです。元のXMLは改変しません。

Paris Dataの歴史的な`x`,`y`列をEPSG:2154と仮定しません。公開GeoJSONのWGS84 geometryから変換します。`h_et_max`は地上階数の情報であり実測メートル高ではありません。詳細な形状・階数・出典区分はRawに保持しています。

IGN APIから121点のNGF-IGN69標高を取得しました。80m間隔の試験的サンプルです。1m DEMを同梱した、あるいは水位を実測したという意味ではありません。

BD TOPOの `hauteur` と3D輪郭のZは建物輪郭・軒の情報です。尖塔や棟の最高点と同一ではありません。IGNの取得方法、精度、更新日を保持し、地面のNGF標高を引いて相対高さへ変換します。推定した屋根の形・向き・高さは別の属性として保存します。実測データの最新性や現地の詳細再現を保証するものではありません。属性の根拠: https://bdtopoexplorer.ign.fr/batiment
