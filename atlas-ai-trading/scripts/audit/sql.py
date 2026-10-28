"""Audit phase 1 (jetable) : exécute une instruction SQL sur le SQL warehouse serverless via le CLI.

Usage : python scripts/audit/sql.py "SELECT 1"
Le profil CLI est lu dans DATABRICKS_CONFIG_PROFILE. Aucun secret n'est manipulé ici.
"""
import json
import os
import subprocess
import sys
import time

WAREHOUSE_ID = os.environ.get("ATLAS_AUDIT_WAREHOUSE", "0e64555bdb7e335b")
PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE", "dbc-2ca00ccd-e312")


def api(method: str, path: str, body: dict | None = None) -> dict:
    cmd = ["databricks", "api", method, path, "-p", PROFILE]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, shell=os.name == "nt")
    if out.returncode != 0:
        raise SystemExit(f"CLI error: {out.stderr.strip()}")
    return json.loads(out.stdout)


def run(statement: str) -> dict:
    t0 = time.time()
    r = api("post", "/api/2.0/sql/statements", {
        "warehouse_id": WAREHOUSE_ID, "statement": statement, "wait_timeout": "50s",
    })
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(3)
        r = api("get", f"/api/2.0/sql/statements/{r['statement_id']}")
    r["_elapsed_s"] = round(time.time() - t0, 1)
    return r


if __name__ == "__main__":
    res = run(sys.argv[1])
    print(f"state={res['status']['state']} elapsed={res['_elapsed_s']}s")
    if "error" in res["status"]:
        print("error:", res["status"]["error"].get("message", "")[:500])
    rows = (res.get("result") or {}).get("data_array")
    if rows:
        for row in rows[:50]:
            print(row)
