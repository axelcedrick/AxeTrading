"""Recherche de chaînes ressemblant à des secrets dans les fichiers suivis du dépôt.

Usage : python scripts/check_secrets.py [racine]   → code de sortie 1 si quelque chose est trouvé.
N'affiche jamais la valeur trouvée : seulement le fichier, la ligne et la règle déclenchée.
Utilisé par tests/unit/test_no_secrets.py et par le hook .githooks/pre-commit.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RULES: dict[str, re.Pattern[str]] = {
    "jeton Databricks": re.compile(r"\bdapi[0-9a-f]{32}\b"),
    "clé dans une URL": re.compile(r"(?i)[?&](api_?key|token|access_token)=[A-Za-z0-9_\-]{12,}"),
    "affectation de secret": re.compile(
        r"(?i)\b(api_?key|apikey|secret|token|password|passwd)\b[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-+/]{16,}[\"']"
    ),
    "en-tête d'authentification": re.compile(
        r"(?i)\b(authorization)[\"']?\s*[:=]\s*[\"'](bearer|apikey)\s+[A-Za-z0-9_\-.]{16,}"
    ),
    "clé privée": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # Jeton isolé de 32 à 64 caractères mêlant lettres et chiffres (format des clés Twelve Data, etc.)
    "jeton isolé": re.compile(
        r"(?<![A-Za-z0-9_%/=.\-])(?=[A-Za-z0-9]*[0-9])(?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]{32,64}(?![A-Za-z0-9_%/=.\-])"
    ),
}

# Contextes connus et non sensibles : (fragment présent sur la ligne, règle concernée).
ALLOWLIST: list[tuple[str, str]] = [
    ("nel.cloudflare.com/report", "jeton isolé"),  # en-tête Report-To de Cloudflare dans les fixtures
]

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".whl", ".zip", ".pdf", ".lock"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — {self.rule}"


def tracked_files(root: Path) -> list[Path]:
    """Fichiers suivis ou ajoutés (non ignorés) sous `root`."""
    # Commande fixe, sans entrée utilisateur.
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],  # noqa: S607
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return [root / p for p in out.split("\0") if p]


def scan_text(text: str, path: str) -> list[Finding]:
    findings = []
    for n, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in RULES.items():
            if pattern.search(line) and not any(frag in line and r == rule for frag, r in ALLOWLIST):
                findings.append(Finding(path, n, rule))
    return findings


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for f in tracked_files(root):
        if f.suffix.lower() in SKIP_SUFFIXES or not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(text, f.relative_to(root).as_posix()))
    return findings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    findings = scan(root)
    for f in findings:
        print(f"SECRET POSSIBLE : {f}")
    if findings:
        print(f"{len(findings)} élément(s) suspect(s). Retirer la valeur et utiliser les secrets Databricks.")
        return 1
    print("Aucun secret détecté.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
