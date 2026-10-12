import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lightingAt, effectiveQuality, QUALITY_PROFILES, previewMinute, summarizeFrames } from '../frontend/src/renderer/graphics';
import { waterDepthByte } from '../frontend/src/renderer/water-depth';
import { Block, SEA, SIZE, HEIGHT, index, generateWorld } from '../shared/world';
test('water depth follows the actual seabed and ignores a bridge above the water', () => {
  const data = new Uint8Array(SIZE * SIZE * HEIGHT);
  data[index(5, 0, 5)] = Block.Stone; data[index(6, 4, 5)] = Block.Sand; data[index(7, SEA, 5)] = Block.Grass;
  for (let y = 1; y <= SEA; y++) data[index(5, y, 5)] = Block.Water;
  assert.equal(waterDepthByte(data, 5, 5), 159); assert.equal(waterDepthByte(data, 6, 5), 32); assert.equal(waterDepthByte(data, 7, 5), 0);
  data[index(5, SEA + 1, 5)] = Block.Wood; assert.equal(waterDepthByte(data, 5, 5), 159);
});
test('building the presentation depth map leaves all saved world bytes intact', () => {
  const world = generateWorld(73129), before = world.slice();
  for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) assert.ok(waterDepthByte(world, x, z) >= 0);
  assert.deepEqual(world, before);
  assert.equal(previewMinute('world', 99325), 99325); assert.equal(previewMinute('evening', 99325), 1050);
});
test('lighting is periodic and keeps night readable with a warm sunset peak', () => {
  for (let minute = 0; minute < 1440; minute += 15) {
    const a = lightingAt(minute), b = lightingAt(minute + 1440);
    for (const k of ['daylight', 'dusk', 'sun', 'ambient', 'exposure'] as const) assert.equal(a[k], b[k]);
    assert.ok(a.sun > 0 && a.ambient > 0 && a.exposure > 0);
  }
  assert.ok(lightingAt(720).sun > lightingAt(1320).sun);
  assert.ok(lightingAt(1070).dusk > .99); assert.ok(lightingAt(720).dusk < .01);
  assert.ok(Math.abs(lightingAt(1439.99).ambient - lightingAt(0).ambient) < .001);
});
test('mobile auto quality starts lower and adaptive fallback respects explicit selections', () => {
  assert.equal(effectiveQuality('auto', true), 'medium'); assert.equal(effectiveQuality('auto', false), 'high');
  assert.equal(effectiveQuality('auto', false, 1), 'medium'); assert.equal(effectiveQuality('auto', true, 2), 'low');
  assert.equal(effectiveQuality('high', true, 2), 'high');
  assert.equal(QUALITY_PROFILES.low.shadowSize, 0); assert.equal(QUALITY_PROFILES.low.aoScale, 0);
});
test('performance statistics count slow frames instead of dropping them', () => {
  const durations = [...Array(95).fill(10), ...Array(5).fill(100)];
  const result = summarizeFrames(durations, Array(100).fill(3));
  assert.equal(result.frames, 100); assert.equal(result.seconds, 1.45); assert.equal(result.frameP95, 10);
  assert.equal(result.cpuMs, 3); assert.ok(result.fps > 68 && result.fps < 70);
  assert.deepEqual(summarizeFrames([], []), { fps: 0, frameP95: 0, cpuMs: 0, seconds: 0, frames: 0 });
});
