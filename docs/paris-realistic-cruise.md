# Seine sightseeing ferry

A 25.091 × 7.574 × 8.161 m original passenger ferry by [Innerscene](https://www.innerscene.com/tools/library/3d-parts/small-passenger-ferry-25-m-bb6ba356) is used as an inferred sightseeing vessel. The asset is CC0 1.0; its download URL and SHA-256 are recorded in `unreal/assets/paris-cruise/manifest.json`. It is not a scan of a specific Paris cruise ship. Its 12 supplied 2048 px base-color textures and material metallic/roughness constants are imported; the source does not supply normal or roughness maps. The glazing is a separate translucent mesh, while the opaque body supports Nanite and a fallback mesh.

The draft is an estimated 1.18 m; it is not a hydrostatic measurement. The water plane uses the existing Seine dataset and water material, with a small vertical bob. A deterministic 154.7 m straight route was selected from the OSM Seine polygon, with a vessel-sized circular clearance plus 1.5 m margin against the riverbank and all generated bridge footprints. The vessel accelerates, decelerates and turns at each end. It does not travel beneath bridges. The model, draft, route and motion are simulated and do not represent live vessel traffic.

## Use and reproduce

- Run `Paris-Cruise.cmd`, or run `unreal/scripts/Start-ParisDigitalTwin.ps1 -CruiseView -Quality Medium`. Press U to follow or leave the ship, F2 to return to the overview, F10 to hide the HUD.
- `unreal/scripts/Build-ParisCruise.ps1` downloads the verified source if necessary, recreates geometry and the route from the local water/bridge GIS data, and bakes Unreal assets. An already downloaded, hash-verified source also works offline. The existing Python GIS environment is required. Close the UE preview before rebuilding assets.
- `gis/.venv/Scripts/python.exe unreal/scripts/tests/test_paris_cruise.py` checks the complete rotation-safe route envelope, bridge clearance, dataset provenance, texture hashes and geometry buffers.
- `unreal/scripts/Test-ParisDigitalTwin.ps1 -Photoreal` runs the Unreal scene suite, including movement, turning, water level, selection and camera tests.
- `unreal/scripts/Measure-ParisDigitalTwin.ps1 -View Riverside -Photoreal -CruiseView -Quality Medium -Duration 10 -CaptureAfter 10 -CleanFrame -ReportPath docs/paris-cruise-performance.json -ScreenshotPath docs/screenshots/paris-cruise.png` captures an actual render and measures performance.

The current result has modeled rails, seating, wheelhouse, windows and deck fittings. The ship uses a simple visually animated route and bob, not a hydrodynamics simulation. No dedicated wake or passengers on board are implemented.
