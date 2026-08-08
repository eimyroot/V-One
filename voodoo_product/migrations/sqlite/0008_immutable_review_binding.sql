ALTER TABLE change_requests
ADD COLUMN review_content_sha256 TEXT
CHECK (
    review_content_sha256 IS NULL
    OR (
        length(review_content_sha256) = 64
        AND review_content_sha256 NOT GLOB '*[^0-9a-f]*'
    )
);

ALTER TABLE approvals
ADD COLUMN review_content_sha256 TEXT
CHECK (
    review_content_sha256 IS NULL
    OR (
        length(review_content_sha256) = 64
        AND review_content_sha256 NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE TRIGGER trg_change_requests_review_content_immutable
BEFORE UPDATE OF workspace_id, title, description, risk, environment, adapter, payload_json, requested_by
ON change_requests
WHEN
    (OLD.review_content_sha256 IS NOT NULL OR NEW.status <> 'DRAFT')
    AND (
        OLD.workspace_id IS NOT NEW.workspace_id
        OR OLD.title IS NOT NEW.title
        OR OLD.description IS NOT NEW.description
        OR OLD.risk IS NOT NEW.risk
        OR OLD.environment IS NOT NEW.environment
        OR OLD.adapter IS NOT NEW.adapter
        OR OLD.payload_json IS NOT NEW.payload_json
        OR OLD.requested_by IS NOT NEW.requested_by
    )
BEGIN
    SELECT RAISE(ABORT, 'submitted change request review content is immutable');
END;

CREATE TRIGGER trg_change_requests_review_digest_insert
BEFORE INSERT ON change_requests
WHEN NEW.review_content_sha256 IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'change request review digest must be created at submission');
END;

CREATE TRIGGER trg_change_requests_review_digest_transition
BEFORE UPDATE OF review_content_sha256 ON change_requests
WHEN
    OLD.review_content_sha256 IS NOT NEW.review_content_sha256
    AND NOT (
        OLD.status = 'DRAFT'
        AND NEW.status = 'REVIEW_REQUIRED'
        AND OLD.review_content_sha256 IS NULL
        AND NEW.review_content_sha256 IS NOT NULL
    )
BEGIN
    SELECT RAISE(ABORT, 'change request review digest transition is invalid');
END;

CREATE TRIGGER trg_change_requests_review_digest_required
BEFORE UPDATE OF status ON change_requests
WHEN
    NEW.status = 'REVIEW_REQUIRED'
    AND NEW.review_content_sha256 IS NULL
BEGIN
    SELECT RAISE(ABORT, 'submitted change request requires review content digest');
END;

CREATE TRIGGER trg_approvals_review_binding_insert
BEFORE INSERT ON approvals
WHEN
    NEW.review_content_sha256 IS NULL
    OR NOT EXISTS (
        SELECT 1
        FROM change_requests cr
        WHERE cr.id = NEW.request_id
          AND cr.status = 'REVIEW_REQUIRED'
          AND cr.review_content_sha256 = NEW.review_content_sha256
    )
BEGIN
    SELECT RAISE(ABORT, 'approval must bind exact pending review content');
END;

CREATE TRIGGER trg_approvals_immutable_update
BEFORE UPDATE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'approval evidence is immutable');
END;

CREATE TRIGGER trg_approvals_immutable_delete
BEFORE DELETE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'approval evidence is immutable');
END;
