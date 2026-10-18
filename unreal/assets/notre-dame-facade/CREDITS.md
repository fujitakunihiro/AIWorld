# Facade point-cloud research candidate

**Notre Dame Paris Facade - Hi Res Point Cloud**, embedded author: **UC San Diego – Digital Media Lab**. Current source account: **CHEI – UC San Diego**.

- [Original listing](https://sketchfab.com/3d-models/notre-dame-paris-facade-hi-res-point-cloud-50deeb164f324d1c8607bafa67f948b9)
- [Public Zenodo record](https://zenodo.org/records/10363984), published 6 May 2019.
- Object license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), confirmed by the original API, embedded GLB credit and Zenodo record.
- Reconstructed from 105 tourist photographs from Flickr and Wikimedia. This is historical, pre-restoration appearance. It is not a 2024/2026 survey.

The original file is retained without modification in the local cache and excluded from Git (405 MB). `fetch_notredame_facade.py` restores it and checks its published MD5 and byte count, then records SHA-256. A cloud of points is not a production-ready textured PBR mesh. It is not automatically placed over the cathedral. Acquisition does not imply architectural or visual acceptance.

Derived assets in `Content/ParisPhotoreal/NotreDameScan` and `facade-*.png` retain this CC BY 4.0 attribution. Adopted modifications: reconstructed 2.5D surfaces for the central and side portals, western rose and kings gallery; UV/normal/coverage atlas; median depth filtering; inferred completion up to 40cm distance, with a 60cm neighbor-depth limit; provisional width/height calibration against published dimensions. Adopted sampling is 1.25cm. A 5cm upper-tower tile with 20cm completion was tested and rejected for insufficient direct support and native visual quality. The upper arcade, towers, belfry openings and other unsupported areas retain authored geometry. Colour includes original photographed illumination; roughness is an estimate. These changes do not establish a modern survey, complete cathedral model or calibrated geographic registration. `paris-notredame-scan.json` records the transformation, source hashes, observed and inferred counts, interpolation and rejected candidates. Coverage includes interpolation and must not be reported as fully measured area. Point-cloud coverage is used to restore the existing authored fallback in unobserved areas.

Sparse depth estimates and inferred colour receive confidence-weighted regularization (10cm radius). Dense observations retain their fine detail after the common 3x3 depth filter. These artistic stabilization steps reduce reconstruction noise; they are not additional measurements or recovered sculptural detail. Mesh normals and tangents are recomputed; fine depth normals are sampled in world space.

The final side-portal selection starts at 5.2m above the local facade base, above the authored wooden doors and lintels. Lower side-door reconstructions were visually unstable and are not adopted. Authored doors remain an explicit fallback; this selection does not establish a complete or seamless reconstruction of those entrances.
