# Pedestrian source assets

Microsoft Rocketbox Avatar Library, copyright (c) 2020 Microsoft, **MIT**.
Source: https://github.com/microsoft/Microsoft-Rocketbox
Pinned revision: `0943055db6ec570bcef9f2c8b41c9e5467c808f9`.
Full permission notice: [LICENSE.md](LICENSE.md). Per-file URLs and SHA256: [sources.json](sources.json).

Subset: Male_Adult_01 / Female_Adult_01, their head/body/hair textures, and matching walk, run, breathing idle and seated breathing animation clips. Avatars represent simulated pedestrians and the playable protagonist, not observed individuals in Paris.

UE adaptation: original skeleton and skin weights, imported at real centimetre scale; texture-driven dielectric clothing and skin, masked two-sided hair; locomotion is driven by the existing route simulation, with root translation locked. Original specular maps inform approximate roughness (not measured PBR roughness). Texture data are capped at 2048px. Near characters use a bounded skeletal pool; the existing lightweight crowd remains available at distance and when optional assets are absent.

Reproduce the meshes, textures and crowd clips: `unreal/scripts/Build-ParisPeople.ps1`; cached inputs can be used with `-Offline`. Raw source copies are cached locally under `Raw/` and excluded from Git; the imported assets and MIT permission notice may be redistributed under this license.

The same source package includes matching `m_run_neutral_01.max.fbx` and `f_run_neutral_01.max.fbx` clips for the playable protagonist. Both are imported with root translation locked and speed matched to UE character movement; the male avatar is currently used for player control.
