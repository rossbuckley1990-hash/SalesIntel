// Rounded prism mesh construction ported from BREAKOUT Shards.ts.
import { BufferAttribute, BufferGeometry } from "three";

export function buildRoundedPrism(segments = 6): BufferGeometry {
  const corners: [number, number, number][] = [
    [1, 1, 0],
    [-1, 1, Math.PI / 2],
    [-1, -1, Math.PI],
    [1, -1, Math.PI * 1.5],
  ];
  const ring: { cx: number; cy: number; dx: number; dy: number }[] = [];
  for (const [cx, cy, a0] of corners) {
    for (let s = 0; s <= segments; s++) {
      const a = a0 + (s / segments) * (Math.PI / 2);
      ring.push({ cx, cy, dx: Math.cos(a), dy: Math.sin(a) });
    }
  }
  const N = ring.length;
  type RingDef = {
    inset: number;
    zs: number;
    zi: number;
    n: (dx: number, dy: number) => [number, number, number];
  };
  const nz =
    (a: number, b: number) =>
    (dx: number, dy: number): [number, number, number] => {
      const l = Math.hypot(a, b);
      return [(dx * a) / l, (dy * a) / l, b / l];
    };
  const defs: RingDef[] = [
    { inset: 1, zs: 1, zi: 0, n: () => [0, 0, 1] }, // 0 front face rim
    { inset: 1, zs: 1, zi: 0, n: nz(0.5, 0.87) }, // 1 bevel top
    { inset: 0, zs: 1, zi: 1, n: nz(0.9, 0.42) }, // 2 bevel bottom
    { inset: 0, zs: 1, zi: 1, n: (dx, dy) => [dx, dy, 0] }, // 3 side top
    { inset: 0, zs: -1, zi: 1, n: (dx, dy) => [dx, dy, 0] }, // 4 side bottom
    { inset: 0, zs: -1, zi: 1, n: nz(0.9, -0.42) }, // 5 back bevel
    { inset: 1, zs: -1, zi: 0, n: nz(0.5, -0.87) }, // 6 back bevel
    { inset: 1, zs: -1, zi: 0, n: () => [0, 0, -1] }, // 7 back face rim
  ];
  const vcount = defs.length * N + 2;
  const position = new Float32Array(vcount * 3);
  const normal = new Float32Array(vcount * 3);
  const corner = new Float32Array(vcount * 2);
  const dir = new Float32Array(vcount * 2);
  const inset = new Float32Array(vcount);
  const zl = new Float32Array(vcount * 2);
  let v = 0;
  const push = (
    c: [number, number],
    d: [number, number],
    ins: number,
    zs: number,
    zi: number,
    n: [number, number, number],
  ) => {
    position.set([c[0] + d[0] * 0.1, c[1] + d[1] * 0.1, zs], v * 3);
    normal.set(n, v * 3);
    corner.set(c, v * 2);
    dir.set(d, v * 2);
    inset[v] = ins;
    zl.set([zs, zi], v * 2);
    v++;
  };
  for (const def of defs)
    for (const r of ring)
      push(
        [r.cx, r.cy],
        [r.dx, r.dy],
        def.inset,
        def.zs,
        def.zi,
        def.n(r.dx, r.dy),
      );
  const cFront = v;
  push([0, 0], [0, 0], 0, 1, 0, [0, 0, 1]);
  const cBack = v;
  push([0, 0], [0, 0], 0, -1, 0, [0, 0, -1]);

  const idx: number[] = [];
  const R = (ri: number, i: number) => ri * N + (i % N);
  for (let i = 0; i < N; i++) idx.push(cFront, R(0, i), R(0, i + 1));
  const strip = (a: number, b: number) => {
    for (let i = 0; i < N; i++)
      idx.push(
        R(a, i),
        R(b, i),
        R(b, i + 1),
        R(a, i),
        R(b, i + 1),
        R(a, i + 1),
      );
  };
  strip(1, 2);
  strip(3, 4);
  strip(5, 6);
  for (let i = 0; i < N; i++) idx.push(cBack, R(7, i + 1), R(7, i));

  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(position, 3));
  g.setAttribute("normal", new BufferAttribute(normal, 3));
  g.setAttribute("aCorner", new BufferAttribute(corner, 2));
  g.setAttribute("aDir", new BufferAttribute(dir, 2));
  g.setAttribute("aInset", new BufferAttribute(inset, 1));
  g.setAttribute("aZ", new BufferAttribute(zl, 2));
  g.setIndex(idx);
  return g;
}
