from pathlib import Path


def test_upstream_policy_automerge_is_narrow_and_explicitly_gated():
    workflow = Path(
        ".github/workflows/approve-upstream-update.yml"
    ).read_text(encoding="utf-8")

    assert "automation/umbrella-upstream" in workflow
    assert 'protected_prefixes = (".github/", "tools/", "tests/downstream/")' in workflow
    assert "downstream manifest changed beyond upstream base" in workflow
    assert 'python "$RUNNER_TEMP/verified-head/tools/rebuild_downstream.py"' not in workflow
    assert '{"malware-scan", "test"}' in workflow
    assert "UMBRELLA_AUTO_MERGE_ENABLED == 'true'" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "actions: write" in workflow
    assert "environment: umbrella-auto-release" not in workflow
    assert "gh pr review" not in workflow
    assert "--match-head-commit" in workflow
    assert "gh workflow run downstream-tests.yml" in workflow


def test_upstream_proposal_records_patch_conflicts_before_failing_closed():
    workflow = Path(
        ".github/workflows/propose-upstream-update.yml"
    ).read_text(encoding="utf-8")

    assert "continue-on-error: true" in workflow
    assert "steps.materialize.outcome == 'failure'" in workflow
    assert "downstream_patch_conflict" in workflow
    assert "if: always()" in workflow
    assert "pip install --require-hashes -r requirements-ci.txt" in workflow
    assert workflow.index("Upload discovery before any risky candidate operation") < workflow.index(
        "Materialize patch-stack candidate without executing it"
    )
    assert "candidate/tree/omega/plugin.video.umbrella" in workflow
    assert "candidate-path: scan-candidate" in workflow
    assert "--candidate scan-candidate" in workflow
    assert "tar --format=posix -cf umbrella-candidate.tar" in workflow
    assert 'archive.extractall("candidate", filter="data")' in workflow
    assert "if git diff --cached --quiet; then" in workflow
    assert "git diff --cached --quiet &&" not in workflow
    assert 'actual_tree="$(git write-tree)"' in workflow
    assert 'git checkout -B "$BRANCH"' not in workflow
    cleanup = "rm -rf -- candidate candidate-artifact scan-candidate security"
    assert cleanup in workflow
    assert workflow.index(cleanup) < workflow.index("git add -A")
