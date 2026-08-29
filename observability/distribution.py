from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
    ks_threshold: float = 0.35,
) -> dict[str, Any]:
    """Robust distribution shift detector combining KS 2-sample test and mean ratio."""
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)
    if cur.size == 0 or base.size == 0:
        return {"is_anomaly": False, "score": 0.0, "method": "distribution_shift", "reason": "empty_input"}

    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))

    # 1. Mean ratio calculation
    if base_mean == 0:
        mean_score = float("inf") if cur_mean != 0 else 1.0
    else:
        mean_score = max(abs(cur_mean / base_mean), abs(base_mean / cur_mean)) if cur_mean != 0 else float("inf")

    # 2. Two-sample Kolmogorov-Smirnov test statistic (pure numpy implementation)
    cur_sorted = np.sort(cur)
    base_sorted = np.sort(base)
    all_vals = np.concatenate([cur_sorted, base_sorted])
    cdf_cur = np.searchsorted(cur_sorted, all_vals, side="right") / cur.size
    cdf_base = np.searchsorted(base_sorted, all_vals, side="right") / base.size
    ks_stat = float(np.max(np.abs(cdf_cur - cdf_base)))

    is_mean_anomaly = bool(mean_score >= ratio_threshold)
    is_ks_anomaly = bool(ks_stat >= ks_threshold and (cur.size >= 5 and base.size >= 5))

    is_anomaly = is_mean_anomaly or is_ks_anomaly
    primary_score = mean_score if is_mean_anomaly else ks_stat

    return {
        "is_anomaly": is_anomaly,
        "score": float(primary_score),
        "method": "ks_and_mean_ratio",
        "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}, mean_ratio={mean_score:.2f}, ks_stat={ks_stat:.3f}",
        "ks_stat": ks_stat,
        "mean_ratio": mean_score,
    }
