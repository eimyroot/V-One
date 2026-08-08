from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from voodoo_product.config import ProductConfig
from voodoo_product.evidence_primitives import canonical_json
from voodoo_product.persistence import DatabaseIntegrityError
from voodoo_product.service import ProductService


def product_config(tmp_path: Path) -> ProductConfig:
    return ProductConfig(
        environment="test",
        database_path=tmp_path / "product.sqlite3",
        sandbox_root=tmp_path / "sandboxes",
        session_signing_secret="s" * 64,
        bootstrap_token="b" * 48,
    )


def bootstrap_product(tmp_path: Path) -> tuple[ProductService, dict[str, str]]:
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    return service, bootstrap


def create_operator(
    service: ProductService,
    *,
    actor_id: str,
    index: int,
) -> dict[str, object]:
    return service.create_user(
        actor_id=actor_id,
        username=f"operator{index}",
        password=f"VeryStrongOperatorPassword{index}!",
        role="operator",
    )


def create_request(
    service: ProductService,
    bootstrap: dict[str, str],
    *,
    workspace_id: str | None = None,
    environment: str = "local",
    payload: dict[str, object] | None = None,
    title: str = "Immutable review binding",
) -> dict[str, object]:
    return service.create_change_request(
        actor_id=bootstrap["user_id"],
        workspace_id=workspace_id or bootstrap["workspace_id"],
        title=title,
        description="bind approval to exact submitted content",
        risk="R2",
        environment=environment,
        adapter="echo",
        payload=payload or {"a": 1, "b": 2},
    )


def expected_review_digest(request: dict[str, object]) -> str:
    subject = {
        "schema": "change-request-review/v1",
        "workspace_id": request["workspace_id"],
        "title": request["title"],
        "description": request["description"],
        "risk": request["risk"],
        "environment": request["environment"],
        "adapter": request["adapter"],
        "payload": request["payload"],
        "requested_by": request["requested_by"],
    }
    return hashlib.sha256(canonical_json(subject).encode("utf-8")).hexdigest()


def test_submission_binds_deterministic_exact_review_content(tmp_path: Path) -> None:
    service, bootstrap = bootstrap_product(tmp_path)
    first = create_request(
        service,
        bootstrap,
        payload={"b": 2, "a": 1},
    )
    second = create_request(
        service,
        bootstrap,
        payload={"a": 1, "b": 2},
    )

    first_submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=str(first["id"]),
    )
    second_submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=str(second["id"]),
    )

    expected = expected_review_digest(first)
    assert first_submitted["review_content_sha256"] == expected
    assert second_submitted["review_content_sha256"] == expected
    assert len(expected) == 64

    submit_event = next(
        event
        for event in service.list_audit_events(limit=100)
        if event["action"] == "change_request.submit"
        and event["target_id"] == first["id"]
    )
    assert submit_event["payload"]["review_content_sha256"] == expected


def test_submitted_content_and_approval_evidence_are_immutable_and_bound(
    tmp_path: Path,
) -> None:
    service, bootstrap = bootstrap_product(tmp_path)
    operator = create_operator(service, actor_id=bootstrap["user_id"], index=1)
    request = create_request(service, bootstrap)
    submitted = service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=str(request["id"]),
    )
    digest = str(submitted["review_content_sha256"])

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "UPDATE change_requests SET title = ? WHERE id = ?",
            ("tampered", request["id"]),
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            """
            UPDATE change_requests SET review_content_sha256 = ?
            WHERE id = ?
            """,
            ("b" * 64, request["id"]),
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            """
            INSERT INTO approvals(
                id, request_id, approver_id, decision, reason,
                review_content_sha256, created_at
            ) VALUES (?, ?, ?, 'APPROVED', 'wrong binding', ?, ?)
            """,
            (
                "appr_wrong_binding",
                request["id"],
                operator["id"],
                "b" * 64,
                "2026-08-08T18:45:00.000+00:00",
            ),
        )

    approved = service.approve_change_request(
        actor_id=str(operator["id"]),
        request_id=str(request["id"]),
        decision="APPROVED",
        reason="exact content reviewed",
    )
    assert approved["status"] == "APPROVED"

    with service.db.connect() as connection:
        approval = connection.execute(
            """
            SELECT id, review_content_sha256
            FROM approvals WHERE request_id = ?
            """,
            (request["id"],),
        ).fetchone()
        execution_count = connection.execute(
            "SELECT COUNT(*) AS count FROM executions WHERE request_id = ?",
            (request["id"],),
        ).fetchone()["count"]

    assert approval["review_content_sha256"] == digest
    assert execution_count == 0

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "UPDATE approvals SET reason = 'tampered' WHERE id = ?",
            (approval["id"],),
        )

    with pytest.raises(DatabaseIntegrityError), service.db.connect() as connection:
        connection.execute(
            "DELETE FROM approvals WHERE id = ?",
            (approval["id"],),
        )

    approval_event = next(
        event
        for event in service.list_audit_events(limit=100)
        if event["action"] == "change_request.approved"
        and event["target_id"] == request["id"]
    )
    assert approval_event["payload"]["review_content_sha256"] == digest


