"""Alimente `silver.instruments` depuis `config/universe.yml` par MERGE. Idempotent.

Usage (tâche de job) : atlas-seed-instruments --catalog atlas_dev --config-dir <chemin>/config
- Une ligne n'est mise à jour (et `updated_ts` avancé) que si une valeur a réellement changé.
- Un instrument retiré du fichier est désactivé (is_active = false), jamais supprimé.
- Si rien n'a changé, le MERGE n'est pas lancé : Delta enregistrerait sinon une version vide.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from atlas.common.config import UniverseConfig, load_universe
from atlas.common.logging import get_logger
from atlas.jobs.ddl import render

COMPARED_COLUMNS = [
    "asset_class",
    "symbol",
    "base_ccy",
    "quote_ccy",
    "pip_size",
    "price_decimals",
    "contract_unit",
    "session_calendar_id",
    "is_active",
    "reference_status",
    "config_version",
]

_UNCHANGED = """(
    {unchanged}
    AND array_sort(map_entries(t.provider_symbols)) = array_sort(map_entries(s.provider_symbols))
  )"""

PENDING_CHANGES_SQL = (
    """
SELECT count(*) AS n
FROM atlas_universe_src AS s
FULL OUTER JOIN {catalog}.silver.instruments AS t ON t.instrument_id = s.instrument_id
WHERE t.instrument_id IS NULL
   OR (s.instrument_id IS NULL AND t.is_active)
   OR (s.instrument_id IS NOT NULL AND t.instrument_id IS NOT NULL AND NOT """
    + _UNCHANGED
    + ")"
)

# Le catalogue est validé par render() ; les colonnes sont des constantes du module.
MERGE_SQL = (
    """
MERGE INTO {catalog}.silver.instruments AS t
USING atlas_universe_src AS s
ON t.instrument_id = s.instrument_id
WHEN MATCHED AND NOT """
    + _UNCHANGED
    + """
  THEN UPDATE SET {updates}, t.provider_symbols = s.provider_symbols, t.updated_ts = current_timestamp()
WHEN NOT MATCHED
  THEN INSERT ({columns}, instrument_id, provider_symbols, updated_ts)
       VALUES ({values}, s.instrument_id, s.provider_symbols, current_timestamp())
WHEN NOT MATCHED BY SOURCE AND t.is_active
  THEN UPDATE SET t.is_active = false, t.updated_ts = current_timestamp()
"""
)


def universe_rows(universe: UniverseConfig) -> list[dict[str, Any]]:
    return [
        {
            "instrument_id": i.instrument_id,
            "asset_class": i.asset_class,
            "symbol": i.symbol,
            "base_ccy": i.base_ccy,
            "quote_ccy": i.quote_ccy,
            "pip_size": float(i.pip_size),
            "price_decimals": int(i.price_decimals),
            "contract_unit": float(i.contract_unit),
            "session_calendar_id": i.session_calendar_id,
            "provider_symbols": dict(i.provider_symbols),
            "is_active": i.is_active,
            "reference_status": i.reference_status,
            "config_version": universe.version,
        }
        for i in universe.instruments
    ]


def _fill(template: str, catalog: str) -> str:
    return render(
        template.format(
            catalog="{catalog}",
            unchanged=" AND ".join(f"t.{c} <=> s.{c}" for c in COMPARED_COLUMNS),
            updates=", ".join(f"t.{c} = s.{c}" for c in COMPARED_COLUMNS),
            columns=", ".join(COMPARED_COLUMNS),
            values=", ".join(f"s.{c}" for c in COMPARED_COLUMNS),
        ),
        catalog,
    )


def merge_sql(catalog: str) -> str:
    return _fill(MERGE_SQL, catalog)


def pending_changes_sql(catalog: str) -> str:
    return _fill(PENDING_CHANGES_SQL, catalog)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True)
    p.add_argument("--config-dir", required=True)
    args = p.parse_args(argv)
    log = get_logger("atlas.seed_instruments")

    universe = load_universe(Path(args.config_dir) / "universe.yml")

    from pyspark.sql import SparkSession
    from pyspark.sql import types as T

    spark = SparkSession.builder.getOrCreate()
    schema = T.StructType(
        [
            T.StructField("instrument_id", T.StringType(), False),
            T.StructField("asset_class", T.StringType(), False),
            T.StructField("symbol", T.StringType(), False),
            T.StructField("base_ccy", T.StringType(), False),
            T.StructField("quote_ccy", T.StringType(), False),
            T.StructField("pip_size", T.DoubleType(), False),
            T.StructField("price_decimals", T.IntegerType(), False),
            T.StructField("contract_unit", T.DoubleType(), False),
            T.StructField("session_calendar_id", T.StringType(), False),
            T.StructField("provider_symbols", T.MapType(T.StringType(), T.StringType()), False),
            T.StructField("is_active", T.BooleanType(), False),
            T.StructField("reference_status", T.StringType(), False),
            T.StructField("config_version", T.IntegerType(), False),
        ]
    )
    spark.createDataFrame(universe_rows(universe), schema).createOrReplaceTempView("atlas_universe_src")
    pending = spark.sql(pending_changes_sql(args.catalog)).collect()[0]["n"]
    if pending == 0:
        log.info(
            "silver.instruments déjà à jour : aucun MERGE", extra={"catalog": args.catalog, "pending": 0}
        )
        return
    metrics = spark.sql(merge_sql(args.catalog)).collect()[0].asDict()
    log.info(
        "MERGE silver.instruments terminé", extra={"catalog": args.catalog, "pending": pending, **metrics}
    )


if __name__ == "__main__":
    main()
