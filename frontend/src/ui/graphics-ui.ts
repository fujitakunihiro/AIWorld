import type { Benchmark, GraphicsSettings, RenderMetrics } from '../renderer/graphics';
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const select = (id: string, valid: string[], fallback: string, key = `ai-world-${id}`) => {
  const value = localStorage.getItem(key); $<HTMLSelectElement>(id).value = value && valid.includes(value) ? value : fallback;
};
export class GraphicsUI {
  onChange: (settings: GraphicsSettings) => void = () => {};
  onMeasure: () => void = () => {};
  private measuring = false;
  constructor() {
    select('graphic-style', ['diorama', 'classic'], 'diorama');
    select('render-quality', ['auto', 'low', 'medium', 'high'], 'auto', 'ai-world-quality');
    select('render-distance', ['near', 'standard', 'far'], 'standard');
    for (const id of ['render-shadows', 'render-ao']) $<HTMLInputElement>(id).checked = localStorage.getItem(`ai-world-${id}`) !== 'off';
    for (const id of ['graphic-style', 'render-quality', 'render-distance', 'render-shadows', 'render-ao', 'light-preview']) $(id).onchange = () => this.apply();
    $('measure-graphics').onclick = () => {
      this.measuring = true; $('measure-graphics').setAttribute('disabled', '');
      $('graphics-benchmark').textContent = '1秒間の準備後、10秒間の描画を測定します。設定とカメラをそのままにしてください。';
      this.onMeasure();
    };
  }
  apply() {
    const settings: GraphicsSettings = {
      style: $<HTMLSelectElement>('graphic-style').value as GraphicsSettings['style'],
      quality: $<HTMLSelectElement>('render-quality').value as GraphicsSettings['quality'],
      distance: $<HTMLSelectElement>('render-distance').value as GraphicsSettings['distance'],
      preview: $<HTMLSelectElement>('light-preview').value as GraphicsSettings['preview'],
      shadows: $<HTMLInputElement>('render-shadows').checked, ao: $<HTMLInputElement>('render-ao').checked
    };
    for (const [id, value] of [['graphic-style', settings.style], ['quality', settings.quality], ['render-distance', settings.distance], ['render-shadows', settings.shadows ? 'on' : 'off'], ['render-ao', settings.ao ? 'on' : 'off']]) localStorage.setItem(`ai-world-${id}`, value);
    const disabled = settings.style === 'classic';
    for (const id of ['render-shadows', 'render-ao']) $<HTMLInputElement>(id).disabled = disabled || settings.quality === 'low';
    if (this.measuring) this.benchmark(null);
    this.onChange(settings);
  }
  notice(text: string) { $('graphics-notice').textContent = text; }
  metrics(metrics: RenderMetrics) {
    const quality = { low: '低', medium: '中', high: '高' }[metrics.effectiveQuality as 'low' | 'medium' | 'high'];
    $('graphics-metrics').textContent = `${metrics.fps.toFixed(1)} FPS · フレーム95% ${metrics.frameP95.toFixed(1)} ms · CPU描画 ${metrics.cpuMs.toFixed(1)} ms\n品質 ${quality} · ${metrics.width}×${metrics.height} · 解像度倍率 ${metrics.ratio.toFixed(2)}\n描画呼び出し ${metrics.calls} · 三角形 ${metrics.triangles.toLocaleString()} · 影 ${metrics.shadowSize || 'OFF'} · AO ${metrics.post ? 'ON' : 'OFF'}\nジオメトリ ${metrics.geometries} · テクスチャ ${metrics.textures}\n${metrics.gpu}`;
  }
  benchmark(result: Benchmark | null) {
    this.measuring = false; $('measure-graphics').removeAttribute('disabled');
    if (!result) { $('graphics-benchmark').textContent = '測定を中止しました。設定を決めて再測定できます。'; return; }
    const m = result.metrics;
    $('graphics-benchmark').textContent = `${result.seconds.toFixed(1)}秒 / ${result.frames}フレーム\n平均 ${result.fps.toFixed(1)} FPS · フレーム95% ${result.frameP95.toFixed(1)} ms · CPU描画 ${result.cpuMs.toFixed(1)} ms\n${m.style === 'diorama' ? 'ジオラマ' : '旧ボクセル'} · ${m.effectiveQuality} · ${m.width}×${m.height} · 影 ${m.shadowSize || 'OFF'} · AO ${m.post ? 'ON' : 'OFF'}`;
  }
}
