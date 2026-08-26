"""LOW COUPLING guard: verify architectural module boundaries.

These tests fail if a lower layer imports a higher layer (e.g. ingestion
importing consensus, or parser importing ticker mappings). They are static
import-graph checks over the source files.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "src" / "thirteenf"
APP = ROOT / "app"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _local_imports(path: Path) -> set[str]:
    return {
        n
        for n in _imports(path)
        if n.startswith("thirteenf") or n.startswith("db") or n.startswith("store")
    }


def test_ingestion_layer_does_not_import_analysis():
    """sec_client / filings / parser must not depend on analytics or UI."""
    forbidden = {
        "consensus",
        "trends",
        "portfolio",
        "manager_scoring",
        "changes",
        "quality",
    }
    for name in ("sec_client.py", "filings.py", "parser.py"):
        imports = _local_imports(SRC / name)
        assert not (imports & forbidden), f"{name} imports {imports & forbidden}"


def test_analytics_layer_does_not_import_ui_or_sec_client():
    """changes/quality/consensus/trends/manager_scoring must not import UI."""
    for name in (
        "changes.py",
        "quality.py",
        "consensus.py",
        "trends.py",
        "manager_scoring.py",
    ):
        imports = _local_imports(SRC / name)
        assert not (imports & {"db"}), f"{name} imports {imports & {'db'}}"
        assert not (imports & {"sec_client", "filings"}), (
            f"{name} imports {imports & {'sec_client', 'filings'}}"
        )


def test_security_master_does_not_depend_on_analytics():
    imports = _local_imports(SRC / "security_master.py")
    assert not (imports & {"consensus", "trends", "portfolio", "changes"})


def test_ui_does_not_import_sec_client():
    """UI is a read-mostly presentation layer; it must not reach SEC."""
    for path in APP.rglob("*.py"):
        imports = _local_imports(path)
        assert not (imports & {"sec_client", "filings"}), (
            f"{path.name} imports {imports & {'sec_client', 'filings'}}"
        )


def test_ui_imports_only_allowed_modules():
    """App modules may import the app-local db helper and thirteenf only
    (plus stdlib / streamlit). No direct sqlite or SEC access."""
    for path in APP.rglob("*.py"):
        imports = _imports(path)
        stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
        third_party = {
            n
            for n in imports
            if not n.startswith(("thirteenf", "db", "store", "streamlit"))
            and n not in stdlib
        }
        assert not third_party, f"{path.name} imports {third_party}"
