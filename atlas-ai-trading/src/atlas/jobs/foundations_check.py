"""Job de vérification des fondations (phase 2) : `atlas_foundations_check`.

Contrôles : schémas et tables présents (et aucune table prématurée), configuration lisible et valide,
secret du fournisseur accessible (jamais affiché), référentiel des instruments conforme au fichier.
La configuration de risque non encore renseignée par l'utilisateur est signalée EN_ATTENTE : c'est
l'état attendu (le moteur refusera toute opération), pas une erreur de fondation.
Le job échoue (code 1) si un contrôle est KO.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from atlas.common.config import ConfigError, MissingValuesError, load_costs, load_risk, load_universe
from atlas.common.logging import get_logger
from atlas.common.secrets import SecretError, get_secret
from atlas.jobs.seed_instruments import universe_rows

EXPECTED_TABLES: dict[str, set[str]] = {
    "bronze": {"raw_candles"},
    "silver": {"instruments", "candles", "cost_assumptions"},
    "gold": {"data_quality_metrics", "pipeline_runs", "audit_log"},
}

OK, KO, PENDING = "OK", "KO", "EN_ATTENTE"


def compare_tables(found: dict[str, set[str]]) -> tuple[str, dict[str, Any]]:
    missing = {s: sorted(EXPECTED_TABLES[s] - found.get(s, set())) for s in EXPECTED_TABLES}
    extra = {s: sorted(found.get(s, set()) - EXPECTED_TABLES[s]) for s in EXPECTED_TABLES}
    missing = {k: v for k, v in missing.items() if v}
    extra = {k: v for k, v in extra.items() if v}
    return (KO if missing or extra else OK), {"missing": missing, "unexpected": extra}


def compare_instruments(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[str, dict]:
    exp = {r["instrument_id"]: r for r in expected}
    act = {r["instrument_id"]: r for r in actual if r.get("is_active")}
    diffs = {
        iid: {k: (exp[iid][k], act[iid].get(k)) for k in exp[iid] if exp[iid][k] != act[iid].get(k)}
        for iid in exp.keys() & act.keys()
    }
    diffs = {k: v for k, v in diffs.items() if v}
    detail = {
        "count": len(act),
        "missing": sorted(exp.keys() - act.keys()),
        "unexpected_active": sorted(act.keys() - exp.keys()),
        "diffs": diffs,
        "reference_status": sorted({r["reference_status"] for r in act.values()}),
    }
    ok = not (detail["missing"] or detail["unexpected_active"] or diffs)
    return (OK if ok else KO), detail


def check_config(config_dir: Path) -> dict[str, tuple[str, Any]]:
    out: dict[str, tuple[str, Any]] = {}
    try:
        universe = load_universe(config_dir / "universe.yml")
        out["config_universe"] = (OK, {"instruments": len(universe.instruments)})
    except ConfigError as exc:
        return {"config_universe": (KO, str(exc))}
    try:
        costs = load_costs(config_dir / "costs.yml", universe=universe)
        out["config_costs"] = (
            OK,
            {"assumptions": len(costs.assumptions), "sources": sorted({a.source for a in costs.assumptions})},
        )
    except ConfigError as exc:
        out["config_costs"] = (KO, str(exc))
    try:
        load_risk(config_dir / "risk.yml")
        out["config_risk"] = (OK, "valeurs fournies et valides")
    except MissingValuesError as exc:
        out["config_risk"] = (PENDING, {"refusée car incomplète": exc.missing})
    except ConfigError as exc:
        out["config_risk"] = (KO, str(exc))
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True)
    p.add_argument("--config-dir", required=True)
    p.add_argument("--secret-scope", required=True)
    p.add_argument("--secret-key", required=True)
    p.add_argument("--target", required=True)
    args = p.parse_args(argv)
    log = get_logger("atlas.foundations_check")
    results: dict[str, tuple[str, Any]] = {}

    results["environment"] = (
        OK,
        {
            "target": args.target,
            "catalog": args.catalog,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "atlas": version("atlas"),
        },
    )

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    schemas = {r[0] for r in spark.sql(f"SHOW SCHEMAS IN {args.catalog}").collect()}
    results["schemas"] = (OK if {"bronze", "silver", "gold"} <= schemas else KO, sorted(schemas))
    found = {
        s: {
            r["tableName"]
            for r in spark.sql(f"SHOW TABLES IN {args.catalog}.{s}").collect()
            if not r["isTemporary"]
        }
        for s in EXPECTED_TABLES
        if s in schemas
    }
    results["tables"] = compare_tables(found)

    config_dir = Path(args.config_dir)
    results.update(check_config(config_dir))

    try:
        get_secret(args.secret_scope, args.secret_key)
        results["secret"] = (
            OK,
            f"{args.secret_scope}/{args.secret_key} présent et valide (valeur non affichée)",
        )
    except SecretError as exc:
        results["secret"] = (KO, str(exc))

    if results["config_universe"][0] == OK:
        expected = universe_rows(load_universe(config_dir / "universe.yml"))
        cols = list(expected[0])
        actual = [
            r.asDict(recursive=True)
            for r in spark.table(f"{args.catalog}.silver.instruments").select(*cols).collect()
        ]
        results["instruments"] = compare_instruments(expected, actual)
    else:
        results["instruments"] = (KO, "configuration de l'univers invalide")

    report = {k: {"status": s, "detail": d} for k, (s, d) in results.items()}
    print("ATLAS_FOUNDATIONS_CHECK " + json.dumps(report, ensure_ascii=False, default=str))
    failed = [k for k, (s, _) in results.items() if s == KO]
    log.info(
        "vérification terminée",
        extra={"failed": failed, "pending": [k for k, (s, _) in results.items() if s == PENDING]},
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
