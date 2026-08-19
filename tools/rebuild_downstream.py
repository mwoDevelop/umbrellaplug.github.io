#!/usr/bin/env python3
"""Reconstruct the Umbrella product tree from upstream plus isolated patches."""

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "downstream-patches.yml"
BASE = re.compile(r'^  base: "([0-9a-f]{40})"$', re.MULTILINE)
COMMITS = re.compile(r'^    commit: "([0-9a-f]{40})"$', re.MULTILINE)
MECHANICAL = ("omega/plugin.video.umbrella/addon.xml",)
PROTECTED = (".github", ".gitmodules")
CONTROL = (
    ".gitignore",
    "DOWNSTREAM.md",
    "downstream-patches.yml",
    "requirements-ci.txt",
    "tools/rebuild_downstream.py",
    "tools/prepare_umbrella_update.py",
    "tests/downstream/test_auto_approval_workflow.py",
    "tests/downstream/test_rebuild.py",
    "tests/downstream/test_update_security_gate.py",
)


def run(*args, cwd=None, input_bytes=None):
    return subprocess.run(
        args,
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def manifest_state():
    payload = MANIFEST.read_text(encoding="utf-8")
    base = BASE.search(payload)
    commits = COMMITS.findall(payload)
    if not base or not commits:
        raise ValueError("downstream patch manifest is incomplete")
    series = []
    excluded = (".github/**", ".gitmodules") + MECHANICAL + CONTROL
    for commit in commits:
        patch = run(
            *(
                "git",
                "-C",
                str(ROOT),
                "diff",
                "%s^" % commit,
                commit,
                "--",
                ".",
                *(":(exclude)%s" % path for path in excluded),
            )
        )
        series.append((commit, patch))
    digest = hashlib.sha256(b"".join(patch for _, patch in series)).hexdigest()
    return base.group(1), series, digest


def reconstruct(output, upstream_base=None):
    output = Path(output)
    if output.exists():
        raise ValueError("output already exists")
    accepted_base, series, digest = manifest_state()
    base = upstream_base or accepted_base
    run("git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(output))
    run("git", "checkout", "--quiet", base, cwd=output)
    for commit, patch in series:
        if not patch:
            continue
        try:
            run("git", "apply", "--3way", "--whitespace=nowarn", "-", cwd=output, input_bytes=patch)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                "downstream patch conflicts at %s: %s"
                % (commit, error.stderr.decode("utf-8", errors="replace"))
            ) from error
    for relative in MECHANICAL + CONTROL:
        source = ROOT / relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for relative in PROTECTED:
        source = ROOT / relative
        target = output / relative
        if not source.exists():
            continue
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        shutil.copytree(source, target) if source.is_dir() else shutil.copyfile(source, target)
    return {
        "base": base,
        "accepted_base": accepted_base,
        "patch_series_sha256": digest,
        "patches": len(series),
    }


def compare_current(generated):
    excluded = {".git", ".pytest_cache", ".venv-downstream", "__pycache__"}
    expected = {
        path.relative_to(ROOT).as_posix(): path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)
    }
    actual = {
        path.relative_to(generated).as_posix(): path
        for path in generated.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.relative_to(generated).parts)
    }
    ignored = {
        ".github/workflows/sync-upstream.yml",
    }
    keys = (set(expected) | set(actual)) - ignored
    changed = [
        key
        for key in sorted(keys)
        if key not in expected
        or key not in actual
        or expected[key].read_bytes() != actual[key].read_bytes()
    ]
    if changed:
        raise ValueError("reconstructed tree differs: %s" % ", ".join(changed))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.check and not args.output:
        parser.error("use --check or --output")
    if args.output:
        state = reconstruct(args.output)
    else:
        with tempfile.TemporaryDirectory(prefix="umbrella-rebuild-") as temporary:
            generated = Path(temporary) / "tree"
            state = reconstruct(generated)
            compare_current(generated)
    print(
        "base=%s patches=%s patch_series_sha256=%s"
        % (state["base"], state["patches"], state["patch_series_sha256"])
    )


if __name__ == "__main__":
    main()
