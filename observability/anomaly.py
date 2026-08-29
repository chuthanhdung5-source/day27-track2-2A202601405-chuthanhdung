"""Anomaly detection starter.

Z-score is deliberately the default baseline. Students should improve `auto`
mode for seasonality/outliers rather than deleting the simple implementation.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Robust MAD detector with proper zero-MAD and constant-history handling."""
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    
    if mad == 0:
        mean_ad = float(np.mean(np.abs(values - median)))
        if mean_ad > 0:
            modified_z = 0.6745 * abs(float(current) - median) / mean_ad
        else:
            # All historical values were completely identical
            if float(current) == median:
                modified_z = 0.0
            else:
                modified_z = float("inf")
    else:
        modified_z = 0.6745 * abs(float(current) - median) / mad

    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable lab API with context-aware auto mode."""
    if method == "mad":
        return mad_detector(current, history, threshold=threshold if threshold != 3.0 else 3.5)
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    
    if method == "auto":
        # Handle context
        hist_values = list(history)
        context_reasons: list[str] = []

        if context:
            # 1. Use same_segment_history if provided and sufficient
            segment_hist = context.get("same_segment_history")
            if segment_hist and len(list(segment_hist)) >= 3:
                hist_values = list(segment_hist)
                context_reasons.append("used_same_segment_history")
            
            # 2. Known event awareness (e.g., promotional sale, maintenance window)
            known_event = context.get("known_event")
            if known_event:
                context_reasons.append(f"known_event={known_event}")
                # For known events, we may relax threshold or adjust sensitivity
                threshold = threshold * 1.5

            metric_name = context.get("metric_name")
            if metric_name:
                context_reasons.append(f"metric={metric_name}")

        values_arr = np.asarray(hist_values, dtype=float)
        
        # Use MAD if sufficient history (robust against historical anomalies)
        if values_arr.size >= 5:
            result = mad_detector(current, values_arr, threshold=threshold if threshold != 3.0 else 3.5)
            result["method"] = "auto:mad"
        else:
            result = zscore_detector(current, values_arr, threshold=threshold)
            result["method"] = "auto:zscore"

        if context_reasons:
            result["reason"] += f" [{', '.join(context_reasons)}]"
            
        return result

    raise ValueError(f"Unsupported method: {method}")
