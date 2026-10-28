# Paris street shopfronts

The existing archived OpenStreetMap scene contains 395 inferred shopfronts and 49 inferred outdoor seating layouts. This layer adds authored signs to the 388 shopfronts with a nonempty mapped name. The shop name and category come from the archived OSM POI; the sign, typography, colour and facade assignment are inferred and are not a surveyed exterior or evidence that a business is currently open. OSM data © OpenStreetMap contributors, ODbL.

All signs use the existing storefront position and orientation, without changing the underlying GIS scene, selection, collisions, seating or pedestrian routes. One hierarchical instanced mesh draws the sign panels. A pool of 24 pairs of text components displays the closest names and category labels within 45 m; unnamed shops keep their original facade without a label. Signs have no collision and are hidden with street details, low quality or GIS debug views.

Use B to inspect a cafe, F8 to walk, F6 to toggle street details and F10 to hide the HUD. The cafe view now rejects camera positions behind or too close to the selected facade. Compare a clean frame with `unreal/scripts/Measure-ParisDigitalTwin.ps1 -View Cafe -Photoreal -Quality Medium -Duration 10 -CaptureAfter 10 -CleanFrame`; add `-NoShopSigns` to inspect the original shopfronts. The generated frame is `docs/screenshots/paris-shopfront.png`.

On the local AMD Radeon(TM) Graphics PC using UE 5.8.3 / D3D12 at 1280×720, Medium (80% internal resolution), the 10-second cafe measurement recorded 32.5 FPS and 33.2 ms P95. This short measurement is scene- and hardware-dependent and does not meet the provisional 60 FPS target. The surrounding architecture, shopfronts, furniture and interiors remain simplified/inferred; the result is not a photographic reconstruction of actual businesses.

## Grocery and restaurant details

The existing named `restaurant` POIs receive a small wall-mounted menu board; mapped `supermarket` and `convenience` POIs receive a shared produce crate and six generic pieces of produce. These objects occupy only the existing inferred shopfront envelope, are decorative and have no collision. The menu and goods are invented, not assertions about actual businesses or stock; the scene does not contain shop interiors or transactions. All objects and names hide together when street details are disabled. Press **I** to move to a grocery and **Y** to move to a restaurant; the view uses the same obstruction and pedestrian-spawn checks as the cafe view.

The current snapshot has 114 restaurant and 8 supermarket/convenience shopfronts with names. On the same PC and settings as above, 10-second grocery and restaurant inspection runs measured 44.2 and 47.4 FPS respectively. These are separate viewpoints and cannot be used as a before/after performance comparison. Screenshots and reports are `docs/screenshots/paris-grocery.png`, `docs/screenshots/paris-restaurant.png`, `docs/paris-grocery-performance.json` and `docs/paris-restaurant-performance.json`.

## Florists, bakeries and bookshops

The same inferred-frontage system adds flower pots with stems and petal clusters for `florist`, loaves for `bakery`, and books for `books`. The archived scene has 4 flower shops, 8 bakeries and 20 bookshops. These are small procedural display props, not licensed scans or verified goods; they are not photographic models and do not imply these shops have those displays. The props share instanced meshes, have no collision and are hidden together with street details/debug views. Press **Z**, **X** or **Q** to focus a flower shop, bakery or bookshop respectively. The selection and names remain linked to the source OSM point.

On the same local AMD integrated GPU, Medium and 1280×720 (80% internal resolution), 10-second inspection runs measured 43.5 FPS for the flower shop, 42.7 FPS for the bakery and 45.9 FPS for the bookshop. These are distinct views, not a controlled performance comparison. See `docs/screenshots/paris-florist.png`, `docs/screenshots/paris-bakery.png`, `docs/screenshots/paris-bookshop.png` and the corresponding performance JSON files.
