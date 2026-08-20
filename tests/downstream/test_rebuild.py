import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
import rebuild_downstream


ROOT = Path(__file__).parents[2]


def test_current_downstream_is_reconstructable():
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "rebuild_downstream.py"), "--check"],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def test_localization_overlay_rejects_upstream_id_collision():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative in rebuild_downstream.LOCALIZATION_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('msgctxt "#49920"\nmsgid "upstream"\nmsgstr ""\n')
        with pytest.raises(ValueError, match="collides with upstream"):
            rebuild_downstream.apply_localizations(root)


def test_missing_upstream_base_is_fetched_by_exact_sha(monkeypatch, tmp_path):
    calls = []
    probes = 0

    def fake_run(*args, cwd=None, input_bytes=None):
        nonlocal probes
        calls.append(args)
        if args[:3] == ("git", "cat-file", "-e"):
            probes += 1
            if probes == 1:
                raise subprocess.CalledProcessError(1, args)
        return b""

    monkeypatch.setattr(rebuild_downstream, "run", fake_run)
    base = "a" * 40
    rebuild_downstream.ensure_upstream_base(tmp_path, base)

    assert (
        "git",
        "fetch",
        "--quiet",
        "--no-tags",
        "--depth=1",
        rebuild_downstream.UPSTREAM_URL,
        base,
    ) in calls
    assert probes == 2
