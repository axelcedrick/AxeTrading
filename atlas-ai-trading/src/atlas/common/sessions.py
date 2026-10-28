"""Calendriers de séances par classe d'actifs.

Règles proposées (statut « à confirmer » par l'utilisateur, voir docs/phases/02-rapport.md) :

- FX_24x5 (Forex au comptant) : ouvert du dimanche 17:00 au vendredi 17:00, heure de New York,
  sans pause quotidienne. En UTC, cela donne 21:00 en heure d'été américaine et 22:00 en heure d'hiver.
- METALS_24x5 (XAU/USD) : ouvert du dimanche 18:00 au vendredi 17:00, heure de New York,
  avec une pause quotidienne de 17:00 à 18:00 (New York), du lundi au jeudi.

Les jours fériés (Noël, Nouvel An) ne sont pas modélisés : une bougie attendue absente un jour
férié apparaîtra comme un trou. C'est une limite connue, à traiter en phase 3.

L'audit a montré que le fournisseur émet des bougies le week-end : ces fonctions servent à les
identifier comme hors séance (drapeau OFF_SESSION). Elles ne doivent jamais être utilisées comme
des cotations négociables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from atlas.common.time import bar_close, ensure_utc

NEW_YORK = ZoneInfo("America/New_York")

# Jours de la semaine (lundi = 0 … dimanche = 6)
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


@dataclass(frozen=True)
class SessionCalendar:
    calendar_id: str
    tz: ZoneInfo
    week_open_day: int
    week_open_time: time
    week_close_day: int
    week_close_time: time
    # Pause quotidienne [début, fin[ en heure locale, ou None
    daily_break: tuple[time, time] | None = None
    status: str = "a_confirmer"

    def is_open(self, ts: datetime) -> bool:
        local = ensure_utc(ts).astimezone(self.tz)
        wd, t = local.weekday(), local.time()
        if wd == SAT:
            return False
        if wd == self.week_open_day and t < self.week_open_time:
            return False
        if wd == self.week_close_day and t >= self.week_close_time:
            return False
        if wd == SUN and self.week_open_day != SUN:
            return False
        if self.daily_break is not None:
            start, end = self.daily_break
            if start <= t < end:
                return False
        return True


CALENDARS: dict[str, SessionCalendar] = {
    "FX_24x5": SessionCalendar(
        calendar_id="FX_24x5",
        tz=NEW_YORK,
        week_open_day=SUN,
        week_open_time=time(17, 0),
        week_close_day=FRI,
        week_close_time=time(17, 0),
    ),
    "METALS_24x5": SessionCalendar(
        calendar_id="METALS_24x5",
        tz=NEW_YORK,
        week_open_day=SUN,
        week_open_time=time(18, 0),
        week_close_day=FRI,
        week_close_time=time(17, 0),
        daily_break=(time(17, 0), time(18, 0)),
    ),
}


def get_calendar(calendar_id: str) -> SessionCalendar:
    try:
        return CALENDARS[calendar_id]
    except KeyError:
        raise ValueError(f"calendrier inconnu : {calendar_id!r} (connus : {sorted(CALENDARS)})") from None


def is_market_open(calendar_id: str, ts: datetime) -> bool:
    """Le marché est-il ouvert à l'instant UTC `ts` ?"""
    return get_calendar(calendar_id).is_open(ts)


def is_bar_expected(calendar_id: str, bar_open_ts: datetime, interval: str) -> bool:
    """La bougie qui s'ouvre à `bar_open_ts` est-elle attendue, c'est-à-dire entièrement en séance ?

    Une bougie à cheval sur une ouverture ou une fermeture n'est pas attendue. Les bornes de séance
    tombent sur des heures pleines, donc cela n'arrive pas pour les intervalles 5 min, 15 min et 1 h.
    """
    cal = get_calendar(calendar_id)
    last_instant = bar_close(bar_open_ts, interval) - timedelta(microseconds=1)
    return cal.is_open(bar_open_ts) and cal.is_open(last_instant)
