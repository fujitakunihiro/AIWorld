import type { EffectKind } from './renderer/effects';
export class VillageAudio {
  enabled = localStorage.getItem('ai-world-sound') === 'on';
  private context?: AudioContext;
  private last = 0;
  constructor() { document.addEventListener('pointerdown', () => { if (this.enabled) void this.unlock(); }, { passive: true }); }
  private async unlock() {
    try { this.context ??= new AudioContext(); if (this.context.state === 'suspended') await this.context.resume(); } catch { /* Sound is optional on unsupported browsers. */ }
  }
  async setEnabled(enabled: boolean) { this.enabled = enabled; localStorage.setItem('ai-world-sound', enabled ? 'on' : 'off'); if (enabled) { await this.unlock(); this.play('harvest'); } }
  play(kind: EffectKind) {
    if (!this.enabled || !this.context || this.context.state !== 'running' || document.hidden || performance.now() - this.last < 550) return;
    this.last = performance.now();
    const frequencies = kind === 'complete' || kind === 'arrival' ? [523, 659, 784] : kind === 'harvest' ? [440, 660] : kind === 'build' ? [170] : [260];
    frequencies.forEach((frequency, i) => {
      const context = this.context!, oscillator = context.createOscillator(), gain = context.createGain(), at = context.currentTime + i * .09;
      oscillator.type = kind === 'build' ? 'triangle' : 'sine'; oscillator.frequency.setValueAtTime(frequency, at); oscillator.frequency.exponentialRampToValueAtTime(frequency * .8, at + .1);
      gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(.035, at + .01); gain.gain.exponentialRampToValueAtTime(.0001, at + .17);
      oscillator.connect(gain); gain.connect(context.destination); oscillator.start(at); oscillator.stop(at + .18);
    });
  }
}
