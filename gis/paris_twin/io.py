import hashlib
import json
import re
import tempfile
import importlib.metadata
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,suffix='.tmp',delete=False,encoding='utf-8',newline='\n') as temporary:
        temporary.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n')
        name=temporary.name
    try:
        Path(name).replace(path)
    finally:
        if Path(name).exists():Path(name).unlink()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generation_metadata(config):
    source=hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        source.update(path.name.encode());source.update(path.read_text(encoding='utf-8').replace('\r\n','\n').encode())
    return {'config_sha256':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),
            'generator_sha256':source.hexdigest(),'python':platform.python_version(),
            'packages':{name:importlib.metadata.version(name) for name in ['numpy','shapely','pyproj','certifi']}}


def paths(config):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',config['district_id']):
        raise ValueError('District ID must be a simple directory name')
    base = ROOT / 'gis' / 'Data'
    return {k:base/k/config['district_id'] for k in ['Raw','Processed','Generated']}
