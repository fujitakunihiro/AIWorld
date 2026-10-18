# Optional personal, noncommercial sculpture

**Notre-Dame de Paris - Virgin Mary** by **Benoît Rogez / shadows44**.

- Original: https://sketchfab.com/3d-models/notre-dame-de-paris-virgin-mary-b5bbdc379daa4ee19e3775bb179dbcc1
- Author: https://sketchfab.com/shadows44
- License: **CC BY-NC 4.0**, https://creativecommons.org/licenses/by-nc/4.0/
- Legal text: https://creativecommons.org/licenses/by-nc/4.0/legalcode
- Public redistribution: Ai2 Objaverse, https://huggingface.co/datasets/allenai/objaverse
- Model file license remains CC BY-NC 4.0; the dataset's ODC-By database license does not replace it.
- Original GLB SHA256: `73c16fb28067adc8480f8719192329b66ac8b84b1ceff8193d8a0245923a1b54`.

The author describes a photo scan of the western Portal of the Virgin, from
photos shot in 2012 or 2013 and processed in Agisoft Metashape. This is a
historical photo reconstruction, not a current survey.

Changes: upper canopy cropped; root-node transform applied; mesh combined,
converted into UE centimetres and aligned provisionally to the left trumeau.
The right-handed glTF basis is reflected into UE's left-handed basis for both
positions and normals. The northern/viewer-left portal is +14m in this facade
frame, verified against the cathedral's official west-facade description:
https://www.notredamedeparis.fr/comprendre/architecture/la-facade-occidentale/
Original UV colour is retained, lit with estimated roughness and an explicit
colour multiplier. Dimensions and alignment are estimates. No unseen back
surface, measured PBR maps or additional texture resolution is claimed.

The user explicitly authorized personal noncommercial use on 2026-10-17.
Original downloads and derived UE assets are optional local files, ignored by
Git. They are **not** relicensed under the code license. `-ParisTwinNoNCStatues`
disables this layer and restores the original figure. Missing assets also
restore the original figure. `Build-ParisCathedralDetails.ps1
-NoncommercialStatue` explicitly acquires and bakes this optional content.

The separate central Jesus Christ candidate has not been downloaded or adopted.
This Virgin model is never reused as a substitute for another portal's saint.
