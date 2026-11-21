"""B25: every test named in docs/SECTION10_MATRIX.md exists; every row has a test; the file is current."""

import ast
import importlib.util

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("section10_matrix", ROOT / "tools" / "section10_matrix.py")
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)


def _names(path):
    tree = ast.parse((ROOT / path).read_text("utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_every_cited_test_exists_and_every_row_has_one():
    n = 0
    for _, rows in sm.MATRIX:
        for what, tests, _ in rows:
            assert tests, what
            for t in tests:
                path, name = t.split("::")
                assert name in _names(path), t
                n += 1
    assert n >= 60


def test_matrix_doc_up_to_date():
    assert (ROOT / "docs" / "SECTION10_MATRIX.md").read_text("utf-8") == sm.render()
