from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from atlas.common.time import (
    NaiveDatetimeError,
    bar_close,
    ensure_utc,
    floor_to_interval,
    is_aligned,
    is_bar_complete,
    localize,
)

PARIS = ZoneInfo("Europe/Paris")
NY = ZoneInfo("America/New_York")


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def test_naive_datetime_refused():
    with pytest.raises(NaiveDatetimeError):
        ensure_utc(datetime(2026, 10, 28, 12, 0))


def test_ensure_utc_converts_offset():
    ts = datetime(2026, 10, 28, 23, 30, tzinfo=timezone(timedelta(hours=2)))
    assert ensure_utc(ts) == utc(2026, 10, 28, 21, 30)


@pytest.mark.parametrize(
    ("ts", "interval", "expected"),
    [
        (utc(2026, 10, 28, 21, 22, 59), "5min", utc(2026, 10, 28, 21, 20)),
        (utc(2026, 10, 28, 21, 29, 59), "15min", utc(2026, 10, 28, 21, 15)),
        (utc(2026, 10, 28, 21, 30), "15min", utc(2026, 10, 28, 21, 30)),
        (utc(2026, 10, 28, 21, 59, 59, 999999), "1h", utc(2026, 10, 28, 21, 0)),
        # minuit
        (utc(2026, 10, 29, 0, 0, 0), "1h", utc(2026, 10, 29, 0, 0)),
        (utc(2026, 10, 28, 23, 59, 59), "15min", utc(2026, 10, 28, 23, 45)),
    ],
)
def test_floor_to_interval(ts, interval, expected):
    assert floor_to_interval(ts, interval) == expected


def test_unknown_interval():
    with pytest.raises(ValueError, match="intervalle inconnu"):
        floor_to_interval(utc(2026, 1, 1), "2min")


def test_bar_close_and_alignment():
    assert bar_close(utc(2026, 10, 28, 23, 45), "15min") == utc(2026, 10, 29, 0, 0)
    assert bar_close(utc(2026, 10, 28, 23, 0), "1h") == utc(2026, 10, 29, 0, 0)
    assert not is_aligned(utc(2026, 10, 28, 21, 7), "15min")
    with pytest.raises(ValueError, match="non alignée"):
        bar_close(utc(2026, 10, 28, 21, 7), "15min")


def test_incomplete_bar_while_forming():
    # Cas observé à l'audit : bougie 5 min de 21:20 reçue vers 21:22 -> en cours de formation
    assert not is_bar_complete(utc(2026, 10, 28, 21, 20), "5min", utc(2026, 10, 28, 21, 22))
    assert not is_bar_complete(utc(2026, 10, 28, 21, 20), "5min", utc(2026, 10, 28, 21, 24, 59, 999999))
    assert is_bar_complete(utc(2026, 10, 28, 21, 20), "5min", utc(2026, 10, 28, 21, 25))


def test_bar_complete_requires_aware_as_of():
    with pytest.raises(NaiveDatetimeError):
        is_bar_complete(utc(2026, 10, 28, 21, 15), "15min", datetime(2026, 10, 28, 21, 40))


def test_dst_change_europe_bars_stay_contiguous_in_utc():
    # Passage à l'heure d'hiver à Paris : 25/10/2026 03:00 CEST -> 02:00 CET (01:00 UTC)
    before = localize(datetime(2026, 10, 25, 2, 45), PARIS)  # ambigu : fold=0 -> CEST
    assert before == utc(2026, 10, 25, 0, 45)
    bars = [utc(2026, 10, 25, 0, 0) + timedelta(minutes=15 * k) for k in range(12)]
    assert all(bar_close(b, "15min") == n for b, n in zip(bars, bars[1:], strict=False))
    assert {floor_to_interval(b, "1h").minute for b in bars} == {0}


def test_dst_change_new_york():
    # Fin de l'heure d'été à New York : 01/11/2026. 17:00 NY = 21:00 UTC avant, 22:00 UTC après.
    assert localize(datetime(2026, 10, 30, 17, 0), NY) == utc(2026, 10, 30, 21, 0)
    assert localize(datetime(2026, 11, 6, 17, 0), NY) == utc(2026, 11, 6, 22, 0)


def test_weekend_bar_alignment_is_calendar_agnostic():
    # Le découpage en bougies ne dépend pas des séances : un samedi s'aligne normalement.
    assert floor_to_interval(utc(2026, 10, 24, 21, 17), "15min") == utc(2026, 10, 24, 21, 15)
