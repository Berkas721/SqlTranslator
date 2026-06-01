CREATE TABLE IF NOT EXISTS event_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    session_id UUID,
    event_type VARCHAR(50) NOT NULL,
    payload JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_event_log_user_ts ON event_log (user_id, created_at DESC);
CREATE INDEX idx_event_log_type    ON event_log (event_type);

WITH sessions AS (
    SELECT
        session_id,
        MIN(created_at) AS session_start,
        MAX(created_at) AS session_end,
        COUNT(*) AS events_count,
        COUNT(DISTINCT event_type) AS distinct_event_types
    FROM event_log
    WHERE created_at >= NOW() - INTERVAL '1 day'
    GROUP BY session_id
),
funnel AS (
    SELECT
        session_id,
        BOOL_OR(event_type = 'view')     AS has_view,
        BOOL_OR(event_type = 'add_cart') AS has_add_cart,
        BOOL_OR(event_type = 'purchase') AS has_purchase
    FROM event_log
    WHERE created_at >= NOW() - INTERVAL '1 day'
    GROUP BY session_id
)
SELECT
    s.session_id,
    s.session_start,
    s.session_end,
    s.events_count,
    s.distinct_event_types,
    f.has_view,
    f.has_add_cart,
    f.has_purchase,
    EXTRACT(EPOCH FROM (s.session_end - s.session_start)) AS duration_sec
FROM sessions s
JOIN funnel f USING (session_id)
WHERE f.has_view = TRUE
ORDER BY s.session_start;
