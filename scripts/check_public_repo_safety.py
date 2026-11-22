#!/usr/bin/env python3
"""Public repository tracked-file guard (not a historical credential audit)."""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_SCAN_BYTES = 1_000_000
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")
TOKEN_MARKERS = (
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
DANGEROUS_SUFFIXES = (".pem",".p12",".pfx",".jks",".keystore",".key",".sqlite",".sqlite3",".db",".dump",".pgdump",".bak")
DANGEROUS_BASENAMES = ("id_rsa","id_ed25519","credentials.json","service-account.json","kubeconfig",".npmrc",".pypirc",".netrc")
SAFE_EXAMPLES = {".env.staging.example"}
SENSITIVE_ASSIGN = re.compile(
    rb"(?im)^\s*(?:SME_\w*(?:PASSWORD|SECRET|TOKEN|KEY)|"
    rb"(?:DATABASE_URL|POSTGRES_PASSWORD|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|"
    rb"OPENAI_API_KEY))\s*=\s*(.+?)\s*$"
)

def dangerous_path(name: str) -> bool:
    path = PurePosixPath(name)
    base = path.name.lower()
    if base in SAFE_EXAMPLES:
        return False
    if base in DANGEROUS_BASENAMES or base.endswith(DANGEROUS_SUFFIXES):
        return True
    if base == ".env" or base.startswith(".env.") or base == "env.local":
        return True
    if any(part in ("private-keys","credentials-private",".ssh") for part in path.parts):
        return True
    return False

def is_documented_placeholder(value: bytes) -> bool:
    v = value.strip().strip(b"'\"")
    return (
        not v
        or v.startswith((b"REPLACE_",b"EXAMPLE_",b"CHANGE_ME",b"$"+b"{",b"$("))
        or v in (b"placeholder",b"not-set",b"dummy",b"example",b"<redacted>")
    )

def inspect(name: str, data: bytes) -> list[str]:
    findings=[]
    if dangerous_path(name):
        findings.append("restricted tracked filename")
    if b"\x00" in data[:2048]:
        return findings
    if PRIVATE_KEY.search(data):
        findings.append("private key block")
    for marker in TOKEN_MARKERS:
        if marker.search(data):
            findings.append("credential-looking token")
            break
    if PurePosixPath(name).name in SAFE_EXAMPLES:
        for match in SENSITIVE_ASSIGN.finditer(data):
            if not is_documented_placeholder(match.group(1)):
                findings.append("non-placeholder sensitive example setting")
                break
    return findings

def checked_files(root: Path, names: list[str]) -> dict[str,list[str]]:
    results={}
    for name in names:
        p=PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts:
            results[name]=["invalid tracked path"]
            continue
        path=root.joinpath(*p.parts)
        if path.is_symlink():
            results[name]=["tracked symlink not inspected"]
            continue
        if not path.is_file():
            results[name]=["tracked file unavailable"]
            continue
        if path.stat().st_size>MAX_SCAN_BYTES:
            results[name]=["file exceeds scanner limit; manual review required"]
            continue
        issues=inspect(name,path.read_bytes())
        if issues:
            results[name]=issues
    return results

def run(root: Path) -> int:
    proc=subprocess.run(["git","-C",str(root),"ls-files","-z"],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if proc.returncode != 0:
        print("PUBLIC_SAFETY=ERROR: cannot inventory tracked files",file=sys.stderr)
        return 2
    names=[part.decode("utf-8",errors="surrogateescape")
           for part in proc.stdout.split(b"\x00") if part]
    if not names:
        print("PUBLIC_SAFETY=ERROR: no tracked files found",file=sys.stderr)
        return 2
    findings=checked_files(root,names)
    if findings:
        for name,issues in sorted(findings.items()):
            print(f"REVIEW_REQUIRED: {name}: {', '.join(issues)}",file=sys.stderr)
        print(f"PUBLIC_SAFETY=FAIL: {len(findings)} tracked files require review",file=sys.stderr)
        return 1
    print(f"PUBLIC_SAFETY=PASS: checked {len(names)} tracked files on current checkout")
    print("LIMITATION: no Git history, fork, PR comment or runtime secret scan")
    return 0

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args(argv)
    return run(args.root.resolve())

if __name__=="__main__":
    sys.exit(main())
