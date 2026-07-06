from pathlib import Path

from batch_queue import build_plan, read_batch_csv
from contact_store import init_contact_store, set_opt_in
from storage import init_database


def test_csv_plan_uses_sequential_delays(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WA_DB_PATH", str(tmp_path / "test.db"))
    init_database()
    init_contact_store()
    set_opt_in("10001", source="test")

    path = tmp_path / "input.csv"
    path.write_text(
        "contact_name,phone,message,consent,consent_source,consent_note\n"
        "One,10001,First,no,,\n"
        "Two,10002,Second,yes,test,Recorded\n",
        encoding="utf-8",
    )

    rows = read_batch_csv(path)
    plan, errors = build_plan(
        rows,
        initial_delay_seconds=15,
        gap_seconds=20,
        maximum_contacts=10,
    )

    assert errors == []
    assert [item.delay_seconds for item in plan] == [15, 35]
    assert plan[0].needs_opt_in is False
    assert plan[1].needs_opt_in is True
