#!/usr/bin/env python3
"""Prepare and safely apply an Umbrella upstream patch-stack candidate."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

import rebuild_downstream


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("downstream-patches.yml")
ADDON_XML = Path("omega/plugin.video.umbrella/addon.xml")
PROTECTED = (".github", ".gitmodules")
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".venv-downstream"}
SCHEMA = 1
MAX_FILES = 20000
MAX_BYTES = 512 * 1024 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r'(<addon\b[^>]*\bversion=")([^"]+)(")')


def _run(*args, cwd=ROOT, check=True, text=True):
    result = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        text=text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError((result.stdout or "") + (result.stderr or ""))
    return result


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _digest(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else _canonical(value)
    ).hexdigest()


def _git_bytes(root, commit, path):
    return subprocess.check_output(
        ["git", "-C", str(root), "show", "%s:%s" % (commit, path)]
    )


def _version(payload):
    match = VERSION.search(payload.decode("utf-8", errors="strict"))
    if not match or not all(part.isdigit() for part in match.group(2).split(".")):
        raise ValueError("unsupported Umbrella version")
    return match.group(2)


def _next_version(upstream_version, downstream_version):
    upstream = tuple(int(part) for part in upstream_version.split("."))
    downstream = tuple(int(part) for part in downstream_version.split("."))
    if len(downstream) == len(upstream) + 1 and downstream[:-1] == upstream:
        return upstream_version + "." + str(downstream[-1] + 1)
    return upstream_version + ".1"


def discover(root=ROOT):
    accepted, _series, _digest_value = rebuild_downstream.manifest_state()
    repository = "https://github.com/umbrellaplug/umbrellaplug.github.io.git"
    row = _run("git", "ls-remote", repository, "refs/heads/master", cwd=root).stdout
    fields = row.split()
    if not fields or not SHA40.fullmatch(fields[0]):
        raise ValueError("Umbrella upstream did not resolve to an exact commit")
    observed = fields[0]
    if observed == accepted:
        return {
            "schema": SCHEMA,
            "action": "noop",
            "accepted_commit": accepted,
            "observed_commit": observed,
        }
    _run("git", "fetch", "--no-tags", repository, observed, cwd=root)
    if _run(
        "git", "merge-base", "--is-ancestor", accepted, observed, cwd=root, check=False
    ).returncode:
        return {
            "schema": SCHEMA,
            "action": "stop",
            "reason": "upstream_rewritten",
            "accepted_commit": accepted,
            "observed_commit": observed,
        }
    protected = _run(
        "git",
        "diff",
        "--name-only",
        accepted,
        observed,
        "--",
        ".github",
        ".gitmodules",
        cwd=root,
    ).stdout.splitlines()
    if protected:
        return {
            "schema": SCHEMA,
            "action": "quarantine",
            "reason": "protected_paths_changed",
            "protected_paths": protected,
            "accepted_commit": accepted,
            "observed_commit": observed,
        }
    upstream_version = _version(
        _git_bytes(root, observed, ADDON_XML.as_posix())
    )
    downstream_version = _version((root / ADDON_XML).read_bytes())
    return {
        "schema": SCHEMA,
        "action": "prepare",
        "accepted_commit": accepted,
        "observed_commit": observed,
        "upstream_version": upstream_version,
        "downstream_version": _next_version(upstream_version, downstream_version),
    }


def _inventory(tree):
    files = {}
    total = 0
    for path in sorted(tree.rglob("*")):
        relative = path.relative_to(tree)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("candidate symlink is forbidden: %s" % relative)
        if not path.is_file():
            continue
        safe = PurePosixPath(relative.as_posix())
        if safe.is_absolute() or ".." in safe.parts:
            raise ValueError("unsafe candidate path")
        payload = path.read_bytes()
        total += len(payload)
        if len(files) >= MAX_FILES or total > MAX_BYTES:
            raise ValueError("candidate exceeds limits")
        files[safe.as_posix()] = {
            "sha256": _digest(payload),
            "size": len(payload),
            "executable": bool(path.stat().st_mode & 0o111),
        }
    return files


def _replace_version(path, version):
    payload = path.read_text(encoding="utf-8")
    updated, count = VERSION.subn(r"\g<1>%s\g<3>" % version, payload, count=1)
    if count != 1:
        raise ValueError("could not update downstream addon version")
    path.write_text(updated, encoding="utf-8")


def prepare(discovery, output, root=ROOT):
    current = discover(root)
    if current != discovery or discovery.get("action") != "prepare":
        raise ValueError("Umbrella discovery drifted or is not preparable")
    output = Path(output)
    if output.exists():
        raise ValueError("candidate output already exists")
    base = _run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="umbrella-update-") as temporary:
        tree = Path(temporary) / "tree"
        try:
            rebuild_downstream.reconstruct(tree, discovery["observed_commit"])
        except (RuntimeError, subprocess.CalledProcessError) as error:
            raise ValueError("downstream patch conflict: %s" % error) from error
        manifest = tree / MANIFEST
        payload = manifest.read_text(encoding="utf-8")
        payload, count = rebuild_downstream.BASE.subn(
            '  base: "%s"' % discovery["observed_commit"], payload, count=1
        )
        if count != 1:
            raise ValueError("could not update accepted upstream base")
        manifest.write_text(payload, encoding="utf-8")
        _replace_version(tree / ADDON_XML, discovery["downstream_version"])
        _run("python3", "-m", "pytest", "-q", cwd=tree)
        _run("git", "add", "-A", cwd=tree)
        expected_tree = _run("git", "write-tree", cwd=tree).stdout.strip()
        files = _inventory(tree)
        metadata = {
            "base_commit": base,
            "expected_tree": expected_tree,
            "accepted_commit": discovery["accepted_commit"],
            "upstream_commit": discovery["observed_commit"],
            "upstream_version": discovery["upstream_version"],
            "downstream_version": discovery["downstream_version"],
            "protected_paths": list(PROTECTED),
        }
        identity = {"schema": SCHEMA, "metadata": metadata, "files": files}
        document = {**identity, "candidate_id": _digest(identity)}
        (output / "tree").mkdir(parents=True)
        for relative, item in files.items():
            source = tree / relative
            target = output / "tree" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            os.chmod(target, 0o755 if item["executable"] else 0o644)
        (output / "candidate.json").write_bytes(_canonical(document))
    return document


def verify(bundle):
    bundle = Path(bundle).resolve()
    document = json.loads((bundle / "candidate.json").read_bytes())
    candidate_id = document.pop("candidate_id", None)
    if candidate_id != _digest(document):
        raise ValueError("candidate identity mismatch")
    document["candidate_id"] = candidate_id
    if document.get("schema") != SCHEMA:
        raise ValueError("unsupported candidate schema")
    if _inventory(bundle / "tree") != document["files"]:
        raise ValueError("candidate inventory mismatch")
    for protected in document["metadata"]["protected_paths"]:
        prefix = protected.rstrip("/") + "/"
        candidate_paths = {
            path
            for path in document["files"]
            if path == protected or path.startswith(prefix)
        }
        root_paths = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / protected).rglob("*")
            if path.is_file()
        } if (ROOT / protected).is_dir() else ({protected} if (ROOT / protected).is_file() else set())
        if candidate_paths != root_paths:
            raise ValueError("protected path inventory changed: %s" % protected)
        for path in candidate_paths:
            if (bundle / "tree" / path).read_bytes() != (ROOT / path).read_bytes():
                raise ValueError("protected path bytes changed: %s" % path)
    return document


def apply(bundle, checkout):
    document = verify(bundle)
    checkout = Path(checkout).resolve()
    if _run("git", "rev-parse", "HEAD", cwd=checkout).stdout.strip() != document[
        "metadata"
    ]["base_commit"]:
        raise ValueError("candidate base drift")
    protected = tuple(document["metadata"]["protected_paths"])
    for row in _run("git", "ls-files", cwd=checkout).stdout.splitlines():
        if row in protected or any(row.startswith(item + "/") for item in protected):
            continue
        if row not in document["files"]:
            (checkout / row).unlink(missing_ok=True)
    for relative, item in document["files"].items():
        destination = checkout / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(bundle) / "tree" / relative, destination)
        os.chmod(destination, 0o755 if item["executable"] else 0o644)
    return document


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    discover_parser = commands.add_parser("discover")
    discover_parser.add_argument("--output", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--discovery", required=True)
    prepare_parser.add_argument("--output", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--bundle", required=True)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--bundle", required=True)
    apply_parser.add_argument("--checkout", default=".")
    args = parser.parse_args()
    if args.command == "discover":
        result = discover()
        Path(args.output).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif args.command == "prepare":
        result = prepare(json.loads(Path(args.discovery).read_text()), args.output)
    elif args.command == "verify":
        result = verify(args.bundle)
    else:
        result = apply(args.bundle, args.checkout)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
