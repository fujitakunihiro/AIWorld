# Near-field tree appearance asset

- Source: [Poly Haven, island_tree_01](https://polyhaven.com/a/island_tree_01)
- License: [CC0-1.0](https://polyhaven.com/license), including the model and its textures.
- Source geometry: 1,599,403 triangles; downloaded glTF plus 2K diffuse, OpenGL normal, ARM and leaf opacity maps.
- `manifest.json` pins the actual URLs, byte sizes, MD5 and SHA-256 checksums. `fetch_paris_nature.py` restores those files; it uses the pinned manifest before consulting the public catalog.
- Raw glTF, buffer and textures are ignored by Git and are reproducible from the manifest. Imported Unreal assets are in `/Game/ParisPhotoreal/Nature`.

This is a broadleaf **appearance proxy**, not identification of Paris tree species or a surveyed tree. The original OSM locations, source IDs, instance rotations and tagged/estimated dimensions remain unchanged. The source mesh is normalized to the existing 6m crown / 10m height envelope and its trunk is placed at ground level. Nearby trees use a shared Nanite mesh with masked, two-sided foliage; low quality restores the original lightweight prototype. Original trunk collision remains available.

The normal maps are converted from OpenGL convention by flipping their green channel. ARM channels are linear: R = AO, G = roughness. Leaf opacity comes from the dedicated linear alpha image, not the alpha channel of a JPEG.
