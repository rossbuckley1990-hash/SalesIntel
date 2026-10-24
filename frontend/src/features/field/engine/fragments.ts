import {
  CanvasTexture,
  Color,
  DoubleSide,
  Group,
  InstancedBufferAttribute,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  ShaderMaterial,
  SRGBColorSpace,
  Vector3,
} from "three";
import { buildRoundedPrism } from "./prism";
import { glslCommon } from "./shaders";
import { boundedScale, type FieldGraph, type FieldNode } from "../graph";

export function nodeColor(node: FieldNode): string {
  if (node.unknown) return "#cba268";
  if (/red|high/i.test(node.risk)) return "#d87772";
  if (/amber|medium/i.test(node.risk)) return "#cba268";
  if (node.kind === "opportunity" || /green/i.test(node.risk)) return "#a4d77d";
  if (node.kind === "action") return "#c4cae5";
  return "#7cb8bf";
}
function fit(
  context: CanvasRenderingContext2D,
  text: string,
  width: number,
): string {
  let value = text;
  while (context.measureText(value).width > width && value.length > 1)
    value = value.slice(0, -1);
  return value === text ? text : value.slice(0, -1) + "…";
}
function labelTexture(node: FieldNode): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 384;
  const c = canvas.getContext("2d")!;
  c.clearRect(0, 0, 768, 384);
  const accent = nodeColor(node);
  c.fillStyle = accent;
  c.font = "500 25px system-ui";
  c.fillText(fit(c, node.subtitle, 660), 40, 64);
  c.fillStyle = "#edf1e9";
  c.font = "500 38px system-ui";
  c.fillText(fit(c, node.title, 680), 40, 135);
  c.fillStyle = node.unknown ? "#cba268" : accent;
  c.font = `${node.kind === "opportunity" || node.kind === "financial" ? "500 66" : "500 42"}px system-ui`;
  c.fillText(fit(c, node.value, 675), 40, 232);
  c.fillStyle = "#9ba69e";
  c.font = "400 22px system-ui";
  c.fillText(
    node.confidence == null
      ? node.kind === "opportunity"
        ? "ESTIMATED · SELECT TO INSPECT"
        : node.id.toUpperCase()
      : `${Math.round(node.confidence * 100)}% CONFIDENCE · ${node.id}`,
    40,
    323,
  );
  c.strokeStyle = accent;
  c.lineWidth = 2;
  c.globalAlpha = 0.6;
  if (node.unknown) c.setLineDash([12, 12]);
  c.strokeRect(16, 16, 736, 352);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

