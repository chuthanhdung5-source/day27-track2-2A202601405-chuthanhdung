import pytest
from student_api import multiwindow_burn, slo_status


def test_burn_rate_math():
    result = slo_status(0.995, bad_events=2, total_events=100)
    assert result["allowed_bad_rate"] == pytest.approx(0.005)
    assert result["actual_bad_rate"] == pytest.approx(0.02)
    assert result["burn_rate"] == pytest.approx(4.0)
    assert result["breached"] is True


def test_zero_events_is_safe():
    result = slo_status(0.99, bad_events=0, total_events=0)
    assert result["burn_rate"] == 0
    assert result["breached"] is False
    assert result["remaining_error_budget_fraction"] == 1.0


def test_100_percent_bad_events_exhausts_budget():
    result = slo_status(0.999, bad_events=100, total_events=100)
    assert result["actual_bad_rate"] == 1.0
    assert result["allowed_bad_rate"] == pytest.approx(0.001)
    assert result["burn_rate"] == pytest.approx(1000.0)
    assert result["remaining_error_budget_fraction"] == 0.0
    assert result["breached"] is True


def test_exact_budget_boundary():
    # Exactly 1 failure out of 100 on a 99.0% SLO target
    result = slo_status(0.99, bad_events=1, total_events=100)
    assert result["actual_bad_rate"] == pytest.approx(0.01)
    assert result["burn_rate"] == pytest.approx(1.0)
    assert result["remaining_error_budget_fraction"] == pytest.approx(0.0)
    assert result["breached"] is False  # Equal is not breached


def test_invalid_slo_arguments_raise():
    with pytest.raises(ValueError):
        slo_status(1.5, bad_events=1, total_events=100)
    with pytest.raises(ValueError):
        slo_status(0.0, bad_events=1, total_events=100)
    with pytest.raises(ValueError):
        slo_status(0.99, bad_events=150, total_events=100)


def test_multiwindow_burn_sustained_fast_burn_pages():
    res = multiwindow_burn(short_window_burn=15.0, long_window_burn=15.0)
    assert res["page"] is True
    assert res["severity"] == "critical"
    assert res["reason"] == "sustained_fast_burn_critical"


def test_multiwindow_burn_sustained_slow_burn_pages():
    res = multiwindow_burn(short_window_burn=7.0, long_window_burn=6.5)
    assert res["page"] is True
    assert res["severity"] == "warning"
    assert res["reason"] == "sustained_slow_burn_warning"


def test_multiwindow_burn_transient_spike_does_not_page():
    res = multiwindow_burn(short_window_burn=16.0, long_window_burn=2.0)
    assert res["page"] is False
    assert res["reason"] == "transient_spike_no_page"


def test_multiwindow_burn_normal_operation_is_safe():
    res = multiwindow_burn(short_window_burn=0.5, long_window_burn=0.4)
    assert res["page"] is False
    assert res["severity"] == "info"


