"""Evidence package structural, negative and boundary regressions."""
import importlib.util
import json
import sys
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("package_browser_evidence",ROOT/"scripts/package_browser_evidence.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA="a"*40
# Minimal valid PNG signature/IHDR dimensions for structural checks; not a rendered screenshot.
def png(width,height):
    return b"\x89PNG\r\n\x1a\n"+b"\x00\x00\x00\x0dIHDR"+width.to_bytes(4,"big")+height.to_bytes(4,"big")+b"\x08\x02\x00\x00\x00"+b"\x00"*8+b"\x00"*5000

class BrowserEvidencePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.entries=[]
        for name in sorted(module.NAMES):
            width,height=(390,844) if name.startswith("unauthorized") else tuple(map(int,name.rsplit("-",1)[1].split("x")))
            (self.root/(name+".png")).write_bytes(png(width,height))
            self.entries.append({"name":name,"file":name+".png","viewport":{"width":width,"height":height},"actual_png":{"width":width,"height":height,"bytes":len(png(width,height)),"sha256":hashlib.sha256(png(width,height)).hexdigest()},"source":"synthetic CI fixture"})
        self.manifest={"evidence_type":"INTEGRATION_TEST_NOT_USER_ACCEPTANCE","synthetic_data":True,"idp":"CI header-token bypass; not real OIDC browser login","production_ready":False,"source_sha":SHA,"acceptance_status":"UNREVIEWED","archival_status":"NOT_VERIFIED","capture_integrity_verified":True,"expected_screen_count":13,"actual_screen_count":13,"screens":self.entries}
        self.save()
    def save(self):
        (self.root/"manifest.json").write_text(json.dumps(self.manifest))
    def test_complete_package(self):
        dest=self.root.parent/"evidence-validation-test.zip"
        try:
            hashes=module.package(self.root,dest,SHA)
            self.assertEqual(len(hashes),14)
            with zipfile.ZipFile(dest) as z:
                self.assertEqual(len(z.namelist()),15)
                self.assertIn("sha256sums.json",z.namelist())
        finally:
            dest.unlink(missing_ok=True)
    def test_missing_png(self):
        (self.root/(self.entries[0]["name"]+".png")).unlink()
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)
    def test_duplicate_entry(self):
        self.entries[1]["name"]=self.entries[0]["name"]
        self.save()
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)
    def test_mismatched_sha(self):
        with self.assertRaises(ValueError): module.inspect(self.root,"b"*40)
    def test_forged_production(self):
        self.manifest["production_ready"]=True
        self.save()
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)
    def test_wrong_image_width(self):
        (self.root/(self.entries[0]["name"]+".png")).write_bytes(png(1,844))
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)
    def test_invalid_png(self):
        (self.root/(self.entries[0]["name"]+".png")).write_bytes(b"this is not a PNG"*3)
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)
    def test_unexpected_file(self):
        (self.root/"extra.txt").write_text("extra")
        with self.assertRaises(ValueError): module.inspect(self.root,SHA)

if __name__=="__main__":
    unittest.main()
