import numpy as np
from student_api import detect_distribution


def test_extreme_mean_shift_detected():
    baseline = [9, 10, 11, 10, 10]
    current = [190, 200, 210, 205]
    assert detect_distribution(current, baseline)["is_anomaly"] is True


def test_identical_distributions_not_anomaly():
    baseline = [10.0, 12.0, 11.0, 9.0, 10.5, 11.5, 9.5]
    current = [10.1, 11.9, 11.0, 9.2, 10.4, 11.6, 9.6]
    assert detect_distribution(current, baseline)["is_anomaly"] is False


def test_same_mean_different_distribution_ks_test_catches_shift():
    """HARD CASE: Both have mean = 10.0, but baseline is uniform and current is polarized bimodal."""
    baseline = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0]  # mean = 10.0
    current = [0.0, 0.0, 0.0, 0.0, 0.0, 20.0, 20.0, 20.0, 20.0, 20.0]   # mean = 10.0
    
    res = detect_distribution(current, baseline)
    # Mean ratio is 1.0 (mean detector would miss this!), but KS test catches the distribution shape anomaly
    assert res["is_anomaly"] is True
    assert res["ks_stat"] > 0.35


def test_empty_distribution_inputs_handled_safely():
    res = detect_distribution([], [10.0, 20.0])
    assert res["is_anomaly"] is False
    assert res["reason"] == "empty_input"


