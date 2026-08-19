from pathlib import Path


def test_upstream_auto_approval_is_narrow_and_observe_only_by_default():
    workflow = Path(
        ".github/workflows/approve-upstream-update.yml"
    ).read_text(encoding="utf-8")

    assert "automation/umbrella-upstream" in workflow
    assert 'protected_prefixes = (".github/", "tools/", "tests/downstream/")' in workflow
    assert "downstream manifest changed beyond upstream base" in workflow
    assert 'python "$RUNNER_TEMP/verified-head/tools/rebuild_downstream.py"' not in workflow
    assert '{"malware-scan", "test"}' in workflow
    assert "UMBRELLA_AUTO_MERGE_ENABLED == 'true'" in workflow
    assert "environment: umbrella-auto-release" in workflow
    assert "--match-head-commit" in workflow
