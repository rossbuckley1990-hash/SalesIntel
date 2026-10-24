// Adapted from BREAKOUT; explicit lifecycle cleanup added.
import {
  Color,
  HalfFloatType,
  LinearFilter,
  LinearMipmapLinearFilter,
  Matrix4,
  Mesh,
  PerspectiveCamera,
  Plane,
  PlaneGeometry,
  ShaderMaterial,
  Vector2,
  Vector3,
  Vector4,
  WebGLRenderTarget,
  type Camera,
  type Scene,
  type WebGLRenderer,
} from "three";

/**
 * A dark, glossy studio floor with a blurred planar reflection (rendered at reduced
 * resolution with a mip chain), a contact shadow, and a pool of light whose colour comes
 * from the commercial scene.
 */
export class MirrorFloor {
  readonly mesh: Mesh;
  readonly y: number;
  enabled = true;
  private rt: WebGLRenderTarget;
  private virtualCamera = new PerspectiveCamera();
  private textureMatrix = new Matrix4();
  private scale = 0.5;
  readonly uniforms;

  constructor(y: number) {
    this.y = y;
    this.rt = new WebGLRenderTarget(512, 512, {
      type: HalfFloatType,
      minFilter: LinearMipmapLinearFilter,
      magFilter: LinearFilter,
      generateMipmaps: true,
      depthBuffer: true,
    });
    this.uniforms = {
      uReflection: { value: this.rt.texture },
      uTextureMatrix: { value: this.textureMatrix },
      uSpill: { value: new Color(0.4, 0.45, 0.55) },
      uSpillAmount: { value: 0 },
      uDevice: { value: new Vector3(0, 0, 0) },
      uDeviceSize: { value: new Vector2(0.95, 2.0) },
      uShadow: { value: 0 },
      uReflect: { value: 1 },
      uTime: { value: 0 },
      uViewport: { value: new Vector4() },
    };
    const mat = new ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        uniform mat4 uTextureMatrix;
        varying vec4 vProj;
        varying vec3 vWorld;
        void main() {
          vProj = uTextureMatrix * vec4(position, 1.0);
          vec4 w = modelMatrix * vec4(position, 1.0);
          vWorld = w.xyz;
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: /* glsl */ `
        uniform sampler2D uReflection;
        uniform vec3 uSpill;
        uniform float uSpillAmount;
        uniform vec3 uDevice;
        uniform vec2 uDeviceSize;
        uniform float uShadow;
        uniform float uReflect;
        varying vec4 vProj;
        varying vec3 vWorld;
        float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
        void main() {
          vec2 uv = vProj.xy / vProj.w;
          vec3 V = normalize(cameraPosition - vWorld);
          float grazing = 1.0 - clamp(V.y, 0.0, 1.0);
          float fres = 0.05 + 0.6 * pow(grazing, 4.0);

          // Glossy reflection: a few taps at a coarse mip, wider further from the stage.
          vec2 rel = vWorld.xz - uDevice.xz;
          float dist = length(rel);
          float lod = 1.4 + dist * 0.4;
          vec2 px = vec2(0.0025 + dist * 0.0012);
          vec3 refl = textureLod(uReflection, uv, lod).rgb * 0.4;
          refl += textureLod(uReflection, uv + vec2( px.x,  px.y * 0.5), lod).rgb * 0.15;
          refl += textureLod(uReflection, uv + vec2(-px.x,  px.y * 0.5), lod).rgb * 0.15;
          refl += textureLod(uReflection, uv + vec2( px.x * 0.5, -px.y), lod).rgb * 0.15;
          refl += textureLod(uReflection, uv + vec2(-px.x * 0.5, -px.y), lod).rgb * 0.15;

          vec3 base = vec3(0.0042, 0.0046, 0.0056);
          base *= 0.85 + 0.3 * hash(floor(vWorld.xz * 220.0));

          // Pool of light thrown forward by the screen.
          vec2 q = rel - vec2(0.0, 0.85);
          float pool = exp(-(q.x * q.x) / (0.9 * uDeviceSize.x * 2.2) - (q.y * q.y) / 1.1);
          vec3 c = base + uSpill * pool * 0.085 * uSpillAmount;

          // Contact shadow (soft, elongated with the device).
          float sh = exp(-(rel.x * rel.x) / (0.18 * uDeviceSize.x * 2.0) - (rel.y * rel.y) / 0.06);
          c *= 1.0 - 0.65 * sh * uShadow;

          c += refl * (0.22 + fres) * uReflect;
          // Dissolve into the void.
          float fade = 1.0 - smoothstep(2.6, 8.5, dist);
          vec3 voidC = vec3(0.0016, 0.0018, 0.0023);
          c = mix(voidC, c, fade);
          c += (hash(gl_FragCoord.xy + 0.5) - 0.5) * 0.0016;
          gl_FragColor = vec4(c, 1.0);
        }`,
    });
    this.mesh = new Mesh(new PlaneGeometry(40, 40), mat);
    this.mesh.rotation.x = -Math.PI / 2;
    this.mesh.position.y = y;
    this.mesh.renderOrder = -5;
  }

  setSize(w: number, h: number, quality: number) {
    this.scale = quality > 0.8 ? 0.5 : 0.35;
    const rw = Math.max(64, Math.round(w * this.scale));
    const rh = Math.max(64, Math.round(h * this.scale));
    if (this.rt.width !== rw || this.rt.height !== rh) this.rt.setSize(rw, rh);
  }

  private reflectorWorld = new Vector3();
  private cameraWorld = new Vector3();
  private rotation = new Matrix4();
  private lookAt = new Vector3();
  private normal = new Vector3();
  private view = new Vector3();
  private target = new Vector3();
  private plane = new Plane();
  private clipPlane = new Vector4();
  private q = new Vector4();

  /** Render the mirrored scene. Call before the main render. */
  update(renderer: WebGLRenderer, scene: Scene, camera: Camera) {
    if (!this.enabled) {
      this.uniforms.uReflect.value = 0;
      return;
    }
    this.uniforms.uReflect.value = 1;
    const mesh = this.mesh;
    mesh.updateMatrixWorld();
    this.reflectorWorld.setFromMatrixPosition(mesh.matrixWorld);
    this.cameraWorld.setFromMatrixPosition(camera.matrixWorld);
    this.rotation.extractRotation(mesh.matrixWorld);
    this.normal.set(0, 0, 1).applyMatrix4(this.rotation);
    this.view.subVectors(this.reflectorWorld, this.cameraWorld);
    if (this.view.dot(this.normal) > 0) return;
    this.view.reflect(this.normal).negate().add(this.reflectorWorld);
    this.rotation.extractRotation(camera.matrixWorld);
    this.lookAt.set(0, 0, -1).applyMatrix4(this.rotation).add(this.cameraWorld);
    this.target
      .subVectors(this.reflectorWorld, this.lookAt)
      .reflect(this.normal)
      .negate()
      .add(this.reflectorWorld);
    const vc = this.virtualCamera;
    vc.position.copy(this.view);
    vc.up.set(0, 1, 0).applyMatrix4(this.rotation).reflect(this.normal);
    vc.lookAt(this.target);
    vc.far = (camera as PerspectiveCamera).far;
    vc.updateMatrixWorld();
    vc.projectionMatrix.copy((camera as PerspectiveCamera).projectionMatrix);

    this.textureMatrix.set(
      0.5,
      0,
      0,
      0.5,
      0,
      0.5,
      0,
      0.5,
      0,
      0,
      0.5,
      0.5,
      0,
      0,
      0,
      1,
    );
    this.textureMatrix
      .multiply(vc.projectionMatrix)
      .multiply(vc.matrixWorldInverse)
      .multiply(mesh.matrixWorld);

    this.plane
      .setFromNormalAndCoplanarPoint(this.normal, this.reflectorWorld)
      .applyMatrix4(vc.matrixWorldInverse);
    this.clipPlane.set(
      this.plane.normal.x,
      this.plane.normal.y,
      this.plane.normal.z,
      this.plane.constant,
    );
    const pm = vc.projectionMatrix.elements;
    this.q.x = (Math.sign(this.clipPlane.x) + pm[8]) / pm[0];
    this.q.y = (Math.sign(this.clipPlane.y) + pm[9]) / pm[5];
    this.q.z = -1;
    this.q.w = (1 + pm[10]) / pm[14];
    this.clipPlane.multiplyScalar(2 / this.clipPlane.dot(this.q));
    pm[2] = this.clipPlane.x;
    pm[6] = this.clipPlane.y;
    pm[10] = this.clipPlane.z + 1 - 0.003;
    pm[14] = this.clipPlane.w;

    const prevTarget = renderer.getRenderTarget();
    mesh.visible = false;
    renderer.setRenderTarget(this.rt);
    renderer.clear();
    renderer.render(scene, vc);
    renderer.setRenderTarget(prevTarget);
    mesh.visible = true;
  }

  dispose() {
    this.rt.dispose();
    this.mesh.geometry.dispose();
    (this.mesh.material as ShaderMaterial).dispose();
  }
}
