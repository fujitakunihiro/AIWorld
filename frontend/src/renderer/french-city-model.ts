import * as THREE from 'three';
import { FRENCH_BUILDINGS } from '../../../shared/world';
import { ModelKit, type ModelPart } from './model-kit';

// Baked by material and 128×128 district so the expanded skyline costs few draw calls.
export function frenchCityModels(kit: ModelKit) {
  const sectors = new Map<string, { parts: ModelPart[]; x: number; z: number }>();
  const walls = ['#e7d8bc', '#d9c3aa', '#f0dec4', '#d7d5c9'];
  const roofs = ['#52616b', '#65747a', '#63616b', '#777369'];
  const awnings = ['#9d4d4d', '#496f78', '#72845d', '#a56f4e'];
  for (const lot of FRENCH_BUILDINGS) {
    const sx = Math.floor(lot.x / 128), sz = Math.floor(lot.z / 128), key = `${sx}:${sz}`;
    const sector = sectors.get(key) ?? { parts: [], x: sx * 128 + 64, z: sz * 128 + 64 };
    sectors.set(key, sector);
    const parts = sector.parts, x = lot.x, z = lot.z, y = 9, wall = walls[lot.style], roof = roofs[lot.style];
    const top = y + lot.floors * 3;
    const b = (color: string, px: number, py: number, pz: number, w: number, h: number, d: number) =>
      kit.box(parts, color, [px, py, pz], [w, h, d]);
    // Limestone shopfronts, cornices and a stepped slate mansard roof.
    b('#b9ab97', x + 3, y + .12, z + 3, 6.3, .24, 6.3);
    b(wall, x + 3, (y + top) / 2, z + 3, 5.9, top - y, 5.9);
    for (let level = 1; level <= lot.floors; level++) b('#f3e8d1', x + 3, y + level * 3 - .14, z + 3, 6.18, .19, 6.18);
    for (const px of [x + .18, x + 5.82]) for (const pz of [z + .18, z + 5.82])
      b('#f3e8d1', px, (y + top) / 2, pz, .22, top - y, .22);
    b(roof, x + 3, top + .45, z + 3, 6.45, 1.1, 6.45);
    b(roof, x + 3, top + 1.3, z + 3, 5.55, .8, 5.55);
    b(roof, x + 3, top + 1.83, z + 3, 4.85, .35, 4.85);
    b('#b9ab97', x + 4.6, top + 2.42, z + 1.25, .54, 1.55, .54);
    b('#655e57', x + 4.6, top + 3.23, z + 1.25, .74, .14, .74);
    if (lot.style % 2 === 0) {
      b('#b9ab97', x + 1.25, top + 2.28, z + 4.7, .46, 1.25, .48);
      b('#655e57', x + 1.25, top + 2.96, z + 4.7, .64, .12, .66);
    }
    // Four street-facing windows per floor, side windows and a small dormer.
    for (let floor = 0; floor < lot.floors; floor++) {
      const wy = y + 1.65 + floor * 3;
      for (const wx of [x + 1.55, x + 4.45]) for (const wz of [z + .025, z + 5.975]) {
        if (floor === 0 && wz > z + 3 && wx === x + 4.45) continue;
        b('#f4e8d4', wx, wy, wz, 1.18, 1.5, .13);
        b('#628e94', wx, wy, wz + (wz < z + 3 ? -.09 : .09), .9, 1.2, .045);
        b('#e8d7b7', wx, wy, wz + (wz < z + 3 ? -.13 : .13), .065, 1.22, .055);
        b('#9f8f7c', wx, wy - .78, wz, 1.3, .14, .27);
      }
      for (const wx of [x + .025, x + 5.975]) {
        b('#f4e8d4', wx, wy, z + 2.6, .13, 1.5, 1.06);
        b('#628e94', wx + (wx < x + 3 ? -.09 : .09), wy, z + 2.6, .045, 1.2, .8);
      }
      if (floor > 0) {
        b('#4e5456', x + 3, wy - .79, z + 6.22, 5.6, .12, .15);
        for (let rail = 0; rail < 9; rail++) b('#4e5456', x + .35 + rail * .66, wy - .52, z + 6.23, .055, .58, .07);
      }
    }
    b('#795947', x + 4.45, y + 1.23, z + 6.02, 1.25, 2.25, .13);
    b(awnings[lot.style], x + 4.45, y + 2.58, z + 6.45, 1.6, .14, 1);
    b('#4e5456', x + 3, y + 3.12, z + 6.13, 5.9, .11, .12);
    for (let i = 0; i <= 7; i++) b('#4e5456', x + .1 + i * .83, y + 3.43, z + 6.13, .055, .68, .07);
    for (const wx of [x + 1.6, x + 4.4]) {
      b('#f4e8d4', wx, top + 1.22, z + 6.24, 1.08, 1, .14);
      b('#628e94', wx, top + 1.22, z + 6.34, .78, .74, .05);
      b(roof, wx, top + 1.89, z + 6.2, 1.35, .13, .92);
    }
    for (let paving = 0; paving < 6; paving++)
      b(paving % 3 === 0 ? '#b8aa96' : '#c8baa4', x + .5 + paving, y + .026, z + 7.04, .94, .025, .62);
    const street = lot.x >= 256 ? 7 : 8;
    if ((lot.x + lot.z) % 20 === 3) {
      b('#454b49', x + street, y + 1.65, z + street, .12, 3.3, .12);
      kit.part(parts, kit.round, '#f1d195', [x + street, y + 3.39, z + street], [.28, .36, .28]);
    } else {
      kit.part(parts, kit.trunk, '#796b54', [x + street, y + 1.9, z + street], [.8, 3.8, .8]);
      kit.part(parts, kit.round, '#738f5e', [x + street, y + 4.4, z + street], [1.45, 1.65, 1.45]);
      kit.part(parts, kit.round, '#91a86e', [x + street - .55, y + 4.8, z + street + .2], [.85, .9, .85]);
    }
  }
  return [...sectors.values()].map(({ parts, x, z }) => {
    const group = kit.assemble(parts); group.userData.modelId = 'french-city'; group.userData.center = new THREE.Vector3(x, 9, z);
    return group;
  });
}
