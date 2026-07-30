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


def test_exact_pr_head_is_scanned_before_downstream_tests():
    workflow = (
        ROOT / ".github/workflows/downstream-tests.yml"
    ).read_text(encoding="utf-8")
    assert "test:\n    needs: malware-scan" in workflow
    assert "git archive HEAD" in workflow
    assert "Scan exact head before executing addon code" in workflow
