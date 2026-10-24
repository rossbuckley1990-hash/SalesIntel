// Ported from the user-supplied BREAKOUT repository. See docs/living/BREAKOUT_PORT.md.
import { clamp } from "./spring";

interface Track {
  start: number;
  duration: number;
  fn: (t: number) => void;
  done: boolean;
  started: boolean;
}

/** A tiny choreography timeline: tracks receive normalised progress 0..1. */
export class Timeline {
  private tracks: Track[] = [];
  private time = 0;
  private finished: (() => void) | null = null;
  running = false;

  add(start: number, duration: number, fn: (t: number) => void): this {
    this.tracks.push({ start, duration, fn, done: false, started: false });
    return this;
  }

  /** Fire once at a moment in time. */
  at(time: number, fn: () => void): this {
    return this.add(time, 0, (t) => t >= 1 && fn());
  }

  play(onDone?: () => void): this {
    this.time = 0;
    this.running = true;
    this.finished = onDone ?? null;
    for (const t of this.tracks) {
      t.done = false;
      t.started = false;
    }
    return this;
  }

  stop() {
    this.running = false;
    this.tracks = [];
  }

  update(dt: number) {
    if (!this.running) return;
    this.time += dt;
    let all = true;
    for (const tr of this.tracks) {
      if (tr.done) continue;
      if (this.time < tr.start) {
        all = false;
        continue;
      }
      const p =
        tr.duration <= 0
          ? 1
          : clamp((this.time - tr.start) / tr.duration, 0, 1);
      tr.started = true;
      tr.fn(p);
      if (p >= 1) tr.done = true;
      else all = false;
    }
    if (all) {
      this.running = false;
      const f = this.finished;
      this.finished = null;
      f?.();
    }
  }
}
