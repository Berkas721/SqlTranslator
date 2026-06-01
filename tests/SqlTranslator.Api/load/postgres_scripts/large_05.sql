CREATE TABLE staging_orders (
    external_id VARCHAR(50),
    user_email VARCHAR(255),
    product_sku VARCHAR(50),
    quantity INT,
    unit_price NUMERIC(12, 2),
    placed_at TIMESTAMP
);

CREATE TABLE dim_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    first_seen TIMESTAMP
);

CREATE TABLE dim_products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE,
    name TEXT
);

CREATE TABLE fact_orders (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES dim_users(id),
    product_id INT REFERENCES dim_products(id),
    quantity INT,
    unit_price NUMERIC(12, 2),
    total NUMERIC(14, 2),
    placed_at TIMESTAMP
);

INSERT INTO dim_users (email, first_seen)
SELECT DISTINCT user_email, MIN(placed_at)
FROM staging_orders
GROUP BY user_email
ON CONFLICT (email) DO NOTHING;

INSERT INTO dim_products (sku, name)
SELECT DISTINCT product_sku, product_sku
FROM staging_orders
ON CONFLICT (sku) DO NOTHING;

INSERT INTO fact_orders (user_id, product_id, quantity, unit_price, total, placed_at)
SELECT
    u.id,
    p.id,
    s.quantity,
    s.unit_price,
    s.quantity * s.unit_price,
    s.placed_at
FROM staging_orders s
JOIN dim_users    u ON u.email = s.user_email
JOIN dim_products p ON p.sku   = s.product_sku;

DELETE FROM staging_orders;
