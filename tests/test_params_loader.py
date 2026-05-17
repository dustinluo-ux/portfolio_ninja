from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from portfolio_ninja.config.params_loader import load_params

_REQUIRED_SECTIONS = ("market_state", "scoring", "portfolio", "risk", "data", "date_normalizer")


def test_params_loader_default_path_returns_dict():
    assert isinstance(load_params(), dict)


def test_params_loader_has_all_required_sections():
    params = load_params()
    for section in _REQUIRED_SECTIONS:
        assert section in params, f"Missing section: {section}"


def test_params_loader_scoring_weights_sum_to_one():
    s = load_params()["scoring"]
    total = Decimal(str(s["w_momentum"])) + Decimal(str(s["w_volatility"])) + Decimal(str(s["w_rsi"]))
    assert total == Decimal("1.0")


def test_params_loader_market_state_periods_are_positive_ints():
    ms = load_params()["market_state"]
    for key in ("momentum_period", "rsi_period", "sma_regime_period", "ewma_span"):
        assert isinstance(ms[key], int) and ms[key] > 0, f"Bad value for {key}: {ms[key]}"


def test_params_loader_default_is_cached():
    assert load_params() is load_params()


def test_params_loader_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_params(path=tmp_path / "nonexistent.yaml")


def test_params_loader_missing_section_raises(tmp_path: Path):
    f = tmp_path / "partial.yaml"
    f.write_text(yaml.dump({"market_state": {}}))
    with pytest.raises(KeyError, match="missing required sections"):
        load_params(path=f)


def test_params_loader_non_mapping_yaml_raises(tmp_path: Path):
    f = tmp_path / "list.yaml"
    f.write_text("- item1\n- item2\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_params(path=f)


def _make_full_params(tmp_path: Path, overrides: dict | None = None) -> Path:
    content: dict = {
        "market_state": {
            "momentum_period": 10,
            "rsi_period": 7,
            "sma_regime_period": 100,
            "ewma_span": 20,
            "scsi_sentiment_baseline": "0.5",
        },
        "scoring": {
            "w_momentum": "0.5",
            "w_volatility": "0.3",
            "w_rsi": "0.2",
            "degenerate_score": "0.5",
        },
        "portfolio": {"expansion_max_longs": 3, "contraction_max_longs": 2},
        "risk": {"concentration_limit": "0.33"},
        "data": {"min_bars": 30, "window_days": 60, "stale_ohlcv_days": 2, "stale_news_days": 14},
        "date_normalizer": {
            "sample_size": 20,
            "fault_window": 15,
            "monotonicity_threshold": "0.90",
        },
    }
    if overrides:
        content.update(overrides)
    f = tmp_path / "custom_params.yaml"
    f.write_text(yaml.dump(content))
    return f


def test_params_loader_custom_path_reads_correct_values(tmp_path: Path):
    f = _make_full_params(tmp_path)
    result = load_params(path=f)
    assert result["scoring"]["w_momentum"] == "0.5"
    assert result["portfolio"]["expansion_max_longs"] == 3


def test_params_loader_custom_path_does_not_pollute_default_cache(tmp_path: Path):
    f = _make_full_params(tmp_path)
    load_params(path=f)
    default = load_params()
    assert default["scoring"]["w_momentum"] == "0.4"
