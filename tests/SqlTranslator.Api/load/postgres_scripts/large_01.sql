CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    region VARCHAR(50),
    capacity INT
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    name TEXT,
    category_id INT,
    price NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inventory (
    warehouse_id INT REFERENCES warehouses(id),
    product_id INT REFERENCES products(id),
    quantity INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (warehouse_id, product_id)
);

CREATE INDEX idx_products_category ON products (category_id);
CREATE INDEX idx_inventory_product ON inventory (product_id);

INSERT INTO warehouses (code, region, capacity) VALUES
    ('WH-MSK-01', 'MSK', 10000),
    ('WH-SPB-01', 'SPB', 5000),
    ('WH-EKB-01', 'EKB', 3000);

INSERT INTO products (sku, name, category_id, price) VALUES
    ('SKU-001', 'Item A', 1, 100.00),
    ('SKU-002', 'Item B', 1, 200.00),
    ('SKU-003', 'Item C', 2, 300.00);

INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES
    (1, 1, 100), (1, 2, 50), (1, 3, 75),
    (2, 1, 200), (2, 2, 30),
    (3, 1, 10);
