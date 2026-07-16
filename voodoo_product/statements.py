from __future__ import annotations

from types import MappingProxyType

from .persistence import DatabaseStatement


def _read(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="read", sqlite_sql=sql)


def _write(name: str, sql: str) -> DatabaseStatement:
    return DatabaseStatement(name=name, mode="write", sqlite_sql=sql)


COUNT_USERS = _read("users.count", "SELECT COUNT(*) AS count FROM users")
INSERT_USER = _write(
    "users.insert",
    "INSERT INTO users(id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
)
SELECT_USER_FOR_AUTH = _read(
    "users.select_for_auth",
    "SELECT id, username, password_hash, role, active FROM users WHERE username = ?",
)
SELECT_ACTIVE_USER = _read(
    "users.select_active",
    "SELECT id, username, role, active FROM users WHERE id = ?",
)

INSERT_WORKSPACE = _write(
    "workspaces.insert",
    "INSERT INTO workspaces(id, name, environment, created_at) VALUES (?, ?, ?, ?)",
)
LIST_WORKSPACES = _read(
    "workspaces.list",
    "SELECT id, name, environment, created_at FROM workspaces ORDER BY name",
)
SELECT_WORKSPACE_CONTEXT = _read(
    "workspaces.select_context",
    "SELECT id, environment FROM workspaces WHERE id = ?",
)

SELECT_AUTH_RATE_LIMIT = _read(
    "auth_rate_limits.select",
    """
    SELECT failure_count, window_started_at, blocked_until
    FROM auth_rate_limits WHERE scope = ? AND key_hash = ?
    """,
)
DELETE_AUTH_RATE_LIMIT = _write(
    "auth_rate_limits.delete",
    "DELETE FROM auth_rate_limits WHERE scope = ? AND key_hash = ?",
)
DELETE_EXPIRED_AUTH_RATE_LIMITS = _write(
    "auth_rate_limits.delete_expired",
    "DELETE FROM auth_rate_limits WHERE updated_at < ?",
)
UPSERT_AUTH_RATE_LIMIT = _write(
    "auth_rate_limits.upsert",
    """
    INSERT INTO auth_rate_limits(
        scope, key_hash, failure_count, window_started_at, blocked_until, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(scope, key_hash) DO UPDATE SET
        failure_count = excluded.failure_count,
        window_started_at = excluded.window_started_at,
        blocked_until = excluded.blocked_until,
        updated_at = excluded.updated_at
    """,
)

INSERT_CHANGE_REQUEST = _write(
    "change_requests.insert",
    """
    INSERT INTO change_requests(
        id, workspace_id, title, description, risk, environment,
        adapter, payload_json, status, requested_by, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
    """,
)
LIST_CHANGE_REQUESTS = _read(
    "change_requests.list",
    """
    SELECT cr.*, u.username AS requested_by_username,
           (SELECT COUNT(*) FROM approvals a
            WHERE a.request_id = cr.id AND a.decision = 'APPROVED') AS approval_count
    FROM change_requests cr
    JOIN users u ON u.id = cr.requested_by
    ORDER BY cr.updated_at DESC LIMIT ?
    """,
)
GET_CHANGE_REQUEST = _read(
    "change_requests.get",
    """
    SELECT cr.*, u.username AS requested_by_username,
           (SELECT COUNT(*) FROM approvals a
            WHERE a.request_id = cr.id AND a.decision = 'APPROVED') AS approval_count
    FROM change_requests cr JOIN users u ON u.id = cr.requested_by
    WHERE cr.id = ?
    """,
)
SELECT_CHANGE_REQUEST_STATUS = _read(
    "change_requests.select_status",
    """
    SELECT cr.status, cr.environment, w.environment AS workspace_environment
    FROM change_requests cr
    JOIN workspaces w ON w.id = cr.workspace_id
    WHERE cr.id = ?
    """,
)
MARK_CHANGE_REQUEST_SUBMITTED = _write(
    "change_requests.mark_submitted",
    "UPDATE change_requests SET status = 'REVIEW_REQUIRED', updated_at = ? WHERE id = ?",
)
SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT = _read(
    "change_requests.select_approval_context",
    """
    SELECT cr.status, cr.environment, cr.requested_by,
           w.environment AS workspace_environment
    FROM change_requests cr
    JOIN workspaces w ON w.id = cr.workspace_id
    WHERE cr.id = ?
    """,
)
UPDATE_CHANGE_REQUEST_STATUS = _write(
    "change_requests.update_status",
    "UPDATE change_requests SET status = ?, updated_at = ? WHERE id = ?",
)
SELECT_CHANGE_REQUEST_FOR_EXECUTION = _read(
    "change_requests.select_for_execution",
    """
    SELECT cr.*, w.environment AS workspace_environment
    FROM change_requests cr
    JOIN workspaces w ON w.id = cr.workspace_id
    WHERE cr.id = ?
    """,
)
MARK_CHANGE_REQUEST_RUNNING = _write(
    "change_requests.mark_running",
    "UPDATE change_requests SET status = 'RUNNING', updated_at = ? WHERE id = ?",
)
MARK_CHANGE_REQUEST_COMPLETED = _write(
    "change_requests.mark_completed",
    "UPDATE change_requests SET status = ?, updated_at = ? WHERE id = ?",
)
COUNT_CHANGE_REQUESTS_BY_STATUS = _read(
    "change_requests.count_by_status",
    "SELECT status, COUNT(*) AS count FROM change_requests GROUP BY status",
)
COUNT_CHANGE_REQUESTS_BY_RISK = _read(
    "change_requests.count_by_risk",
    "SELECT risk, COUNT(*) AS count FROM change_requests GROUP BY risk",
)

