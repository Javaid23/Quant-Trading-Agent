from datetime import date

from agent.defense.exit_manager import ExitManager


TODAY = date(2026, 9, 3)
# 26 days out -> outside the expiry window, so time never forces an exit in these P&L tests.
FAR_OPTION = "AAPL260929C00330000"


def test_take_profit_triggers_on_target_gain():
    manager = ExitManager(take_profit_pct=0.5, stop_loss_pct=0.5, min_days_to_expiry=3)

    decision = manager.evaluate_position(
        {"symbol": FAR_OPTION, "unrealized_plpc": "0.62"}, today=TODAY
    )

    assert decision["action"] == "take_profit"
    assert decision["should_close"] is True


def test_stop_loss_triggers_on_target_loss():
    manager = ExitManager(take_profit_pct=0.5, stop_loss_pct=0.5, min_days_to_expiry=3)

    decision = manager.evaluate_position(
        {"symbol": FAR_OPTION, "unrealized_plpc": "-0.55"}, today=TODAY
    )

    assert decision["action"] == "stop_loss"
    assert decision["should_close"] is True


def test_near_expiry_forces_exit_even_when_flat():
    manager = ExitManager(min_days_to_expiry=3)
    # Expires 2026-09-04 -> 1 day out, inside the window.
    near_option = "AAPL260904C00330000"

    decision = manager.evaluate_position(
        {"symbol": near_option, "unrealized_plpc": "0.05"}, today=TODAY
    )

    assert decision["action"] == "expiry_exit"
    assert decision["days_to_expiry"] == 1


def test_loss_takes_priority_over_expiry():
    manager = ExitManager(stop_loss_pct=0.5, min_days_to_expiry=3)
    near_option = "AAPL260904C00330000"

    decision = manager.evaluate_position(
        {"symbol": near_option, "unrealized_plpc": "-0.80"}, today=TODAY
    )

    assert decision["action"] == "stop_loss"


def test_position_within_thresholds_is_held():
    manager = ExitManager(take_profit_pct=0.5, stop_loss_pct=0.5, min_days_to_expiry=3)

    decision = manager.evaluate_position(
        {"symbol": FAR_OPTION, "unrealized_plpc": "0.10"}, today=TODAY
    )

    assert decision["action"] == "hold"
    assert decision["should_close"] is False


def test_evaluate_portfolio_returns_one_decision_per_position():
    manager = ExitManager()
    positions = [
        {"symbol": FAR_OPTION, "unrealized_plpc": "0.62"},
        {"symbol": "MSFT260929P00480000", "unrealized_plpc": "-0.55"},
    ]

    decisions = manager.evaluate_portfolio(positions, today=TODAY)

    assert len(decisions) == 2
    assert {d["action"] for d in decisions} == {"take_profit", "stop_loss"}
