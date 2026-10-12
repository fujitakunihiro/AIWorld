import { PerspectiveCamera, Spherical, Vector3 } from 'three';
import { SIZE } from '../../../shared/world';
export class WorldCamera {
  target = new Vector3(SIZE / 2, 7, SIZE / 2);
  orbit = new Spherical(84, 0.82, 0.72);
  private pointers = new Map<number, { x: number; y: number; touch: boolean }>();
  private start = { x: 0, y: 0, at: 0 };
  private moved = false;
  private timer?: ReturnType<typeof setTimeout>;
  onTap: (x: number, y: number) => void = () => {};
  onHover: (x: number, y: number) => void = () => {};
  onLongPress: () => void = () => {};
  onPan: () => void = () => {};
  constructor(readonly camera: PerspectiveCamera, readonly element: HTMLCanvasElement) {
    element.addEventListener('contextmenu', e => e.preventDefault());
    element.addEventListener('pointerdown', e => {
      element.setPointerCapture(e.pointerId);
      this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, touch: e.pointerType === 'touch' });
      if (this.pointers.size === 1) {
        this.start = { x: e.clientX, y: e.clientY, at: performance.now() }; this.moved = false;
        this.timer = setTimeout(() => { if (!this.moved && e.pointerType === 'touch') { this.moved = true; this.onLongPress(); } }, 550);
      } else { this.moved = true; clearTimeout(this.timer); }
    });
    element.addEventListener('pointermove', e => {
      this.onHover(e.clientX, e.clientY);
      const old = this.pointers.get(e.pointerId); if (!old) return;
      const next = { x: e.clientX, y: e.clientY, touch: old.touch };
      if (Math.hypot(e.clientX - this.start.x, e.clientY - this.start.y) > 7) { this.moved = true; clearTimeout(this.timer); }
      if (this.pointers.size === 2) {
        const other = [...this.pointers.entries()].find(([id]) => id !== e.pointerId)![1];
        const before = Math.hypot(old.x - other.x, old.y - other.y);
        const after = Math.hypot(next.x - other.x, next.y - other.y);
        if (after > 8 && before > 8) this.orbit.radius *= before / after;
        let twist = Math.atan2(next.y - other.y, next.x - other.x) - Math.atan2(old.y - other.y, old.x - other.x);
        twist = Math.atan2(Math.sin(twist), Math.cos(twist)); this.orbit.theta -= twist;
        this.pan((next.x - old.x) / 2, (next.y - old.y) / 2);
      } else if (this.pointers.size === 1 && this.moved) {
        if (old.touch || e.buttons === 2 || e.shiftKey) this.pan(next.x - old.x, next.y - old.y);
        else { this.orbit.theta -= (next.x - old.x) * 0.006; this.orbit.phi -= (next.y - old.y) * 0.004; }
      }
      this.pointers.set(e.pointerId, next); this.update();
    });
    element.addEventListener('pointerup', e => {
      clearTimeout(this.timer);
      if (this.pointers.size === 1 && !this.moved && e.button === 0 && performance.now() - this.start.at < 550) this.onTap(e.clientX, e.clientY);
      this.pointers.delete(e.pointerId);
    });
    element.addEventListener('pointercancel', e => { clearTimeout(this.timer); this.moved = true; this.pointers.delete(e.pointerId); });
    element.addEventListener('wheel', e => { e.preventDefault(); this.zoom(Math.exp(e.deltaY * 0.001)); }, { passive: false });
    this.update();
  }
  pan(dx: number, dy: number) {
    this.onPan();
    const scale = this.orbit.radius / Math.max(this.element.clientHeight, 300);
    const t = this.orbit.theta;
    this.target.x += (-dx * Math.cos(t) - dy * Math.sin(t)) * scale;
    this.target.z += (dx * Math.sin(t) - dy * Math.cos(t)) * scale;
  }
  zoom(factor: number) { this.orbit.radius *= factor; this.update(); }
  home() {
    this.target.set(SIZE / 2, 7, SIZE / 2);
    const aspect = window.innerWidth / window.innerHeight;
    this.orbit.set(Math.max(175, Math.min(400, 205 / Math.min(1, aspect))), 0.82, 0.72); this.update();
  }
  update() {
    this.orbit.radius = Math.max(12, Math.min(450, this.orbit.radius));
    this.orbit.phi = Math.max(0.18, Math.min(1.4, this.orbit.phi));
    this.target.x = Math.max(0, Math.min(SIZE, this.target.x)); this.target.z = Math.max(0, Math.min(SIZE, this.target.z));
    this.camera.position.copy(this.target).add(new Vector3().setFromSpherical(this.orbit));
    this.camera.lookAt(this.target);
  }
}
