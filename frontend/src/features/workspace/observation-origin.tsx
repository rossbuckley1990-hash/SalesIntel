"use client";

/** Optional on historical snapshots made before inbox integration. */
export type ObservationOrigin = {
  origin?: "web_search" | "evidence_inbox" | "rightclick_x" | "public_api";
  organisation_name?: string | null;
  site?: string | null;
  retrieved_at?: string | null;
};

export function ImportedObservationDetails({ observation }: { observation: ObservationOrigin }) {
  if ((observation.origin === "rightclick_x" || observation.origin === "public_api")) return <p className="mt-2 text-xs leading-5 text-[#825929]">
    <strong>Public API · unverified</strong>
    {" · Retrieved: "}{observation.retrieved_at?.trim() || "Date not provided"}
    {" · Context only. Confirm the identifier, location and source before associating it with an organisation or opportunity."}
  </p>;
  if (observation.origin !== "evidence_inbox") return null;
  return <p className="mt-2 text-xs leading-5 text-[#825929]">
    <strong>Imported · unverified</strong>
    {" · Organisation: "}{observation.organisation_name?.trim() || "Not provided"}
    {" · Site: "}{observation.site?.trim() || "Not provided"}
    {" · Retrieved: "}{observation.retrieved_at?.trim() || "Date not provided"}
    {" · Confirm identity, site and the original source before use."}
  </p>;
}
