"use client";
import { useState } from "react";
import { ArrowRight, Upload } from "lucide-react";
import { fieldLabel, mutate, request } from "./api";
import { Badge, Button, Heading, SectionHeading } from "./ui";
import type { SharedProps } from "./types";

type Preview = {
  id: string;
  filename: string;
  headers: string[];
  fields: string[];
  mapping: Record<string, string>;
  rows: {
    row: number;
    operation: string;
    existing_id: number | null;
    values: Record<string, string | number | null>;
    before: Record<string, string | number | null> | null;
  }[];
  errors: { row_number: number | null; field: string; message: string }[];
  can_commit: boolean;
  expires_in_minutes: number;
};

export function Imports(props: SharedProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function inspect() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("mapping", JSON.stringify(mapping));
      const next = await request<Preview>("/imports/preview", {
        method: "POST",
        body: form,
      });
      setPreview(next);
      setMapping(next.mapping);
      setDirty(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function commit() {
    if (!preview || dirty) return;
    setBusy(true);
    try {
      const result = await mutate<{ rows_imported: number }>(
        `/imports/${preview.id}/commit`,
        {},
      );
      await props.refresh();
      setPreview(null);
      setFile(null);
      setMapping({});
      props.notify(
        `${result.rows_imported} reviewed rows imported. The latest change can be undone.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="Data import / Review before it changes"
        title="Bring your pipeline into focus."
        description="Map the fields, inspect changes and resolve every validation issue before committing."
      />
      <section className="m-import-drop">
        <Upload size={30} strokeWidth={1.2} />
        <h2>CSV or Excel tracker</h2>
        <p>
          Up to 5MB and 5,000 rows. Imports preserve the source filename and row
          reference.
        </p>
        <label className="m-file-label">
          Choose tracker
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setPreview(null);
              setMapping({});
              setError("");
            }}
          />
        </label>
        {file && (
          <p>
            {file.name} · {(file.size / 1024).toFixed(0)} KB
          </p>
        )}
        <Button
          kind="primary"
          disabled={!file || busy}
          onClick={() => void inspect()}
        >
          Preview and validate <ArrowRight size={16} />
        </Button>
      </section>
      {error && (
        <p className="m-error" role="alert">
          {error}
        </p>
      )}
      {preview && (
        <>
          <section className="m-surface">
            <SectionHeading
              title="Field mapping"
              detail="Each target field can be mapped once. Unmapped columns are ignored."
            />
            <div className="m-mapping-grid">
              {preview.headers.map((header) => (
                <label key={header}>
                  {header}
                  <select
                    value={mapping[header] || ""}
                    onChange={(e) => {
                      setMapping((m) => ({ ...m, [header]: e.target.value }));
                      setDirty(true);
                    }}
                  >
                    <option value="">Ignore column</option>
                    {preview.fields.map((field) => (
                      <option key={field} value={field}>
                        {fieldLabel(field)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <Button onClick={() => void inspect()} disabled={busy}>
              Refresh preview after mapping
            </Button>
          </section>
          {preview.errors.length > 0 && (
            <section className="m-validation-errors" role="alert">
              <h3>{preview.errors.length} validation issues</h3>
              {preview.errors.map((e, i) => (
                <p key={i}>
                  Row {e.row_number || "—"} · {e.field}: {e.message}
                </p>
              ))}
            </section>
          )}
          <section className="m-surface">
            <SectionHeading
              title={`${preview.rows.length} proposed changes`}
              detail="Updates match opportunity name and buyer. Duplicate rows inside a file are blocked."
            />
            <div className="m-table-scroll">
              <table className="m-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Operation</th>
                    <th>Opportunity</th>
                    <th>Changes for review</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td>
                        <Badge
                          tone={row.operation === "update" ? "amber" : "green"}
                        >
                          {row.operation}
                        </Badge>
                      </td>
                      <td>
                        {row.values.name}
                        <small>{row.values.buyer_name}</small>
                      </td>
                      <td>
                        <details>
                          <summary>Inspect mapped fields</summary>
                          {Object.entries(row.values).map(([key, value]) => (
                            <p className="m-small" key={key}>
                              {fieldLabel(key)}:{" "}
                              {row.before
                                ? `${row.before[key] ?? "Unknown"} → `
                                : ""}
                              {value ?? "Unknown"}
                            </p>
                          ))}
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="m-notice">
              <span>
                {dirty
                  ? "Mapping changed. Refresh the preview before committing."
                  : `Review expires in ${preview.expires_in_minutes} minutes. Any intervening pipeline change requires a new preview.`}
              </span>
              <Button
                kind="primary"
                disabled={busy || dirty || !preview.can_commit}
                onClick={() => void commit()}
              >
                Commit reviewed import
              </Button>
            </div>
          </section>
        </>
      )}
    </>
  );
}
