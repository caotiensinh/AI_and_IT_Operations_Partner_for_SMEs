#!/usr/bin/env python3
"""Fail-closed bounded audit of reachable Git history and all fetched branches.

Never print secret values, matched lines, or raw sensitive file contents.
This is a heuristic audit, not proof that a publicly exposed credential is safe.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_public_repo_safety import MAX_SCAN_BYTES, inspect, dangerous_path

SHA_RE = re.compile(r"^[a-f0-9]{40,64}$")
# Blob object names may be displayed for reproducibility; secret bytes never are.
BAD_OUTPUT = {"credential-looking token", "private key block",
              "restricted tracked filename", "non-placeholder sensitive example setting"}


class AuditError(RuntimeError):
    pass


def git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode:
        raise AuditError("Git inventory command failed: " + args[0])
    return proc.stdout


def inventories(root: Path) -> tuple[list[tuple[str, str]], set[str]]:
    refs = git(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes", "refs/tags")
    names = [x.decode("utf-8", "surrogateescape") for x in refs.splitlines() if x]
    if not names:
        raise AuditError("No local or remote Git refs were fetched")
    if not any(x.startswith("refs/remotes/origin/") or x == "refs/heads/main" for x in names):
        raise AuditError("No main/remote Git branch discovered")
    objects = git(root, "rev-list", "--objects", "--all")
    parsed = []
    for line in objects.splitlines():
        oid, _, path = line.partition(b" ")
        name = oid.decode("ascii")
        if not SHA_RE.fullmatch(name):
            raise AuditError("Invalid Git object identifier")
        parsed.append((name, path.decode("utf-8", "surrogateescape")))
    if not parsed:
        raise AuditError("No reachable Git objects")
    # Enumerate ALL path names in every reachable commit, not just the first
    # path associated with deduplicated objects by git rev-list --objects.
    history_names = git(root, "log", "--all", "--format=", "--name-only", "-z")
    paths = {part.decode("utf-8", "surrogateescape")
             for part in history_names.split(b"\x00") if part.strip()}
    return parsed, paths


def scan(root: Path) -> tuple[dict[str, list[str]], dict[str, int]]:
    objects, historical_paths = inventories(root)
    findings: dict[str, list[str]] = {}
    for path in historical_paths:
        if dangerous_path(path):
            findings[f"path:{path}"] = ["restricted historical filename"]
    # Use one streaming batch process; avoid one subprocess per blob.
    cmd = ["git", "-C", str(root), "cat-file", "--batch"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None and proc.stdout is not None
    blobs = 0
    oversized = 0
    try:
        for oid, known_path in objects:
            proc.stdin.write((oid + "\n").encode("ascii"))
            proc.stdin.flush()
            header = proc.stdout.readline()
            parts = header.strip().split()
            if len(parts) != 3 or parts[0].decode("ascii") != oid:
                raise AuditError("Malformed Git batch object reply")
            kind = parts[1]
            size = int(parts[2])
            if size < 0 or size > 1_000_000_000:
                raise AuditError("Unreasonable Git object size")
            if size > MAX_SCAN_BYTES:
                # Larger blobs are not silently declared clean.
                # Stream and discard in bounded chunks.
                left = size
                while left:
                    chunk = proc.stdout.read(min(left, 65536))
                    if not chunk:
                        raise AuditError("Unexpected end of Git object stream")
                    left -= len(chunk)
                oversized += int(kind == b"blob")
                data = b""
            else:
                data = proc.stdout.read(size)
                if len(data) != size:
                    raise AuditError("Truncated Git object stream")
            if proc.stdout.read(1) != b"\n":
                raise AuditError("Git object framing error")
            if kind != b"blob":
                continue
            blobs += 1
            if size > MAX_SCAN_BYTES:
                # Conservative: cannot certify this blob with current detector.
                findings["blob:" + oid] = ["oversized blob not audited"]
                continue
            issues = inspect(known_path or "historical-blob", data)
            if issues:
                # Print only immutable object identifiers, not secret snippets.
                findings["blob:" + oid] = issues
    finally:
        proc.stdin.close()
        proc.stdout.close()
        code = proc.wait(timeout=30)
        if code != 0:
            raise AuditError("Git cat-file failed")
    return findings, {"refs_reachable_objects": len(objects),
                      "history_paths": len(historical_paths),
                      "blobs": blobs, "oversized": oversized}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        findings, stats = scan(args.root.resolve())
    except (AuditError, OSError, subprocess.TimeoutExpired, UnicodeError, ValueError) as exc:
        print("HISTORY_AUDIT=ERROR: " + type(exc).__name__, file=sys.stderr)
        return 2
    for key, issues in sorted(findings.items()):
        print("REVIEW_REQUIRED: " + key + ": " + ", ".join(issues), file=sys.stderr)
    print(f"HISTORY_AUDIT={'FAIL' if findings else 'PASS'}: "
          f"objects={stats['refs_reachable_objects']}, paths={stats['history_paths']}, "
          f"blobs={stats['blobs']}, oversized={stats['oversized']}, "
          f"findings={len(findings)}")
    print("LIMITATION: scans reachable refs fetched to checkout; no forks, deleted refs, GitHub comments, Actions secrets, or exposed-token validity")
    if findings:
        print("Rotate/revoke any truly exposed credential; deleting Git history alone is insufficient.", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
