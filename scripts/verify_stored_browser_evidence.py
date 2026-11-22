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
    # The base inspector deliberately disallows extraneous files.
    # Verify SHA256SUMS separately without trusting its contents.
    from package_browser_evidence import NAMES
    names = {name + ".png" for name in NAMES} | {"manifest.json"}
    if {p.name for p in archive.iterdir()} != names | {"SHA256SUMS"}:
        raise ValueError("Unexpected or missing stored evidence file")
    import json
    manifest_path = archive / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Symlinked manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_sha") != sha:
        raise ValueError("Evidence bound to wrong source SHA")
    temp = {}
    if not isinstance(manifest.get("screens"),list) or len(manifest["screens"]) != len(NAMES):
        raise ValueError("Invalid screenshot manifest")
    seen=set()
    for item in manifest["screens"]:
        if not isinstance(item,dict) or set(item)!={"name","viewport","source"} or item["name"] not in NAMES or item["name"] in seen:
            raise ValueError("Missing/duplicate screenshots")
        seen.add(item["name"])
        width,height = (390,844) if item["name"]=="unauthorized-390x844" else tuple(map(int,item["name"].rsplit("-",1)[1].split("x")))
        if item["viewport"] != {"width":width,"height":height} or "synthetic CI fixture" not in str(item["source"]):
            raise ValueError("Screenshot viewport or provenance mismatch")
        path=archive/(item["name"]+".png")
        if path.is_symlink() or not path.is_file() or not 24 <= path.stat().st_size <= 12*1024*1024:
            raise ValueError("Invalid screenshot file")
        with path.open("rb") as f:
            header=f.read(24)
        if not header.startswith(b"\x89PNG\r\n\x1a\n") or int.from_bytes(header[16:20],"big")!=width:
            raise ValueError("PNG header/width mismatch")
        temp[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    if (manifest.get("evidence_type")!="INTEGRATION_TEST_NOT_USER_ACCEPTANCE"
        or manifest.get("synthetic_data") is not True
        or manifest.get("production_ready") is not False
        or "CI header-token bypass" not in str(manifest.get("idp"))):
        raise ValueError("Invalid archive provenance")
    temp["manifest.json"]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return temp

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
