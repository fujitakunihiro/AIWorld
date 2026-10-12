import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import type { QualityProfile } from './graphics';

export class DioramaPostProcessing {
  private composer: EffectComposer;
  private ao: SSAOPass;
  private hidden: THREE.Object3D[] = [];
  constructor(private renderer: THREE.WebGLRenderer, private scene: THREE.Scene, camera: THREE.Camera, profile: QualityProfile) {
    const target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType }); target.samples = 2;
    this.composer = new EffectComposer(renderer, target);
    this.composer.addPass(new RenderPass(scene, camera));
    this.ao = new SSAOPass(scene, camera, 1, 1, profile.aoSamples);
    this.ao.kernelRadius = 1.25; this.ao.minDistance = .00015; this.ao.maxDistance = .012;
    this.ao.copyMaterial.fragmentShader = this.ao.copyMaterial.fragmentShader.replace('gl_FragColor = opacity * texel;', 'gl_FragColor = vec4(mix(vec3(1.0), texel.rgb, 0.55), texel.a);');
    const renderAO = this.ao.render.bind(this.ao);
    this.ao.render = (renderer, write, read, delta, mask) => {
      this.scene.traverse(o => { if (o.visible && o.userData.skipAO) { this.hidden.push(o); o.visible = false; } });
      try { renderAO(renderer, write, read, delta, mask); }
      finally { for (const o of this.hidden) o.visible = true; this.hidden.length = 0; }
    };
    this.composer.addPass(this.ao); this.composer.addPass(new OutputPass());
    this.resize(profile);
  }
  resize(profile: QualityProfile) {
    this.composer.setPixelRatio(this.renderer.getPixelRatio()); this.composer.setSize(innerWidth, innerHeight);
    const ratio = this.renderer.getPixelRatio() * profile.aoScale;
    this.ao.setSize(Math.max(1, Math.round(innerWidth * ratio)), Math.max(1, Math.round(innerHeight * ratio)));
  }
  render(delta: number) { this.composer.render(delta); }
  dispose() {
    // r180's SSAOPass.dispose omits ssaoMaterial and noiseTexture.
    this.ao.dispose(); this.ao.ssaoMaterial.dispose(); this.ao.noiseTexture.dispose();
    for (const pass of this.composer.passes) if (pass !== this.ao) pass.dispose();
    this.composer.dispose();
  }
}
