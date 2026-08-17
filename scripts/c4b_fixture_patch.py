from pathlib import Path

path = Path("tests/system/test_durable_execution_epoch_lease.py")
text = path.read_text(encoding="utf-8")
start_marker = '''        connection.execute(
            """
            INSERT INTO change_requests(
'''
end_marker = '''        connection.execute(
            """
            INSERT INTO authorization_snapshots(
'''

if text.count(start_marker) != 1:
    raise SystemExit(f"expected one change-request seed, found {text.count(start_marker)}")
if text.count(end_marker) != 1:
    raise SystemExit(f"expected one snapshot seed, found {text.count(end_marker)}")

start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = '''        connection.execute(
            """
            INSERT INTO change_requests(
                id, workspace_id, title, description, risk, environment, adapter,
                payload_json, status, requested_by, created_at, updated_at
            ) VALUES (
                'cr_c4b', 'wrk_main', 'C4b', '', 'R1', 'local', 'echo', '{}',
                'DRAFT', 'usr_admin',
                '2026-08-17T05:00:00.000+00:00',
                '2026-08-17T05:00:00.000+00:00'
            )
            """
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'REVIEW_REQUIRED',
                review_content_sha256 = ?,
                updated_at = '2026-08-17T05:01:00.000+00:00'
            WHERE id = 'cr_c4b'
            """,
            (REVIEW_DIGEST,),
        )
        connection.execute(
            """
            UPDATE change_requests
            SET status = 'APPROVED',
                updated_at = '2026-08-17T05:02:00.000+00:00'
            WHERE id = 'cr_c4b'
            """
        )
'''

path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
