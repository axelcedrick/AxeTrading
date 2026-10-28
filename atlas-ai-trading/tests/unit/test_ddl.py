from pathlib import Path

import pytest

from atlas.jobs.ddl import constraint_target, load_statements, render, run, split_statements

DDL = Path(__file__).resolve().parents[2] / "sql" / "ddl"

PHASE2_TABLES = {
    "bronze.raw_candles",
    "silver.instruments",
    "silver.candles",
    "silver.cost_assumptions",
    "gold.data_quality_metrics",
    "gold.pipeline_runs",
    "gold.audit_log",
}


def test_split_respects_quotes_and_comments():
    sql = "-- commentaire ; ici\nSELECT 'a;b -- c', 'l\\'or' ;\nSELECT 2;"
    assert split_statements(sql) == ["SELECT 'a;b -- c', 'l\\'or'", "SELECT 2"]


def test_split_rejects_unterminated_string():
    with pytest.raises(ValueError, match="non terminée"):
        split_statements("SELECT 'l'or';")


def test_split_rejects_missing_semicolon():
    with pytest.raises(ValueError, match="final"):
        split_statements("SELECT 1")


def test_render_validates_catalog_name():
    assert render("CREATE SCHEMA {catalog}.x", "atlas_dev") == "CREATE SCHEMA atlas_dev.x"
    with pytest.raises(ValueError):
        render("x", "atlas; DROP CATALOG y")


def test_repo_ddl_parses_and_creates_only_phase2_tables():
    stmts = load_statements(DDL, "atlas_dev")
    created = {
        s.sql.split()[5].removeprefix("atlas_dev.")
        for s in stmts
        if s.sql.upper().startswith("CREATE TABLE IF NOT EXISTS")
    }
    assert created == PHASE2_TABLES
    assert all(s.sql.split()[0].upper() in {"CREATE", "ALTER"} for s in stmts)
    assert all("IF NOT EXISTS" in s.sql.upper() for s in stmts if s.sql.upper().startswith("CREATE"))
    assert not any("DROP" in s.sql.upper().split() for s in stmts)


def test_run_skips_existing_constraints_second_time():
    stmts = load_statements(DDL, "atlas_dev")
    executed, constraints = [], {}

    def execute(sql):
        executed.append(sql)
        t = constraint_target(sql)
        if t:
            constraints.setdefault(t[0], set()).add(t[1])

    first = run(stmts, execute, lambda t: constraints.get(t, set()))
    second = run(stmts, execute, lambda t: constraints.get(t, set()))
    n_constraints = sum(1 for s in stmts if constraint_target(s.sql))
    assert n_constraints == 8
    assert first == {"executed": len(stmts), "skipped_existing_constraint": 0}
    assert second == {"executed": len(stmts) - n_constraints, "skipped_existing_constraint": n_constraints}
