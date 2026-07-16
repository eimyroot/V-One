CREATE TABLE receipts_v3 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    execution_id TEXT NOT NULL UNIQUE REFERENCES executions(id),
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    receipt_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

WITH RECURSIVE receipt_chain(
    sequence, id, execution_id, payload_json, previous_hash, receipt_hash, created_at
) AS (
    SELECT 1, id, execution_id, payload_json, previous_hash, receipt_hash, created_at
    FROM receipts
    WHERE previous_hash = 'GENESIS'

    UNION ALL

    SELECT receipt_chain.sequence + 1,
           receipts.id,
           receipts.execution_id,
           receipts.payload_json,
           receipts.previous_hash,
           receipts.receipt_hash,
           receipts.created_at
    FROM receipts
    JOIN receipt_chain ON receipts.previous_hash = receipt_chain.receipt_hash
)
INSERT INTO receipts_v3(
    sequence, id, execution_id, payload_json, previous_hash, receipt_hash, created_at
)
SELECT sequence, id, execution_id, payload_json, previous_hash, receipt_hash, created_at
FROM receipt_chain;

CREATE TABLE receipt_sequence_migration_guard (
    valid INTEGER NOT NULL CHECK(valid = 1)
);

INSERT INTO receipt_sequence_migration_guard(valid)
SELECT CASE
    WHEN (SELECT COUNT(*) FROM receipts) = (SELECT COUNT(*) FROM receipts_v3) THEN 1
    ELSE 0
END;

DROP TABLE receipt_sequence_migration_guard;
DROP TABLE receipts;
ALTER TABLE receipts_v3 RENAME TO receipts;
