import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { Resident, Resource } from '../../../shared/village';
import { residentRole, residentSeed, type ResidentPose, type ResidentRole, type ResidentTool } from './resident-pose';

export interface ResidentRig {
  group: THREE.Group; upper: THREE.Group; head: THREE.Group; arms: THREE.Group[]; legs: THREE.Group[];
  tools: Record<ResidentTool, THREE.Mesh>; cargo: THREE.Mesh; cacheKey: string;
}
interface Part { geometry: THREE.BufferGeometry; color: string; p: number[]; s: number[]; rotation?: number[]; feature?: 'eye' | 'mouth' }
interface Template { head: THREE.BufferGeometry; body: THREE.BufferGeometry; arm: THREE.BufferGeometry; leg: THREE.BufferGeometry; users: number }
// Rounded original miniature characters. One shared vertex-color material for all body parts.
export class ResidentModelLibrary {
  private cube = new THREE.BoxGeometry(1, 1, 1);
  private sphere = new THREE.SphereGeometry(1, 12, 8);
  private detail = new THREE.SphereGeometry(1, 8, 5);
  private cylinder = new THREE.CylinderGeometry(1, 1, 1, 10);
  private taper = new THREE.CylinderGeometry(.78, 1, 1, 10);
  private object = new THREE.Object3D();
  private material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .83, metalness: 0 });
  private templates = new Map<string, Template>();
  private toolGeometry = new Map<ResidentTool, THREE.BufferGeometry>();
  private cargoGeometry = new Map<Resource, THREE.BufferGeometry>();
  readonly skinColors = ['#efc99f', '#dcb58d', '#e6be96', '#c69e7d'];
  private hairColors = ['#65513e', '#473d36', '#967455', '#54483f'];
  signature(r: Pick<Resident, 'id' | 'job' | 'color'>) { return `${residentRole(r.job)}:${r.color}:${residentSeed(r.id) % 16}`; }
  private part(parts: Part[], geometry: THREE.BufferGeometry, color: string, p: number[], s: number[], rotation?: number[]) { parts.push({ geometry, color, p, s, rotation }); }
  private box(parts: Part[], color: string, p: number[], s: number[], rotation?: number[]) { this.part(parts, this.cube, color, p, s, rotation); }
  private round(parts: Part[], color: string, p: number[], s: number[], rotation?: number[]) { this.part(parts, Math.max(...s) < .25 ? this.detail : this.sphere, color, p, s, rotation); }
  private tube(parts: Part[], color: string, p: number[], s: number[], rotation?: number[]) { this.part(parts, this.cylinder, color, p, s, rotation); }
  private bake(parts: Part[]) {
    const geometries = parts.map(part => {
      const geometry = part.geometry.index ? part.geometry.toNonIndexed() : part.geometry.clone();
      this.object.position.set(part.p[0], part.p[1], part.p[2]); this.object.scale.set(part.s[0], part.s[1], part.s[2]);
      this.object.rotation.set(...(part.rotation ?? [0, 0, 0]) as [number, number, number]); this.object.updateMatrix(); geometry.applyMatrix4(this.object.matrix);
      const color = new THREE.Color(part.color), colors = new Float32Array(geometry.getAttribute('position').count * 3);
      for (let i = 0; i < colors.length; i += 3) { colors[i] = color.r; colors[i + 1] = color.g; colors[i + 2] = color.b; }
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3)); return geometry;
    });
    const result = mergeGeometries(geometries); geometries.forEach(g => g.dispose());
    if (!result) throw new Error('住民モデルのジオメトリを結合できません。');
    result.computeBoundingSphere(); return result;
  }
  private mesh(geometry: THREE.BufferGeometry) { const mesh = new THREE.Mesh(geometry, this.material); mesh.castShadow = mesh.receiveShadow = true; return mesh; }
  private face(parts: Part[]) {
    const geometry = this.bake(parts), source = geometry.getAttribute('position');
    const targets = [source.clone(), source.clone(), source.clone()]; let offset = 0;
    for (const part of parts) {
      const count = part.geometry.index?.count ?? part.geometry.getAttribute('position').count;
      for (let i = offset; i < offset + count; i++) {
        if (part.feature === 'eye') targets[0].setY(i, .035 + (source.getY(i) - .035) * .06);
        if (part.feature === 'mouth') {
          const curve = .038 * ((source.getX(i) / .043) ** 2 - .35);
          targets[1].setY(i, source.getY(i) + curve); targets[2].setY(i, source.getY(i) - curve);
        }
      }
      offset += count;
    }
    geometry.morphAttributes.position = targets; return geometry;
  }
  private template(r: Resident, role: ResidentRole): Template {
    const seed = residentSeed(r.id), skin = this.skinColors[seed % 4], hair = this.hairColors[Math.floor(seed % 16 / 4)];
    const head: Part[] = [], body: Part[] = [], arm: Part[] = [], leg: Part[] = [];
    this.round(head, skin, [0, .04, 0], [.32, .32, .29]);
    this.round(head, hair, [0, .2, -.025], [.325, .19, .3]);
    for (const side of [-1, 1]) {
      this.round(head, skin, [side * .31, .025, 0], [.068, .09, .055]);
      this.round(head, hair, [side * .22, .11, .22], [.12, .065, .065], [0, 0, side * .25]);
      this.round(head, '#393d38', [side * .11, .035, .274], [.037, .05, .018]);
      head[head.length - 1].feature = 'eye';
      this.round(head, '#fff3d5', [side * .115, .051, .29], [.009, .012, .006]);
      head[head.length - 1].feature = 'eye';
      this.round(head, '#d9a18c', [side * .19, -.055, .245], [.048, .023, .015]);
    }
    this.round(head, skin, [0, -.025, .294], [.043, .052, .037]);
    this.round(head, '#aa775f', [0, -.1, .271], [.043, .013, .012]);
    head[head.length - 1].feature = 'mouth';
    if (role === 'farmer') {
      this.tube(head, '#d7bd7c', [0, .25, 0], [.43, .07, .4]); this.round(head, '#d7bd7c', [0, .29, -.025], [.28, .16, .27]);
      this.tube(head, '#98724a', [0, .32, -.02], [.276, .055, .266]);
    } else if (role === 'miner') {
      this.round(head, '#849594', [0, .245, -.025], [.34, .17, .3]); this.box(head, '#ad8861', [0, .28, .287], [.15, .09, .04]);
    } else if (role === 'builder') {
      this.round(head, '#b78962', [0, .255, -.035], [.325, .14, .3]); this.round(head, '#b78962', [0, .23, .27], [.26, .035, .11]);
    } else if (role === 'lumberjack') {
      this.round(head, '#607c68', [0, .25, -.04], [.3, .155, .29]); this.round(head, '#607c68', [.075, .39, -.035], [.07, .07, .07]);
    }
    this.part(body, this.taper, r.color, [0, .26, 0], [.24, .5, .19]);
    this.tube(body, '#6e5542', [0, .055, 0], [.243, .065, .192]);
    this.box(body, '#d8b473', [0, .055, .19], [.08, .07, .03]);
    this.tube(body, skin, [0, .52, 0], [.07, .13, .07]);
    this.box(body, '#e4cfab', [0, .43, .157], [.24, .08, .07], [.2, 0, 0]);
    if (role === 'builder' || role === 'farmer') {
      this.box(body, role === 'farmer' ? '#ddd3aa' : '#a47a55', [0, .22, .188], [.33, .36, .048]);
      this.box(body, '#856c49', [.09, .17, .22], [.14, .12, .025]);
    } else if (role === 'lumberjack') {
      for (const side of [-1, 1]) this.box(body, '#6d5844', [side * .155, .29, .17], [.095, .41, .055]);
      this.box(body, '#bd9765', [0, .4, .202], [.16, .1, .04]);
    } else if (role === 'miner') this.box(body, '#b68566', [0, .41, .196], [.25, .1, .055], [0, 0, -.1]);
    else this.box(body, '#7f9460', [.12, .27, .185], [.06, .41, .04], [0, 0, -.35]);
    this.round(arm, r.color, [0, -.135, 0], [.105, .18, .11]);
    this.tube(arm, '#e4cfab', [0, -.235, .006], [.095, .07, .105]);
    this.round(arm, skin, [0, -.335, .016], [.077, .13, .08]);
    this.round(arm, skin, [0, -.44, .027], [.085, .075, .085]);
    this.tube(leg, '#566469', [0, -.2, 0], [.095, .4, .095]);
    this.round(leg, '#69523e', [0, -.47, .045], [.117, .075, .18]);
    this.tube(leg, '#80664a', [0, -.405, .01], [.108, .11, .108]);
    return { head: this.face(head), body: this.bake(body), arm: this.bake(arm), leg: this.bake(leg), users: 0 };
  }
  private tool(kind: ResidentTool) {
    let geometry = this.toolGeometry.get(kind); if (geometry) return geometry;
    const parts: Part[] = [];
    if (kind === 'basket') {
      this.part(parts, this.taper, '#b79667', [0, -.09, .055], [.14, .24, .12]);
      this.tube(parts, '#806449', [0, .04, .055], [.14, .035, .12]);
    } else {
      this.tube(parts, '#97734d', [0, -.12, 0], [.025, kind === 'hoe' ? .7 : .52, .025]);
      if (kind === 'hammer') this.box(parts, '#99a4a0', [0, .125, 0], [.24, .13, .13]);
      if (kind === 'axe') {
        this.box(parts, '#98a8a4', [.1, .12, 0], [.24, .2, .055], [0, 0, -.3]);
        this.box(parts, '#c6d0c5', [.218, .075, 0], [.04, .2, .04], [0, 0, -.3]);
      }
      if (kind === 'pick') this.box(parts, '#99a4a0', [0, .125, 0], [.43, .065, .07], [0, 0, .15]);
      if (kind === 'hoe') this.box(parts, '#99a4a0', [0, -.44, .08], [.22, .055, .18]);
    }
    geometry = this.bake(parts); this.toolGeometry.set(kind, geometry); return geometry;
  }
  private cargo(kind: Resource) {
    let geometry = this.cargoGeometry.get(kind); if (geometry) return geometry;
    const parts: Part[] = [];
    if (kind === 'wood') for (const [y, z] of [[0, 0], [0, .14], [.13, .07]]) {
      this.tube(parts, '#a47a55', [0, y, z], [.078, .5, .078], [0, 0, Math.PI / 2]);
      for (const x of [-.254, .254]) this.tube(parts, '#d8b180', [x, y, z], [.065, .008, .065], [0, 0, Math.PI / 2]);
    } else {
      this.part(parts, this.taper, '#b79667', [0, 0, 0], [.24, .3, .17]);
      this.tube(parts, '#806449', [0, .165, 0], [.2, .04, .145]);
      for (const side of [-1, 1]) this.round(parts, kind === 'food' ? '#d6a568' : '#96a19c', [side * .095, .17, 0], [.09, .075, .09]);
    }
    geometry = this.bake(parts); this.cargoGeometry.set(kind, geometry); return geometry;
  }
  create(r: Resident): ResidentRig {
    const key = this.signature(r); let template = this.templates.get(key);
    if (!template) { template = this.template(r, residentRole(r.job)); this.templates.set(key, template); } template.users++;
    const group = new THREE.Group(), upper = new THREE.Group(), head = new THREE.Group();
    upper.position.y = .64; group.add(upper); upper.add(this.mesh(template.body)); head.position.y = .72; head.add(this.mesh(template.head)); upper.add(head);
    const arms = [-1, 1].map(side => { const pivot = new THREE.Group(); pivot.position.set(side * .32, .46, 0); pivot.add(this.mesh(template!.arm)); upper.add(pivot); return pivot; });
    const legs = [-1, 1].map(side => { const pivot = new THREE.Group(); pivot.position.set(side * .125, .6, 0); pivot.add(this.mesh(template!.leg)); group.add(pivot); return pivot; });
    const tools = {} as ResidentRig['tools'];
    for (const kind of ['axe', 'pick', 'hammer', 'hoe', 'basket'] as const) { const mesh = this.mesh(this.tool(kind)); mesh.position.set(0, -.44, .05); mesh.visible = false; arms[1].add(mesh); tools[kind] = mesh; }
    const cargo = this.mesh(this.cargo('food')); cargo.position.set(0, .25, .4); cargo.visible = false; upper.add(cargo);
    return { group, upper, head, arms, legs, tools, cargo, cacheKey: key };
  }
  pose(rig: ResidentRig, pose: ResidentPose, blend = 1) {
    const lerp = (a: number, b: number) => THREE.MathUtils.lerp(a, b, blend);
    rig.upper.position.y = lerp(rig.upper.position.y, pose.upperY); rig.upper.rotation.x = lerp(rig.upper.rotation.x, pose.lean);
    rig.head.rotation.x = lerp(rig.head.rotation.x, pose.headNod); rig.head.rotation.y = lerp(rig.head.rotation.y, pose.headTurn);
    const face = rig.head.children[0] as THREE.Mesh;
    for (const [i, value] of [pose.blink, pose.smile, pose.worry].entries()) face.morphTargetInfluences![i] = lerp(face.morphTargetInfluences![i], value);
    for (let i = 0; i < 2; i++) {
      rig.arms[i].rotation.x = lerp(rig.arms[i].rotation.x, pose.arms[i]); rig.legs[i].rotation.x = lerp(rig.legs[i].rotation.x, pose.legs[i]);
      rig.legs[i].position.y = lerp(rig.legs[i].position.y, pose.legY); rig.legs[i].scale.y = lerp(rig.legs[i].scale.y, pose.legScale);
    }
    for (const kind of Object.keys(rig.tools) as ResidentTool[]) rig.tools[kind].visible = pose.showTool && kind === pose.tool;
    rig.cargo.visible = !!pose.cargo;
    if (pose.cargo) { rig.cargo.geometry = this.cargo(pose.cargo); rig.cargo.scale.setScalar(pose.cargoScale); }
  }
  release(rig: ResidentRig) {
    rig.group.removeFromParent(); const template = this.templates.get(rig.cacheKey);
    if (template && --template.users === 0) {
      for (const geometry of [template.head, template.body, template.arm, template.leg]) geometry.dispose(); this.templates.delete(rig.cacheKey);
    }
  }
  dispose() {
    for (const template of this.templates.values()) for (const geometry of [template.head, template.body, template.arm, template.leg]) geometry.dispose();
    for (const geometry of [...this.toolGeometry.values(), ...this.cargoGeometry.values(), this.cube, this.sphere, this.detail, this.cylinder, this.taper]) geometry.dispose();
    this.templates.clear(); this.toolGeometry.clear(); this.cargoGeometry.clear(); this.material.dispose();
  }
}
