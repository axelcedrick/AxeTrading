"""Audit phase 1 (jetable) : tests fournisseur Twelve Data exécutés DANS un job serverless.

Argument : main | fresh | burst.
- Chaque appel est journalisé dans atlas.bronze.audit_calls (budget global plafonné).
- La clé est lue depuis le secret Databricks, envoyée en en-tête (jamais dans l'URL),
  et retirée de tout ce qui est sauvegardé ou affiché.
"""
import json
import sys
import time
from datetime import datetime, timezone

import requests
from databricks.sdk.runtime import dbutils
from pyspark.sql import SparkSession

PHASE = sys.argv[1]
BASE = "https://api.twelvedata.com"
BUDGET_MAX = 38          # plafond de la phase 1 (40) moins 2 appels de diagnostic hors journal
SPACING_S = 8.5          # 8 appels / minute max -> ~7 par minute
FIXTURES = "/Volumes/atlas/bronze/audit_fixtures"
LEDGER = "atlas.bronze.audit_calls"

spark = SparkSession.builder.getOrCreate()
KEY = dbutils.secrets.get("atlas-audit", "twelvedata_api_key")
# Garde-fou : un secret mal saisi (caractère invisible) est refusé avant tout appel, jamais corrigé en silence.
if not (KEY and KEY.isascii() and KEY.isalnum()):
    raise SystemExit("secret twelvedata_api_key invalide (caractère non alphanumérique) : à ressaisir")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {LEDGER} (
    call_ts TIMESTAMP, phase STRING, label STRING, endpoint STRING, params STRING,
    http_status INT, api_code INT, credits_used STRING, credits_left STRING,
    elapsed_ms INT, note STRING)""")


def scrub(text: str) -> str:
    return text.replace(KEY, "***MASQUÉ***") if KEY else text


def calls_used() -> int:
    return spark.sql(f"SELECT count(*) AS n FROM {LEDGER}").collect()[0]["n"]


def out(**kw):
    print("AUDIT_RESULT " + scrub(json.dumps(kw, default=str, ensure_ascii=False)))


def call(label: str, endpoint: str, params: dict, save: str | None = None, spacing=True):
    used = calls_used()
    if used >= BUDGET_MAX:
        raise RuntimeError(f"budget atteint ({used}/{BUDGET_MAX}) : appel '{label}' annulé")
    t = time.time()
    r = requests.get(f"{BASE}/{endpoint}", params=params,
                     headers={"Authorization": f"apikey {KEY}"}, timeout=30)
    elapsed = int((time.time() - t) * 1000)
    now = datetime.now(timezone.utc)
    try:
        body = r.json()
    except ValueError:
        body = {"_non_json": r.text[:500]}
    api_code = body.get("code") if isinstance(body, dict) else None
    hdrs = {k: v for k, v in r.headers.items() if "credit" in k.lower() or "limit" in k.lower()}
    spark.createDataFrame([(now, PHASE, label, endpoint, json.dumps(params), r.status_code,
                            api_code, r.headers.get("api-credits-used"),
                            r.headers.get("api-credits-left"), elapsed,
                            scrub(json.dumps(hdrs)))],
                          schema=spark.table(LEDGER).schema).write.mode("append").saveAsTable(LEDGER)
    if save:
        fixture = {"_audit": {"label": label, "endpoint": endpoint, "params": params,
                              "request_ts_utc": now.isoformat(), "http_status": r.status_code,
                              "response_headers": dict(r.headers)},
                   "payload": body}
        dbutils.fs.put(f"{FIXTURES}/{save}.json", scrub(json.dumps(fixture, indent=2)), True)
    if spacing:
        time.sleep(SPACING_S)
    return r, body, now


def last_bar(body):
    vals = body.get("values") or []
    return vals[0] if vals else None


def freshness(sym: str, interval: str, label: str, save: str | None = None):
    r, body, now = call(label, "time_series",
                        {"symbol": sym, "interval": interval, "outputsize": 3, "timezone": "UTC"}, save)
    bar = last_bar(body)
    lag = None
    if bar:
        bar_open = datetime.fromisoformat(bar["datetime"]).replace(tzinfo=timezone.utc)
        lag = round((now - bar_open).total_seconds(), 1)
    out(test="C5", symbol=sym, interval=interval, request_utc=now.isoformat(),
        last_bar=bar, lag_from_bar_open_s=lag, http=r.status_code, api_code=body.get("code"),
        message=body.get("message"))


UNIVERSE = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF", "XAU/USD"]

if PHASE == "main":
    # C2 + C3 : une bougie 15 min par instrument (fuseau par défaut, pour observer meta)
    for i, sym in enumerate(UNIVERSE):
        r, body, now = call(f"C3 {sym} 15min", "time_series",
                            {"symbol": sym, "interval": "15min", "outputsize": 2},
                            save=f"c3_{sym.replace('/', '')}_15min")
        out(test="C2" if i == 0 else "C3", symbol=sym, http=r.status_code, status=body.get("status"),
            api_code=body.get("code"), message=body.get("message"), meta=body.get("meta"),
            values=body.get("values"))
    # C4 : intervalles 5 min et 1 h (15 min couvert ci-dessus)
    for sym in ["EUR/USD", "XAU/USD"]:
        for itv in ["5min", "1h"]:
            r, body, _ = call(f"C4 {sym} {itv}", "time_series",
                              {"symbol": sym, "interval": itv, "outputsize": 2, "timezone": "UTC"},
                              save=f"c4_{sym.replace('/', '')}_{itv}")
            out(test="C4", symbol=sym, interval=itv, http=r.status_code, status=body.get("status"),
                api_code=body.get("code"), message=body.get("message"), values=body.get("values"))
    # C5 échantillon 1 (1 min, puis 15 min déjà vu ci-dessus)
    for sym in ["EUR/USD", "XAU/USD"]:
        freshness(sym, "1min", f"C5#1 {sym}", save=f"c5_{sym.replace('/', '')}_1min_s1")
    # C6 : profondeur 15 min (5000 points + 1 page) et 1 h (5000 points)
    for itv, pages in [("15min", 2), ("1h", 1)]:
        end = None
        oldest_all = None
        total = 0
        for p in range(pages):
            params = {"symbol": "EUR/USD", "interval": itv, "outputsize": 5000, "timezone": "UTC",
                      "order": "desc"}
            if end:
                params["end_date"] = end
            r, body, _ = call(f"C6 EUR/USD {itv} p{p + 1}", "time_series", params,
                              save=f"c6_EURUSD_{itv}_p{p + 1}" if p == 0 else None)
            vals = body.get("values") or []
            total += len(vals)
            if not vals:
                out(test="C6", interval=itv, page=p + 1, http=r.status_code,
                    api_code=body.get("code"), message=body.get("message"))
                break
            newest, oldest = vals[0]["datetime"], vals[-1]["datetime"]
            oldest_all = oldest
            # Trous : écarts > intervalle attendu (week-ends inclus)
            step = 900 if itv == "15min" else 3600
            ts = [datetime.fromisoformat(v["datetime"]) for v in vals]
            gaps = [(ts[k + 1].isoformat(), ts[k].isoformat(), (ts[k] - ts[k + 1]).total_seconds())
                    for k in range(len(ts) - 1) if (ts[k] - ts[k + 1]).total_seconds() > step]
            big = [g for g in gaps if g[2] > 6 * 3600]
            dups = len(ts) - len(set(ts))
            out(test="C6", interval=itv, page=p + 1, points=len(vals), newest=newest, oldest=oldest,
                n_gaps=len(gaps), n_gaps_over_6h=len(big), sample_big_gaps=big[:4],
                n_small_gaps=len(gaps) - len(big), sample_small_gaps=[g for g in gaps if g[2] <= 6 * 3600][:5],
                duplicates=dups, volume_field_present=("volume" in vals[0]), fields=list(vals[0].keys()))
            end = oldest
        out(test="C6", interval=itv, total_points=total, oldest_reached=oldest_all)
    r, body, _ = call("C6 earliest EUR/USD 15min", "earliest_timestamp",
                      {"symbol": "EUR/USD", "interval": "15min"}, save="c6_earliest_EURUSD_15min")
    out(test="C6", earliest=body)
    # C7 : quote (bid/ask éventuels)
    r, body, _ = call("C7 quote EUR/USD", "quote", {"symbol": "EUR/USD"}, save="c7_quote_EURUSD")
    out(test="C7", quote_fields=list(body.keys()) if isinstance(body, dict) else None, quote=body)
    # C8 : consommation
    r, body, _ = call("C8 api_usage", "api_usage", {}, save="c8_api_usage")
    out(test="C8", api_usage=body, headers={k: v for k, v in r.headers.items()})

elif PHASE == "fresh":
    for sym in ["EUR/USD", "XAU/USD"]:
        freshness(sym, "1min", f"C5 {sym}")

elif PHASE == "burst":
    # C8 : déclencher UNE fois la limite par minute, puis s'arrêter au premier refus.
    # Les 2 premiers appels servent aussi de 3e échantillon C5 (budget de 40 appels).
    while datetime.now(timezone.utc).second > 3:   # démarrer en début de minute
        time.sleep(0.5)
    for i in range(10):
        sym = ["EUR/USD", "XAU/USD"][i] if i < 2 else "EUR/USD"
        r, body, now = call(f"C8 burst {i + 1}" + (" + C5#3" if i < 2 else ""), "time_series",
                            {"symbol": sym, "interval": "1min", "outputsize": 3, "timezone": "UTC"},
                            spacing=False, save="c8_rate_limit_error" if i >= 7 else None)
        if i < 2 and last_bar(body):
            bar_open = datetime.fromisoformat(last_bar(body)["datetime"]).replace(tzinfo=timezone.utc)
            out(test="C5", symbol=sym, interval="1min", request_utc=now.isoformat(), last_bar=last_bar(body),
                lag_from_bar_open_s=round((now - bar_open).total_seconds(), 1))
        code = body.get("code") if isinstance(body, dict) else None
        out(test="C8", burst_call=i + 1, utc=now.isoformat(), http=r.status_code, api_code=code,
            message=body.get("message") if isinstance(body, dict) else None,
            headers={k: v for k, v in r.headers.items() if k.lower().startswith(("api-", "x-", "retry"))})
        if r.status_code == 429 or code == 429:
            break

out(test="BUDGET", calls_used_total=calls_used(), max=BUDGET_MAX)