/** BREAKOUT's bevelled instanced shard geometry, now shaded from data rather than video. */
export class CommercialFragments {
  readonly group = new Group();
  readonly mesh: InstancedMesh;
  readonly labels: Mesh[] = [];
  readonly sizes: { x: number; y: number; z: number }[] = [];
  private textures: CanvasTexture[] = [];
  private targetSizes: { x: number; y: number; z: number }[] = [];
  private originalSizes: { x: number; y: number; z: number }[] = [];
  constructor(readonly graph: FieldGraph) {
    const geometry = buildRoundedPrism(6);
    const count = graph.nodes.length;
    const dims = new Float32Array(count * 4);
    const tint = new Float32Array(count * 3);
    graph.nodes.forEach((node, i) => {
      const scale = ["opportunity", "financial"].includes(node.kind)
        ? boundedScale(node.numericValue, graph.maxValue)
        : 0.78;
      const size = { x: 1.45 * scale, y: 0.73 * scale, z: 0.075 };
      this.sizes.push(size);
      dims.set([size.x, size.y, size.z, 0.1], i * 4);
      new Color(nodeColor(node)).toArray(tint, i * 3);
    });
    geometry.setAttribute("iDims", new InstancedBufferAttribute(dims, 4));
    geometry.setAttribute("iTint", new InstancedBufferAttribute(tint, 3));
    const material = new ShaderMaterial({
      vertexShader: `attribute vec2 aCorner; attribute vec2 aDir; attribute float aInset; attribute vec2 aZ; attribute vec4 iDims; attribute vec3 iTint; varying vec3 vN; varying vec3 vWorld; varying vec3 vTint;
      void main(){ float r=min(iDims.w,min(iDims.x,iDims.y)); float beta=min(iDims.z*.85,r*.6); vec2 xy=aCorner*(iDims.xy-r)+aDir*(r-aInset*beta); float z=aZ.x*(iDims.z-aZ.y*beta); vec4 w=modelMatrix*instanceMatrix*vec4(xy,z,1.); vWorld=w.xyz; vN=normalize(mat3(modelMatrix*instanceMatrix)*normal); vTint=iTint; gl_Position=projectionMatrix*viewMatrix*w; }`,
      fragmentShader: `${glslCommon} varying vec3 vN; varying vec3 vWorld; varying vec3 vTint;
      void main(){ vec3 n=normalize(vN); vec3 view=normalize(cameraPosition-vWorld); vec3 reflection=studioEnv(reflect(-view,n)); float f=fresnelSchlick(max(dot(n,view),0.),.06); float front=max(n.z,0.); vec3 base=mix(vec3(.04,.055,.055),vec3(.014,.023,.020),front); vec3 c=base+reflection*(.025+f*.22)+vTint*.12*(1.-front); gl_FragColor=vec4(c,1.); }`,
    });
    this.mesh = new InstancedMesh(geometry, material, count);
    this.mesh.frustumCulled = false;
    this.group.add(this.mesh);
    graph.nodes.forEach((node, i) => {
      const size = this.sizes[i];
      const texture = labelTexture(node);
      this.textures.push(texture);
      const plane = new Mesh(
        new PlaneGeometry(size.x * 1.96, size.y * 1.96),
        new MeshBasicMaterial({
          map: texture,
          transparent: true,
          depthWrite: false,
          side: DoubleSide,
          toneMapped: false,
        }),
      );
      this.labels.push(plane);
      this.group.add(plane);
    });
    this.targetSizes = this.sizes.map((v) => ({ ...v }));
    this.originalSizes = this.sizes.map((v) => ({ ...v }));
  }
  setGraph(graph: FieldGraph) {
    graph.nodes.forEach((node, i) => {
      const scale = ["opportunity", "financial"].includes(node.kind)
        ? boundedScale(node.numericValue, graph.maxValue)
        : 0.78;
      this.targetSizes[i] = { x: 1.45 * scale, y: 0.73 * scale, z: 0.075 };
      const texture = labelTexture(node);
      this.textures[i].dispose();
      this.textures[i] = texture;
      const material = this.labels[i].material as MeshBasicMaterial;
      material.map = texture;
      material.needsUpdate = true;
      const tint = this.mesh.geometry.getAttribute(
        "iTint",
      ) as InstancedBufferAttribute;
      const color = new Color(nodeColor(node));
      tint.setXYZ(i, color.r, color.g, color.b);
      tint.needsUpdate = true;
    });
  }
  morph(dt: number, reduced: boolean) {
    const dims = this.mesh.geometry.getAttribute(
      "iDims",
    ) as InstancedBufferAttribute;
    const blend = reduced ? 1 : 1 - Math.exp(-8 * dt);
    this.sizes.forEach((size, i) => {
      size.x += (this.targetSizes[i].x - size.x) * blend;
      size.y += (this.targetSizes[i].y - size.y) * blend;
      dims.setXYZW(i, size.x, size.y, size.z, 0.1);
      this.labels[i].scale.set(
        size.x / this.originalSizes[i].x,
        size.y / this.originalSizes[i].y,
        1,
      );
    });
    dims.needsUpdate = true;
  }
  update(index: number, position: Vector3, lift = 0) {
    const matrix = new Matrix4().makeTranslation(
      position.x,
      position.y,
      position.z + lift,
    );
    this.mesh.setMatrixAt(index, matrix);
    this.labels[index].position.set(
      position.x,
      position.y,
      position.z + lift + this.sizes[index].z + 0.012,
    );
  }
  flush() {
    this.mesh.instanceMatrix.needsUpdate = true;
  }
  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as ShaderMaterial).dispose();
    for (const plane of this.labels) {
      plane.geometry.dispose();
      (plane.material as MeshBasicMaterial).dispose();
    }
    this.textures.forEach((t) => t.dispose());
  }
}
