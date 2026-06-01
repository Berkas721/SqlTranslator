WITH user_segments AS (
    SELECT
        u.id,
        u.email,
        u.country,
        COUNT(o.id) AS orders_count,
        SUM(o.amount) AS total_spent,
        MAX(o.created_at) AS last_order_at,
        CASE
            WHEN SUM(o.amount) > 10000 THEN 'vip'
            WHEN SUM(o.amount) > 1000 THEN 'regular'
            ELSE 'casual'
        END AS segment
    FROM users u
    LEFT JOIN orders o ON o.user_id = u.id
    WHERE u.deleted_at IS NULL
    GROUP BY u.id, u.email, u.country
),
country_aggregates AS (
    SELECT
        country,
        segment,
        COUNT(*) AS users_count,
        AVG(total_spent) AS avg_spent
    FROM user_segments
    GROUP BY country, segment
)
SELECT
    us.country,
    us.segment,
    us.email,
    us.total_spent,
    us.last_order_at,
    ca.users_count AS country_segment_size,
    ca.avg_spent AS country_segment_avg
FROM user_segments us
JOIN country_aggregates ca
  ON ca.country = us.country
 AND ca.segment = us.segment
WHERE us.last_order_at >= NOW() - INTERVAL '90 days'
ORDER BY us.country, us.segment, us.total_spent DESC;
