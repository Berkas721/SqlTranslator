SELECT
    p.id,
    p.name,
    c.name AS category_name,
    CASE
        WHEN p.price < 100 THEN 'cheap'
        WHEN p.price < 1000 THEN 'medium'
        ELSE 'expensive'
    END AS price_band
FROM products p
INNER JOIN categories c ON c.id = p.category_id
WHERE p.in_stock = TRUE
ORDER BY p.price;
