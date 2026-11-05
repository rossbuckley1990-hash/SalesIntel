import importlib.util
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location("db_preflight", Path(__file__).resolve().parents[1] / "scripts" / "db_preflight.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def make(path, extra=""):
    with sqlite3.connect(path) as c:
        c.execute("create table accounts (id integer primary key, name varchar(255) not null)")
        c.execute(f"create table deals (id integer primary key, account_id integer references accounts(id), title text not null{extra})")
        c.executemany("insert into accounts(name) values (?)", [("A",), ("B",)])


def test_backup_verify_and_restore_never_touch_the_source(tmp_path):
    live = tmp_path / "live.db"
    make(live)
    before = tool.sha256(live)
    manifest = tool.backup(live, tmp_path / "backups")
    assert manifest["integrity"] == "ok" and manifest["rows"] == {"accounts": 2, "deals": 0} and tool.sha256(live) == before
    copy = tmp_path / "backups" / manifest["backup"]
    assert tool.verify(copy)["ok"]
    restored = tool.restore(copy, tmp_path / "restored.db")
    assert restored["integrity"] == "ok"
    with pytest.raises(SystemExit):
        tool.restore(copy, live)  # never overwrites an existing file
    with sqlite3.connect(copy) as c:
        c.execute("delete from accounts")
    assert tool.verify(copy)["ok"] is False  # tampering or corruption is detected


def test_reconcile_reports_drift_and_refuses_to_call_it_stamp_safe(tmp_path):
    reference, live = tmp_path / "ref.db", tmp_path / "live.db"
    make(reference, ", stage varchar(24) not null")
    make(live)
    result = tool.reconcile(live, reference)
    assert result["stamp_safe"] is False and result["differences"]["missing_columns"] == ["deals.stage"]
    same = tmp_path / "same.db"
    make(same, ", stage varchar(24) not null")
    assert tool.reconcile(same, reference)["stamp_safe"] is True


def test_inspect_is_read_only(tmp_path):
    live = tmp_path / "live.db"
    make(live)
    before = tool.sha256(live)
    assert tool.inspect(live)["integrity"] == "ok" and tool.sha256(live) == before
