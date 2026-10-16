# Facade point-cloud research candidate

**Notre Dame Paris Facade - Hi Res Point Cloud**, embedded author: **UC San Diego – Digital Media Lab**. Current source account: **CHEI – UC San Diego**.

- [Original listing](https://sketchfab.com/3d-models/notre-dame-paris-facade-hi-res-point-cloud-50deeb164f324d1c8607bafa67f948b9)
- [Public Zenodo record](https://zenodo.org/records/10363984), published 6 May 2019.
- Object license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), confirmed by the original API, embedded GLB credit and Zenodo record.
- Reconstructed from 105 tourist photographs from Flickr and Wikimedia. This is historical, pre-restoration appearance. It is not a 2024/2026 survey.

The original file is retained without modification in the local cache and excluded from Git (405 MB). `fetch_notredame_facade.py` restores it and checks its published MD5 and byte count, then records SHA-256. A cloud of points is not a production-ready textured PBR mesh. It is not automatically placed over the cathedral. Acquisition does not imply architectural or visual acceptance.

Derived assets in `Content/ParisPhotoreal/NotreDameScan` and `facade-*.png` retain this CC BY 4.0 attribution. Modifications: selected central portal, western rose and kings-gallery 2.5D surfaces, UV/normal/coverage maps, median depth filtering, inferred completion up to 40cm distance from observations and a provisional width/height calibration against published dimensions. Colour includes original photographed illumination; roughness is an estimate. These changes do not establish a modern survey, complete cathedral model or calibrated geographic registration. `paris-notredame-scan.json` records the transformation, source hashes, inferred interpolation and remaining holes. Point-cloud coverage is used to restore the existing authored fallback in unobserved areas.
