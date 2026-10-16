"""Read-only inventory of actual Paris assets and renderer prerequisites."""
import argparse
import configparser
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def asset_file(project, package):
    if not isinstance(package, str) or not package.startswith('/Game/'):
        return None
    relative = Path(package[6:] + '.uasset')
    if '..' in relative.parts or relative.is_absolute():
        return None
    target = (project / 'Content' / relative).resolve()
    return target if target.is_relative_to((project / 'Content').resolve()) else None


def validate_registry(registry, project, textures):
    errors, inventory = [], []
    if registry.get('format') != 'paris_photoreal_assets_v1':
        errors.append('Unsupported asset registry format')
    source = json.loads((textures / 'manifest.json').read_text(encoding='utf-8-sig'))
    for item in registry.get('existing_sets', []):
        material = asset_file(project, item.get('material'))
        if not material or not material.is_file():
            errors.append(f"Missing current UE material: {item.get('id')}")
        if item.get('surface_layout') != 'ARH' or item.get('normal_source') != 'world_height_derivatives':
            errors.append(f"Current surface packing/normal declaration mismatch: {item.get('id')}")
        files = []
        for suffix in ('basecolor', 'surface'):
            name = f"{item['recipe']}_{suffix}.png"
            path = textures / name
            package = f"/Game/Textures/T_Paris{item['recipe']}{suffix.title()}"
            texture_asset = asset_file(project, package)
            if not path.is_file() or not texture_asset.is_file():
                errors.append(f'Missing current texture: {name}')
                continue
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != source['files'].get(name):
                errors.append(f'Texture hash mismatch: {name}')
            if data[:8] != b'\x89PNG\r\n\x1a\n':
                errors.append(f'Invalid PNG: {name}')
                continue
            width, height = struct.unpack('>II', data[16:24])
            files.append(dict(file=name, width=width, height=height, ue_asset=package))
        inventory.append(dict(id=item['id'], status='generated_in_repo', material=item['material'],
                              textures=files, photographic_reference=False, surface_layout='ARH'))
    for item in registry.get('required_assets', []):
        if item.get('status') != 'missing' or item.get('ue_asset') is not None:
            errors.append(f"Unverified required asset cannot be marked available or bound: {item.get('id')}")
    return errors, inventory


def audit(root=ROOT, engine=Path('D:/Epic Games/UE_5.8')):
    project = root / 'unreal/AIWorld'
    registry = json.loads((root / 'unreal/assets/paris-photoreal-assets.json').read_text(encoding='utf-8-sig'))
    errors, inventory = validate_registry(registry, project, root / 'unreal/textures/paris')
    spec=importlib.util.spec_from_file_location('paris_photo_sources',root/'unreal/scripts/paris_photo_sources.py')
    photo=importlib.util.module_from_spec(spec);spec.loader.exec_module(photo)
    photo_folder=root/'unreal/textures/paris-photo'
    manifest=json.loads((root/registry['photographic_manifest']).read_text(encoding='utf-8'))
    errors.extend(photo.validate(manifest,photo_folder))
    for entry in manifest['sets']:
        material='/Game/Materials/'+entry['material']
        packages=[material]+['/Game/Textures/T_ParisPhoto'+entry['key'].title()+role.title() for role in entry['maps']]
        for package in packages:
            if not asset_file(project,package).is_file():errors.append('Missing imported UE photo asset: '+package)
        inventory.append(dict(id=entry['id'],status='bundled_cc0_photographic_proxy',material=material,
            surface_layout='ORM',normal_convention='DirectX',source_url=entry['source_url'],paris_site_reference=False))
    if not asset_file(project,'/Game/Textures/T_ParisDayEnvironment').is_file():errors.append('Missing imported HDR cubemap')
    ini = configparser.ConfigParser(strict=False, interpolation=None)
    ini.read(project / 'Config/DefaultEngine.ini', encoding='utf-8-sig')
    renderer = dict(ini['/Script/Engine.RendererSettings'])
    pcg = engine / 'Engine/Plugins/PCG/PCG.uplugin'
    runtime_log = root / 'docs/paris-street-realism-native-tests.log'
    if not runtime_log.is_file():runtime_log=root/'docs/paris-twin-render-compact-tests.log'
    log = runtime_log.read_text(encoding='utf-8-sig', errors='replace') if runtime_log.is_file() else ''
    gpu_file = root / 'docs/paris-gpu-capabilities.json'
    gpu = json.loads(gpu_file.read_text(encoding='utf-8-sig')) if gpu_file.is_file() else None
    performance_file = root / 'docs/paris-street-realism-performance.json'
    if not performance_file.is_file():performance_file=root/'docs/paris-twin-render-isolated-cache-performance.json'
    if not performance_file.is_file():
        performance_file = root / 'docs/paris-twin-render-overview-performance.json'
    performance = json.loads(performance_file.read_text(encoding='utf-8-sig')) if performance_file.is_file() else {}
    observed_dx11 = performance.get('rhi', '').startswith('DX11')
    gi_configured = renderer.get('r.dynamicglobalilluminationmethod') == '1'
    vsm_configured = renderer.get('r.shadow.virtual.enable', '').lower() in ('1', 'true')
    return dict(format='paris_rendering_audit_v1', errors=errors,
                engine=json.loads((engine / 'Engine/Build/Build.version').read_text(encoding='utf-8-sig')),
                gpu_capability_probe=gpu, renderer_settings=renderer,
                default_rhi=ini['/Script/WindowsTargetPlatform.WindowsTargetSettings'].get('defaultgraphicsrhi'),
                features={
                    'nanite': dict(current_use=False if observed_dx11 else None, reason='Observed DX11 excludes Nanite; pipeline uses runtime fast-build visuals with no Nanite asset build'),
                    'lumen': dict(configured_gi=gi_configured, current_use=False if not gi_configured else None, reason='Enabling config alone cannot verify offline cards/SDF or Lumen rendering'),
                    'virtual_shadow_maps': dict(configured=vsm_configured, current_use=False if observed_dx11 or not vsm_configured else None),
                    'pbr_materials': dict(current_use=True, generated_sets=sum(x['status']=='generated_in_repo' for x in inventory), photographic_sets=len(manifest['sets'])),
                    'pcg': dict(installed=pcg.is_file(), loaded_in_observed_run='Mounting Engine plugin PCG' in log, authored_graph_in_use=False),
                    'world_partition': dict(current_use=False if 'world_partition=0' in log else None, observed_runtime_disabled='world_partition=0' in log),
                    'hlod': dict(current_use=False, custom_render_cache_is_hlod=False, reason='No World Partition HLOD layers/actors/build; exact visual copies, no simplification')},
                observed_performance=performance_file.name if performance else None,
                current_assets=inventory, environment=manifest['environment'],required_assets=registry['required_assets'],
                note='Filesystem/config/log audit. UE load/render verification is recorded separately in native tests and screenshots; DX12 rendering has not been tested.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, default=Path('D:/Epic Games/UE_5.8'))
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/paris-rendering-audit.json')
    args = parser.parse_args()
    result = audit(engine=args.engine)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(errors=result['errors'], generated_sets=result['features']['pbr_materials']['generated_sets'],photographic_sets=result['features']['pbr_materials']['photographic_sets'],
                         missing_groups=len(result['required_assets'])), ensure_ascii=True))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
