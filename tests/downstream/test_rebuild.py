import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_current_downstream_is_reconstructable():
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "rebuild_downstream.py"), "--check"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
