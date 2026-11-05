"""Non-destructive database preflight, backup and recovery for SalesIntel's SQLite files.

The live database was built with create_all, not Alembic, so its alembic_version is
empty. Stamping it at the head revision would only be safe if its schema matches the
schema the migrations produce. This tool proves or disproves that, and never stamps.

  inspect   --db FILE                 integrity, tables, row counts, Alembic state (read-only)
  reconcile --db FILE                 compare against a schema built by `alembic upgrade head`
  backup    --db FILE --out DIR       consistent online copy, integrity-checked, with a manifest
  verify    --backup FILE             re-check a backup against its manifest
  restore   --backup FILE --to FILE   copy a verified backup to a NEW path (never overwrites)

Nothing here writes to the source database. Restoring over a live file is a manual,
documented step (docs/DATABASE_OPERATIONS.md) so it can only happen deliberately.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[1]


def readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"No database at {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]


def columns(conn: sqlite3.Connection, table: str) -> dict[str, dict]:
    return {r[1]: {"type": (r[2] or "").upper(), "notnull": bool(r[3]), "pk": bool(r[5])} for r in conn.execute(f'pragma table_info("{table}")')}


def indexes(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'pragma index_list("{table}")') if not r[1].startswith("sqlite_autoindex")}


def foreign_keys(conn: sqlite3.Connection, table: str) -> set[str]:
    return {f"{r[3]}->{r[2]}.{r[4]}" for r in conn.execute(f'pragma foreign_key_list("{table}")')}


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables(conn)}


def alembic_state(conn: sqlite3.Connection) -> dict:
    if "alembic_version" not in tables(conn):
        return {"table": False, "revision": None}
    rows = [r[0] for r in conn.execute("select version_num from alembic_version")]
    return {"table": True, "revision": rows[0] if rows else None}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(path: Path) -> dict:
    with readonly(path) as conn:
        return {"path": str(path), "bytes": path.stat().st_size, "integrity": conn.execute("pragma quick_check").fetchone()[0],
                "tables": len(tables(conn)), "alembic": alembic_state(conn), "rows": row_counts(conn)}


def reference_schema() -> Path:
    """Build an empty database from the migrations alone."""
    folder = Path(tempfile.mkdtemp(prefix="salesintel-reference-"))
    target = folder / "reference.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{target}", "PYTHONPATH": str(BACKEND)}
    result = subprocess.run([sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), "upgrade", "head"],
                            cwd=BACKEND, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"Could not build the reference schema:\n{result.stderr[-2000:]}")
    return target


def head_revision(reference: Path) -> str | None:
    with readonly(reference) as conn:
        return alembic_state(conn)["revision"]


def reconcile(path: Path, reference: Path | None = None) -> dict:
    reference = reference or reference_schema()
    with readonly(path) as live, readonly(reference) as ref:
        live_tables = set(tables(live)) - {"alembic_version"}
        ref_tables = set(tables(ref)) - {"alembic_version"}
        diffs: dict[str, list] = {"missing_tables": sorted(ref_tables - live_tables), "extra_tables": sorted(live_tables - ref_tables),
                                  "missing_columns": [], "extra_columns": [], "type_differences": [], "nullability_differences": [], "foreign_key_differences": [], "missing_indexes": []}
        for table in sorted(live_tables & ref_tables):
            have, want = columns(live, table), columns(ref, table)
            diffs["missing_columns"] += [f"{table}.{c}" for c in sorted(set(want) - set(have))]
            diffs["extra_columns"] += [f"{table}.{c}" for c in sorted(set(have) - set(want))]
            for name in sorted(set(have) & set(want)):
                if have[name]["type"] != want[name]["type"]:
                    diffs["type_differences"].append(f"{table}.{name}: live {have[name]['type'] or '(none)'} vs migrations {want[name]['type'] or '(none)'}")
                if have[name]["notnull"] != want[name]["notnull"] and not have[name]["pk"]:
                    diffs["nullability_differences"].append(f"{table}.{name}: live {'NOT NULL' if have[name]['notnull'] else 'NULL'} vs migrations {'NOT NULL' if want[name]['notnull'] else 'NULL'}")
            diffs["foreign_key_differences"] += [f"{table}: {fk}" for fk in sorted(foreign_keys(ref, table) ^ foreign_keys(live, table))]
            diffs["missing_indexes"] += [f"{table}.{i}" for i in sorted(indexes(ref, table) - indexes(live, table))]
        blocking = {k: v for k, v in diffs.items() if v and k not in ("missing_indexes",)}
        return {"database": str(path), "alembic": alembic_state(live), "migrations_head": head_revision(reference),
                "stamp_safe": not blocking, "differences": diffs,
                "verdict": ("Schema matches the migrations. Stamping at head would be accurate, but it is still not done automatically."
                            if not blocking else "Do not stamp. The live schema differs from what the migrations produce; reconcile these differences first.")}


def backup(path: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = out / f"{path.stem}-{stamp}.db"
    if target.exists():
        raise SystemExit(f"{target} already exists")
    with readonly(path) as source, sqlite3.connect(target) as copy:
        source.backup(copy)  # consistent snapshot, safe while the app is running
    with readonly(target) as conn:
        integrity = conn.execute("pragma integrity_check").fetchone()[0]
        manifest = {"source": str(path), "backup": target.name, "created_at": stamp, "sha256": sha256(target), "bytes": target.stat().st_size,
                    "integrity": integrity, "alembic": alembic_state(conn), "rows": row_counts(conn)}
    if integrity != "ok":
        raise SystemExit(f"Backup failed its integrity check: {integrity}")
    target.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def verify(backup_path: Path) -> dict:
    manifest_path = backup_path.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise SystemExit(f"No manifest beside {backup_path}")
    manifest = json.loads(manifest_path.read_text())
    problems = []
    if sha256(backup_path) != manifest["sha256"]:
        problems.append("checksum differs from the manifest")
    with readonly(backup_path) as conn:
        if (integrity := conn.execute("pragma integrity_check").fetchone()[0]) != "ok":
            problems.append(f"integrity check: {integrity}")
        if row_counts(conn) != manifest["rows"]:
            problems.append("row counts differ from the manifest")
    return {"backup": str(backup_path), "ok": not problems, "problems": problems}


def restore(backup_path: Path, to: Path) -> dict:
    if to.exists():
        raise SystemExit(f"{to} already exists. Restore only writes to a new path; switching files is a manual step.")
    checked = verify(backup_path)
    if not checked["ok"]:
        raise SystemExit(f"Backup did not verify: {checked['problems']}")
    with readonly(backup_path) as source, sqlite3.connect(to) as copy:
        source.backup(copy)
    return {"restored_to": str(to), "from": str(backup_path), "integrity": inspect(to)["integrity"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "reconcile"):
        sub.add_parser(name).add_argument("--db", type=Path, required=True)
    b = sub.add_parser("backup")
    b.add_argument("--db", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    sub.add_parser("verify").add_argument("--backup", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("--backup", type=Path, required=True)
    r.add_argument("--to", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {"inspect": lambda: inspect(args.db), "reconcile": lambda: reconcile(args.db), "backup": lambda: backup(args.db, args.out),
              "verify": lambda: verify(args.backup), "restore": lambda: restore(args.backup, args.to)}[args.command]()
    print(json.dumps(result, indent=1, default=str))
    return 0 if result.get("ok", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
