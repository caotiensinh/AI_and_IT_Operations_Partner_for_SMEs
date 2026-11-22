#!/usr/bin/env python3
"""Validate and package synthetic Chromium screenshot evidence, without uploading it."""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

VIEWPORTS = ((1440,900),(820,1180),(390,844),(320,640))
NAMES = {f"{screen}-{width}x{height}" for screen in ("overview","assets","monitoring") for width,height in VIEWPORTS}
NAMES.add("unauthorized-390x844")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 12 * 1024 * 1024

def inspect(directory: Path, expected_sha: str):
    if not SHA_RE.fullmatch(expected_sha):
        raise ValueError("Expected source SHA must be exactly 40 lowercase hex characters")
    root = directory.resolve(strict=True)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Symlink manifest forbidden")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest,dict) or set(manifest) != {"evidence_type","synthetic_data","idp","production_ready","source_sha","screens"}:
        raise ValueError("Unexpected manifest schema")
    if (manifest["evidence_type"] != "INTEGRATION_TEST_NOT_USER_ACCEPTANCE"
        or manifest["synthetic_data"] is not True or manifest["production_ready"] is not False
        or manifest["source_sha"] != expected_sha or not isinstance(manifest["idp"],str)
        or "CI header-token bypass" not in manifest["idp"]):
        raise ValueError("Untrusted manifest provenance")
    screens = manifest["screens"]
    if not isinstance(screens,list) or len(screens) != len(NAMES):
        raise ValueError("Expected exactly 13 screenshot entries")
    actual = set()
    checksums = {}
    for entry in screens:
        if not isinstance(entry,dict) or set(entry) != {"name","viewport","source"}:
            raise ValueError("Unexpected screenshot entry")
        name = entry["name"]
        if not isinstance(name,str) or name not in NAMES or name in actual:
            raise ValueError("Unknown or duplicate screenshot name")
        actual.add(name)
        size = entry["viewport"]
        if not isinstance(size,dict) or set(size) != {"width","height"}:
            raise ValueError("Invalid viewport")
        expected = (390,844) if name=="unauthorized-390x844" else tuple(map(int,name.rsplit("-",1)[1].split("x")))
        if type(size["width"]) is not int or type(size["height"]) is not int or (size["width"],size["height"]) != expected:
            raise ValueError("Viewport mismatch")
        if not isinstance(entry["source"],str) or "synthetic CI fixture" not in entry["source"]:
            raise ValueError("Screenshot provenance required")
        path = root / (name+".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked screenshot: "+name)
        if not 24 <= path.stat().st_size <= MAX_PNG_BYTES:
            raise ValueError("Implausible screenshot size: "+name)
        with path.open("rb") as stream:
            header=stream.read(24)
        if not header.startswith(PNG_HEADER):
            raise ValueError("Invalid PNG signature: "+name)
        actual_width=int.from_bytes(header[16:20],"big")
        if actual_width != expected[0]:
            raise ValueError("PNG image width differs from viewport: "+name)
        checksums[name+".png"]=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != NAMES:
        raise ValueError("Incomplete screenshot set")
    found = {p.name for p in root.iterdir()}
    if found != set(checksums)|{"manifest.json"}:
        raise ValueError("Unexpected files in evidence folder")
    checksums["manifest.json"]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return checksums

def package(directory: Path, output: Path, expected_sha: str):
    checksums = inspect(directory,expected_sha)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(checksums):
            archive.write(directory/name,arcname=name)
        archive.writestr("sha256sums.json",json.dumps(checksums,sort_keys=True,indent=2)+"\n")
    print(f"Verified {len(checksums)-1} real Chromium PNGs, manifest SHA={expected_sha}; ZIP={output}")
    return checksums

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--source-sha",required=True)
    args=parser.parse_args()
    try:
        package(args.directory,args.output,args.source_sha)
    except (OSError,ValueError,json.JSONDecodeError,zipfile.BadZipFile) as error:
        print(f"EVIDENCE_INVALID: {error}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
