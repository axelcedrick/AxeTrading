"""Utilitaires de temps : tout est en UTC, et toute date sans fuseau est refusée.

Les bornes de bougies sont alignées sur l'époque Unix en UTC (5 min, 15 min, 1 h).
Une bougie est identifiée par son heure d'ouverture `bar_open_ts` ; elle couvre [ouverture, clôture[.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo

INTERVAL_SECONDS: dict[str, int] = {
    "5min": 5 * 60,
    "15min": 15 * 60,
    "1h": 60 * 60,
}


class NaiveDatetimeError(ValueError):
    """Une date sans fuseau horaire a été fournie là où un instant précis est exigé."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(ts: datetime) -> datetime:
    """Convertit un instant avec fuseau en UTC. Refuse une date « naïve » (sans fuseau)."""
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise NaiveDatetimeError(f"date sans fuseau refusée : {ts.isoformat()}")
    return ts.astimezone(UTC)


def localize(wall_time: datetime, tz: tzinfo) -> datetime:
    """Interprète une heure murale (sans fuseau) dans `tz` et la renvoie en UTC."""
    if wall_time.tzinfo is not None:
        raise ValueError("localize attend une heure murale sans fuseau")
    return wall_time.replace(tzinfo=tz).astimezone(UTC)


def interval_seconds(interval: str) -> int:
    try:
        return INTERVAL_SECONDS[interval]
    except KeyError:
        raise ValueError(
            f"intervalle inconnu : {interval!r} (attendus : {sorted(INTERVAL_SECONDS)})"
        ) from None


def floor_to_interval(ts: datetime, interval: str) -> datetime:
    """Heure d'ouverture de la bougie qui contient l'instant `ts`."""
    ts = ensure_utc(ts)
    step = interval_seconds(interval)
    epoch = int(ts.timestamp())
    return datetime.fromtimestamp(epoch - epoch % step, UTC)


def is_aligned(ts: datetime, interval: str) -> bool:
    ts = ensure_utc(ts)
    return ts.microsecond == 0 and int(ts.timestamp()) % interval_seconds(interval) == 0


def bar_close(bar_open_ts: datetime, interval: str) -> datetime:
    """Heure de clôture (exclue) d'une bougie. L'ouverture doit être alignée."""
    bar_open_ts = ensure_utc(bar_open_ts)
    if not is_aligned(bar_open_ts, interval):
        raise ValueError(f"ouverture non alignée sur {interval} : {bar_open_ts.isoformat()}")
    return bar_open_ts + timedelta(seconds=interval_seconds(interval))


def is_bar_complete(bar_open_ts: datetime, interval: str, as_of: datetime) -> bool:
    """Vrai si la bougie est terminée à l'instant `as_of` (clôture atteinte ou dépassée).

    L'audit a montré que le fournisseur renvoie la bougie en cours de formation :
    seul ce calcul, pas la réponse du fournisseur, décide si une bougie est complète.
    """
    return ensure_utc(as_of) >= bar_close(bar_open_ts, interval)
