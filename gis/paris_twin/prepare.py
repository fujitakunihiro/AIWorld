"""Reuse validated export inputs/products; restore the chosen district to UE."""
import shutil
import tempfile
from pathlib import Path
from .acquire import verify_cache
from .io import ROOT, paths, read, sha, generation_metadata

PRODUCTS=('Generated/scene.json','Generated/runtime.json','Generated/runtime-meshes.bin','Generated/business-placement.json','Generated/surface-validation.json','Generated/diagnostics.json',
          'Generated/map.html','Generated/map.svg','Generated/street-placement.json','Generated/pedestrian-network.json','Generated/traffic-network.json','Processed/district.json','Processed/features.wgs84.geojson')


def prepare(config):
    folders=paths(config);raw=verify_cache(config)
    checksums={name:item['sha256'] for name,item in raw['files'].items()}
    manifest_path=folders['Generated']/'generation-cache.json'
    cached=None
    if manifest_path.exists():
        try:
            manifest=read(manifest_path)
            valid=(manifest['district_id']==config['district_id'] and manifest['generation']==generation_metadata(config)
                   and manifest['raw_checksums']==checksums and set(manifest['products'])==set(PRODUCTS))
            if valid:
                for key,checksum in manifest['products'].items():
                    folder,name=key.split('/',1)
                    if sha(folders[folder]/name)!=checksum:valid=False;break
            if valid:cached=manifest
        except (ValueError,KeyError,OSError,TypeError):
            cached=None
    if not cached:
        from .normalize import normalize
        from .mesh import export
        return {**export(config,normalize(config)),'cached':False}
    native=ROOT/'unreal/AIWorld/Content/Data/paris-digital-twin.json'
    expected=cached['products']['Generated/scene.json']
    if not native.exists() or sha(native)!=expected:
        native.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=native.parent,suffix='.tmp',delete=False) as temp:
            temporary=Path(temp.name)
        try:
            shutil.copyfile(folders['Generated']/'scene.json',temporary)
            temporary.replace(native)
        finally:
            if temporary.exists():temporary.unlink()
    for source,name in [('runtime.json','paris-digital-twin-runtime.json'),('runtime-meshes.bin','paris-digital-twin-meshes.bin')]:
        target=native.parent/name
        if not target.exists() or sha(target)!=cached['products']['Generated/'+source]:
            from .runtime import write_bytes
            write_bytes(target,(folders['Generated']/source).read_bytes())
    return dict(native_file=str(native),sha256=expected,cached=True,**cached['statistics'])
