BEGIN;

UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
INSERT INTO ledger (account_id, delta) VALUES (1, -100), (2, 100);

COMMIT;
