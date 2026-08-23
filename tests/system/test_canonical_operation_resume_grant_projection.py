from types import SimpleNamespace

import pytest

from voodoo_product.canonical_operation_resume import (
    SELECT_GRANT_BY_EXECUTION,
    CanonicalOperationResumeDenied,
    CanonicalOperationResumeService,
)


def _grant() -> SimpleNamespace:
    return SimpleNamespace(
        jti="jti_test",
        grant_id="grt_test",
        execution_id="exec_test",
        request_id="req_test",
        workspace_id="ws_test",
        environment="test",
        authorization_snapshot_digest="a" * 64,
        execution_capsule_digest="b" * 64,
        grant_digest="c" * 64,
        issued_at="2026-08-23T08:00:00.000+00:00",
        expires_at="2026-08-23T08:01:00.000+00:00",
        revocation_epoch=7,
    )


def _row(grant: SimpleNamespace) -> dict[str, object]:
    return {
        "jti": grant.jti,
        "grant_id": grant.grant_id,
        "execution_id": grant.execution_id,
        "request_id": grant.request_id,
        "workspace_id": grant.workspace_id,
        "environment": grant.environment,
        "authorization_snapshot_digest": grant.authorization_snapshot_digest,
        "execution_capsule_digest": grant.execution_capsule_digest,
        "grant_digest": grant.grant_digest,
        "issued_at": grant.issued_at,
        "expires_at": grant.expires_at,
        "revocation_epoch": grant.revocation_epoch,
    }


@pytest.mark.parametrize(
    ("field", "corrupt_value"),
    [
        ("issued_at", "2026-08-23T07:59:59.000+00:00"),
        ("expires_at", "2026-08-23T08:02:00.000+00:00"),
        ("revocation_epoch", 8),
    ],
)
def test_resume_rejects_corrupted_persisted_grant_projection(
    field: str,
    corrupt_value: object,
) -> None:
    grant = _grant()
    row = _row(grant)
    row[field] = corrupt_value

    with pytest.raises(CanonicalOperationResumeDenied) as exc_info:
        CanonicalOperationResumeService._validate_grant_row(row, grant=grant)

    assert exc_info.value.reason == "GRANT_ROW_INVALID"


def test_resume_selects_all_security_relevant_grant_projection_fields() -> None:
    sql = SELECT_GRANT_BY_EXECUTION.sqlite_sql

    for field in ("issued_at", "expires_at", "revocation_epoch"):
        assert field in sql
