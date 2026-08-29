from student_api import detect_metric


def test_large_volume_drop_is_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(300, history, method="zscore")
    assert result["is_anomaly"] is True


def test_stable_value_is_not_anomaly():
    history = [1000, 1010, 995, 1008, 1004, 1012, 998]
    result = detect_metric(1002, history, method="zscore")
    assert result["is_anomaly"] is False


def test_mad_detector_handles_zero_mad():
    # Constant history: MAD is 0
    history = [100, 100, 100, 100, 100]
    # Value equal to median -> not anomaly
    assert detect_metric(100, history, method="mad")["is_anomaly"] is False
    # Value different from median -> is anomaly
    assert detect_metric(150, history, method="mad")["is_anomaly"] is True


def test_auto_context_with_segment_history():
    general_history = [500, 510, 505, 520, 515]
    # Saturday normal segment is 200
    saturday_history = [200, 205, 195, 202]
    context = {"same_segment_history": saturday_history, "day_of_week": 5}
    # 200 on Saturday is normal in segment context
    res = detect_metric(200, general_history, method="auto", context=context)
    assert res["is_anomaly"] is False

