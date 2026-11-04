"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { Button } from "./ui";

export type LeadAction = { id: number; lead_id: number; text: string; status: "open" | "completed" | "deferred"; due_date: string | null };

async function saveAction<T>(path: string, method: "POST" | "PATCH", body: unknown): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(typeof result?.detail === "string" ? result.detail : "Could not save this next move. Please try again.");
  }
  return response.json();
}

/** User-owned follow-ups. Recommendations are editable before anything is saved. */
export function LeadActions({ leadId, suggestion, initialActions }: { leadId: number; suggestion: string; initialActions: LeadAction[] }) {
  const [actions, setActions] = useState(initialActions);
  const changed = useRef(false);
  const [text, setText] = useState(suggestion);
  const [dueDate, setDueDate] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [editDate, setEditDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  // The list is shown immediately, then the lead is refreshed. Do not let a
  // late refresh overwrite an action the user has already changed locally.
  useEffect(() => { if (!changed.current) setActions(initialActions); }, [initialActions]);

  async function add(event: FormEvent) {
    event.preventDefault();
    if (busy || text.trim().length < 5) return;
    setBusy(true); setMessage("");
    try {
      const action = await saveAction<LeadAction>(`/api/research-dossiers/leads/${leadId}/actions`, "POST", { text: text.trim(), due_date: dueDate || null });
      changed.current = true;
      setActions((current) => [action, ...current]);
      setText(""); setDueDate(""); setMessage("Next move saved. Find it on Today.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save the next move."); }
    finally { setBusy(false); }
  }

  async function update(id: number, change: { status?: LeadAction["status"]; text?: string; due_date?: string | null }) {
    if (busy) return;
    setBusy(true); setMessage("");
    try {
      const action = await saveAction<LeadAction>(`/api/research-dossiers/actions/${id}`, "PATCH", change);
      changed.current = true;
      setActions((current) => current.map((item) => item.id === id ? action : item));
      setEditing(null); setMessage("Next move updated.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update the next move."); }
    finally { setBusy(false); }
  }

  return <section className="mt-5 border-t border-[var(--misi-border)] pt-5" aria-label="Next moves">
    <div><h4 className="text-sm font-semibold text-[var(--misi-ink)]">Your next moves</h4><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">Keep the work you choose alongside the evidence. Open moves also appear on Today.</p></div>
    {actions.length > 0 && <ul className="mt-4 divide-y divide-white/10 border-y border-[var(--misi-border)]">{actions.map((action) => <li key={action.id} className="py-4">
      {editing === action.id ? <form onSubmit={(event) => { event.preventDefault(); if (editText.trim().length >= 5) void update(action.id, { text: editText.trim(), due_date: editDate || null }); }}>
        <label htmlFor={`edit-action-${action.id}`} className="block text-xs text-[var(--misi-ink)]">Edit next move</label><textarea id={`edit-action-${action.id}`} value={editText} onChange={(event) => setEditText(event.target.value)} required minLength={5} maxLength={1200} rows={2} className="mt-1 w-full rounded-lg border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]" />
        <div className="mt-2 flex flex-wrap items-end gap-2"><label htmlFor={`edit-date-${action.id}`} className="text-xs text-[var(--misi-ink)]">Due date, optional<input id={`edit-date-${action.id}`} type="date" value={editDate} onChange={(event) => setEditDate(event.target.value)} className="mt-1 block rounded-lg border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]" /></label><Button type="submit" disabled={busy || editText.trim().length < 5}>Save move</Button><Button type="button" disabled={busy} onClick={() => setEditing(null)}>Cancel</Button></div>
      </form> : <><p className="text-sm leading-6 text-[var(--misi-ink)]">{action.text}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{action.status === "open" ? "Open" : action.status === "completed" ? "Completed" : "Deferred"}{action.due_date ? ` · Due ${action.due_date}` : " · No due date"}</p><div className="mt-3 flex flex-wrap gap-2"><Button disabled={busy} onClick={() => { setEditing(action.id); setEditText(action.text); setEditDate(action.due_date || ""); }}>Edit</Button>{action.status !== "completed" && <Button disabled={busy} onClick={() => void update(action.id, { status: "completed" })}>Mark done</Button>}{action.status === "open" && <Button disabled={busy} onClick={() => void update(action.id, { status: "deferred" })}>Defer</Button>}{action.status !== "open" && <Button disabled={busy} onClick={() => void update(action.id, { status: "open" })}>Reopen</Button>}</div></>}
    </li>)}</ul>}
    {actions.length >= 50 && <p className="mt-2 text-xs text-[var(--misi-muted)]">Showing the latest 50 saved moves.</p>}
    <form onSubmit={(event) => void add(event)} className="mt-4 rounded-xl border border-[var(--misi-border)] p-4"><h4 className="text-sm font-semibold text-[var(--misi-ink)]">Add a next move</h4><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">Edit the suggested verification step or write your own.</p><label htmlFor="lead-action-text" className="mt-3 block text-xs text-[var(--misi-ink)]">Action</label><input id="lead-action-text" value={text} onChange={(event) => setText(event.target.value)} required minLength={5} maxLength={1200} className="mt-1 w-full rounded-lg border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]" /><div className="mt-3 flex flex-wrap items-end gap-3"><label htmlFor="lead-action-date" className="text-xs text-[var(--misi-ink)]">Due date, optional<input id="lead-action-date" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="mt-1 block rounded-lg border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]" /></label><Button type="submit" disabled={busy || text.trim().length < 5}>{busy ? "Saving…" : "Add next move"}</Button></div></form>
    {message && <p role="status" className="mt-2 text-xs leading-5 text-[var(--misi-accent)]">{message}</p>}
  </section>;
}
