"""Audit phase 1 (jetable) : diagnostic du rejet HTTP 400. N'affiche jamais la clé, seulement des classes de caractères."""
import json
import unicodedata

import requests
from databricks.sdk.runtime import dbutils

key = dbutils.secrets.get("atlas-audit", "twelvedata_api_key")


def cls(c):
    if c.isascii() and c.isalnum():
        return "alnum"
    return f"U+{ord(c):04X}:{unicodedata.category(c)}"


non_alnum = [(i, cls(c)) for i, c in enumerate(key) if cls(c) != "alnum"]
print("AUDIT_RESULT " + json.dumps({"test": "diag-key", "length": len(key),
                                     "length_stripped": len(key.strip()), "non_alnum_positions": non_alnum}))
# Requête sans clé : vérifie que l'API répond en JSON depuis le workspace (pas de crédit consommé attendu).
r = requests.get("https://api.twelvedata.com/time_series", params={"symbol": "EUR/USD", "interval": "1h", "outputsize": 1}, timeout=30)
print("AUDIT_RESULT " + json.dumps({"test": "diag-nokey", "http": r.status_code, "server": r.headers.get("Server"),
                                     "body": r.text[:300]}))
