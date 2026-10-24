// BREAKOUT studio lighting utilities. Video sampling intentionally excluded.
/** Shared GLSL used by the screen, shards, matter and floor shaders. */

export const glslCommon = /* glsl */ `
float sdRoundRect(vec2 p, vec2 halfSize, float r) {
  vec2 q = abs(p) - halfSize + r;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// Interleaved gradient noise: cheap, stable screen-space dither for fades.
float ign(vec2 p) {
  return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

/*
 * Analytic studio environment: an overhead softbox, a key strip light and a cool rim
 * strip, in a near-black room. Used for glass sheen and edge glints so every surface
 * reflects the same imaginary studio.
 */
vec3 studioEnv(vec3 R) {
  vec3 c = vec3(0.003, 0.0035, 0.005) + vec3(0.010, 0.011, 0.014) * pow(1.0 - abs(R.y), 8.0);
  if (R.y > 0.0) {
    vec2 p = R.xz / R.y;
    float box = smoothstep(1.35, 0.95, abs(p.x)) * smoothstep(0.9, 0.55, abs(p.y - 0.55));
    c += vec3(1.0, 0.985, 0.96) * box * 1.35;
  }
  if (R.x < 0.0) {
    vec2 q = R.yz / -R.x;
    float strip = smoothstep(0.22, 0.10, abs(q.y - 0.75)) * smoothstep(1.3, 0.7, abs(q.x - 0.15));
    c += vec3(0.86, 0.91, 1.0) * strip * 0.9;
  }
  if (R.x > 0.0) {
    vec2 q = R.yz / R.x;
    float rim = smoothstep(0.16, 0.06, abs(q.y + 0.55)) * smoothstep(1.5, 0.8, abs(q.x));
    c += vec3(0.72, 0.82, 1.0) * rim * 0.8;
  }
  return c;
}

float fresnelSchlick(float cosTheta, float f0) {
  return f0 + (1.0 - f0) * pow(1.0 - clamp(cosTheta, 0.0, 1.0), 5.0);
}
`;
