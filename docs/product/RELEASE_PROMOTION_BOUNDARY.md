# Release Promotion Boundary

Release promotion is explicit and ordered:

`IMPLEMENTED -> VERIFIED -> RELEASE_CANDIDATE -> RELEASED`

Skipping states is invalid. Production release requires the `production_release_authorized` acceptance gate and a rollback plan.
