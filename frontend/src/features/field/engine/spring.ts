// Ported from the user-supplied BREAKOUT repository. See docs/living/BREAKOUT_PORT.md.
/**
 * Analytic damped springs. Stable at any frame time (no explicit-Euler blowups),
 * so motion stays smooth when the tab hiccups or the GPU is busy.
 */

export interface SpringConfig {
  /** Angular frequency (rad/s). Higher = snappier. */
  stiffness: number;
  /** Damping ratio. 1 = critically damped, <1 overshoots. */
  damping: number;
}

export const SPRING = {
  gentle: { stiffness: 6, damping: 1 },
  smooth: { stiffness: 9, damping: 0.95 },
  snappy: { stiffness: 16, damping: 0.85 },
  bouncy: { stiffness: 13, damping: 0.55 },
  camera: { stiffness: 4.2, damping: 1 },
} satisfies Record<string, SpringConfig>;

/** Advance a 1D damped harmonic oscillator exactly by dt. Returns [x, v]. */
export function stepSpring(
  x: number,
  v: number,
  target: number,
  dt: number,
  cfg: SpringConfig,
): [number, number] {
  const w = cfg.stiffness;
  const z = cfg.damping;
  const d = x - target;
  if (dt <= 0) return [x, v];
  if (z < 1) {
    const wd = w * Math.sqrt(1 - z * z);
    const e = Math.exp(-z * w * dt);
    const c = Math.cos(wd * dt);
    const s = Math.sin(wd * dt);
    const b = (v + z * w * d) / wd;
    const nd = e * (d * c + b * s);
    const nv = e * (c * (b * wd - z * w * d) - s * (d * wd + z * w * b));
    return [target + nd, nv];
  }
  // Critically damped (and overdamped treated as critical for simplicity).
  const e = Math.exp(-w * dt);
  const nd = (d + (v + w * d) * dt) * e;
  const nv = (v - (v + w * d) * w * dt) * e;
  return [target + nd, nv];
}

export class Spring {
  value: number;
  velocity = 0;
  target: number;
  constructor(
    initial: number,
    public cfg: SpringConfig = SPRING.smooth,
  ) {
    this.value = initial;
    this.target = initial;
  }
  set(v: number): this {
    this.value = v;
    this.target = v;
    this.velocity = 0;
    return this;
  }
  update(dt: number): number {
    [this.value, this.velocity] = stepSpring(
      this.value,
      this.velocity,
      this.target,
      dt,
      this.cfg,
    );
    return this.value;
  }
  get settled(): boolean {
    return (
      Math.abs(this.value - this.target) < 1e-4 &&
      Math.abs(this.velocity) < 1e-3
    );
  }
}

export const clamp = (x: number, a: number, b: number) =>
  x < a ? a : x > b ? b : x;
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smoothstep = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
export const easeOutExpo = (t: number) =>
  t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
export const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
export const easeOutCubic = (t: number) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);

/** Small deterministic PRNG so layouts explode the same way for the same content. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Frame-rate independent exponential smoothing factor. */
export const damp = (lambda: number, dt: number) => 1 - Math.exp(-lambda * dt);