INSERT_APPROVAL = _write(
    "approvals.insert",
    """
    INSERT INTO approvals(id, request_id, approver_id, decision, reason, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
)
COUNT_APPROVED = _read(
    "approvals.count_approved",
    "SELECT COUNT(*) AS count FROM approvals WHERE request_id = ? AND decision = 'APPROVED'",
)
LIST_APPROVALS = _read(
    "approvals.list",
    """
    SELECT cr.id AS request_id, cr.title, cr.risk, cr.environment, cr.status,
           cr.updated_at, u.username AS requested_by,
           (SELECT COUNT(*) FROM approvals a
            WHERE a.request_id = cr.id AND a.decision = 'APPROVED') AS approved_count,
           CASE WHEN cr.environment = 'production' THEN 2 ELSE 1 END AS required_count
    FROM change_requests cr JOIN users u ON u.id = cr.requested_by
    ORDER BY cr.updated_at DESC
    """,
)
LIST_PENDING_APPROVALS = _read(
    "approvals.list_pending",
    """
    SELECT cr.id AS request_id, cr.title, cr.risk, cr.environment, cr.status,
           cr.updated_at, u.username AS requested_by,
           (SELECT COUNT(*) FROM approvals a
            WHERE a.request_id = cr.id AND a.decision = 'APPROVED') AS approved_count,
           CASE WHEN cr.environment = 'production' THEN 2 ELSE 1 END AS required_count
    FROM change_requests cr JOIN users u ON u.id = cr.requested_by
    WHERE cr.status = 'REVIEW_REQUIRED'
    ORDER BY cr.updated_at DESC
    """,
)

SELECT_EXECUTION_BY_IDEMPOTENCY_KEY = _read(
    "executions.select_by_idempotency_key",
    "SELECT id, request_id FROM executions WHERE idempotency_key = ?",
)
INSERT_EXECUTION = _write(
    "executions.insert",
    """
    INSERT INTO executions(
        id, request_id, status, adapter, output_json, idempotency_key,
        started_at, lease_expires_at
    ) VALUES (?, ?, 'RUNNING', ?, '{}', ?, ?, ?)
    """,
)
COMPLETE_EXECUTION = _write(
    "executions.complete",
    """
    UPDATE executions
    SET status = ?, output_json = ?, error = ?, completed_at = ?, lease_expires_at = NULL
    WHERE id = ? AND status = 'RUNNING' AND fence = ?
    RETURNING id
    """,
)
SELECT_EXECUTION_FOR_RECOVERY = _read(
    "executions.select_for_recovery",
    """
    SELECT e.id, e.request_id, e.status, e.adapter, e.output_json,
           e.fence, e.lease_expires_at,
           cr.workspace_id, cr.risk, cr.environment
    FROM executions e
    JOIN change_requests cr ON cr.id = e.request_id
    WHERE e.id = ?
    """,
)
INTERRUPT_EXECUTION = _write(
    "executions.interrupt",
    """
    UPDATE executions
    SET status = 'INTERRUPTED', output_json = ?, error = ?, completed_at = ?,
        lease_expires_at = NULL, fence = fence + 1
    WHERE id = ? AND status = 'RUNNING' AND fence = ? AND lease_expires_at IS ?
    RETURNING id
    """,
)
LIST_EXECUTIONS = _read(
    "executions.list",
    """
    SELECT e.*, cr.title, cr.risk, cr.environment, cr.workspace_id,
           r.id AS receipt_id, r.receipt_hash
    FROM executions e
    JOIN change_requests cr ON cr.id = e.request_id
    LEFT JOIN receipts r ON r.execution_id = e.id
    ORDER BY e.started_at DESC LIMIT ?
    """,
)
GET_EXECUTION = _read(
    "executions.get",
    """
    SELECT e.*, cr.title, cr.risk, cr.environment, cr.workspace_id,
           r.id AS receipt_id, r.receipt_hash
    FROM executions e
    JOIN change_requests cr ON cr.id = e.request_id
    LEFT JOIN receipts r ON r.execution_id = e.id
    WHERE e.id = ?
    """,
)
COUNT_EXECUTIONS_BY_STATUS = _read(
    "executions.count_by_status",
    "SELECT status, COUNT(*) AS count FROM executions GROUP BY status",
)

LIST_RECEIPTS = _read(
    "receipts.list",
    "SELECT * FROM receipts ORDER BY sequence DESC LIMIT ?",
)
LIST_RECEIPTS_FOR_VERIFICATION = _read(
    "receipts.list_for_verification",
    "SELECT * FROM receipts ORDER BY sequence",
)
SELECT_RECEIPT_HEAD = _read(
    "receipts.select_head",
    "SELECT receipt_hash FROM receipts ORDER BY sequence DESC LIMIT 1",
)
INSERT_RECEIPT = _write(
    "receipts.insert",
    """
    INSERT INTO receipts(
        id, execution_id, payload_json, previous_hash, receipt_hash, created_at
    ) VALUES (?, ?, ?, ?, ?, ?)
    """,
)

LIST_AUDIT_EVENTS = _read(
    "audit_events.list",
    "SELECT * FROM audit_events ORDER BY sequence DESC LIMIT ?",
)
LIST_AUDIT_EVENTS_FOR_VERIFICATION = _read(
    "audit_events.list_for_verification",
    "SELECT * FROM audit_events ORDER BY sequence",
)
SELECT_AUDIT_HEAD = _read(
    "audit_events.select_head",
    "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1",
)
INSERT_AUDIT_EVENT = _write(
    "audit_events.insert",
    """
    INSERT INTO audit_events(
        id, actor_id, action, target_type, target_id,
        payload_json, previous_hash, event_hash, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
)

UPSERT_EMERGENCY_STOP = _write(
    "runtime_flags.upsert_emergency_stop",
    """
    INSERT INTO runtime_flags(key, value, updated_by, updated_at)
    VALUES ('emergency_stop', ?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET
        value = excluded.value,
        updated_by = excluded.updated_by,
        updated_at = excluded.updated_at
    """,
)
SELECT_EMERGENCY_STOP = _read(
    "runtime_flags.select_emergency_stop",
    "SELECT value FROM runtime_flags WHERE key = 'emergency_stop'",
)
HEALTH_CHECK = _read("system.health", "SELECT 1")


ALL_STATEMENTS = (
    COUNT_USERS,
    INSERT_USER,
    SELECT_USER_FOR_AUTH,
    SELECT_ACTIVE_USER,
    INSERT_WORKSPACE,
    LIST_WORKSPACES,
    SELECT_WORKSPACE_CONTEXT,
    SELECT_AUTH_RATE_LIMIT,
    DELETE_AUTH_RATE_LIMIT,
    DELETE_EXPIRED_AUTH_RATE_LIMITS,
    UPSERT_AUTH_RATE_LIMIT,
    INSERT_CHANGE_REQUEST,
    LIST_CHANGE_REQUESTS,
    GET_CHANGE_REQUEST,
    SELECT_CHANGE_REQUEST_STATUS,
    MARK_CHANGE_REQUEST_SUBMITTED,
    SELECT_CHANGE_REQUEST_APPROVAL_CONTEXT,
    UPDATE_CHANGE_REQUEST_STATUS,
    SELECT_CHANGE_REQUEST_FOR_EXECUTION,
    MARK_CHANGE_REQUEST_RUNNING,
    MARK_CHANGE_REQUEST_COMPLETED,
    COUNT_CHANGE_REQUESTS_BY_STATUS,
    COUNT_CHANGE_REQUESTS_BY_RISK,
    INSERT_APPROVAL,
    COUNT_APPROVED,
    LIST_APPROVALS,
    LIST_PENDING_APPROVALS,
    SELECT_EXECUTION_BY_IDEMPOTENCY_KEY,
    INSERT_EXECUTION,
    COMPLETE_EXECUTION,
    SELECT_EXECUTION_FOR_RECOVERY,
    INTERRUPT_EXECUTION,
    LIST_EXECUTIONS,
    GET_EXECUTION,
    COUNT_EXECUTIONS_BY_STATUS,
    LIST_RECEIPTS,
    LIST_RECEIPTS_FOR_VERIFICATION,
    SELECT_RECEIPT_HEAD,
    INSERT_RECEIPT,
    LIST_AUDIT_EVENTS,
    LIST_AUDIT_EVENTS_FOR_VERIFICATION,
    SELECT_AUDIT_HEAD,
    INSERT_AUDIT_EVENT,
    UPSERT_EMERGENCY_STOP,
    SELECT_EMERGENCY_STOP,
    HEALTH_CHECK,
)

STATEMENTS_BY_NAME = MappingProxyType({statement.name: statement for statement in ALL_STATEMENTS})
if len(STATEMENTS_BY_NAME) != len(ALL_STATEMENTS):
    raise RuntimeError("database statement names must be unique")
