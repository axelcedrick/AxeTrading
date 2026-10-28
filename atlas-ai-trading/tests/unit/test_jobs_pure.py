"""Parties pures des jobs (sans Spark) : génération du MERGE et comparaisons du contrôle."""

from pathlib import Path

from atlas.common.config import load_universe
from atlas.jobs.foundations_check import (
    EXPECTED_TABLES,
    KO,
    OK,
    PENDING,
    check_config,
    compare_instruments,
    compare_tables,
)
from atlas.jobs.seed_instruments import merge_sql, pending_changes_sql, universe_rows

ROOT = Path(__file__).resolve().parents[2]


def test_universe_rows_and_merge_sql():
    rows = universe_rows(load_universe(ROOT / "config" / "universe.yml"))
    assert len(rows) == 6 and rows[-1]["instrument_id"] == "XAUUSD"
    sql = merge_sql("atlas_dev")
    assert "MERGE INTO atlas_dev.silver.instruments" in sql
    assert "WHEN NOT MATCHED BY SOURCE AND t.is_active" in sql
    assert "DELETE" not in sql.upper()
    pending = pending_changes_sql("atlas_dev")
    assert "FULL OUTER JOIN atlas_dev.silver.instruments" in pending and "{" not in pending


def test_compare_tables_detects_premature_gold_table():
    found = {k: set(v) for k, v in EXPECTED_TABLES.items()}
    assert compare_tables(found)[0] == OK
    found["gold"].add("signals")
    status, detail = compare_tables(found)
    assert status == KO and detail["unexpected"] == {"gold": ["signals"]}


def test_compare_instruments():
    expected = universe_rows(load_universe(ROOT / "config" / "universe.yml"))
    assert compare_instruments(expected, [dict(r) for r in expected])[0] == OK
    altered = [dict(r) for r in expected]
    altered[0]["pip_size"] = 0.001
    status, detail = compare_instruments(expected, altered[:-1])
    assert status == KO and detail["missing"] == ["XAUUSD"] and "EURUSD" in detail["diffs"]


def test_check_config_reports_risk_pending():
    res = check_config(ROOT / "config")
    assert res["config_universe"][0] == OK and res["config_costs"][0] == OK
    assert res["config_risk"][0] == PENDING
