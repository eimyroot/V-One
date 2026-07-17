from pathlib import Path

path = Path("tests/system/test_change_request_service.py")
text = path.read_text(encoding="utf-8")
old = (
    "            isinstance(call.args[0], ast.Attribute)\n"
    "            or isinstance(call.args[0], ast.IfExp)\n"
)
new = "            isinstance(call.args[0], (ast.Attribute, ast.IfExp))\n"
if text.count(old) != 1:
    raise SystemExit("expected one split AST type assertion")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
