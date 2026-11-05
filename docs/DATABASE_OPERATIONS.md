# Database operations: preflight, backup and recovery

SalesIntel runs on a local SQLite file, `.runtime/false-alarm-pilot-v2.db`. Its schema was created with `create_all`, not Alembic, so its `alembic_version` table holds no revision. All the tooling below is in `backend/scripts/db_preflight.py`, and none of it writes to the source database.

## 1. Preflight before any schema change

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/db_preflight.py inspect   --db .runtime/false-alarm-pilot-v2.db
PYTHONPATH=backend .venv/bin/python backend/scripts/db_preflight.py reconcile --db .runtime/false-alarm-pilot-v2.db
```

- `inspect` opens the file read-only. It reports integrity, tables, row counts and the Alembic state.
- `reconcile` builds an empty database from the migrations alone (`alembic upgrade head`) and compares it with the live file. It checks tables, columns, column types, nullability, foreign keys and indexes. It does not check default values or check constraints.

Result on 5 November 2026: the integrity check passed; there are 60 tables; there are no differences from migration head `0019_salesintel_crm`; and `stamp_safe` is true.

## 2. Bringing the live database under Alembic (decision required, not done)

Stamping records that the database is at a revision without running any migration. It is only correct when `reconcile` reports `stamp_safe: true`. As of 5 November it does.

Because stamping changes how future migrations are applied, it is left to an explicit decision. If approved:

1. Stop SalesIntel and the scheduled collectors.
2. Take and verify a backup (section 3).
3. Run `reconcile` again and confirm `stamp_safe: true`.
4. Run `DATABASE_URL=sqlite:///$PWD/.runtime/false-alarm-pilot-v2.db PYTHONPATH=backend .venv/bin/python -m alembic -c backend/alembic.ini stamp 0019_salesintel_crm`.
5. Confirm with `inspect` that the revision is recorded, then restart.

From then on, schema changes go through `alembic upgrade head` after a backup, never through `create_all` on the live file.

## 3. Backup

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/db_preflight.py backup --db .runtime/false-alarm-pilot-v2.db --out .runtime/backups
PYTHONPATH=backend .venv/bin/python backend/scripts/db_preflight.py verify --backup .runtime/backups/<file>.db
```

- The backup uses SQLite's online backup, so it is consistent even while SalesIntel is running.
- It writes a `.manifest.json` beside the backup with the checksum, integrity result, Alembic state and row counts.
- `verify` re-checks all of these and reports a changed or corrupted backup.

The latest verified backup is `.runtime/backups/false-alarm-pilot-v2-20261105T092340Z.db` (86,709 rows).

## 4. Recovery

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/db_preflight.py restore --backup .runtime/backups/<file>.db --to .runtime/restored.db
```

`restore` verifies the backup and writes a copy to a new path. It refuses to overwrite an existing file. To switch to the restored file:

1. Stop SalesIntel and the collectors.
2. Rename the live file aside: `mv .runtime/false-alarm-pilot-v2.db .runtime/false-alarm-pilot-v2.replaced-<date>.db`.
3. Move the restored file into place: `mv .runtime/restored.db .runtime/false-alarm-pilot-v2.db`.
4. Run `inspect`, then restart.

The replaced file is kept until you decide otherwise.

## 5. Rules

- Back up before any schema change or bulk operation.
- Never run `create_all`, `drop_all` or `reset_db` against the live file.
- Test against a copy: the `backup` command produces one.
