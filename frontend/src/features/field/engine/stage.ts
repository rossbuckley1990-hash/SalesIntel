import {
  BufferAttribute,
  BufferGeometry,
  Color,
  HalfFloatType,
  LineBasicMaterial,
  LineSegments,
  PerspectiveCamera,
  Plane,
  Raycaster,
  Scene,
  SRGBColorSpace,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import {
  BloomEffect,
  EffectComposer,
  EffectPass,
  RenderPass,
} from "postprocessing";
import type RAPIER from "@dimforge/rapier3d-compat";
import { CommercialFragments } from "./fragments";
import { MirrorFloor } from "./MirrorFloor";
import { Spring, SPRING, clamp, mulberry32 } from "./spring";
import { Timeline } from "./timeline";
import type { FieldGraph } from "../graph";

type RapierModule = typeof RAPIER;
type Diagnostics = {
  activeEngines: number;
  duplicateFrames: number;
  frames: number;
  fps: number;
  textures: number;
  geometries: number;
  drawCalls: number;
  quality: number;
};
declare global {
  interface Window {
    __MISI_FIELD_DIAGNOSTICS__?: Diagnostics;
  }
}
let physicsReady: Promise<RapierModule> | undefined;
async function physics() {
  physicsReady ??= import("@dimforge/rapier3d-compat").then(async (module) => {
    const engine = module.default;
    await engine.init();
    return engine;
  });
  return physicsReady;
}
const DT = 1 / 120;

/** Data-scene adaptation of BREAKOUT Stage + Breakout: fixed steps, damped home forces,
 * kinematic pointer dragging, analytic camera springs and scoped GPU ownership. */
export class FieldStage {
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(34, 1, 0.1, 150);
  readonly renderer: WebGLRenderer;
  readonly composer: EffectComposer;
  readonly fragments: CommercialFragments;
  readonly floor = new MirrorFloor(-4.5);
  private world: RAPIER.World | null = null;
  private rapier: RapierModule | null = null;
  private bodies: RAPIER.RigidBody[] = [];
  private positions: Vector3[] = [];
  private targets: Vector3[] = [];
  private homes: Vector3[] = [];
  private labels: HTMLDivElement[] = [];
  private localUndo: Vector3[][] = [];
  private lines: LineSegments;
  private edgePositions: Float32Array;
  private timeline = new Timeline();
  private cameraX = new Spring(0, SPRING.camera);
  private cameraY = new Spring(0.3, SPRING.camera);
  private radius = new Spring(20, SPRING.camera);
  private resizeObserver: ResizeObserver;
  private frame = 0;
  private disposed = false;
  private selected = -1;
  private dragging = -1;
  private pointerStart = new Vector2();
  private dragTarget = new Vector3();
  private raycaster = new Raycaster();
  private plane = new Plane(new Vector3(0, 0, 1), 0);
  private acc = 0;
  private lastTime = 0;
  private slowFrames = 0;
  private quality = 1;
  private width = 1;
  private height = 1;
  private visible = true;
  private cleanupListeners: (() => void)[] = [];
  constructor(
    private canvas: HTMLCanvasElement,
    private overlay: HTMLDivElement,
    public graph: FieldGraph,
    private onSelect: (id: string) => void,
    private fallback: () => void,
    private reduced: boolean,
  ) {
    this.renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.setClearColor(0x0b110f, 1);
    this.scene.background = new Color(0x0b110f);
    this.fragments = new CommercialFragments(graph);
    this.scene.add(this.fragments.group);
    this.floor.uniforms.uSpill.value.set(0x8cbf71);
    this.floor.uniforms.uSpillAmount.value = 0.25;
    this.floor.uniforms.uReflect.value = 0.35;
    this.scene.add(this.floor.mesh);
    this.composer = new EffectComposer(this.renderer, {
      frameBufferType: HalfFloatType,
      multisampling: 0,
    });
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.composer.addPass(
      new EffectPass(
        this.camera,
        new BloomEffect({
          intensity: 0.12,
          luminanceThreshold: 0.95,
          mipmapBlur: true,
        }),
      ),
    );
    this.edgePositions = new Float32Array(graph.edges.length * 6);
    const geometry = new BufferGeometry();
    geometry.setAttribute(
      "position",
      new BufferAttribute(this.edgePositions, 3),
    );
    this.lines = new LineSegments(
      geometry,
      new LineBasicMaterial({
        color: 0x507562,
        transparent: true,
        opacity: 0.45,
      }),
    );
    this.lines.frustumCulled = false;
    this.scene.add(this.lines);
    this.homes = this.layout();
    this.targets = this.homes.map((p) => p.clone());
    const random = mulberry32(
      graph.nodes.reduce((sum, n) => sum + n.recordId, 1701),
    );
    this.positions = this.homes.map((p) =>
      this.reduced
        ? p.clone()
        : new Vector3(
            (random() - 0.5) * 15,
            (random() - 0.5) * 10,
            -3 - random() * 5,
          ),
    );
    graph.nodes.forEach((node) => {
      const label = document.createElement("div");
      label.className = "m-field-node-label";
      label.textContent = node.title;
      label.setAttribute("aria-hidden", "true");
      this.overlay.append(label);
      this.labels.push(label);
    });
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement!);
    this.resize();
    this.listen(canvas, "pointerdown", this.pointerDown as EventListener);
    this.listen(canvas, "pointermove", this.pointerMove as EventListener);
    this.listen(canvas, "pointerup", this.pointerUp as EventListener);
    this.listen(canvas, "pointercancel", this.pointerUp as EventListener);
    this.listen(canvas, "lostpointercapture", this.pointerUp as EventListener);
    this.listen(canvas, "webglcontextlost", ((e: Event) => {
      e.preventDefault();
      this.fallback();
    }) as EventListener);
    this.listen(canvas, "keydown", this.keyDown as EventListener);
    this.listen(document, "visibilitychange", () => {
      this.visible = !document.hidden;
      this.lastTime = 0;
      if (this.visible && !this.frame && !this.disposed)
        this.frame = requestAnimationFrame(this.tick);
    });
    this.visible = !document.hidden;
    const diagnostics = (window.__MISI_FIELD_DIAGNOSTICS__ ??= {
      activeEngines: 0,
      duplicateFrames: 0,
      frames: 0,
      fps: 0,
      textures: 0,
      geometries: 0,
      drawCalls: 0,
      quality: 1,
    });
    diagnostics.activeEngines++;
    if (!this.reduced)
      void physics()
        .then((engine) => {
          if (this.disposed) return;
          this.rapier = engine;
          this.world = new engine.World({ x: 0, y: 0, z: 0 });
          this.world.timestep = DT;
          this.positions.forEach((p, i) => {
            const body = this.world!.createRigidBody(
              engine.RigidBodyDesc.dynamic()
                .setTranslation(p.x, p.y, p.z)
                .setLinearDamping(2)
                .setAngularDamping(5)
                .lockRotations()
                .setCcdEnabled(true),
            );
            const size = this.fragments.sizes[i];
            this.world!.createCollider(
              engine.ColliderDesc.cuboid(size.x * 0.97, size.y * 0.97, size.z)
                .setRestitution(0.12)
                .setFriction(0.55),
              body,
            );
            this.bodies.push(body);
          });
        })
        .catch(() => {
          if (!this.disposed) this.fallback();
        });
    this.requestFrame();
  }
  private requestFrame() {
    if (!this.frame && !this.disposed && this.visible)
      this.frame = requestAnimationFrame(this.tick);
  }
  updateGraph(graph: FieldGraph) {
    this.graph = graph;
    this.fragments.setGraph(graph);
    this.labels.forEach(
      (label, i) => (label.textContent = graph.nodes[i].title),
    );
    this.requestFrame();
  }
  private listen(target: EventTarget, event: string, handler: EventListener) {
    target.addEventListener(event, handler);
    this.cleanupListeners.push(() =>
      target.removeEventListener(event, handler),
    );
  }
  private layout(grouped = false): Vector3[] {
    const focused = this.graph.edges.length > 0;
    const count = this.graph.nodes.length;
    if (!focused)
      return this.graph.nodes.map(
        (_, i) =>
          new Vector3(
            ((i % 3) - 1) * 4.1,
            (Math.floor((count - 1) / 3) / 2 - Math.floor(i / 3)) * 2.8,
            0,
          ),
      );
    return this.graph.nodes.map((node, i) => {
      if (node.kind === "opportunity") return new Vector3(0, 0, 1.1);
      if (grouped) {
        const left = node.unknown || node.kind === "action";
        const peers = this.graph.nodes
          .slice(0, i)
          .filter(
            (n) =>
              (n.unknown || n.kind === "action") === left &&
              n.kind !== "opportunity",
          ).length;
        return new Vector3(left ? -4.3 : 4.3, 3.5 - peers * 1.5, -0.5);
      }
      const angle =
        ((i - 1) / Math.max(1, count - 1)) * Math.PI * 2 - Math.PI / 2;
      return new Vector3(
        Math.cos(angle) * 5.3,
        Math.sin(angle) * 3.9,
        -0.5 + Math.sin(angle * 2) * 0.2,
      );
    });
  }
  private resize() {
    if (this.disposed) return;
    this.requestFrame();
    const rect = this.canvas.parentElement!.getBoundingClientRect();
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    this.renderer.setPixelRatio(
      Math.min(window.devicePixelRatio || 1, 1.6) * this.quality,
    );
    this.renderer.setSize(this.width, this.height, false);
    this.composer.setSize(this.width, this.height);
    this.floor.setSize(this.width, this.height, this.quality);
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.radius.target = Math.max(
      18,
      8.2 / (Math.tan((17 * Math.PI) / 180) * this.camera.aspect),
    );
  }
  setMode(mode: "assemble" | "risk" | "group" | "pack") {
    this.requestFrame();
    this.localUndo.push(this.targets.map((p) => p.clone()));
    this.localUndo = this.localUndo.slice(-20);
    this.timeline.stop();
    if (mode === "pack" && !this.reduced) {
      this.targets = this.graph.nodes.map(
        (_, i) => new Vector3(0, 0, i * -0.12),
      );
      this.timeline
        .at(0.9, () => {
          this.targets = this.homes.map((p) => p.clone());
        })
        .play();
    } else if (mode === "group") this.targets = this.layout(true);
    else if (mode === "risk")
      this.targets = this.homes.map((p, i) =>
        p
          .clone()
          .add(
            new Vector3(
              0,
              0,
              this.graph.nodes[i].unknown ||
              /red/i.test(this.graph.nodes[i].risk)
                ? 2
                : -1,
            ),
          ),
      );
    else {
      this.targets = this.homes.map((p) => p.clone());
      this.selected = -1;
      this.cameraX.target = 0;
      this.cameraY.target = 0.3;
    }
    if (this.reduced) this.positions = this.targets.map((p) => p.clone());
  }
  undoMove() {
    this.requestFrame();
    const previous = this.localUndo.pop();
    if (previous) {
      this.targets = previous;
      this.timeline.stop();
    }
  }
  focus(id: string) {
    this.requestFrame();
    const i = this.graph.nodes.findIndex((n) => n.id === id);
    this.selected = i;
    if (i >= 0) {
      const p = this.positions[i];
      this.cameraX.target = p.x * 0.1;
      this.cameraY.target = 0.3 + p.y * 0.08;
      this.onSelect(id);
    }
  }
  private pointerRay(event: PointerEvent) {
    const rect = this.canvas.getBoundingClientRect();
    this.raycaster.setFromCamera(
      new Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        1 - ((event.clientY - rect.top) / rect.height) * 2,
      ),
      this.camera,
    );
  }
  private hit(event: PointerEvent) {
    this.pointerRay(event);
    let index = -1;
    let distance = Infinity;
    const hit = new Vector3();
    this.positions.forEach((p, i) => {
      this.plane.constant = -p.z;
      if (this.raycaster.ray.intersectPlane(this.plane, hit)) {
        const size = this.fragments.sizes[i];
        if (
          Math.abs(hit.x - p.x) <= size.x &&
          Math.abs(hit.y - p.y) <= size.y
        ) {
          const d = this.camera.position.distanceTo(hit);
          if (d < distance) {
            index = i;
            distance = d;
          }
        }
      }
    });
    return index;
  }
  private pointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return;
    const i = this.hit(event);
    if (i < 0) return;
    this.canvas.focus();
    this.focus(this.graph.nodes[i].id);
    this.dragging = i;
    this.pointerStart.set(event.clientX, event.clientY);
    this.dragTarget.copy(this.positions[i]);
    this.localUndo.push(this.targets.map((p) => p.clone()));
    this.localUndo = this.localUndo.slice(-20);
    if (this.rapier && this.bodies[i])
      this.bodies[i].setBodyType(
        this.rapier.RigidBodyType.KinematicPositionBased,
        true,
      );
    this.canvas.setPointerCapture(event.pointerId);
    this.canvas.style.cursor = "grabbing";
  };
  private pointerMove = (event: PointerEvent) => {
    if (this.dragging < 0) {
      this.canvas.style.cursor = this.hit(event) >= 0 ? "grab" : "default";
      return;
    }
    this.pointerRay(event);
    this.plane.constant = -this.positions[this.dragging].z;
    const p = new Vector3();
    if (this.raycaster.ray.intersectPlane(this.plane, p)) {
      p.x = clamp(p.x, -7, 7);
      p.y = clamp(p.y, -4.5, 4.5);
      this.requestFrame();
      this.dragTarget.copy(p);
      this.targets[this.dragging].copy(p);
    }
  };
  private pointerUp = () => {
    if (this.dragging >= 0 && this.rapier && this.bodies[this.dragging])
      this.bodies[this.dragging].setBodyType(
        this.rapier.RigidBodyType.Dynamic,
        true,
      );
    this.dragging = -1;
    this.canvas.style.cursor = "default";
  };
  private keyDown = (event: KeyboardEvent) => {
    if (
      ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)
    ) {
      event.preventDefault();
      const direction =
        event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1;
      const index =
        (this.selected + direction + this.graph.nodes.length) %
        this.graph.nodes.length;
      if (this.graph.nodes[index]) this.focus(this.graph.nodes[index].id);
    }
    if (event.key === "Escape") this.setMode("assemble");
    if ((event.metaKey || event.ctrlKey) && event.key === "z") {
      event.preventDefault();
      this.undoMove();
    }
  };
  private step() {
    if (!this.world) return;
    this.bodies.forEach((body, i) => {
      const target = this.targets[i];
      if (i === this.dragging) {
        body.setNextKinematicTranslation(this.dragTarget);
        return;
      }
      const p = body.translation();
      const v = body.linvel();
      const kp = 36,
        kd = 10;
      body.setLinvel(
        {
          x: v.x + (kp * (target.x - p.x) - kd * v.x) * DT,
          y: v.y + (kp * (target.y - p.y) - kd * v.y) * DT,
          z: v.z + (kp * (target.z - p.z) - kd * v.z) * DT,
        },
        true,
      );
    });
    this.world.step();
  }
  private tick = (now: number) => {
    this.frame = 0;
    if (this.disposed || !this.visible) return;
    const rawDt = this.lastTime ? (now - this.lastTime) / 1000 : 1 / 60;
    const dt = Math.min(rawDt, 0.05);
    this.lastTime = now;
    this.timeline.update(dt);
    this.fragments.morph(dt, this.reduced);
    this.bodies.forEach((body, i) => {
      const size = this.fragments.sizes[i];
      body
        .collider(0)
        .setHalfExtents({ x: size.x * 0.97, y: size.y * 0.97, z: size.z });
    });
    if (this.reduced) {
      this.positions = this.targets.map((p) => p.clone());
    } else if (this.world) {
      this.acc += dt;
      let n = 0;
      while (this.acc >= DT && n < 5) {
        this.step();
        this.acc -= DT;
        n++;
      }
      if (n === 5) this.acc = 0;
      this.bodies.forEach((b, i) => this.positions[i].copy(b.translation()));
    } else
      this.positions.forEach((p, i) =>
        p.lerp(this.targets[i], 1 - Math.exp(-8 * dt)),
      );
    this.positions.forEach((p, i) =>
      this.fragments.update(i, p, this.selected === i ? 0.08 : 0),
    );
    this.fragments.flush();
    const tx = this.reduced ? this.cameraX.target : this.cameraX.update(dt);
    const ty = this.reduced ? this.cameraY.target : this.cameraY.update(dt);
    const r = this.reduced ? this.radius.target : this.radius.update(dt);
    this.camera.position.set(tx, ty + 0.5, r);
    this.camera.lookAt(tx, ty, 0);
    this.camera.updateMatrixWorld();
    const byId = new Map(this.graph.nodes.map((node, i) => [node.id, i]));
    this.graph.edges.forEach((edge, i) => {
      const a = this.positions[byId.get(edge.source)!];
      const b = this.positions[byId.get(edge.target)!];
      this.edgePositions.set(
        [a.x, a.y, a.z - 0.13, b.x, b.y, b.z - 0.13],
        i * 6,
      );
    });
    (this.lines.geometry.attributes.position as BufferAttribute).needsUpdate =
      true;
    this.positions.forEach((p, i) => {
      const screen = p
        .clone()
        .add(new Vector3(0, -this.fragments.sizes[i].y - 0.13, 0.1))
        .project(this.camera);
      const label = this.labels[i];
      label.style.transform = `translate(${((screen.x + 1) * this.width) / 2}px,${((1 - screen.y) * this.height) / 2}px) translate(-50%,0)`;
      label.style.opacity = screen.z > 1 ? "0" : "1";
    });
    this.floor.enabled = this.quality >= 0.75;
    this.floor.update(this.renderer, this.scene, this.camera);
    this.composer.render(dt);
    if (rawDt > 1 / 40) this.slowFrames++;
    else this.slowFrames = Math.max(0, this.slowFrames - 1);
    if (this.slowFrames > 100 && this.quality > 0.6) {
      this.quality = Math.max(0.6, this.quality - 0.15);
      this.slowFrames = 0;
      this.resize();
    }
    const d = window.__MISI_FIELD_DIAGNOSTICS__!;
    d.frames++;
    if (rawDt === 0) d.duplicateFrames++;
    d.fps = d.fps ? d.fps * 0.95 + (1 / Math.max(rawDt, 0.001)) * 0.05 : 1 / dt;
    d.textures = this.renderer.info.memory.textures;
    d.geometries = this.renderer.info.memory.geometries;
    d.drawCalls = this.renderer.info.render.calls;
    d.quality = this.quality;
    if (!this.reduced || this.dragging >= 0) this.requestFrame();
  };
  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.timeline.stop();
    this.resizeObserver.disconnect();
    this.cleanupListeners.forEach((fn) => fn());
    this.world?.free();
    this.bodies = [];
    this.fragments.dispose();
    this.lines.geometry.dispose();
    (this.lines.material as LineBasicMaterial).dispose();
    this.floor.dispose();
    this.composer.dispose();
    this.renderer.dispose();
    if (!this.renderer.getContext().isContextLost())
      this.renderer.forceContextLoss();
    this.labels.forEach((label) => label.remove());
    const d = window.__MISI_FIELD_DIAGNOSTICS__;
    if (d) {
      d.activeEngines = Math.max(0, d.activeEngines - 1);
      d.textures = 0;
      d.geometries = 0;
    }
  }
}
