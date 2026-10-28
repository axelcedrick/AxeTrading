from datetime import UTC, datetime

import pytest

from atlas.common.sessions import is_bar_expected, is_market_open


def utc(*args):
    return datetime(*args, tzinfo=UTC)


# Rappel : heure d'été à New York jusqu'au 01/11/2026 (17:00 NY = 21:00 UTC), puis 22:00 UTC.


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        (utc(2026, 10, 28, 21, 23), True),  # mercredi soir (mesures de l'audit)
        (utc(2026, 10, 23, 20, 59), True),  # vendredi, juste avant la fermeture
        (utc(2026, 10, 23, 21, 0), False),  # vendredi 17:00 NY : fermé
        (utc(2026, 10, 24, 21, 15), False),  # samedi : bougie observée chez le fournisseur, hors séance
        (utc(2026, 10, 25, 20, 59), False),  # dimanche avant l'ouverture
        (utc(2026, 10, 25, 21, 0), True),  # dimanche 17:00 NY : ouverture
        (utc(2026, 11, 6, 21, 30), True),  # vendredi, heure d'hiver : ferme à 22:00 UTC
        (utc(2026, 11, 6, 22, 0), False),
        (utc(2026, 11, 8, 21, 30), False),  # dimanche, heure d'hiver : ouvre à 22:00 UTC
        (utc(2026, 11, 8, 22, 0), True),
    ],
)
def test_fx_open(ts, expected):
    assert is_market_open("FX_24x5", ts) is expected


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        (utc(2026, 10, 25, 21, 30), False),  # dimanche : l'or ouvre une heure après le Forex
        (utc(2026, 10, 25, 22, 0), True),
        (utc(2026, 10, 28, 21, 15), False),  # pause quotidienne 17:00-18:00 NY
        (utc(2026, 10, 28, 22, 0), True),
        (utc(2026, 10, 28, 20, 59), True),
        (utc(2026, 10, 23, 21, 0), False),  # vendredi soir
    ],
)
def test_metals_open(ts, expected):
    assert is_market_open("METALS_24x5", ts) is expected


def test_bar_expected_fx():
    assert is_bar_expected("FX_24x5", utc(2026, 10, 23, 20, 45), "15min")  # dernière du vendredi
    assert not is_bar_expected("FX_24x5", utc(2026, 10, 23, 21, 0), "15min")
    assert not is_bar_expected("FX_24x5", utc(2026, 10, 24, 12, 0), "1h")  # samedi
    assert is_bar_expected("FX_24x5", utc(2026, 10, 25, 21, 0), "1h")  # première du dimanche


def test_bar_expected_metals_daily_break():
    assert is_bar_expected("METALS_24x5", utc(2026, 10, 28, 20, 0), "1h")
    assert not is_bar_expected("METALS_24x5", utc(2026, 10, 28, 21, 0), "1h")
    assert not is_bar_expected("METALS_24x5", utc(2026, 10, 28, 21, 45), "15min")
    assert is_bar_expected("METALS_24x5", utc(2026, 10, 28, 22, 0), "5min")


def test_unknown_calendar():
    with pytest.raises(ValueError, match="calendrier inconnu"):
        is_market_open("NYSE", utc(2026, 10, 28, 15, 0))
