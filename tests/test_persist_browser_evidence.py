"""Positive and negative archive storage contract regressions."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

import sys
sys.path.insert(0,str(ROOT/"scripts"))
pack=load("package_browser_evidence","scripts/package_browser_evidence.py")
archive=load("persist_browser_evidence","scripts/persist_browser_evidence.py")
SHA="a"*40
def png(width,height):
    return b"\x89PNG\r\n\x1a\n"+b"\x00\x00\x00\x0dIHDR"+width.to_bytes(4,"big")+height.to_bytes(4,"big")+b"\x08\x02\x00\x00\x00"+b"\x00"*8

class PersistEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name)
        self.source=self.base/"input";self.source.mkdir()
        self.root=self.base/"persistent";self.root.mkdir()
        screens=[]
        for name in sorted(pack.NAMES):
            w,h=(390,844) if name.startswith("unauthorized") else tuple(map(int,name.rsplit("-",1)[1].split("x")))
            (self.source/(name+".png")).write_bytes(png(w,h))
            screens.append({"name":name,"viewport":{"width":w,"height":h},"source":"synthetic CI fixture"})
        (self.source/"manifest.json").write_text(json.dumps({"evidence_type":"INTEGRATION_TEST_NOT_USER_ACCEPTANCE","synthetic_data":True,"idp":"CI header-token bypass; not real OIDC browser login","production_ready":False,"source_sha":SHA,"screens":screens}))
    def test_persist_and_verify(self):
        dest=archive.persist(self.source,self.root,SHA)
        self.assertEqual(len(list(dest.iterdir())),15)
        self.assertEqual(pack.inspect(dest,SHA),pack.inspect(self.source,SHA) if False else {k:v for k,v in pack.inspect(self.source,SHA).items()})
    def test_existing_archive_never_overwritten(self):
        archive.persist(self.source,self.root,SHA)
        with self.assertRaises(FileExistsError):
            archive.persist(self.source,self.root,SHA)
    def test_wrong_sha_fails_without_output(self):
        with self.assertRaises(ValueError):
            archive.persist(self.source,self.root,"b"*40)
        self.assertFalse((self.root/SHA).exists())
    def test_missing_file_fails_closed(self):
        (self.source/"overview-1440x900.png").unlink()
        with self.assertRaises(ValueError):
            archive.persist(self.source,self.root,SHA)
    def test_nonexistent_storage_fails(self):
        with self.assertRaises(ValueError):
            archive.persist(self.source,self.root/"missing",SHA)
    def test_relative_storage_fails(self):
        with self.assertRaises(ValueError):
            archive.persist(self.source,Path("relative"),SHA)

if __name__=="__main__":
    unittest.main()
