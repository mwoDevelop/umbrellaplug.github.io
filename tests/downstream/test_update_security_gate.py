import ast
import hashlib
import json
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
        "0ebfd26322d8686c1bef1222f3783cd8e55c5e78"
    ) in workflow


def test_exact_pr_head_is_scanned_before_downstream_tests():
    workflow = (
        ROOT / ".github/workflows/downstream-tests.yml"
    ).read_text(encoding="utf-8")
    assert "test:\n    needs: malware-scan" in workflow
    assert "omega/plugin.video.umbrella" in workflow
    assert "downstream-patches.yml" in workflow
    assert "Scan exact head before executing addon code" in workflow
    assert "baseline: .github/security-baseline.json" in workflow


def test_security_baseline_is_bound_to_current_reviewed_bytes():
    baseline = json.loads(
        (ROOT / ".github/security-baseline.json").read_text(encoding="utf-8")
    )
    assert baseline["schema"] == 1
    for item in baseline["findings"]:
        relative = item["path"].removeprefix("tree/")
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert digest == item["sha256"]
