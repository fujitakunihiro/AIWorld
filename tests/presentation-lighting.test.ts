import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lightingAt } from '../presentation/src/renderer/lighting';

test('time-of-day lighting wraps every day and preserves the warm sunset peak', () => {
  for (let minute = 0; minute < 1440; minute += 15) {
    const a = lightingAt(minute), b = lightingAt(minute + 1440);
    for (const key of ['daylight', 'dusk', 'sun', 'ambient', 'exposure'] as const) assert.equal(a[key], b[key]);
    assert.ok(a.sun > 0 && a.ambient > 0 && a.exposure > 0);
  }
  assert.ok(lightingAt(720).sun > lightingAt(1320).sun);
  assert.ok(lightingAt(1070).dusk > .99);
  assert.ok(lightingAt(720).dusk < .01);
  assert.ok(Math.abs(lightingAt(1439.99).ambient - lightingAt(0).ambient) < .001);
});
