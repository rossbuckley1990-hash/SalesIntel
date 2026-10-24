# BREAKOUT port and visual contract

The user-supplied `/Users/ross/Breakout.zip` was inspected by extracting only source files to a temporary directory. Its archive, Git metadata, dependencies, browser profiles and capture assets were not copied into MiSi. This is a source adaptation, not an unmodified package import. Retain the source owner's licensing/provenance review before distributing the application externally.

| BREAKOUT source | MiSi implementation | Adaptation |
| --- | --- | --- |
| `src/core/spring.ts` | `frontend/src/features/field/engine/spring.ts` | Analytic damped oscillator, camera presets, seeded random generator. Frame-partition invariance tested. |
| `src/core/timeline.ts` | `engine/timeline.ts` | Interruptible track timeline used by asset convergence. Stop clears pending callbacks. |
| `src/render/Shards.ts` | `engine/prism.ts`, `engine/fragments.ts` | Rounded bevel prism geometry and instanced dimensions. Source-driven colours and label textures replace screen/video UVs. |
| `src/render/shaders/common.ts` | `engine/shaders.ts` | Shared studio lighting, Fresnel and noise utility GLSL. No video sampling. |
| `src/render/MirrorFloor.ts` | `engine/MirrorFloor.ts` | Planar reflected camera, clipping and rough reflection; explicit resource disposal added. |
| `src/render/Stage.ts` | `engine/stage.ts` | Renderer/composer ownership, restrained bloom, resizing, camera, adaptive quality and scoped lifecycle. |
| `src/breakout/Breakout.ts` | `engine/stage.ts` | Rapier dynamic bodies, fixed timestep, damped home forces and kinematic dragging. Commercial layout replaces device explosion. |
| `Atmosphere.ts`, `SpatialField.ts`, `Backdrop.ts` | Inspected; omitted | Dense decorative particles and capture-oriented atmosphere would add GPU cost without a recorded commercial meaning. Recorded relation lines and the studio floor supply depth. |
| `Device.ts` | Inspected; omitted | No iPhone image, camera, screen recording, Apple Vision or capture permission is needed. |

Paths beginning `engine/` above are relative to `frontend/src/features/field/`.

## Data grammar

Each fragment has a real record ID. Portfolio view contains opportunities; focus view adds existing buyer profiles, field evidence and linked actions. A buyer link is explicitly a recorded name match, not an externally verified relationship. Other links come from evidence entity IDs or action opportunity IDs. No invented network edges are rendered.

The selected metric is annual revenue, annual gross margin or probability-weighted whole-contract value. Width is `0.85 + 0.6 × sqrt(clamp(value / maximum, 0, 1))`; the maximum is the current portfolio's selected recorded metric. This is a bounded comparative encoding, not proportional area. Unknown financial values use a fixed outlined marker, excluded from the scale. Evidence records have equal sizes. Missing evidence uses broken borders, and provenance/confidence text remains readable in the inspector and data view. Green/amber/red encode recorded risk; cyan identifies evidence/account records. Confidence is textual, not an invented numerical risk score.

Dragging, grouping, risk reveal, focus, reset and spatial undo only affect scene state. They never write commercial values. Building a pursuit pack saves an immutable API-backed asset; convergence animation is an interruptible acknowledgement. Saved scenarios use server calculations. Their existing fragment dimensions morph toward new values while the same canvas and renderer remain mounted.

## Lifecycle and fallbacks

Three.js, postprocessing and Rapier enter through client-only dynamic feature imports. Today, tables and ordinary actions do not create a renderer. One field engine owns its physics world, texture labels, geometries, materials, floor render target, composer, RAF and event subscriptions. Cleanup disposes each resource and loses the old context. Every effect creates a fresh canvas so React development effect replay cannot reuse a deliberately lost context.

Physics uses a 1/120 second step, capped at five steps per frame, and never computes money. Pixel ratio is capped at 1.6; sustained slow frames reduce quality and disable reflection at the lower tier. Hidden documents suspend rendering. Reduced-motion preference and small screens default to the semantic data view. Explicit reduced-motion 3D uses immediate camera/layout updates and renders on interaction rather than continuously. WebGL absence or context loss returns to the same data records and actions. Arrow keys select records, Escape resets and Cmd/Ctrl+Z reverses spatial movement. A semantic record list is always available.

Headless Chromium lifecycle tests measure the actual renderer state across repeated navigation and resizing, verify stable texture counts, zero active engines after unmount, no continuing frames, and forced context-loss fallback. Headless results do not establish a 60 FPS guarantee on a physical device.
