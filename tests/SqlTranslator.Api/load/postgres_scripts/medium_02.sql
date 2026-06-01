WITH recent_orders AS (
    SELECT user_id, amount
    FROM orders
    WHERE created_at >= NOW() - INTERVAL '30 days'
)
SELECT user_id, COUNT(*) AS n, AVG(amount) AS avg_amount
FROM recent_orders
GROUP BY user_id
ORDER BY n DESC;
