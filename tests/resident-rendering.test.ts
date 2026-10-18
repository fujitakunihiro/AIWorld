import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { Simulation } from '../backend/src/simulation/engine';
import { generateWorld } from '../shared/world';
import type { Action, Resident } from '../shared/village';
import { residentMood, residentPose, residentRole, workTool } from '../presentation/src/renderer/resident-pose';
import { ResidentModelLibrary } from '../presentation/src/renderer/resident-model';
const resident = () => new Simulation(generateWorld(73129)).state.residents[0];

test('profession and actual tasks choose different tools without changing the resident or its AI', () => {
  const r = resident(), before = JSON.stringify(r);
  assert.equal(residentRole(r.job), 'builder'); assert.equal(workTool(r), 'hammer');
  const gather = { ...r, action: 'gathering' as const };
  assert.equal(workTool(gather, 'wood'), 'axe'); assert.equal(workTool(gather, 'stone'), 'pick'); assert.equal(workTool(gather, 'food'), 'basket');
  assert.equal(workTool({ ...r, action: 'farming' }), 'hoe'); assert.equal(workTool({ ...r, job: '農家', action: 'building' }), 'hammer');
  for (const job of ['建築家', '木こり', '採掘師', '農家', '採集家']) residentPose({ ...r, job }, 2, false);
  assert.equal(JSON.stringify(r), before);
});

test('walking, harvesting, hammering and waiting have distinct finite poses; reduced motion stays static', () => {
  const r = resident(), poses = new Set<string>();
  for (const action of ['idle', 'moving', 'gathering', 'building', 'farming', 'resting', 'eating', 'socializing', 'exploring', 'delivering'] as Action[]) {
    const s = { ...r, action };
    const a = residentPose(s, 1.1, false, 'wood'), b = residentPose(s, 1.9, false, 'wood');
    for (const value of [...a.legs, ...a.arms, a.upperY, a.lean, a.headTurn, a.legY, a.legScale]) assert.ok(Number.isFinite(value) && Math.abs(value) < 2);
    if (['idle', 'moving', 'gathering', 'building', 'farming'].includes(action)) { assert.notDeepEqual(a, b); poses.add(JSON.stringify(a)); }
    assert.deepEqual(residentPose(s, 1, true, 'wood'), residentPose(s, 900, true, 'wood'));
  }
  assert.equal(poses.size, 5);
});

test('carried food, logs and stone use actual inventory, and animation never moves the game-space root', () => {
  const r = resident(), library = new ResidentModelLibrary(), rig = library.create(r), before = structuredClone(r);
  rig.group.position.set(r.position.x, r.position.y, r.position.z); const root = rig.group.position.clone();
  for (const resource of ['food', 'wood', 'stone'] as const) {
    const carrying = { ...r, action: 'moving' as const, inventory: { food: 0, wood: 0, stone: 0, [resource]: 8 } };
    const pose = residentPose(carrying, 1, false); assert.equal(pose.cargo, resource); assert.equal(pose.showTool, false);
    library.pose(rig, pose); assert.ok(rig.cargo.visible); assert.deepEqual(rig.group.position, root);
  }
  library.pose(rig, residentPose(r, 0, false)); assert.equal(rig.cargo.visible, false); assert.deepEqual(r, before);
  library.release(rig); library.dispose();
});

test('shared templates survive releasing a twin and are disposed when the last resident changes profession', () => {
  const r = resident(), library = new ResidentModelLibrary(), a = library.create(r), b = library.create(r);
  const aHead = (a.head.children[0] as THREE.Mesh).geometry, bHead = (b.head.children[0] as THREE.Mesh).geometry;
  assert.equal(aHead, bHead); let disposed = 0; aHead.addEventListener('dispose', () => disposed++);
  library.release(a); assert.equal(disposed, 0); library.release(b); assert.equal(disposed, 1);
  const farmer = library.create({ ...r, job: '農家' }); assert.notEqual(farmer.cacheKey, a.cacheKey);
  library.release(farmer); library.dispose();
});

test('pause freezes the displayed pose, active rigs stay compact, and hidden tools are not selectable', () => {
  const r = resident(), library = new ResidentModelLibrary(), rig = library.create(r);
  library.pose(rig, residentPose({ ...r, action: 'building' }, 1, false)); rig.group.updateMatrixWorld(true);
  const before = rig.arms[1].matrixWorld.clone(); library.pose(rig, residentPose({ ...r, action: 'building' }, 10, false), 0); rig.group.updateMatrixWorld(true);
  assert.deepEqual(rig.arms[1].matrixWorld, before);
  const visible: THREE.Mesh[] = []; rig.group.traverseVisible(o => { if (o instanceof THREE.Mesh) visible.push(o); });
  assert.equal(visible.length, 7); assert.equal(Object.values(rig.tools).filter(t => t.visible).length, 1);
  const neutral = residentPose({ ...r, action: 'idle' }, 0, true); library.pose(rig, neutral);
  const bounds = new THREE.Box3().setFromObject(rig.head); assert.ok(bounds.max.y < 2);
  assert.equal(rig.arms[1].scale.y, 1, 'tools use unscaled shoulder pivots');
  library.release(rig); library.dispose();
});

test('expressions explain real needs and conversation, blinking stays bounded and reduced motion is still', () => {
  const r = { ...resident(), health: 100, energy: 80, hunger: 10, action: 'idle' as const, speech: null }, before = structuredClone(r);
  assert.equal(residentMood(r), 'calm');
  assert.equal(residentMood({ ...r, energy: 10 }), 'tired');
  assert.equal(residentMood({ ...r, action: 'socializing' }), 'happy');
  assert.equal(residentMood({ ...r, hunger: 90, action: 'socializing' }), 'worried');
  assert.equal(residentMood({ ...r, health: 20 }), 'worried');
  const values = Array.from({ length: 600 }, (_, i) => residentPose(r, i / 60, false).blink);
  assert.ok(values.some(v => v > .8) && values.some(v => v === 0)); assert.ok(values.every(v => v >= 0 && v <= 1));
  assert.equal(residentPose(r, 30, true).blink, 0); assert.equal(residentPose({ ...r, action: 'resting' }, 30, true).blink, .85);
  const library = new ResidentModelLibrary(), rig = library.create(r), mesh = rig.head.children[0] as THREE.Mesh;
  library.pose(rig, residentPose({ ...r, action: 'socializing' }, 1, false));
  assert.equal(mesh.morphTargetInfluences![1], 1);
  const weights = mesh.morphTargetInfluences!.slice();
  library.pose(rig, residentPose({ ...r, hunger: 90 }, 2, false), 0); assert.deepEqual(mesh.morphTargetInfluences, weights);
  assert.deepEqual(r, before); library.release(rig); library.dispose();
});
