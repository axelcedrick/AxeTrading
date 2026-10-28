"""Échoue si une chaîne ressemblant à un secret est présente dans le dépôt (fichiers suivis ou ajoutés)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_secrets", ROOT / "scripts" / "check_secrets.py")
check_secrets = importlib.util.module_from_spec(_spec)
sys.modules["check_secrets"] = check_secrets
_spec.loader.exec_module(check_secrets)


def test_repository_contains_no_secret():
    findings = check_secrets.scan(ROOT)
    assert not findings, "secrets possibles :\n" + "\n".join(map(str, findings))


def test_scanner_detects_known_shapes():
    # Les valeurs sont construites à l'exécution pour ne pas déclencher le scanner sur ce fichier.
    tok = "a1b2c3d4" * 4
    samples = {
        "jeton Databricks": "x = dapi" + "0123456789abcdef" * 2,
        "clé dans une URL": "https://api.example.com/x?apikey=" + tok,
        "affectation de secret": 'api_key = "' + tok + '"',
        "jeton isolé": "cle: " + tok,
    }
    for rule, line in samples.items():
        assert any(f.rule == rule for f in check_secrets.scan_text(line, "x")), rule


def test_scanner_ignores_ordinary_text():
    assert not check_secrets.scan_text("instrument_id: EURUSD, run_id 331932626405436", "x")
