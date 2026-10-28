"""Journalisation structurée (JSON, une ligne par événement) avec masquage des secrets.

Toute valeur lue par `atlas.common.secrets.get_secret` est enregistrée ici et remplacée par
`***` dans chaque message, argument et champ supplémentaire, avant écriture.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

MASK = "***"
_MIN_SECRET_LEN = 4  # en dessous, le masquage abîmerait les messages sans protéger grand-chose

_lock = threading.Lock()
_secret_values: set[str] = set()

# Attributs standards d'un LogRecord, exclus des champs « extra »
_STD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


def register_secret(value: str) -> None:
    """Déclare une valeur à masquer dans tous les journaux du processus."""
    if value and len(value) >= _MIN_SECRET_LEN:
        with _lock:
            _secret_values.add(value)


def redact(text: str) -> str:
    with _lock:
        values = sorted(_secret_values, key=len, reverse=True)
    for v in values:
        text = text.replace(v, MASK)
    return text


def _redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return type(obj)(_redact_obj(v) for v in obj)
    return obj


class SecretRedactionFilter(logging.Filter):
    """Masque les secrets connus dans le message, ses arguments et les champs supplémentaires."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        for key in set(vars(record)) - _STD_ATTRS:
            setattr(record, key, _redact_obj(getattr(record, key)))
        if record.exc_info:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in set(vars(record)) - _STD_ATTRS:
            payload[key] = getattr(record, key)
        if record.exc_text:
            payload["exc"] = record.exc_text
        return redact(json.dumps(payload, default=str, ensure_ascii=False))


def get_logger(name: str = "atlas", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.addFilter(SecretRedactionFilter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return logger
