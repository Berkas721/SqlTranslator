INSERT INTO orders (user_id, product_id, amount, created_at)
SELECT u.id, p.id, p.price, NOW()
FROM users u
CROSS JOIN products p
WHERE u.is_test = TRUE
  AND p.category_id = 1
ON CONFLICT DO NOTHING
RETURNING id;
