from student_api import rag_embedding_shift, rag_length_shift


def test_rag_length_collapse_is_detected():
    baseline_batch_means = [40, 42, 39, 41, 43, 40, 42]
    current_texts = ["x y", "a b c", "one two"]
    assert rag_length_shift(current_texts, baseline_batch_means)["is_anomaly"] is True


def test_rag_length_normal_variation_is_not_anomaly():
    baseline_batch_means = [40, 42, 39, 41, 43, 40, 42]
    # Normal texts with average length ~41 words
    current_texts = ["word " * 41, "term " * 40, "item " * 42]
    assert rag_length_shift(current_texts, baseline_batch_means)["is_anomaly"] is False


def test_rag_length_massive_inflation_detected():
    baseline_batch_means = [40, 42, 39, 41, 43, 40, 42]
    # Document dump with 500 words
    current_texts = ["long text paragraph " * 100]
    assert rag_length_shift(current_texts, baseline_batch_means)["is_anomaly"] is True


def test_rag_embedding_shift_detected():
    baseline_norms = [1.0, 1.01, 0.99, 1.0, 1.02, 0.98]
    shifted_norms = [2.5, 2.6, 2.4, 2.5]
    res = rag_embedding_shift(shifted_norms, baseline_norms)
    assert res["is_anomaly"] is True


def test_rag_embedding_subtle_noise_is_not_anomaly():
    baseline_norms = [1.0, 1.01, 0.99, 1.0, 1.02, 0.98]
    stable_norms = [1.002, 0.998, 1.005, 0.995]
    res = rag_embedding_shift(stable_norms, baseline_norms)
    assert res["is_anomaly"] is False


def test_rag_empty_inputs_handling():
    res_text = rag_length_shift([], [40, 42, 39])
    assert isinstance(res_text, dict)
    res_embed = rag_embedding_shift([], [1.0, 1.0])
    assert res_embed["is_anomaly"] is False


