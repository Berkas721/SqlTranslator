SELECT
    o.id,
    o.created_at,
    u.name AS user_name,
    p.name AS product_name,
    o.amount,
    ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY o.created_at DESC) AS rn
FROM orders o
JOIN users u ON u.id = o.user_id
JOIN products p ON p.id = o.product_id
WHERE o.amount > 0;
