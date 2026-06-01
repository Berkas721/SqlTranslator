CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customers_email ON customers (email);

INSERT INTO customers (email, full_name) VALUES
    ('a@example.com', 'Alice'),
    ('b@example.com', 'Bob'),
    ('c@example.com', 'Carol');
