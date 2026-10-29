"""Deterministic original stereo rain synthesis, with a periodic loop boundary."""
import hashlib
import json
from pathlib import Path
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT/'unreal/assets/paris-weather/Generated'
RATE, SECONDS = 48000, 32


def generate(kind):
    rng = np.random.default_rng(20261029 + (kind == 'runoff'))
    count = RATE*SECONDS
    freq = np.fft.rfftfreq(count, 1/RATE)
    result = np.zeros((count, 2), np.float64)
    for channel in range(2):
        # Periodic filtered noise is seamless without a crossfade dip.
        raw = rng.normal(size=count)
        spectrum = np.fft.rfft(raw)
        response = (freq/(freq+180)) / np.sqrt(1+(freq/2800)**2)
        response /= np.sqrt(np.maximum(freq, 120)/500)
        bed = np.fft.irfft(spectrum*response, n=count)
        t = np.arange(count)/RATE
        swell = .9+.06*np.sin(2*np.pi*t/SECONDS*3)+.04*np.sin(2*np.pi*t/SECONDS*7+channel*.3)
        result[:, channel] = bed*swell*(.10 if kind == 'rain' else .012)
    # Thousands of small, decorrelated impacts instead of an audible white hiss.
    events = 19000 if kind == 'rain' else 600
    for _ in range(events):
        start = rng.integers(count)
        duration = rng.uniform(.006, .045) if kind == 'rain' else rng.uniform(.025, .10)
        n = int(duration*RATE)
        t = np.arange(n)/RATE
        decay = np.exp(-t/(duration*.20))*(1-np.exp(-t*5000))
        pitch = rng.uniform(900, 6500) if kind == 'rain' else rng.uniform(450, 2300)
        impact = (.7*rng.normal(size=n)+.3*np.sin(2*np.pi*pitch*t))*decay
        impact *= rng.uniform(.025, .16) if kind == 'rain' else rng.uniform(.06, .26)
        pan = rng.uniform(-1, 1)
        indices = (start+np.arange(n)) % count
        for c, gain in enumerate((np.sqrt((1-pan)/2), np.sqrt((1+pan)/2))):
            result[indices, c] += impact*gain
    result -= result.mean(axis=0)
    peak = float(np.max(np.abs(result)))
    result *= min(1., .80/max(peak, 1e-9))
    pcm = np.rint(result*32767).astype('<i2')
    path = DEST/f'{kind}.wav'
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(RATE); out.writeframes(pcm.tobytes())
    return dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                seconds=SECONDS, sample_rate=RATE, channels=2,
                rms=float(np.sqrt(np.mean((pcm/32768.)**2))), peak=float(np.abs(pcm.astype(float)).max()/32768),
                seam_jump=float(np.abs(pcm[0].astype(float)-pcm[-1]).max()/32768))


if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    data = dict(recipe='original_periodic_stereo_rain_v1', provenance='Original deterministic procedural synthesis; no field recording or external audio assets.',
                files={kind: generate(kind) for kind in ('rain', 'runoff')})
    (DEST/'manifest.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data))
