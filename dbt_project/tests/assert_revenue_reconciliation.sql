-- Singular test: Daily revenue in fct_daily_revenue must match the sum of completed orders from stg_orders
with mart_total as (
    select sum(daily_revenue) as total_mart_revenue
    from {{ ref('fct_daily_revenue') }}
),
stg_total as (
    select sum(amount_usd) as total_stg_revenue
    from {{ ref('stg_orders') }}
    where status = 'completed'
)
select *
from mart_total m
cross join stg_total s
where abs(coalesce(m.total_mart_revenue, 0) - coalesce(s.total_stg_revenue, 0)) > 0.01
