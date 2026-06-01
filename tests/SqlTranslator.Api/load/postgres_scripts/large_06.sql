CREATE TABLE sales (
    id BIGSERIAL PRIMARY KEY,
    region VARCHAR(50),
    salesperson_id INT,
    product_id INT,
    quantity INT,
    amount NUMERIC(12, 2),
    sold_at TIMESTAMP
);

CREATE INDEX idx_sales_region   ON sales (region);
CREATE INDEX idx_sales_sold_at  ON sales (sold_at);

WITH monthly AS (
    SELECT
        region,
        salesperson_id,
        DATE_TRUNC('month', sold_at) AS month,
        SUM(amount)   AS revenue,
        SUM(quantity) AS units_sold
    FROM sales
    WHERE sold_at >= NOW() - INTERVAL '12 months'
    GROUP BY region, salesperson_id, DATE_TRUNC('month', sold_at)
),
ranked AS (
    SELECT
        region,
        month,
        salesperson_id,
        revenue,
        units_sold,
        RANK() OVER (PARTITION BY region, month ORDER BY revenue DESC) AS revenue_rank,
        LAG(revenue) OVER (PARTITION BY region, salesperson_id ORDER BY month) AS prev_month_revenue
    FROM monthly
),
qoq AS (
    SELECT
        region,
        month,
        SUM(revenue) AS total_revenue,
        SUM(revenue) - LAG(SUM(revenue)) OVER (PARTITION BY region ORDER BY month) AS revenue_delta
    FROM monthly
    GROUP BY region, month
)
SELECT
    r.region,
    r.month,
    r.salesperson_id,
    r.revenue,
    r.revenue_rank,
    r.prev_month_revenue,
    CASE
        WHEN r.prev_month_revenue IS NULL THEN NULL
        WHEN r.prev_month_revenue = 0 THEN NULL
        ELSE (r.revenue - r.prev_month_revenue) / r.prev_month_revenue
    END AS mom_growth,
    q.total_revenue,
    q.revenue_delta
FROM ranked r
JOIN qoq q ON q.region = r.region AND q.month = r.month
WHERE r.revenue_rank <= 5
ORDER BY r.region, r.month, r.revenue_rank;
