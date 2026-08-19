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
