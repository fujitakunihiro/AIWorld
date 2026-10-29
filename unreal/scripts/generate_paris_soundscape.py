"""Hash-verified field recordings, offline regeneration and original ferry synthesis."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT/'unreal/assets/paris-soundscape'
RATE = 48000
SUFFIX = dict(bell='Bell', crowd='Crowd', river='Seine', boat='Ferry', pigeon='Pigeon', siren='Siren')


def prepare(entry, offline):
    raw = ASSETS/'Raw'/entry['file']
    if not raw.exists():
        if offline: raise RuntimeError('Missing offline source: '+str(raw))
        raw.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(entry['url'], headers={'User-Agent': 'ParisDigitalTwinAudio/1.0 (asset acquisition)'})
        data = urllib.request.urlopen(req, timeout=45).read()
        if hashlib.sha256(data).hexdigest() != entry['sha256']: raise RuntimeError('Changed remote audio: '+entry['key'])
        raw.write_bytes(data)
    if hashlib.sha256(raw.read_bytes()).hexdigest() != entry['sha256']: raise RuntimeError('Changed cached audio: '+entry['key'])
    data, rate = sf.read(str(raw), dtype='float64', always_2d=True)
    # Mono sources let UE place the sound in the real world, rather than keeping
    # a baked stereo pan that contradicts the listener's heading.
    data = data.mean(axis=1)
    start = round(entry['start']*rate); count = round(entry['seconds']*rate)
    data = data[start:start+count]
    if len(data) < rate: raise RuntimeError('Recording too short: '+entry['key'])
    if rate != RATE: data = np.interp(np.arange(round(len(data)*RATE/rate))*rate/RATE, np.arange(len(data)), data)
    if entry['loop']:
        n = round(.6*RATE); w = np.linspace(0, 1, n)
        data = np.concatenate((data[n:-n], data[-n:]*(1-w)+data[:n]*w))
    else:
        n = min(round(.15*RATE), len(data)//8); data[:n] *= np.linspace(0, 1, n)
        n = min(round(.7*RATE), len(data)//5); data[-n:] *= np.linspace(1, 0, n)
    return data


def ferry():
    n = RATE*32; t = np.arange(n)/RATE; rng = np.random.default_rng(20261029)
    phase = 2*np.pi*(48*t+.18*32/(4*np.pi)*(1-np.cos(4*np.pi*t/32)))
    tone = sum(np.sin(phase*h+.13*h)/h**1.6 for h in range(1, 10))
    f = np.fft.rfftfreq(n, 1/RATE)
    noise = np.fft.irfft(np.fft.rfft(rng.normal(size=n))*(f/(f+35))/(1+(f/1600)**2), n=n)
    return .19*tone*(.94+.06*np.sin(2*np.pi*t/32*5))+.075*noise


def export(entry, data):
    data -= data.mean()
    rms = np.sqrt(np.mean(data*data)); peak = np.max(np.abs(data))
    target = dict(bell=.16, crowd=.09, river=.12, boat=.11, pigeon=.13, siren=.15)[entry['key']]
    gain = min(target/max(rms, 1e-9), .80/max(peak, 1e-9)); data *= gain
    if not np.isfinite(data).all() or len(data) < RATE: raise RuntimeError('Invalid audio buffer')
    path = ASSETS/'Generated'/(entry['key']+'.wav')
    sf.write(str(path), data, RATE, subtype='PCM_16')
    decoded, rate = sf.read(str(path), always_2d=True)
    if rate != RATE or decoded.shape[1] != 1 or np.max(abs(decoded)) >= .99: raise RuntimeError('Audio export verification failed')
    result = dict(entry, asset='/Game/Soundscape/A_Paris'+SUFFIX[entry['key']], generated_file=path.name,
                  generated_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  sample_rate=RATE, channels=1, duration_seconds=len(decoded)/RATE,
                  rms=float(np.sqrt(np.mean(decoded*decoded))), peak=float(np.max(abs(decoded))),
                  processing='Trim, stereo-to-mono where applicable, linear resample to 48kHz, DC removal, gain, fade/crossfade; PCM16')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--offline', action='store_true'); args = parser.parse_args()
    source = json.loads((ASSETS/'sources.json').read_text(encoding='utf-8'))
    (ASSETS/'Generated').mkdir(parents=True, exist_ok=True)
    entries = [export(e, prepare(e, args.offline)) for e in source['sources']]
    boat = dict(key='boat', title='Original inferred passenger-ferry diesel engine', author='Project Paris Digital Twin',
                page='', url='', license='Project-original', license_url='', loop=True,
                note='Original periodic harmonic/noise synthesis, not a recording of the rendered vessel.')
    entries.append(export(boat, ferry()))
    manifest = dict(recipe='paris_recorded_soundscape_v1', files=entries)
    (ASSETS/'Generated/manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({e['key']: dict(seconds=round(e['duration_seconds'], 3), peak=round(e['peak'], 3), sha256=e['generated_sha256']) for e in entries}))
