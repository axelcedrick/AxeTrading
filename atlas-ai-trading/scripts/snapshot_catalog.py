"""Instantané d'un catalogue ATLAS (lignes, schéma, contraintes, version Delta) pour vérifier l'idempotence.

Usage : python scripts/snapshot_catalog.py atlas_dev > avant.json
Passe par le SQL warehouse via le CLI Databricks (profil dans DATABRICKS_CONFIG_PROFILE).
Comparer deux instantanés : python scripts/snapshot_catalog.py --diff avant.json apres.json
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time

PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE", "dbc-2ca00ccd-e312")
TABLES = [
    "bronze.raw_candles",
    "silver.instruments",
    "silver.candles",
    "silver.cost_assumptions",
    "gold.data_quality_metrics",
    "gold.pipeline_runs",
    "gold.audit_log",
]


def _api(method: str, path: str, body: dict | None = None) -> dict:
    cmd = ["databricks", "api", method, path, "-p", PROFILE]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt", check=False)  # noqa: S603
    if out.returncode != 0:
        raise SystemExit(f"erreur CLI : {out.stderr.strip()}")
    return json.loads(out.stdout)


def _warehouse_id() -> str:
    whs = _api("get", "/api/2.0/sql/warehouses").get("warehouses", [])
    if not whs:
        raise SystemExit("aucun SQL warehouse")
    return whs[0]["id"]


def sql(statement: str, wh: str) -> list[list]:
    r = _api(
        "post", "/api/2.0/sql/statements", {"warehouse_id": wh, "statement": statement, "wait_timeout": "50s"}
    )
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = _api("get", f"/api/2.0/sql/statements/{r['statement_id']}")
    if r["status"]["state"] != "SUCCEEDED":
        raise SystemExit(f"{statement[:60]} : {r['status'].get('error', {}).get('message', '')[:300]}")
    return (r.get("result") or {}).get("data_array") or []


def snapshot(catalog: str) -> dict:
    # Identifiant contrôlé : les requêtes ci-dessous n'interpolent que ce nom et des noms fixes.
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", catalog):
        raise SystemExit(f"nom de catalogue invalide : {catalog!r}")
    wh = _warehouse_id()
    snap = {"catalog": catalog, "tables": {}}
    for t in TABLES:
        fq = f"{catalog}.{t}"
        cols = sql(f"DESCRIBE TABLE {fq}", wh)
        props = sql(f"SHOW TBLPROPERTIES {fq}", wh)
        snap["tables"][t] = {
            "rows": int(sql(f"SELECT count(*) FROM {fq}", wh)[0][0]),  # noqa: S608
            "schema_sha256": hashlib.sha256(json.dumps(cols).encode()).hexdigest()[:16],
            "describe_rows": len(cols),
            "constraints": sorted(k for k, _ in props if k.startswith("delta.constraints.")),
            "delta_version": int(sql(f"DESCRIBE HISTORY {fq} LIMIT 1", wh)[0][0]),
        }
    max_ts = f"SELECT max(updated_ts) FROM {catalog}.silver.instruments"  # noqa: S608
    snap["instruments_max_updated_ts"] = sql(max_ts, wh)[0][0]
    snap["schemas"] = sorted(r[0] for r in sql(f"SHOW SCHEMAS IN {catalog}", wh))
    snap["tables_per_schema"] = {
        s: sorted(r[1] for r in sql(f"SHOW TABLES IN {catalog}.{s}", wh))
        for s in ("bronze", "silver", "gold")
    }
    return snap


def diff(a: dict, b: dict) -> list[str]:
    out = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k), y.get(k), f"{path}.{k}" if path else k)
        elif x != y:
            out.append(f"{path} : {x!r} -> {y!r}")

    walk(a, b, "")
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--diff":
        with open(sys.argv[2], encoding="utf-8") as f1, open(sys.argv[3], encoding="utf-8") as f2:
            changes = diff(json.load(f1), json.load(f2))
        print("\n".join(changes) if changes else "AUCUNE DIFFÉRENCE")
        sys.exit(1 if changes else 0)
    print(json.dumps(snapshot(sys.argv[1]), indent=1, ensure_ascii=False))
