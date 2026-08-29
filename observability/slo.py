from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "multiwindow",
) -> dict[str, Any]:
    """Evaluate multi-window burn rate based on Google SRE Alerting on SLOs principles.

    Multiwindow alerting prevents false alarms from short transient spikes while
    ensuring rapid paging for sustained budget burn.
    """
    # 1. Critical fast burn: 1h burn >= 14.4 AND 6h burn >= 14.4 (consumes ~2% budget in 1h, sustained)
    if short_window_burn >= 14.4 and long_window_burn >= 14.4:
        return {
            "page": True,
            "severity": "critical",
            "reason": "sustained_fast_burn_critical",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
            "policy": policy,
        }

    # 2. Warning slow burn: 6h burn >= 6.0 AND 36h burn >= 6.0 (consumes ~5% budget in 6h, sustained)
    if short_window_burn >= 6.0 and long_window_burn >= 6.0:
        return {
            "page": True,
            "severity": "warning",
            "reason": "sustained_slow_burn_warning",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
            "policy": policy,
        }

    # 3. Transient spike: high short burn but long window is not elevated -> do NOT page
    if short_window_burn >= 6.0 and long_window_burn < 6.0:
        return {
            "page": False,
            "severity": "warning" if short_window_burn >= 14.4 else "info",
            "reason": "transient_spike_no_page",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
            "policy": policy,
        }

    # 4. Normal / safe operation
    return {
        "page": False,
        "severity": "info",
        "reason": "normal_burn_rate",
        "short_window_burn": short_window_burn,
        "long_window_burn": long_window_burn,
        "policy": policy,
    }
