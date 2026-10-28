"""Garde-fous de qualité des données (CLAUDE.md §4).

SQUELETTES À IMPLÉMENTER EN PHASE 3 : chaque test est marqué `xfail` strict. Il échoue tant que le
contrôle n'existe pas, et pytest signalera XPASS (en erreur) si quelqu'un le fait passer sans retirer
la marque. Ces tests ne doivent jamais être comptés comme réussis.
"""

import pytest

PHASE3 = "à implémenter en phase 3 (ingestion) : contrôle de qualité pas encore écrit"


@pytest.mark.xfail(reason=PHASE3, raises=NotImplementedError, strict=True)
def test_incomplete_bar_never_yields_signal():
    """Une bougie en cours de formation (bar_close_ts > request_ts) est is_complete = false et exclue."""
    raise NotImplementedError


@pytest.mark.xfail(reason=PHASE3, raises=NotImplementedError, strict=True)
def test_stale_quote_never_yields_signal():
    """Une dernière bougie plus ancienne que le seuil de péremption marque l'instrument STALE."""
    raise NotImplementedError


@pytest.mark.xfail(reason=PHASE3, raises=NotImplementedError, strict=True)
def test_inconsistent_ohlc_never_yields_signal():
    """OHLC invalide, volume négatif, horodatage futur, trou non comblé, hors séance : rejetés ou marqués."""
    raise NotImplementedError


@pytest.mark.xfail(reason=PHASE3, raises=NotImplementedError, strict=True)
def test_duplicate_bar_never_yields_signal():
    """Une bougie reçue deux fois (chevauchement de pagination, audit C6) n'est écrite qu'une fois."""
    raise NotImplementedError
