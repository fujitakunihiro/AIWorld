export type GraphicStyle = 'diorama' | 'classic';
export type Quality = 'auto' | 'low' | 'medium' | 'high';
export type LightPreview = 'world' | 'day' | 'evening' | 'night';
export interface GraphicsSettings {
  style: GraphicStyle; quality: Quality; shadows: boolean; ao: boolean;
  distance: 'near' | 'standard' | 'far'; preview: LightPreview; grass: 'off' | 'sparse' | 'lush';
}
export interface QualityProfile { pixelRatio: number; shadowSize: number; aoScale: number; aoSamples: number; distance: number; grassDensity: number; decorationDistance: number }
export const QUALITY_PROFILES: Record<Exclude<Quality, 'auto'>, QualityProfile> = {
  low: { pixelRatio: 1, shadowSize: 0, aoScale: 0, aoSamples: 8, distance: 48, grassDensity: .12, decorationDistance: 28 },
  medium: { pixelRatio: 1.25, shadowSize: 1024, aoScale: .5, aoSamples: 8, distance: 80, grassDensity: .45, decorationDistance: 55 },
  high: { pixelRatio: 1.75, shadowSize: 2048, aoScale: .5, aoSamples: 16, distance: 180, grassDensity: 1, decorationDistance: 90 }
};
export function effectiveQuality(quality: Quality, mobile: boolean, downgrade = 0): Exclude<Quality, 'auto'> {
  if (quality !== 'auto') return quality;
  return (['low', 'medium', 'high'] as const)[Math.max(0, (mobile ? 1 : 2) - downgrade)];
}
export const previewMinute = (preview: LightPreview, time: number) => ({ world: time, day: 720, evening: 1050, night: 1320 })[preview];
export function lightingAt(time: number) {
  const minute = ((time % 1440) + 1440) % 1440, angle = (minute - 360) / 1440 * Math.PI * 2;
  const daylight = Math.max(0, Math.sin(angle));
  const dusk = Math.max(Math.exp(-(((minute - 355) / 65) ** 2)), Math.exp(-(((minute - 1070) / 65) ** 2)));
  const softDay = Math.sqrt(daylight);
  return { angle, daylight, dusk, sun: .4 + softDay * 2.3 + dusk * .75, ambient: .82 + softDay * .38 + dusk * .12, exposure: 1.12 - daylight * .08 };
}
export interface RenderMetrics {
  fps: number; frameP95: number; cpuMs: number; calls: number; triangles: number;
  geometries: number; textures: number; width: number; height: number; ratio: number;
  gpu: string; effectiveQuality: string; post: boolean; shadowSize: number; style: GraphicStyle;
}
export interface Benchmark { fps: number; frameP95: number; cpuMs: number; seconds: number; frames: number; metrics: RenderMetrics }
export function summarizeFrames(durations: number[], cpu: number[]) {
  const sorted = durations.slice().sort((a, b) => a - b);
  const elapsed = durations.reduce((a, b) => a + b, 0);
  return { fps: elapsed ? durations.length * 1000 / elapsed : 0, frameP95: sorted[Math.max(0, Math.ceil(sorted.length * .95) - 1)] ?? 0,
    cpuMs: cpu.reduce((a, b) => a + b, 0) / Math.max(1, cpu.length), seconds: elapsed / 1000, frames: durations.length };
}
