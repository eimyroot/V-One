from __future__ import annotations

import hashlib

import pytest

from voodoo_product.release_promotion import ReleasePromotionDecision, ReleasePromotionError

DIGEST_A = hashlib.sha256(b"release evidence").hexdigest()


def test_release_promotion_round_trips_with_digest() -> None:
    decision = ReleasePromotionDecision.create(
        release_id="release-001",
        source_state="VERIFIED",
        target_state="RELEASE_CANDIDATE",
        purpose="promote only verified changes toward release",
        system_benefit="prevents unverified code from becoming a release candidate",
        evidence_digests=(DIGEST_A,),
        acceptance_gates=("tests_passed", "rollback_defined"),
        rollback_plan="revert release candidate branch before production deployment",
        promoted_by="release-and-progressive-delivery-governor",
    )

    assert ReleasePromotionDecision.from_dict(decision.to_dict()) == decision


def test_release_promotion_rejects_skipped_transition() -> None:
    with pytest.raises(ReleasePromotionError):
        ReleasePromotionDecision.create(
            release_id="release-001",
            source_state="IMPLEMENTED",
            target_state="RELEASED",
            purpose="reject skipped release states",
            system_benefit="keeps release promotion auditable",
            evidence_digests=(DIGEST_A,),
            acceptance_gates=("tests_passed",),
            rollback_plan="revert before production deployment",
            promoted_by="release-and-progressive-delivery-governor",
        )


def test_release_promotion_requires_production_authorization_for_released() -> None:
    with pytest.raises(ReleasePromotionError):
        ReleasePromotionDecision.create(
            release_id="release-001",
            source_state="RELEASE_CANDIDATE",
            target_state="RELEASED",
            purpose="require explicit production release authorization",
            system_benefit="prevents accidental production release",
            evidence_digests=(DIGEST_A,),
            acceptance_gates=("tests_passed",),
            rollback_plan="roll back deployed artifact",
            promoted_by="release-and-progressive-delivery-governor",
        )
