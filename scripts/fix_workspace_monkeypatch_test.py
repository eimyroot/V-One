from pathlib import Path

path = Path("tests/system/test_workspace_service.py")
text = path.read_text(encoding="utf-8")
old = '''    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T13:00:00.000+00:00")
    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    workspace = service.create_workspace(
'''
new = '''    service = ProductService(product_config(tmp_path))
    bootstrap = service.bootstrap_admin(
        username="admin",
        password="VeryStrongAdminPassword1!",
        token="b" * 48,
    )
    monkeypatch.setattr(service_module, "new_id", controlled_new_id)
    monkeypatch.setattr(service_module, "utc_now", lambda: "2026-07-17T13:00:00.000+00:00")
    workspace = service.create_workspace(
'''
if text.count(old) != 1:
    raise SystemExit("expected one workspace monkeypatch setup block")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
