#!/usr/bin/env python3
"""Verify screenshot files against Chromium manifest; NOT an archival or user-acceptance gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

VIEWPORTS = ((1440, 900), (820, 1180), (390, 844), (320, 640))
EXPECTED = {
    f"{screen}-{w}x{h}": (w, h)
    for screen in ("overview", "assets", "monitoring")
    for w, h in VIEWPORTS
}
EXPECTED["unauthorized-390x844"] = (390, 844)
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def validate(directory: Path, expected_sha: str) -> dict:
    if not SHA.fullmatch(expected_sha):
        raise ValueError("expected Git SHA must be exactly 40 lowercase hex characters")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if (
        manifest.get("evidence_type") != "INTEGRATION_TEST_NOT_USER_ACCEPTANCE"
        or manifest.get("synthetic_data") is not True
        or manifest.get("production_ready") is not False
        or manifest.get("acceptance_status") != "UNREVIEWED"
        or manifest.get("archival_status") != "NOT_VERIFIED"
        or manifest.get("capture_integrity_verified") is not True
        or manifest.get("source_sha") != expected_sha
        or manifest.get("expected_screen_count") != 13
        or manifest.get("actual_screen_count") != 13
    ):
        raise ValueError("manifest provenance, classification or commit mismatch")
    images = manifest.get("screens")
    if not isinstance(images, list) or len(images) != 13:
        raise ValueError("exactly 13 screenshots required")
    discovered = {}
    for entry in images:
        if not isinstance(entry, dict):
            raise ValueError("invalid screenshot entry")
        name = entry.get("name")
        if name not in EXPECTED or name in discovered:
            raise ValueError("unknown or duplicated screenshot")
        width, height = EXPECTED[name]
        if entry.get("file") != name + ".png" or entry.get("viewport") != {"width": width, "height": height}:
            raise ValueError("screenshot filename/viewport mismatch")
        # Do not allow traversal or unexpected contents, including symlinks.
        path = directory / (name + ".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or linked screenshot")
        raw = path.read_bytes()
        if len(raw) < 5000 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            raise ValueError("screenshot missing, truncated or not PNG")
        real_width, real_height = struct.unpack(">II", raw[16:24])
        data = entry.get("actual_png")
        if not isinstance(data, dict) or set(data) != {"width", "height", "bytes", "sha256"}:
            raise ValueError("missing integrity evidence")
        if (
            (real_width, real_height) != (width, height)
            or (data["width"], data["height"]) != (width, height)
            or type(data["bytes"]) is not int or data["bytes"] != len(raw)
            or not isinstance(data["sha256"], str)
            or not DIGEST.fullmatch(data["sha256"])
            or hashlib.sha256(raw).hexdigest() != data["sha256"]
        ):
            raise ValueError("screenshot size, dimensions or SHA256 mismatch")
        discovered[name] = data["sha256"]
    if set(discovered) != set(EXPECTED):
        raise ValueError("incomplete screenshot coverage")
    # Unexpected source files can hide stale screenshots or an unreviewed capture.
    actual_files = {p.name for p in directory.iterdir()}
    if actual_files != {name + ".png" for name in EXPECTED} | {"manifest.json"}:
        raise ValueError("evidence directory has unexpected entries")
    return {"commit": expected_sha, "screens": len(discovered), "integrity": "PASS",
            "archive": "NOT_VERIFIED", "human_acceptance": "PENDING"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = validate(args.directory, args.sha)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"CAPTURE_INTEGRITY=FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    print("CAPTURE_INTEGRITY=PASS; EVIDENCE_ARCHIVE=NOT_VERIFIED; UI_ACCEPTANCE=PENDING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
