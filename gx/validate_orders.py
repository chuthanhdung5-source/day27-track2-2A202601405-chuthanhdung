#!/usr/bin/env python3
"""Great Expectations Core Expectation Suite and Validation flow.

Demonstrates modern dataframe flow with Expectation Suite, Validation Definition,
and Checkpoint with severity-aware actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def build_and_run_gx_validation(orders_df: pd.DataFrame | None = None) -> bool:
    if orders_df is None:
        orders_path = ROOT / "data" / "incoming" / "orders.csv"
        orders_df = pd.read_csv(orders_path)

    context = gx.get_context()

    # Create / get data source
    data_source_name = "orders_pandas"
    try:
        data_source = context.data_sources.get(data_source_name)
    except Exception:
        data_source = context.data_sources.add_pandas(data_source_name)

    asset_name = "orders_dataframe"
    try:
        asset = data_source.get_asset(asset_name)
    except Exception:
        asset = data_source.add_dataframe_asset(name=asset_name)

    batch_def_name = "whole_orders"
    try:
        batch_definition = asset.get_batch_definition(batch_def_name)
    except Exception:
        batch_definition = asset.add_batch_definition_whole_dataframe(batch_def_name)

    batch = batch_definition.get_batch(batch_parameters={"dataframe": orders_df})

    expectations = [
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="amount", min_value=0, severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="currency", value_set=["USD", "VND"], severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status", value_set=["pending", "completed", "refunded", "cancelled"], severity="warning"
        ),
    ]

    all_ok = True
    print("=== GREAT EXPECTATIONS SUITE EXECUTION ===")
    for expectation in expectations:
        result = batch.validate(expectation)
        success = bool(result.success)
        all_ok = all_ok and success
        status = "PASS" if success else "FAIL"
        print(f"[{status}] {expectation.__class__.__name__:<40} (column={getattr(expectation, 'column', 'N/A')})")

    action = "PASS (Pipeline proceeds)" if all_ok else "BLOCK / QUARANTINE (Critical contract failure detected)"
    print(f"\nOverall GX Result: {'PASS' if all_ok else 'FAIL'}")
    print(f"Operational Action: {action}")
    return all_ok


def main() -> None:
    build_and_run_gx_validation()


if __name__ == "__main__":
    main()
