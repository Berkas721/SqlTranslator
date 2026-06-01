CREATE MATERIALIZED VIEW daily_revenue AS
SELECT
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*) AS orders_count,
    SUM(amount) AS revenue
FROM orders
WHERE status = 'completed'
GROUP BY DATE_TRUNC('day', created_at);

CREATE INDEX idx_daily_revenue_day ON daily_revenue (day);
