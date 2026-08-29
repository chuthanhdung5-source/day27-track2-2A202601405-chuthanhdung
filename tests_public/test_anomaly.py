from student_api import detect_metric


def test_large_volume_drop_is_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(300, history, method="zscore")
    assert result["is_anomaly"] is True


def test_stable_value_is_not_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(1002, history, method="zscore")
    assert result["is_anomaly"] is False


def test_mad_detector_handles_zero_mad_constant_history():
    # Constant history: MAD is 0
    history = [100, 100, 100, 100, 100]
    # Value equal to median -> not anomaly
    assert detect_metric(100, history, method="mad")["is_anomaly"] is False
    # Value different from median -> is anomaly
    assert detect_metric(150, history, method="mad")["is_anomaly"] is True


def test_mad_resists_outlier_contamination_in_history():
    # History contains an extreme historical outlier (5000), which inflates std for Z-score
    history = [100, 102, 101, 5000, 99, 100, 103, 98]
    # Current value 250 is a real anomaly (2.5x normal ~100)
    mad_result = detect_metric(250, history, method="mad")
    # MAD should correctly catch it because median is ~101 and MAD is small
    assert mad_result["is_anomaly"] is True


def test_auto_seasonality_saturday_vs_monday():
    # General history has mixed weekdays (~600) and weekends (~200)
    general_history = [600, 610, 595, 620, 200, 210, 605]
    saturday_history = [200, 205, 195, 202, 198]
    monday_history = [600, 610, 595, 620, 605]

    # Case 1: 200 on Saturday is normal
    sat_context = {"same_segment_history": saturday_history, "day_of_week": 5, "metric_name": "row_count"}
    sat_res = detect_metric(200, general_history, method="auto", context=sat_context)
    assert sat_res["is_anomaly"] is False

    # Case 2: 200 on Monday is a huge drop anomaly
    mon_context = {"same_segment_history": monday_history, "day_of_week": 0, "metric_name": "row_count"}
    mon_res = detect_metric(200, general_history, method="auto", context=mon_context)
    assert mon_res["is_anomaly"] is True


def test_auto_known_event_relaxation():
    history = [500, 510, 495, 505, 515]
    # In a flash sale, 1000 is expected and known
    context = {"known_event": "black_friday_mega_sale", "metric_name": "row_count"}
    res = detect_metric(1000, history, method="auto", context=context)
    # The known event context relaxes the threshold so it doesn't trigger a false alarm
    assert res["score"] > 0


def test_insufficient_history_returns_false_gracefully():
    # History with fewer than 3 elements
    res = detect_metric(500, [100, 200], method="auto")
    assert res["is_anomaly"] is False
    assert res["score"] == 0.0


