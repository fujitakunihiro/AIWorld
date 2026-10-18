import * as THREE from 'three';
import { ARC, CAROUSEL, LOUVRE, NOTRE_DAME, PARIS_BRIDGES, bridgeCenter, riverCenter } from '../../../shared/world';
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

  // A compact, walkable-scale Louvre courtyard and its glass pyramid.
  const palace: ModelPart[] = [], lx = LOUVRE.x, lz = LOUVRE.z, ly = LOUVRE.y;
  const pb = (color: string, x: number, y: number, z: number, w: number, h: number, d: number) =>
    kit.box(palace, color, [lx + x, ly + y, lz + z], [w, h, d]);
  const limestone = '#d8c9ac', pale = '#eadcc1', slate = '#555a59', glass = '#72949a';
  // Four wings surround an open courtyard, avoiding a solid collision-like mass.
  for (const side of [-1, 1]) {
    pb(limestone, 0, 5.1, side * 21, 48, 10.2, 8);
    pb(limestone, side * 24, 5.1, 0, 8, 10.2, 35);
    for (let x = -21; x <= 21; x += 4) {
      pb(pale, x, 5.5, side * 25.1, .4, 11.1, .35);
      pb('#75888a', x, 4.3, side * 25.2, 1.1, 2.2, .22);
      pb('#bcae95', x, 3.05, side * 25.25, 1.25, .18, .35);
    }
    for (let z = -14; z <= 14; z += 4) {
      pb(pale, side * 28.1, 5.5, z, .35, 11.1, .4);
      pb('#75888a', side * 28.2, 4.3, z, .22, 2.2, 1.1);
      pb('#bcae95', side * 28.2, 3.05, z, .35, .18, 1.25);
    }
  }
  for (const side of [-1, 1]) pb(slate, 0, 10.45, side * 21, 49, .65, 8.8);
  for (const side of [-1, 1]) pb(slate, side * 24, 10.45, 0, 8.8, .65, 35);
  for (const [x, z, scale] of [[-5, -4, 5.2], [6, 5, 3.2]] as const) {
    kit.part(palace, kit.cone, glass, [lx + x, ly + 2.15, lz + z], [scale, 2.8, scale]);
    pb('#d7d2c7', x, .3, z, scale * 2.1, .45, scale * 2.1);
  }
  const palaceGroup = kit.assemble(palace); palaceGroup.userData.modelId = LOUVRE.id;
  palaceGroup.userData.center = new THREE.Vector3(lx, ly + 4, lz); root.add(palaceGroup);

  // Notre-Dame's twin west towers, high nave, crossing and flying buttresses.
  const cathedral: ModelPart[] = [], nx = NOTRE_DAME.x, nz = NOTRE_DAME.z, ny = NOTRE_DAME.y;
  const cb = (color: string, x: number, y: number, z: number, w: number, h: number, d: number) =>
    kit.box(cathedral, color, [nx + x, ny + y, nz + z], [w, h, d]);
  const cathedralStone = '#c7b99f', roof = '#4e5a59', window = '#516d77';
  cb(cathedralStone, 0, 5.2, -1, 18, 10.4, 31);
  cb(cathedralStone, 0, 6.2, 0, 25, 12.4, 10);
  cb(roof, 0, 11.1, -1, 18.5, 1.3, 32);
  cb(roof, 0, 12.2, 0, 26, 1.25, 10);
  for (const x of [-7.5, 7.5]) {
    cb(cathedralStone, x, 12.8, 12.4, 7, 15, 7);
    cb(cathedralStone, x, 21, 12.4, 7.7, 1, 7.7);
    for (let y = 8; y <= 16; y += 3) cb(window, x, y, 15.95, 1.8, 2.1, .12);
  }
  for (const x of [-10.4, 10.4]) for (const z of [-10, -4, 2, 8]) {
    cb(cathedralStone, x, 4.8, z, 1.35, 9.6, 1.35);
    cb(cathedralStone, x * 1.16, 6.2, z + 1.6, 2.7, .45, 3.4);
  }
  for (const z of [-12, -5, 2, 9]) cb(window, 0, 6.2, z, 2.1, 4, .16);
  cb('#8d765d', 0, 3, 15.99, 2.4, 5.6, .16);
  const churchGroup = kit.assemble(cathedral); churchGroup.userData.modelId = NOTRE_DAME.id;
  churchGroup.userData.center = new THREE.Vector3(nx, ny + 9, nz); root.add(churchGroup);

  for (const center of PARIS_BRIDGES) {
    const parts: ModelPart[] = [];
    const b = (color: string, p: number[], s: number[]) => kit.box(parts, color, p, s);
    const mid = bridgeCenter(center), start = mid - 25, end = mid + 25;
    b(shadow, [mid, 8.48, center], [50, .82, 3.5]);
    b('#d9c6a4', [mid, 8.96, center], [50.5, .13, 3.7]);
    for (const side of [-1, 1]) {
      const z = center + side * 1.84;
      for (let x = start; x <= end; x += 2) b(stone, [x, 9.49, z], [.17, .95, .2]);
      b(stone, [mid, 9.96, z], [49.9, .22, .19]);
      for (const pier of [mid - 18, mid - 6, mid + 6, mid + 18]) b(stone, [pier, 6.38, z - side * .18], [1.45, 3.4, .65]);
      // The open curved spans read as a stone bridge above the water.
      for (let span = 0; span < 5; span++) {
        const from = start + 1 + span * 10;
        for (let i = 0; i < 8; i++) {
          const t = (i + .5) / 8, x = from + i * 1.24;
          const y = 6.05 + Math.sin(Math.PI * t) * 1.65;
          b(trim, [x, y, z - side * .08], [1.38, .21, .24]);
        }
      }
    }
    for (let x = start; x <= end; x += 2) b('#e6d4b6', [x, 9.035, center], [1.8, .02, 3.33]);
    const group = kit.assemble(parts); group.userData.modelId = `paris-bridge-${center}`; group.userData.center = new THREE.Vector3(mid, 9, center); root.add(group);
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
  for (const [z, dx] of [[83, -3], [143, 2], [244, -2]]) {
    const x = riverCenter(z) + dx;
    kit.box(extras, '#6c4d3e', [x, 6.13, z], [2.6, .35, 5.4]);
    kit.box(extras, '#efe1c4', [x, 6.52, z - .3], [1.9, .45, 2.3]);
    kit.box(extras, '#4e6470', [x, 6.86, z - .3], [2.1, .1, 2.45]);
    kit.box(extras, '#b67a55', [x, 6.2, z + 2.7], [1.4, .12, .4]);
  }
  const extrasGroup = kit.assemble(extras); extrasGroup.userData.modelId = 'paris-extras'; extrasGroup.userData.center = new THREE.Vector3(CAROUSEL.x, 9, CAROUSEL.z); root.add(extrasGroup);
  // Temporary roof sectors are baked into the assembled geometry.
  for (const part of extras) if (part.geometry !== kit.cube && part.geometry !== kit.trunk && part.geometry !== kit.round) part.geometry.dispose();
  return root;
}
