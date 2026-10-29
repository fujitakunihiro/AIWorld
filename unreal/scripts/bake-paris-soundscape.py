"""Import actual generated mono WAVs and preserve source/license metadata."""
import hashlib
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'unreal/assets/paris-soundscape/Generated'
CONTENT = ROOT/'unreal/AIWorld/Content'
assets = unreal.EditorAssetLibrary; tools = unreal.AssetToolsHelpers.get_asset_tools()
assets.make_directory('/Game/Soundscape'); (CONTENT/'Soundscape').mkdir(parents=True, exist_ok=True)
manifest = json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
for entry in manifest['files']:
    wav = SOURCE/entry['generated_file']
    if hashlib.sha256(wav.read_bytes()).hexdigest() != entry['generated_sha256']: raise RuntimeError('Changed WAV: '+str(wav))
    path = entry['asset']; name = path.rsplit('/', 1)[1]
    sound = assets.load_asset(path) if assets.does_asset_exist(path) else None
    if not sound or assets.get_metadata_tag(sound, 'ParisSound.SHA256') != entry['generated_sha256']:
        task = unreal.AssetImportTask(); task.set_editor_properties(dict(filename=str(wav), destination_path='/Game/Soundscape', destination_name=name, automated=True, replace_existing=True, save=True))
        tools.import_asset_tasks([task]); sound = assets.load_asset(path)
    if not isinstance(sound, unreal.SoundWave): raise RuntimeError('Missing SoundWave: '+path)
    sound.set_editor_properties(dict(looping=entry['loop'], volume=1.))
    for key, value in dict(SHA256=entry['generated_sha256'], SourcePage=entry['page'], Author=entry['author'], License=entry['license'], LicenseURL=entry['license_url'], Processing=entry['processing']).items():
        assets.set_metadata_tag(sound, 'ParisSound.'+key, value)
    if not assets.save_loaded_asset(sound, only_if_is_dirty=False): raise RuntimeError('Sound save failed: '+path)
(CONTENT/'Data/paris-soundscape.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
unreal.log('PARIS_SOUNDSCAPE_ASSETS_READY')
