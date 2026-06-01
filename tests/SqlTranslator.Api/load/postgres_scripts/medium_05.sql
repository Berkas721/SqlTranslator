SELECT
    user_id,
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*) AS events_per_day
FROM events
WHERE created_at BETWEEN '2025-01-01' AND '2025-12-31'
  AND event_type IN ('click', 'view', 'purchase')
GROUP BY user_id, DATE_TRUNC('day', created_at)
HAVING COUNT(*) > 5
ORDER BY day, user_id;
