import json
import logging

import pytest

from atlas.common.logging import JsonFormatter, SecretRedactionFilter, redact
from atlas.common.secrets import SecretError, get_secret

FAKE = "fauxsecret0123456789abcdefTEST"  # valeur factice de test


def reader_returning(value):
    return lambda scope, key: value


def test_get_secret_ok_and_registered_for_redaction():
    assert get_secret("atlas", "k", reader=reader_returning(FAKE)) == FAKE
    assert redact(f"url?x={FAKE}&y") == "url?x=***&y"


def test_missing_secret_message_is_explicit_and_safe():
    def boom(scope, key):
        raise KeyError(f"no secret {FAKE}")  # même si l'erreur d'origine contenait une valeur

    with pytest.raises(SecretError) as exc:
        get_secret("atlas", "twelvedata_api_key", reader=boom)
    msg = str(exc.value)
    assert "atlas/twelvedata_api_key" in msg and "docs/secrets.md" in msg
    assert FAKE not in msg
    assert exc.value.__cause__ is None


@pytest.mark.parametrize("bad", ["", "\x00" + "a" * 32, "abc def", "abc\n"])
def test_invalid_secret_refused(bad):
    with pytest.raises(SecretError):
        get_secret("atlas", "k", reader=reader_returning(bad))


def test_outside_databricks_fails_clearly():
    with pytest.raises(SecretError, match="introuvable|indisponible"):
        get_secret("atlas", "k")


def test_log_record_is_redacted_everywhere(capsys):
    secret = get_secret("atlas", "k2", reader=reader_returning("autrefaux9876543210zyxw"))
    logger = logging.getLogger("atlas.test.redaction")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretRedactionFilter())
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning("appel avec %s", secret, extra={"params": {"apikey": secret}, "lst": [secret]})
        try:
            raise RuntimeError(f"échec {secret}")
        except RuntimeError:
            logger.exception("erreur")
    finally:
        logger.removeHandler(handler)
    err = capsys.readouterr().err
    assert secret not in err
    first = json.loads(err.splitlines()[0])
    assert first["msg"] == "appel avec ***"
    assert first["params"] == {"apikey": "***"} and first["lst"] == ["***"]
