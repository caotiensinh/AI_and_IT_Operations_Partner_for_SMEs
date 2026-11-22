#!/usr/bin/env python3
"""Read-only verifier for archived Chromium evidence, no deletion or mutation."""
import argparse
import hashlib
import sys
from pathlib import Path
from package_browser_evidence import inspect, SHA_RE

def verify(root: Path, sha: str) -> dict[str, str]:
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise ValueError("SHA must be full 40-character lowercase git SHA")
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("Storage root must be an existing absolute non-symlink directory")
    archive = root / sha
    if archive.is_symlink() or not archive.is_dir():
        raise ValueError("No non-symlink archive for the requested commit")
    checks_file = archive / "SHA256SUMS"
    if checks_file.is_symlink() or not checks_file.is_file():
        raise ValueError("Missing or unsafe SHA256SUMS")
    expected = inspect_payload(archive, sha)
    lines = checks_file.read_text(encoding="utf-8").splitlines()
    recorded = {}
    for line in lines:
        if "  " not in line:
            raise ValueError("Invalid checksum line")
        digest, name = line.split("  ", 1)
        if name in recorded or name not in expected or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Duplicate, unexpected, or invalid checksum entry")
        recorded[name] = digest
    if set(recorded) != set(expected) or recorded != expected:
        raise ValueError("Missing or mismatched SHA256 evidence")
    print(f"ARCHIVE_VERIFIED: sha={sha}; png=13; files={len(expected)}")
    return recorded

def inspect_payload(archive: Path, sha: str) -> dict[str, str]:
    """Verify the exact Spec 027 metadata and PNG integrity without modifying storage."""
    import json
    import struct
    from package_browser_evidence import NAMES
    names = {name + ".png" for name in NAMES} | {"manifest.json"}
    if {p.name for p in archive.iterdir()} != names | {"SHA256SUMS"}:
        raise ValueError("Unexpected or missing stored evidence file")
    manifest_path = archive / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Symlinked manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("source_sha") != sha
        or manifest.get("evidence_type") != "INTEGRATION_TEST_NOT_USER_ACCEPTANCE"
        or manifest.get("synthetic_data") is not True
        or manifest.get("production_ready") is not False
        or manifest.get("acceptance_status") != "UNREVIEWED"
        or manifest.get("archival_status") != "NOT_VERIFIED"
        or manifest.get("capture_integrity_verified") is not True
        or manifest.get("expected_screen_count") != 13
        or manifest.get("actual_screen_count") != 13
        or "CI header-token bypass" not in str(manifest.get("idp"))):
        raise ValueError("Invalid archive provenance")
    entries = manifest.get("screens")
    if not isinstance(entries, list) or len(entries) != 13:
        raise ValueError("Invalid screenshot manifest")
    results = {}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name","file","viewport","actual_png","source"}:
            raise ValueError("Invalid screenshot entry")
        name = entry["name"]
        if name not in NAMES or name in seen or entry["file"] != name + ".png":
            raise ValueError("Missing/duplicate screenshots")
        seen.add(name)
        width,height = (390,844) if name == "unauthorized-390x844" else tuple(map(int,name.rsplit("-",1)[1].split("x")))
        if entry["viewport"] != {"width":width,"height":height} or "synthetic CI fixture" not in str(entry["source"]):
            raise ValueError("Screenshot viewport or provenance mismatch")
        path = archive / (name + ".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Invalid screenshot file")
        data = path.read_bytes()
        if len(data) < 5000 or len(data) > 12*1024*1024 or data[:8] != b"\\x89PNG\\r\\n\\x1a\\n" or data[12:16] != b"IHDR":
            raise ValueError("Invalid PNG content")
        real_width,real_height=struct.unpack(">II",data[16:24])
        checksum=hashlib.sha256(data).hexdigest()
        expected = {"width":width,"height":height,"bytes":len(data),"sha256":checksum}
        if (real_width,real_height) != (width,height) or entry["actual_png"] != expected:
            raise ValueError("PNG dimensions or SHA256 mismatch")
        results[path.name]=checksum
    results["manifest.json"]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return results

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--source-sha",required=True)
    args=p.parse_args(argv)
    try:
        verify(args.root,args.source_sha)
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(f"ARCHIVE_INVALID: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
