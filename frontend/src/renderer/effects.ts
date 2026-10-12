import * as THREE from 'three';
import type { Position } from '../../../shared/village';
export type EffectKind = 'build' | 'complete' | 'harvest' | 'arrival' | 'gather';
interface Particle { p: THREE.Vector3; v: THREE.Vector3; life: number; total: number; size: number; color: THREE.Color; fall: boolean }
export class WorldEffects {
  enabled = true;
  onSound: (kind: EffectKind) => void = () => {};
  private particles: Particle[] = [];
  private mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85, depthWrite: false }), 160);
  private dummy = new THREE.Object3D();
  private reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  constructor(scene: THREE.Scene) { this.mesh.count = 0; this.mesh.frustumCulled = false; this.mesh.userData.skipAO = true; this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); scene.add(this.mesh); }
  emit(kind: EffectKind, position: Position) {
    this.onSound(kind);
    if (!this.enabled || this.reduced) return;
    const count = kind === 'complete' || kind === 'arrival' ? 24 : kind === 'build' ? 4 : 6;
    const colors = kind === 'complete' ? ['#ffe9a4', '#98c59c', '#fff8df'] : kind === 'arrival' ? ['#9acaca', '#e0b2c7', '#ecd28b'] : kind === 'harvest' ? ['#cbd07c', '#e4c779'] : ['#cba779', '#efe2c4'];
    for (let i = 0; i < count && this.particles.length < 160; i++) {
      const life = kind === 'complete' || kind === 'arrival' ? 1.7 : 0.65;
      this.particles.push({ p: new THREE.Vector3(position.x + (Math.random() - .5) * .5, position.y + .5, position.z + (Math.random() - .5) * .5),
        v: new THREE.Vector3((Math.random() - .5) * 3, 1.5 + Math.random() * 2.5, (Math.random() - .5) * 3), life, total: life, size: .09 + Math.random() * .12, color: new THREE.Color(colors[i % colors.length]), fall: false });
    }
  }
  block(position: Position, color: string) {
    if (!this.enabled || this.reduced || this.particles.length >= 160) return;
    this.particles.push({ p: new THREE.Vector3(position.x + .5, position.y + 1.7, position.z + .5), v: new THREE.Vector3(0, -1.8, 0), life: .5, total: .5, size: .8, color: new THREE.Color(color), fall: true });
  }
  frame(delta: number, paused: boolean) {
    if (!this.enabled || this.reduced) this.particles.length = 0;
    if (!paused) for (const particle of this.particles) { particle.life -= delta; particle.p.addScaledVector(particle.v, delta); if (!particle.fall) particle.v.y -= delta * 4; }
    this.particles = this.particles.filter(p => p.life > 0);
    this.mesh.count = this.particles.length;
    this.particles.forEach((p, i) => {
      this.dummy.position.copy(p.p); this.dummy.scale.setScalar(p.size * (p.fall ? 1 : Math.min(1, p.life / .3)));
      this.dummy.rotation.set(p.life, p.life * 2, 0); this.dummy.updateMatrix(); this.mesh.setMatrixAt(i, this.dummy.matrix); this.mesh.setColorAt(i, p.color);
    });
    if (this.particles.length) { this.mesh.instanceMatrix.needsUpdate = true; if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true; }
  }
}
