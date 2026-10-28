"""Chargement validé de la configuration (`config/*.yml`).

Principe : schéma strict (champ inconnu = erreur), types et bornes vérifiés. Une valeur manquante ou
hors bornes est une erreur explicite, jamais un repli silencieux sur une valeur par défaut.
Les bornes de `RiskConfig` sont des garde-fous de cohérence, pas des recommandations.
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from atlas.common.sessions import CALENDARS
from atlas.common.time import INTERVAL_SECONDS


class ConfigError(ValueError):
    """Configuration absente, illisible ou invalide."""


class MissingValuesError(ConfigError):
    """Des valeurs que seul l'utilisateur peut fournir sont absentes."""

    def __init__(self, path: Path, missing: list[str]):
        self.missing = missing
        super().__init__(
            f"{path} : valeurs manquantes, à fournir par l'utilisateur : {', '.join(missing)}. "
            "Aucune valeur par défaut n'est appliquée."
        )


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)


Interval = Literal["5min", "15min", "1h"]
ReferenceStatus = Literal["a_confirmer", "valide"]


# --------------------------------------------------------------------------- univers
class Instrument(_Strict):
    instrument_id: Annotated[str, Field(pattern=r"^[A-Z0-9]{3,12}$")]
    symbol: str
    asset_class: Literal["FX", "COMMODITY", "CRYPTO", "EQUITY"]
    base_ccy: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    quote_ccy: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    pip_size: Annotated[float, Field(gt=0)]
    price_decimals: Annotated[int, Field(ge=0, le=10)]
    contract_unit: Annotated[float, Field(gt=0)]
    session_calendar_id: str
    provider_symbols: dict[str, str]
    is_active: bool
    reference_status: ReferenceStatus

    @field_validator("session_calendar_id")
    @classmethod
    def _known_calendar(cls, v: str) -> str:
        if v not in CALENDARS:
            raise ValueError(f"calendrier inconnu {v!r} (connus : {sorted(CALENDARS)})")
        return v

    @field_validator("provider_symbols")
    @classmethod
    def _non_empty(cls, v: dict[str, str]) -> dict[str, str]:
        if not v:
            raise ValueError("au moins un symbole fournisseur est requis")
        return v


class Intervals(_Strict):
    live: list[Interval]
    # intervalle cible -> intervalle source (le cible est agrégé, jamais demandé au fournisseur)
    derived: dict[Interval, Interval]
    backfill: list[Interval]
    backtest: list[Interval]

    @model_validator(mode="after")
    def _coherent(self) -> Intervals:
        for target, source in self.derived.items():
            if INTERVAL_SECONDS[source] >= INTERVAL_SECONDS[target]:
                raise ValueError(f"{target} ne peut pas être dérivé de {source} (plus grand ou égal)")
            if INTERVAL_SECONDS[target] % INTERVAL_SECONDS[source]:
                raise ValueError(f"{target} n'est pas un multiple de {source}")
            if source not in self.live:
                raise ValueError(f"source {source} de {target} absente des intervalles live")
        return self