@pytest.mark.parametrize(
    ("first_decision", "second_decision", "terminal_status"),
    [
        ("APPROVED", "DENIED", "APPROVED"),
        ("DENIED", "APPROVED", "DENIED"),
    ],
)
def test_terminal_decision_rejects_later_distinct_approver(
    tmp_path: Path,
    first_decision: str,
    second_decision: str,
    terminal_status: str,
) -> None:
    service, bootstrap = bootstrap_product(tmp_path)
    first = create_operator(service, actor_id=bootstrap["user_id"], index=1)
    second = create_operator(service, actor_id=bootstrap["user_id"], index=2)
    request = create_request(service, bootstrap)
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=str(request["id"]),
    )

    result = service.approve_change_request(
        actor_id=str(first["id"]),
        request_id=str(request["id"]),
        decision=first_decision,
        reason="first terminal decision",
    )
    assert result["status"] == terminal_status

    with pytest.raises(RuntimeError, match="request is not awaiting review"):
        service.approve_change_request(
            actor_id=str(second["id"]),
            request_id=str(request["id"]),
            decision=second_decision,
            reason="must be rejected after terminal outcome",
        )

    with service.db.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM approvals WHERE request_id = ?",
            (request["id"],),
        ).fetchone()["count"]
    assert count == 1


def test_concurrent_final_approval_and_denial_yield_one_terminal_outcome(
    tmp_path: Path,
) -> None:
    service, bootstrap = bootstrap_product(tmp_path)
    operators = [
        create_operator(service, actor_id=bootstrap["user_id"], index=index)
        for index in (1, 2, 3)
    ]
    production_workspace = service.create_workspace(
        actor_id=bootstrap["user_id"],
        name="Production",
        environment="production",
    )
    request = create_request(
        service,
        bootstrap,
        workspace_id=str(production_workspace["id"]),
        environment="production",
        title="Concurrent terminal review",
    )
    service.submit_change_request(
        actor_id=bootstrap["user_id"],
        request_id=str(request["id"]),
    )
    first = service.approve_change_request(
        actor_id=str(operators[0]["id"]),
        request_id=str(request["id"]),
        decision="APPROVED",
        reason="first production approval",
    )
    assert first["status"] == "REVIEW_REQUIRED"

    barrier = Barrier(2)

    def decide(actor_id: str, decision: str) -> tuple[str, str]:
        barrier.wait()
        try:
            result = service.approve_change_request(
                actor_id=actor_id,
                request_id=str(request["id"]),
                decision=decision,
                reason=f"concurrent {decision.lower()}",
            )
        except RuntimeError as exc:
            return ("error", str(exc))
        return ("ok", str(result["status"]))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(decide, str(operators[1]["id"]), "APPROVED"),
            executor.submit(decide, str(operators[2]["id"]), "DENIED"),
        ]
        outcomes = [future.result() for future in futures]

    assert sorted(outcome[0] for outcome in outcomes) == ["error", "ok"]
    error = next(outcome[1] for outcome in outcomes if outcome[0] == "error")
    assert error == "request is not awaiting review"

    final = service.get_change_request(str(request["id"]))
    assert final["status"] in {"APPROVED", "DENIED"}

    with service.db.connect() as connection:
        decisions = connection.execute(
            "SELECT decision FROM approvals WHERE request_id = ?",
            (request["id"],),
        ).fetchall()
    assert len(decisions) == 2
