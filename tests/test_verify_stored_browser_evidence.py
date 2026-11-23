"""Independent read-only archival checks; corruption must fail closed."""
import importlib.util
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import package_browser_evidence as pack
import persist_browser_evidence as store
import verify_stored_browser_evidence as verifier
SHA="a"*40

def png(w,h):
    return b"\x89PNG\r\n\x1a\n"+b"\x00\x00\x00\x0dIHDR"+w.to_bytes(4,"big")+h.to_bytes(4,"big")+b"\x08\x02\x00\x00\x00"+b"\x00"*8+b"\x00"*5000

class StoredEvidenceVerification(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.root=base/"archive"; self.root.mkdir()
        src=base/"source";src.mkdir()
        entries=[]
        for name in sorted(pack.NAMES):
            w,h=(390,844) if name=="unauthorized-390x844" else tuple(map(int,name.rsplit("-",1)[1].split("x")))
            (src/(name+".png")).write_bytes(png(w,h))
            entries.append({"name":name,"file":name+".png","viewport":{"width":w,"height":h},"actual_png":{"width":w,"height":h,"bytes":len(png(w,h)),"sha256":hashlib.sha256(png(w,h)).hexdigest()},"source":"synthetic CI fixture"})
        (src/"manifest.json").write_text(json.dumps({
            "evidence_type":"INTEGRATION_TEST_NOT_USER_ACCEPTANCE",
            "synthetic_data":True,
            "idp":"CI header-token bypass; not real OIDC browser login",
            "production_ready":False,
            "source_sha":SHA,
            "acceptance_status":"UNREVIEWED",
            "archival_status":"NOT_VERIFIED",
            "capture_integrity_verified":True,
            "expected_screen_count":13,
            "actual_screen_count":13,
            "screens":entries}))
        self.stored=store.persist(src,self.root,SHA)
    def test_archive_verified_readonly(self):
        before=(self.stored/"SHA256SUMS").read_bytes()
        self.assertEqual(len(verifier.verify(self.root,SHA)),14)
        self.assertEqual((self.stored/"SHA256SUMS").read_bytes(),before)
    def test_tampered_png_rejected(self):
        p=self.stored/"overview-1440x900.png"
        p.write_bytes(p.read_bytes()+b"tamper")
        with self.assertRaises(ValueError):verifier.verify(self.root,SHA)
    def test_missing_checksum_rejected(self):
        (self.stored/"SHA256SUMS").unlink()
        with self.assertRaises(ValueError):verifier.verify(self.root,SHA)
    def test_wrong_sha_rejected(self):
        with self.assertRaises(ValueError):verifier.verify(self.root,"b"*40)
    def test_unexpected_file_rejected(self):
        (self.stored/"extra.txt").write_text("unexpected")
        with self.assertRaises(ValueError):verifier.verify(self.root,SHA)
    def test_wrong_provenance_rejected(self):
        path=self.stored/"manifest.json"
        data=json.loads(path.read_text())
        data["production_ready"]=True
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):verifier.verify(self.root,SHA)
    def test_malformed_checksum_rejected(self):
        with (self.stored/"SHA256SUMS").open("a") as f:f.write("nonsense\n")
        with self.assertRaises(ValueError):verifier.verify(self.root,SHA)

if __name__=="__main__":
    unittest.main()
