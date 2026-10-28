"""Exécute les scripts `sql/ddl/NNN_*.sql` sur un catalogue d'environnement. Idempotent.

Usage (tâche de job) : atlas-ddl --catalog atlas_dev --ddl-dir <chemin>/sql/ddl
- `{catalog}` est remplacé par le nom du catalogue de la cible.
- Les `CREATE ... IF NOT EXISTS` sont idempotents par nature.
- Un `ALTER TABLE t ADD CONSTRAINT nom CHECK (...)` n'est exécuté que si la contrainte n'existe pas
  encore (propriété Delta `delta.constraints.nom`), pour que le second passage ne change rien.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from atlas.common.logging import get_logger

_CATALOG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ADD_CONSTRAINT_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+(?P<table>[\w.`]+)\s+ADD\s+CONSTRAINT\s+(?P<name>\w+)\s+CHECK\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Statement:
    source: str  # fichier d'origine
    index: int  # rang dans le fichier
    sql: str


def split_statements(text: str) -> list[str]:
    """Découpe un script SQL en instructions, en retirant les commentaires `--`.

    Les `;` et `--` à l'intérieur d'une chaîne entre apostrophes sont respectés ; l'apostrophe
    s'échappe par `\\'` (en Spark SQL, `''` n'est pas un échappement mais une concaténation).
    """
    statements, buf = [], []
    in_str = escaped = False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            buf.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == "'":
                in_str = False
        elif c == "'":
            in_str = True
            buf.append(c)
        elif text.startswith("--", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(c)
        i += 1
    if in_str:
        raise ValueError("chaîne SQL non terminée (apostrophe non échappée ?)")
    tail = "".join(buf).strip()
    if tail:
        raise ValueError(f"instruction sans « ; » final : {tail[:80]}…")
    return statements


def render(sql: str, catalog: str) -> str:
    if not _CATALOG_RE.match(catalog):
        raise ValueError(f"nom de catalogue invalide : {catalog!r}")
    return sql.replace("{catalog}", catalog)


def load_statements(ddl_dir: str | Path, catalog: str) -> list[Statement]:
    files = sorted(Path(ddl_dir).glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise FileNotFoundError(f"aucun script DDL dans {ddl_dir}")
    out = []
    for f in files:
        for n, sql in enumerate(split_statements(f.read_text(encoding="utf-8")), start=1):
            rendered = render(sql, catalog)
            if "{" in rendered and "}" in rendered and re.search(r"\{\w+\}", rendered):
                raise ValueError(f"{f.name}#{n} : paramètre non remplacé")
            out.append(Statement(f.name, n, rendered))
    return out


def constraint_target(sql: str) -> tuple[str, str] | None:
    m = _ADD_CONSTRAINT_RE.match(sql)
    return (m["table"], m["name"].lower()) if m else None


def run(
    statements: list[Statement],
    execute: Callable[[str], None],
    existing_constraints: Callable[[str], set[str]],
) -> dict[str, int]:
    """Exécute les instructions ; renvoie le nombre d'instructions exécutées et ignorées."""
    log = get_logger("atlas.ddl")
    stats = {"executed": 0, "skipped_existing_constraint": 0}
    for st in statements:
        target = constraint_target(st.sql)
        if target and target[1] in existing_constraints(target[0]):
            stats["skipped_existing_constraint"] += 1
            log.info(
                "contrainte déjà présente", extra={"file": st.source, "stmt": st.index, "constraint": target}
            )
            continue
        execute(st.sql)
        stats["executed"] += 1
        log.info("instruction exécutée", extra={"file": st.source, "stmt": st.index, "head": st.sql[:70]})
    return stats


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True)
    p.add_argument("--ddl-dir", required=True)
    args = p.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()

    def existing(table: str) -> set[str]:
        rows = spark.sql(f"SHOW TBLPROPERTIES {table}").collect()
        return {
            r["key"][len("delta.constraints.") :].lower()
            for r in rows
            if r["key"].startswith("delta.constraints.")
        }

    stats = run(load_statements(args.ddl_dir, args.catalog), lambda s: spark.sql(s), existing)
    get_logger("atlas.ddl").info("DDL terminé", extra={"catalog": args.catalog, **stats})


if __name__ == "__main__":
    main()
