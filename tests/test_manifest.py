"""hassfest-style static checks (the real hassfest runs in CI)."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CC = ROOT / "custom_components" / "deltatru"


def test_manifest():
    m = json.loads((CC / "manifest.json").read_text())
    keys = list(m)
    assert keys[:2] == ["domain", "name"] and keys[2:] == sorted(keys[2:])
    for k in ("documentation", "issue_tracker", "codeowners", "version", "iot_class", "config_flow"):
        assert k in m
    assert m["domain"] == CC.name


def test_hacs():
    h = json.loads((ROOT / "hacs.json").read_text())
    assert h["name"] == "DeltaTru" and "homeassistant" in h


def test_translations_match_strings_and_code():
    strings = json.loads((CC / "strings.json").read_text())
    assert json.loads((CC / "translations" / "en.json").read_text()) == strings
    keys = set()
    for py in CC.glob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_attr_translation_key" for t in node.targets):
                keys.add(node.value.value)
    ent = {k for d in strings["entity"].values() for k in d}
    assert keys <= ent
    from custom_components.deltatru.const import ALERT_FAMILIES
    assert {f"alert_{f}" for f in ALERT_FAMILIES} <= set(strings["entity"]["binary_sensor"])
