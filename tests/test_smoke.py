"""End-to-end smoke test — full canonical pipeline with stub adapters."""
from portfolio_ninja.domain.stubs import StubDataAdapter, StubExecutionAdapter
from portfolio_ninja.orchestrator import run
from portfolio_ninja.operator_report import render_report


def test_smoke_full_canonical_pipeline_returns_valid_audit_record():
    audit_record = run(
        tickers=["AAPL", "MSFT", "GOOG", "AMZN", "META"],
        data_adapter=StubDataAdapter(),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=730,
    )
    assert audit_record is not None
    assert audit_record.validation_status == "valid"
    assert audit_record.cycle_id != ""
    assert audit_record.run_mode == "backtest"
    assert len(audit_record.tickers) == 5


def test_smoke_all_pipeline_hashes_present_in_audit_record():
    audit_record = run(
        tickers=["AAPL", "MSFT", "GOOG", "AMZN", "META"],
        data_adapter=StubDataAdapter(),
        exec_adapter=StubExecutionAdapter(),
    )
    required_keys = {
        "universe", "market_dataset", "market_state", "experiment_params",
        "score_set", "ranked_universe", "target_portfolio", "risk_decision",
        "execution_intent",
    }
    assert required_keys.issubset(set(audit_record.pipeline_hashes.keys()))
    for key, value in audit_record.pipeline_hashes.items():
        assert value != "", f"Empty hash for {key}"


def test_smoke_operator_report_is_non_empty_string():
    audit_record = run(
        tickers=["AAPL", "MSFT"],
        data_adapter=StubDataAdapter(),
        exec_adapter=StubExecutionAdapter(),
    )
    report = render_report(audit_record)
    assert isinstance(report, str)
    assert len(report) > 0
    assert "Cycle ID" in report
    assert "backtest" in report


def test_smoke_pipeline_is_deterministic_for_same_inputs():
    kwargs = dict(
        tickers=["AAPL", "MSFT", "GOOG"],
        data_adapter=StubDataAdapter(),
        exec_adapter=StubExecutionAdapter(),
        run_mode="backtest",
        window_days=730,
    )
    ar1 = run(**kwargs)
    kwargs["data_adapter"] = StubDataAdapter()
    kwargs["exec_adapter"] = StubExecutionAdapter()
    ar2 = run(**kwargs)
    assert ar1.pipeline_hashes["universe"] == ar2.pipeline_hashes["universe"]
    assert ar1.pipeline_hashes["market_dataset"] == ar2.pipeline_hashes["market_dataset"]
    assert ar1.pipeline_hashes["target_portfolio"] == ar2.pipeline_hashes["target_portfolio"]
