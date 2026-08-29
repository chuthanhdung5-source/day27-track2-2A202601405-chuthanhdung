from student_api import column_downstream, downstream_assets


def test_transitive_downstream_assets():
    graph = {
        "raw_orders": ["stg_orders"],
        "stg_orders": ["revenue"],
        "revenue": ["dashboard"],
    }
    assert downstream_assets(graph, "raw_orders") == ["stg_orders", "revenue", "dashboard"]


def test_transitive_column_downstream():
    col_graph = {
        "raw_orders.amount": ["stg_orders.amount_usd"],
        "stg_orders.amount_usd": ["fct_daily_revenue.daily_revenue"],
        "fct_daily_revenue.daily_revenue": ["ceo_revenue_dashboard.revenue"],
    }
    assert column_downstream(col_graph, "raw_orders.amount") == [
        "stg_orders.amount_usd",
        "fct_daily_revenue.daily_revenue",
        "ceo_revenue_dashboard.revenue",
    ]


def test_deep_multihop_lineage():
    # 6 levels of lineage
    graph = {
        "source_db": ["cdc_stream"],
        "cdc_stream": ["raw_landing"],
        "raw_landing": ["stg_table"],
        "stg_table": ["int_joined"],
        "int_joined": ["fct_mart"],
        "fct_mart": ["bi_dashboard"],
    }
    expected = ["cdc_stream", "raw_landing", "stg_table", "int_joined", "fct_mart", "bi_dashboard"]
    assert downstream_assets(graph, "source_db") == expected


def test_diamond_dag_no_duplicates():
    # Diamond: A -> B, A -> C, B -> D, C -> D, D -> E
    graph = {
        "A": ["B", "C"],
        "B": ["D"],
        "C": ["D"],
        "D": ["E"],
    }
    result = downstream_assets(graph, "A")
    assert result == ["B", "C", "D", "E"]
    # Ensure no duplicates in traversal
    assert len(result) == len(set(result))


def test_cyclic_graph_does_not_infinite_loop():
    # Graph with cycle: A -> B -> C -> A, and C -> D
    graph = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],
        "D": [],
    }
    # BFS with seen set must terminate gracefully without infinite loop
    result = downstream_assets(graph, "A")
    assert set(result) == {"B", "C", "D"}


def test_nonexistent_or_leaf_node():
    graph = {"A": ["B"], "B": []}
    assert downstream_assets(graph, "B") == []
    assert downstream_assets(graph, "nonexistent_node") == []
    assert column_downstream(graph, "nonexistent_col") == []


