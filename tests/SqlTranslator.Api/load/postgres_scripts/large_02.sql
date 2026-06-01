WITH RECURSIVE category_tree AS (
    SELECT id, parent_id, name, 1 AS depth, name::TEXT AS path
    FROM categories
    WHERE parent_id IS NULL

    UNION ALL

    SELECT c.id, c.parent_id, c.name, ct.depth + 1, ct.path || ' > ' || c.name
    FROM categories c
    JOIN category_tree ct ON c.parent_id = ct.id
),
product_stats AS (
    SELECT
        p.category_id,
        COUNT(*) AS products_count,
        AVG(p.price) AS avg_price,
        SUM(CASE WHEN p.in_stock THEN 1 ELSE 0 END) AS in_stock_count
    FROM products p
    GROUP BY p.category_id
)
SELECT
    ct.id,
    ct.depth,
    ct.path,
    COALESCE(ps.products_count, 0) AS products_count,
    COALESCE(ps.avg_price, 0) AS avg_price,
    COALESCE(ps.in_stock_count, 0) AS in_stock_count
FROM category_tree ct
LEFT JOIN product_stats ps ON ps.category_id = ct.id
ORDER BY ct.path;
