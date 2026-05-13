import pytest
from datetime import date
from decimal import Decimal

from portfolio_ninja.domain.objects import ScoreSet
from portfolio_ninja.score_arbitration_engine import rank_scores

TODAY = date(2026, 1, 15)


def _make_score_set(scores: dict[str, Decimal]) -> ScoreSet:
    return ScoreSet(
        scores=scores,
        model_id="stub_v1",
        as_of_date=TODAY,
        params_hash="f" * 64,
    )


def test_score_arbitration_engine_valid_scores_returns_ranked_universe():
    ss = _make_score_set({"AAPL": Decimal("0.8"), "MSFT": Decimal("0.6")})
    ru = rank_scores(ss)
    assert ru.validation_status == "valid"
    assert ru.as_of_date == TODAY
    assert len(ru.ranked) == 2


def test_score_arbitration_engine_ranked_list_contains_every_ticker():
    ss = _make_score_set({"AAPL": Decimal("0.8"), "MSFT": Decimal("0.6"), "GOOG": Decimal("0.7")})
    ru = rank_scores(ss)
    tickers = [t for t, _ in ru.ranked]
    assert set(tickers) == {"AAPL", "MSFT", "GOOG"}


def test_score_arbitration_engine_ranked_descending_by_score():
    ss = _make_score_set({"AAPL": Decimal("0.8"), "MSFT": Decimal("0.6"), "GOOG": Decimal("0.7")})
    ru = rank_scores(ss)
    scores = [s for _, s in ru.ranked]
    assert scores == sorted(scores, reverse=True)


def test_score_arbitration_engine_tie_breaking_is_lexicographic_ascending():
    ss = _make_score_set({"ZZZ": Decimal("0.5"), "AAA": Decimal("0.5"), "MMM": Decimal("0.5")})
    ru = rank_scores(ss)
    tickers = [t for t, _ in ru.ranked]
    assert tickers == ["AAA", "MMM", "ZZZ"]


def test_score_arbitration_engine_empty_score_set_raises_value_error():
    ss = _make_score_set({})
    with pytest.raises(ValueError, match="ScoreSet must not be empty"):
        rank_scores(ss)


def test_score_arbitration_engine_all_scores_in_output_are_decimal():
    ss = _make_score_set({"AAPL": Decimal("0.8"), "MSFT": Decimal("0.6")})
    ru = rank_scores(ss)
    for _, score in ru.ranked:
        assert isinstance(score, Decimal)


def test_score_arbitration_engine_validation_status_is_valid_on_success():
    ss = _make_score_set({"AAPL": Decimal("0.8")})
    ru = rank_scores(ss)
    assert ru.validation_status == "valid"


def test_score_arbitration_engine_params_hash_is_deterministic():
    ss = _make_score_set({"AAPL": Decimal("0.8")})
    ru1 = rank_scores(ss)
    ru2 = rank_scores(ss)
    assert ru1.params_hash == ru2.params_hash
    assert len(ru1.params_hash) == 64