class UniverseConfig(_Strict):
    version: int
    reference_values_status: ReferenceStatus
    intervals: Intervals
    instruments: Annotated[list[Instrument], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique(self) -> UniverseConfig:
        for attr in ("instrument_id", "symbol"):
            values = [getattr(i, attr) for i in self.instruments]
            dup = {v for v in values if values.count(v) > 1}
            if dup:
                raise ValueError(f"{attr} en double : {sorted(dup)}")
        return self

    def by_id(self) -> dict[str, Instrument]:
        return {i.instrument_id: i for i in self.instruments}


# --------------------------------------------------------------------------- risque
class RiskConfig(_Strict):
    """Paramètres de risque. Tous obligatoires ; aucune valeur par défaut (voir config/risk.yml)."""

    version: int
    account_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    paper_capital: Annotated[float, Field(gt=0)]
    risk_per_trade_pct: Annotated[float, Field(gt=0, le=5)]
    max_total_open_risk_pct: Annotated[float, Field(gt=0, le=20)]
    max_daily_loss_pct: Annotated[float, Field(gt=0, le=20)]
    max_leverage: Annotated[float, Field(gt=0, le=100)]
    max_open_positions: Annotated[int, Field(ge=1, le=50)]
    max_pair_correlation: Annotated[float, Field(ge=0, le=1)]
    max_spread_pct_of_stop: Annotated[float, Field(gt=0, le=100)]
    max_slippage_pct_of_stop: Annotated[float, Field(gt=0, le=100)]
    max_signal_age_minutes: Annotated[int, Field(ge=1, le=1440)]
    min_data_quality_score: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def _coherent(self) -> RiskConfig:
        if self.risk_per_trade_pct > self.max_total_open_risk_pct:
            raise ValueError("risk_per_trade_pct ne peut pas dépasser max_total_open_risk_pct")
        return self


# --------------------------------------------------------------------------- coûts
class SessionWindow(_Strict):
    start_utc: time
    end_utc: time  # exclue ; peut être inférieure à start_utc (passage de minuit)

    def minutes(self) -> set[int]:
        s = self.start_utc.hour * 60 + self.start_utc.minute
        e = self.end_utc.hour * 60 + self.end_utc.minute
        if s == e:
            raise ValueError("fenêtre de séance vide")
        return set(range(s, e)) if s < e else set(range(s, 1440)) | set(range(0, e))


class CostAssumption(_Strict):
    instrument_id: str
    session: str
    spread_pips: Annotated[float, Field(ge=0)]
    slippage_pips: Annotated[float, Field(ge=0)]
    commission_pips: Annotated[float, Field(ge=0)]
    source: Literal["hypothèse", "mesuré"]
    valid_from: date


class CostsConfig(_Strict):
    version: int
    unit: Literal["pips"]
    sessions: dict[str, SessionWindow]
    assumptions: Annotated[list[CostAssumption], Field(min_length=1)]

    @model_validator(mode="after")
    def _coherent(self) -> CostsConfig:
        covered: list[int] = []
        for w in self.sessions.values():
            covered.extend(w.minutes())
        if len(covered) != 1440 or len(set(covered)) != 1440:
            raise ValueError("les séances de coûts doivent couvrir les 24 h sans chevauchement")
        keys = [(a.instrument_id, a.session, a.valid_from) for a in self.assumptions]
        if len(keys) != len(set(keys)):
            raise ValueError("hypothèse de coût en double (instrument, séance, valid_from)")
        unknown = {a.session for a in self.assumptions} - set(self.sessions)
        if unknown:
            raise ValueError(f"séances inconnues : {sorted(unknown)}")
        return self

    def check_against(self, universe: UniverseConfig) -> None:
        """Chaque instrument actif doit avoir une hypothèse pour chaque séance."""
        have = {(a.instrument_id, a.session) for a in self.assumptions}
        ids = {i.instrument_id for i in universe.instruments}
        unknown = {a.instrument_id for a in self.assumptions} - ids
        if unknown:
            raise ConfigError(f"coûts : instruments absents de l'univers : {sorted(unknown)}")
        missing = [
            f"{i.instrument_id}/{s}"
            for i in universe.instruments
            if i.is_active
            for s in self.sessions
            if (i.instrument_id, s) not in have
        ]
        if missing:
            raise ConfigError(f"coûts : hypothèses manquantes pour {missing}")


# --------------------------------------------------------------------------- chargement
def _read_yaml(path: str | Path) -> tuple[Path, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"fichier de configuration absent : {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{p} : YAML illisible ({exc})") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{p} : un dictionnaire YAML est attendu à la racine")
    return p, data


def _validate[M: BaseModel](model: type[M], p: Path, data: dict[str, Any]) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(x) for x in e['loc']) or '(racine)'} : {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"{p} invalide : {details}") from None


def load_universe(path: str | Path) -> UniverseConfig:
    p, data = _read_yaml(path)
    return _validate(UniverseConfig, p, data)


def load_risk(path: str | Path) -> RiskConfig:
    p, data = _read_yaml(path)
    expected = list(RiskConfig.model_fields)
    missing = [k for k in expected if data.get(k) is None]
    if missing:
        raise MissingValuesError(p, missing)
    return _validate(RiskConfig, p, data)


def load_costs(path: str | Path, universe: UniverseConfig | None = None) -> CostsConfig:
    p, data = _read_yaml(path)
    costs = _validate(CostsConfig, p, data)
    if universe is not None:
        costs.check_against(universe)
    return costs
