from pathlib import Path

import pytest
import yaml

from atlas.common.config import (
    ConfigError,
    MissingValuesError,
    load_costs,
    load_risk,
    load_universe,
)

CONFIG = Path(__file__).resolve().parents[2] / "config"

VALID_RISK = {
    "version": 1,
    "account_currency": "EUR",
    "paper_capital": 10000,
    "risk_per_trade_pct": 0.5,
    "max_total_open_risk_pct": 2,
    "max_daily_loss_pct": 2,
    "max_leverage": 10,
    "max_open_positions": 3,
    "max_pair_correlation": 0.7,
    "max_spread_pct_of_stop": 15,
    "max_slippage_pct_of_stop": 10,
    "max_signal_age_minutes": 30,
    "min_data_quality_score": 0.9,
}  # valeurs de TEST uniquement, pas une recommandation


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


# ------------------------------------------------------------------ fichiers du dépôt
def test_repo_universe_loads():
    u = load_universe(CONFIG / "universe.yml")
    assert [i.instrument_id for i in u.instruments] == [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCHF",
        "XAUUSD",
    ]
    assert all(i.reference_status == "a_confirmer" for i in u.instruments)
    assert u.intervals.derived == {"1h": "15min"}


def test_repo_costs_load_and_cover_universe():
    u = load_universe(CONFIG / "universe.yml")
    c = load_costs(CONFIG / "costs.yml", universe=u)
    assert {a.source for a in c.assumptions} == {"hypothèse"}


def test_repo_risk_is_refused_until_user_fills_it():
    with pytest.raises(MissingValuesError) as exc:
        load_risk(CONFIG / "risk.yml")
    assert "risk_per_trade_pct" in exc.value.missing
    assert "à fournir par l'utilisateur" in str(exc.value)


# ------------------------------------------------------------------ risque
def test_risk_valid(tmp_path):
    r = load_risk(write(tmp_path, "risk.yml", VALID_RISK))
    assert r.risk_per_trade_pct == 0.5


def test_risk_absent_file(tmp_path):
    with pytest.raises(ConfigError, match="absent"):
        load_risk(tmp_path / "nope.yml")


def test_risk_missing_key(tmp_path):
    data = dict(VALID_RISK)
    del data["max_daily_loss_pct"]
    with pytest.raises(MissingValuesError, match="max_daily_loss_pct"):
        load_risk(write(tmp_path, "risk.yml", data))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("risk_per_trade_pct", 0),
        ("risk_per_trade_pct", 6),
        ("risk_per_trade_pct", -1),
        ("max_pair_correlation", 1.5),
        ("max_open_positions", 0),
        ("max_leverage", 500),
        ("min_data_quality_score", -0.1),
        ("account_currency", "euro"),
        ("risk_per_trade_pct", "beaucoup"),
    ],
)
def test_risk_out_of_bounds(tmp_path, field, value):
    data = dict(VALID_RISK, **{field: value})
    with pytest.raises(ConfigError, match=field):
        load_risk(write(tmp_path, "risk.yml", data))


def test_risk_unknown_field_refused(tmp_path):
    with pytest.raises(ConfigError, match="martingale"):
        load_risk(write(tmp_path, "risk.yml", dict(VALID_RISK, martingale=True)))


def test_risk_per_trade_above_total(tmp_path):
    data = dict(VALID_RISK, risk_per_trade_pct=3, max_total_open_risk_pct=2)
    with pytest.raises(ConfigError, match="max_total_open_risk_pct"):
        load_risk(write(tmp_path, "risk.yml", data))


def test_invalid_yaml(tmp_path):
    p = tmp_path / "risk.yml"
    p.write_text("a: [1, 2", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML illisible"):
        load_risk(p)


# ------------------------------------------------------------------ univers
def _universe():
    return yaml.safe_load((CONFIG / "universe.yml").read_text(encoding="utf-8"))


def test_universe_duplicate_id(tmp_path):
    data = _universe()
    data["instruments"].append(dict(data["instruments"][0]))
    with pytest.raises(ConfigError, match="en double"):
        load_universe(write(tmp_path, "u.yml", data))


def test_universe_unknown_calendar(tmp_path):
    data = _universe()
    data["instruments"][0]["session_calendar_id"] = "LUNE"
    with pytest.raises(ConfigError, match="calendrier inconnu"):
        load_universe(write(tmp_path, "u.yml", data))


def test_universe_bad_derivation(tmp_path):
    data = _universe()
    data["intervals"]["derived"] = {"15min": "1h"}
    with pytest.raises(ConfigError, match="dérivé"):
        load_universe(write(tmp_path, "u.yml", data))


def test_universe_negative_pip(tmp_path):
    data = _universe()
    data["instruments"][0]["pip_size"] = -0.0001
    with pytest.raises(ConfigError, match="pip_size"):
        load_universe(write(tmp_path, "u.yml", data))


# ------------------------------------------------------------------ coûts
def _costs():
    return yaml.safe_load((CONFIG / "costs.yml").read_text(encoding="utf-8"))


def test_costs_sessions_must_cover_day(tmp_path):
    data = _costs()
    data["sessions"]["london"]["end_utc"] = "11:00"
    with pytest.raises(ConfigError, match="24 h"):
        load_costs(write(tmp_path, "c.yml", data))


def test_costs_negative_spread(tmp_path):
    data = _costs()
    data["assumptions"][0]["spread_pips"] = -1
    with pytest.raises(ConfigError, match="spread_pips"):
        load_costs(write(tmp_path, "c.yml", data))


def test_costs_source_label_required(tmp_path):
    data = _costs()
    data["assumptions"][0]["source"] = "deviné"
    with pytest.raises(ConfigError, match="source"):
        load_costs(write(tmp_path, "c.yml", data))


def test_costs_missing_instrument_session(tmp_path):
    data = _costs()
    data["assumptions"] = [a for a in data["assumptions"] if a["instrument_id"] != "XAUUSD"]
    u = load_universe(CONFIG / "universe.yml")
    with pytest.raises(ConfigError, match="XAUUSD"):
        load_costs(write(tmp_path, "c.yml", data), universe=u)
