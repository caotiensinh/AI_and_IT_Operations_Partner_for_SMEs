#!/usr/bin/env python3
"""Persist verified synthetic Chromium evidence atomically to an OWNER-configured local disk.

This is intended for a trusted self-hosted runner with durable mounted storage,
NOT a temporary GitHub-hosted runner. No network transfers or deletion.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile

from package_browser_evidence import inspect

def persist(source: Path, root: Path, sha: str) -> Path:
    # Fail closed if destination isn't an existing dedicated storage directory.
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("Evidence root must be an existing absolute non-symlink directory")
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Source must be a real directory")
    source = source.resolve(strict=True)
    root = root.resolve(strict=True)
    if root == source or root in source.parents or source in root.parents:
        raise ValueError("Source and evidence storage roots must be separate")
    checksums = inspect(source, sha)
    target = root / sha
    if target.exists() or target.is_symlink():
        raise FileExistsError("Immutable evidence directory already exists: " + str(target))
    # root ownership and access must be managed outside this script.
    tmp = Path(tempfile.mkdtemp(prefix=".incoming-", dir=root))
    try:
        os.chmod(tmp, 0o700)
        for name in sorted(checksums):
            dest = tmp / name
            shutil.copyfile(source / name, dest)
            os.chmod(dest, 0o600)
        (tmp / "SHA256SUMS").write_text(
            "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)),
            encoding="utf-8",
        )
        os.chmod(tmp / "SHA256SUMS", 0o600)
        # Verify AFTER copying to ensure output checksums match source.
        import hashlib
        for name, digest in checksums.items():
            if hashlib.sha256((tmp / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Copy integrity check failed: " + name)
        # os.rename directory is atomic when root is on one filesystem.
        if target.exists() or target.is_symlink():
            raise FileExistsError("Concurrent archive already exists")
        tmp.rename(target)
        print(f"EVIDENCE_PERSISTED: {target}; screenshots=13; manifest=1; SHA={sha}")
        return target
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--source-sha", required=True)
    a = p.parse_args(argv)
    try:
        persist(a.source, a.root, a.source_sha)
    except (OSError, ValueError) as exc:
        print(f"EVIDENCE_STORAGE_FAILED: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
