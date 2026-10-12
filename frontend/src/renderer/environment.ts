import * as THREE from 'three';
import { SIZE, type Edit } from '../../../shared/world';
import { lightingAt, type GraphicsSettings, type QualityProfile } from './graphics';
import { waterDepthByte } from './water-depth';

// All resources here are presentation only. World bytes, navigation and saved time remain authoritative.
export class DioramaEnvironment {
  readonly solid = new THREE.MeshLambertMaterial({ vertexColors: true });
  readonly water = new THREE.MeshPhongMaterial({ color: '#ffffff', transparent: true, opacity: .87, depthWrite: false, shininess: 90, specular: '#e5eee5' });
  readonly sky: THREE.Mesh;
  private depthBytes = new Uint8Array(SIZE * SIZE);
  private depth = new THREE.DataTexture(this.depthBytes, SIZE, SIZE, THREE.RedFormat);
  private waveTime = { value: 0 };
  private skyUniforms = { zenith: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, bottom: { value: new THREE.Color() } };
  private nightTop = new THREE.Color('#182842'); private dayTop = new THREE.Color('#83b4d2');
  private nightHorizon = new THREE.Color('#465b75'); private dayHorizon = new THREE.Color('#ede5cd'); private duskHorizon = new THREE.Color('#edb494');
  private nightSun = new THREE.Color('#a8c8ee'); private daySun = new THREE.Color('#fff2d8'); private duskSun = new THREE.Color('#ffbc8a');
  private nightAmbient = new THREE.Color('#adbbdb'); private dayAmbient = new THREE.Color('#e4eddf');
  private reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  constructor(scene: THREE.Scene, private sun: THREE.DirectionalLight, private ambient: THREE.HemisphereLight) {
    this.depth.minFilter = this.depth.magFilter = THREE.LinearFilter; this.depth.generateMipmaps = false; this.depth.needsUpdate = true;
    this.water.onBeforeCompile = shader => {
      shader.uniforms.waveTime = this.waveTime; shader.uniforms.waterDepth = { value: this.depth };
      shader.uniforms.shallowColor = { value: new THREE.Color('#82c7bd') }; shader.uniforms.deepColor = { value: new THREE.Color('#427997') };
      shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 waterPosition; varying float waterTop; varying vec3 rippleX; varying vec3 rippleZ;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nwaterPosition = (modelMatrix * vec4(position, 1.0)).xyz; waterTop = step(0.9, normal.y); rippleX = normalMatrix * vec3(1.0,0.0,0.0); rippleZ = normalMatrix * vec3(0.0,0.0,1.0);');
      shader.fragmentShader = shader.fragmentShader.replace('#include <common>', '#include <common>\nuniform float waveTime; uniform sampler2D waterDepth; uniform vec3 shallowColor; uniform vec3 deepColor; varying vec3 waterPosition; varying float waterTop; varying vec3 rippleX; varying vec3 rippleZ;')
        .replace('#include <color_fragment>', `#include <color_fragment>
          float bedDepth = texture2D(waterDepth, clamp(waterPosition.xz / ${SIZE.toFixed(1)}, 0.0, 1.0)).r * 8.0;
          diffuseColor.rgb *= mix(shallowColor, deepColor, smoothstep(0.5, 5.5, bedDepth));
          float waveA = waterPosition.x * 1.1 + waterPosition.z * 0.7 + waveTime * 0.75 + sin(waterPosition.z * 0.27 + waterPosition.x * 0.18 + waveTime * 0.2);
          float waveB = waterPosition.z * 1.7 - waterPosition.x * 0.4 - waveTime * 0.55 + cos(waterPosition.x * 0.21 - waterPosition.z * 0.14);
          float crest = pow(clamp(0.5 + 0.325 * sin(waveA) + 0.175 * sin(waveB), 0.0, 1.0), 10.0);
          float shore = (1.0 - smoothstep(0.3, 2.2, bedDepth)) * waterTop;
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.78, 0.87, 0.8), shore * (0.06 + crest * 0.22));`)
        .replace('#include <normal_fragment_begin>', `#include <normal_fragment_begin>
          vec3 ripple = vec3(-cos(waveA) * 0.065, 0.0, -cos(waveB) * 0.045);
          normal = normalize(normal + (rippleX * ripple.x + rippleZ * ripple.z) * waterTop);`);
    };
    this.water.customProgramCacheKey = () => 'diorama-water-v2';
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(650, 24, 12), new THREE.ShaderMaterial({
      uniforms: this.skyUniforms, side: THREE.BackSide, depthWrite: false, fog: false,
      vertexShader: `varying vec3 direction; void main() { direction = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `uniform vec3 zenith; uniform vec3 horizon; uniform vec3 bottom; varying vec3 direction;
        void main() { float h = normalize(direction).y; vec3 c = mix(horizon, zenith, smoothstep(0.0, 0.72, h));
          c = mix(c, bottom, 1.0 - smoothstep(-0.55, 0.0, h)); gl_FragColor = vec4(c, 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`
    }));
    this.sky.frustumCulled = false; this.sky.renderOrder = -100; this.sky.userData.skipAO = true; scene.add(this.sky);
    this.sun.shadow.bias = -.00025; this.sun.shadow.normalBias = .1; this.sun.shadow.radius = 3;
    this.sun.shadow.camera.near = 1; this.sun.shadow.camera.far = 260;
    scene.add(this.sun.target);
  }
  world(data: Uint8Array) { for (let z = 0; z < SIZE; z++) for (let x = 0; x < SIZE; x++) this.depthPixel(data, x, z); this.depth.needsUpdate = true; }
  edits(data: Uint8Array, edits: Edit[]) { for (const e of edits) this.depthPixel(data, e.x, e.z); this.depth.needsUpdate = true; }
  private depthPixel(data: Uint8Array, x: number, z: number) {
    this.depthBytes[x + z * SIZE] = waterDepthByte(data, x, z);
  }
  shadow(profile: QualityProfile, enabled: boolean) {
    const size = enabled ? profile.shadowSize : 0;
    this.sun.castShadow = !!size;
    if (size && this.sun.shadow.mapSize.x !== size) {
      this.sun.shadow.map?.dispose(); this.sun.shadow.map = null; this.sun.shadow.mapSize.set(size, size);
    }
  }
  frame(time: number, now: number, camera: THREE.Camera, target: THREE.Vector3, radius: number, settings: GraphicsSettings) {
    this.sky.visible = settings.style === 'diorama'; if (!this.sky.visible) return;
    const light = lightingAt(time);
    this.sky.position.copy(camera.position); this.waveTime.value = this.reduced ? 0 : now / 1000;
    this.skyUniforms.zenith.value.copy(this.nightTop).lerp(this.dayTop, light.daylight);
    this.skyUniforms.horizon.value.copy(this.nightHorizon).lerp(this.dayHorizon, Math.sqrt(light.daylight)).lerp(this.duskHorizon, light.dusk * .8);
    this.skyUniforms.bottom.value.copy(this.skyUniforms.horizon.value).multiplyScalar(.88);
    this.sun.color.copy(this.nightSun).lerp(this.daySun, Math.min(1, light.daylight * 3)).lerp(this.duskSun, light.dusk);
    this.sun.intensity = light.sun; this.ambient.intensity = light.ambient;
    this.ambient.color.copy(this.nightAmbient).lerp(this.dayAmbient, light.daylight); this.ambient.groundColor.set('#927f64');
    this.sun.target.position.copy(target);
    // A tightly bounded shadow map follows the view; world coordinates and collision stay unchanged.
    const elevation = Math.max(.3, Math.abs(Math.sin(light.angle)));
    this.sun.position.copy(target).add(new THREE.Vector3(Math.cos(light.angle) * 80, elevation * 100, 45));
    const extent = THREE.MathUtils.clamp(radius * .52, 20, 92), shadow = this.sun.shadow.camera;
    shadow.left = shadow.bottom = -extent; shadow.right = shadow.top = extent; shadow.updateProjectionMatrix();
  }
  get horizon() { return this.skyUniforms.horizon.value; }
}
