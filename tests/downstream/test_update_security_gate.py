import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "prepare_umbrella_update.py"
WORKFLOW = ROOT / ".github" / "workflows" / "propose-upstream-update.yml"


def _function_source(name):
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.get_source_segment(source, node)


def test_prepare_never_executes_candidate_tests():
    assert "pytest" not in _function_source("prepare")


def test_tests_are_deferred_until_after_the_scanner_gate():
    assert "pytest" in _function_source("test_bundle")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    scan = workflow.index("Scan exact candidate before executing tests")
    execute = workflow.index("Test the scanned content-addressed candidate")
    assert scan < execute
    assert (
        "mwoDevelop/kodi/.github/actions/upstream-malware-scan@"
        "28f29307987e277836cb610c944c120d60638ba4"
    ) in workflow
