from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from student_api import validate_orders
from src.contract_validator import determine_action, failed_issues, load_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "orders_contract.yaml"


def healthy_df():
    now = datetime.now(timezone.utc)
    t1 = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t2 = (now - timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return pd.DataFrame([
        {
            "order_id": 1,
            "customer_id": "C1",
            "amount": 10.0,
            "currency": "USD",
            "status": "completed",
            "created_at": t1,
            "updated_at": t1,
        },
        {
            "order_id": 2,
            "customer_id": "C2",
            "amount": 20.0,
            "currency": "USD",
            "status": "pending",
            "created_at": t2,
            "updated_at": t2,
        },
    ])


def failed(issues):
    return [i for i in issues if not i["passed"]]


def test_healthy_contract_passes_all_checks():
    issues = validate_orders(healthy_df(), CONTRACT)
    assert not failed(issues)
    assert determine_action(issues) == "pass"


def test_duplicate_order_id_is_detected():
    df = healthy_df()
    df.loc[1, "order_id"] = 1
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "unique" and i["column"] == "order_id" for i in issues)


def test_invalid_currency_is_detected():
    df = healthy_df()
    df.loc[0, "currency"] = "BTC"
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "accepted_values" and i["column"] == "currency" for i in issues)


def test_type_drift_string_in_int():
    df = healthy_df()
    df["order_id"] = ["not_an_int", "also_not"]
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "type" and i["column"] == "order_id" for i in issues)


def test_type_drift_float_in_int():
    df = healthy_df()
    df["order_id"] = [1.25, 2.75]
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "type" and i["column"] == "order_id" for i in issues)


def test_stale_data_fails_freshness():
    df = healthy_df()
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    df["updated_at"] = [stale_time, stale_time]
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "freshness" and i["column"] == "updated_at" for i in issues)


def test_missing_required_column_detected():
    df = healthy_df().drop(columns=["customer_id"])
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "required_column" and i["column"] == "customer_id" for i in issues)
    assert determine_action(issues) == "block"


def test_null_value_in_required_column_detected():
    df = healthy_df()
    df.loc[0, "customer_id"] = None
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "not_null" and i["column"] == "customer_id" for i in issues)


def test_negative_amount_range_violation():
    df = healthy_df()
    df.loc[0, "amount"] = -50.0
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "range" and i["column"] == "amount" for i in issues)
    assert determine_action(issues) == "block"


def test_invalid_datetime_format_fails_type_check():
    df = healthy_df()
    df.loc[0, "created_at"] = "invalid-date-format-999"
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "type" and i["column"] == "created_at" for i in issues)


def test_invalid_status_value_detected():
    df = healthy_df()
    df.loc[0, "status"] = "in_transit_unknown"
    issues = failed(validate_orders(df, CONTRACT))
    assert any(i["check"] == "accepted_values" and i["column"] == "status" for i in issues)


def test_empty_dataframe_handling():
    empty_df = pd.DataFrame(columns=["order_id", "customer_id", "amount", "currency", "status", "created_at", "updated_at"])
    issues = validate_orders(empty_df, CONTRACT)
    assert isinstance(issues, list)


