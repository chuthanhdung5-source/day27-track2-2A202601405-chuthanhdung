"""Simple contract validator used as the starter baseline.

The implementation intentionally covers only common deterministic checks.
Students are expected to extend it with:
- stronger type validation/coercion rules,
- freshness checks,
- cross-field/cross-table assertions,
- severity-aware actions (block/quarantine/warn),
- richer observability metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
) -> dict[str, Any]:
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
    }


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns", {})

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                    )
                )
            continue

        series = df[column]

        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                )
            )

        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                )
            )

        # Type validation
        declared_type = rules.get("type")
        if declared_type:
            non_null = series.dropna()
            type_passed = True
            type_details = f"declared_type={declared_type}"

            if declared_type in ("integer", "int"):
                numeric = pd.to_numeric(non_null, errors="coerce")
                invalid_type_mask = numeric.isna() | (numeric % 1 != 0)
                invalid_type_count = int(invalid_type_mask.sum())
                type_passed = (invalid_type_count == 0)
                type_details = f"declared_type=integer; invalid_count={invalid_type_count}"
            elif declared_type in ("number", "float"):
                numeric = pd.to_numeric(non_null, errors="coerce")
                invalid_type_count = int(numeric.isna().sum())
                type_passed = (invalid_type_count == 0)
                type_details = f"declared_type=number; invalid_count={invalid_type_count}"
            elif declared_type in ("datetime", "timestamp"):
                parsed_dt = pd.to_datetime(non_null, errors="coerce")
                invalid_dt_count = int(parsed_dt.isna().sum())
                type_passed = (invalid_dt_count == 0)
                type_details = f"declared_type=datetime; invalid_count={invalid_dt_count}"
            elif declared_type in ("boolean", "bool"):
                valid_bools = {True, False, 0, 1, "true", "false", "True", "False", "0", "1"}
                invalid_bool_count = int((~non_null.isin(valid_bools)).sum())
                type_passed = (invalid_bool_count == 0)
                type_details = f"declared_type=boolean; invalid_count={invalid_bool_count}"
            elif declared_type in ("string", "str"):
                pass

            issues.append(
                _issue(
                    "type",
                    column=column,
                    severity=severity,
                    passed=type_passed,
                    details=type_details,
                )
            )

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                )
            )

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                )
            )

    # Contract-level Freshness validation
    freshness_config = contract.get("freshness")
    if freshness_config and isinstance(freshness_config, dict):
        freshness_col = freshness_config.get("column", "updated_at")
        max_delay_minutes = float(freshness_config.get("max_delay_minutes", 30))
        freshness_sev = freshness_config.get("severity", "warning")

        if freshness_col in df.columns and len(df) > 0:
            parsed_dt = pd.to_datetime(df[freshness_col], utc=True, errors="coerce")
            valid_dt = parsed_dt.dropna()
            if len(valid_dt) > 0:
                latest_ts = valid_dt.max()
                now_ts = pd.Timestamp.now(tz="UTC")
                delay_minutes = (now_ts - latest_ts).total_seconds() / 60.0
                passed_freshness = bool(delay_minutes <= max_delay_minutes)
                issues.append(
                    _issue(
                        "freshness",
                        column=freshness_col,
                        severity=freshness_sev,
                        passed=passed_freshness,
                        details=f"delay_minutes={delay_minutes:.2f}; max_delay_minutes={max_delay_minutes}",
                    )
                )
            else:
                issues.append(
                    _issue(
                        "freshness",
                        column=freshness_col,
                        severity=freshness_sev,
                        passed=False,
                        details=f"Unable to parse valid datetime in freshness column: {freshness_col}",
                    )
                )

    return issues


def determine_action(issues: list[dict[str, Any]]) -> str:
    """Determine operational pipeline action based on validation issues."""
    failed = [i for i in issues if not i.get("passed", False)]
    if not failed:
        return "pass"
    has_critical = any(i.get("severity") == "critical" for i in failed)
    if has_critical:
        return "block"
    has_warning = any(i.get("severity") == "warning" for i in failed)
    if has_warning:
        return "quarantine"
    return "warn"


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order[min_severity]
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]
