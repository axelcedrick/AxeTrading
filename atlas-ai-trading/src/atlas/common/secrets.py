"""Point d'accès unique aux secrets.

Sur Databricks, les secrets sont lus via `dbutils.secrets` (secret scope). La valeur n'est jamais
journalisée : elle est enregistrée auprès du filtre de masquage de `atlas.common.logging`.
Une valeur absente, vide ou contenant des caractères de contrôle est une erreur, jamais corrigée en
silence (incident de l'audit : un caractère nul inséré à la saisie sous Windows).
"""

from __future__ import annotations

from collections.abc import Callable

from atlas.common.logging import register_secret

SecretReader = Callable[[str, str], str]


class SecretError(RuntimeError):
    """Le secret demandé est absent ou invalide. Le message ne contient jamais la valeur."""


def _databricks_reader(scope: str, key: str) -> str:
    try:
        from databricks.sdk.runtime import dbutils
    except ImportError as exc:  # hors Databricks
        raise SecretError(
            f"secret {scope}/{key} : dbutils indisponible (exécution hors Databricks). "
            "Les secrets ne sont lus que dans le workspace."
        ) from exc
    return dbutils.secrets.get(scope=scope, key=key)


def get_secret(scope: str, key: str, reader: SecretReader | None = None) -> str:
    """Renvoie la valeur du secret `scope/key`, ou lève `SecretError` avec un message explicite."""
    reader = reader or _databricks_reader
    try:
        value = reader(scope, key)
    except SecretError:
        raise
    except Exception as exc:  # noqa: BLE001 — l'erreur d'origine peut varier selon l'environnement
        raise SecretError(
            f"secret {scope}/{key} introuvable ou illisible ({type(exc).__name__}). "
            "Voir docs/secrets.md pour le créer."
        ) from None
    if not value:
        raise SecretError(f"secret {scope}/{key} vide")
    if any(not c.isprintable() or c.isspace() for c in value):
        raise SecretError(
            f"secret {scope}/{key} invalide : caractère de contrôle ou espace présent. "
            "Le ressaisir avec la procédure de docs/secrets.md."
        )
    register_secret(value)
    return value
