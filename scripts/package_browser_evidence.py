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
    """Require the canonical Spec 027 capture contract before packaging."""
    from validate_browser_evidence import validate
    validate(directory, expected_sha)
    root = directory.resolve(strict=True)
    checksums = {}
    for name in sorted(NAMES):
        path = root / (name + ".png")
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    checksums["manifest.json"] = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
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
