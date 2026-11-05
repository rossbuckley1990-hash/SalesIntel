/** Translate historical integration terminology in user-facing system output. */
export function publicSourceLabel(value: string): string {
  return value.replace(/rightclick[-_ ]?x/gi, "public source discovery");
}

/** Keep historical research portable without exposing legacy integration names. */
export function publicResearchExport(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(publicResearchExport);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [
    key.replace(/rightclick_x/gi, "public_api").replace(/rightclick/gi, "public_source"),
    key === "origin" && item === "rightclick_x" ? "public_api" : publicResearchExport(item),
  ]));
  if (typeof value === "string") return /^https?:\/\//i.test(value) ? value : publicSourceLabel(value);
  return value;
}
