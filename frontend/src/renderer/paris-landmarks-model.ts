import * as THREE from 'three';
import { ARC, CAROUSEL, PARIS_BRIDGES } from '../../../shared/world';
import { ModelKit, type ModelPart } from './model-kit';

export function parisLandmarks(kit: ModelKit) {
  const root = new THREE.Group(), stone = '#d6c7aa', trim = '#f0e2c7', shadow = '#a99a82';
  const arch: ModelPart[] = [];
  for (const side of [-1, 1]) {
    kit.box(arch, stone, [side * 3.35, 4, 0], [2.35, 8, 5.2]);
    kit.box(arch, trim, [side * 3.35, 1.4, 2.65], [1.65, 2.6, .12]);
    for (const y of [1.5, 4.3, 7.1]) kit.box(arch, shadow, [side * 3.35, y, -2.64], [1.9, .12, .11]);
  }
  kit.box(arch, stone, [0, 9.25, 0], [9.2, 3.05, 5.3]);
  for (const y of [8.05, 10.6, 11.25]) kit.box(arch, trim, [0, y, 0], [9.8, .23, 5.7]);
  for (const side of [-1, 1]) for (let i = 0; i < 6; i++) {
    kit.box(arch, shadow, [side * 4.65, 8.1 + i * .42, 0], [.09, .09, 5.05]);
    kit.box(arch, trim, [side * 2.55, 7.05 + i * .23, 2.67], [.11, .11, .1]);
  }
  const archGroup = kit.assemble(arch); archGroup.position.set(ARC.x, ARC.y, ARC.z); archGroup.scale.y = 1.4;
  archGroup.userData.modelId = ARC.id; archGroup.userData.center = new THREE.Vector3(ARC.x, ARC.y, ARC.z); root.add(archGroup);

  for (const center of PARIS_BRIDGES) {
    const parts: ModelPart[] = [];
    const b = (color: string, p: number[], s: number[]) => kit.box(parts, color, p, s);
    b(shadow, [257.5, 8.48, center], [40, .82, 3.5]);
    b('#d9c6a4', [257.5, 8.96, center], [40.5, .13, 3.7]);
    for (const side of [-1, 1]) {
      const z = center + side * 1.84;
      for (let x = 238; x <= 277; x += 2) b(stone, [x, 9.49, z], [.17, .95, .2]);
      b(stone, [257.5, 9.96, z], [39.9, .22, .19]);
      for (const pier of [244, 253, 262, 271]) b(stone, [pier, 6.38, z - side * .18], [1.45, 3.4, .65]);
      // The open curved spans read as a stone bridge above the water.
      for (let span = 0; span < 4; span++) {
        const from = 240 + span * 9;
        for (let i = 0; i < 8; i++) {
          const t = (i + .5) / 8, x = from + i * 1.12;
          const y = 6.05 + Math.sin(Math.PI * t) * 1.65;
          b(trim, [x, y, z - side * .08], [1.3, .21, .24]);
        }
      }
    }
    for (let x = 239; x <= 277; x += 2) b('#e6d4b6', [x, 9.035, center], [1.8, .02, 3.33]);
    const group = kit.assemble(parts); group.userData.modelId = `paris-bridge-${center}`; group.userData.center = new THREE.Vector3(257, 9, center); root.add(group);
  }

  const extras: ModelPart[] = [];
  // A striped carousel and café terrace bring life to the open eastern square.
  const cx = CAROUSEL.x, cz = CAROUSEL.z, gy = CAROUSEL.y;
  kit.box(extras, '#c5b396', [cx, gy + .14, cz], [7.2, .28, 7.2]);
  kit.part(extras, kit.trunk, '#a77a5c', [cx, gy + 1.85, cz], [.7, 3.35, .7]);
  for (let i = 0; i < 8; i++) {
    const sector = new THREE.ConeGeometry(4, 2.5, 8, 1, true, i * Math.PI / 4, Math.PI / 4);
    kit.part(extras, sector, i % 2 ? '#f2e5cc' : '#a95f59', [cx, gy + 4.4, cz], [1, 1, 1]);
  }
  for (let i = 0; i < 8; i++) {
    const angle = i * Math.PI / 4, x = cx + Math.cos(angle) * 2.6, z = cz + Math.sin(angle) * 2.6;
    kit.box(extras, '#a77a5c', [x, gy + 2.12, z], [.12, 3.4, .12]);
    kit.part(extras, kit.round, '#f2d29a', [x, gy + 1.45, z], [.53, .25, .36], 0, [0, -angle, 0]);
  }
  for (const [x, z] of [[285, 139], [285, 149], [303, 139], [303, 149]]) {
    kit.box(extras, '#927257', [x, gy + .72, z], [1.2, .13, 1.2]);
    kit.box(extras, '#927257', [x, gy + .38, z], [.13, .65, .13]);
    for (const dx of [-1, 1]) kit.box(extras, '#a95f59', [x + dx * 1.05, gy + .48, z], [.55, .14, .55]);
  }
  // Small river boats stay within the navigable water and cost only a few baked meshes.
  for (const [x, z] of [[254, 91], [257, 136], [251, 188]]) {
    kit.box(extras, '#6c4d3e', [x, 6.13, z], [2.6, .35, 5.4]);
    kit.box(extras, '#efe1c4', [x, 6.52, z - .3], [1.9, .45, 2.3]);
    kit.box(extras, '#4e6470', [x, 6.86, z - .3], [2.1, .1, 2.45]);
    kit.box(extras, '#b67a55', [x, 6.2, z + 2.7], [1.4, .12, .4]);
  }
  const extrasGroup = kit.assemble(extras); extrasGroup.userData.modelId = 'paris-extras'; extrasGroup.userData.center = new THREE.Vector3(280, 9, 140); root.add(extrasGroup);
  // Temporary roof sectors are baked into the assembled geometry.
  for (const part of extras) if (part.geometry !== kit.cube && part.geometry !== kit.trunk && part.geometry !== kit.round) part.geometry.dispose();
  return root;
}
