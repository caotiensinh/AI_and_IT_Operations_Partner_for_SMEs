"""Positive/negative/boundary regressions for public tracked-file scanner."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("public_safety",ROOT/"scripts/check_public_repo_safety.py")
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicSafetyTests(unittest.TestCase):
    def test_repository_staging_example_is_placeholder_only(self):
        data=(ROOT/".env.staging.example").read_bytes()
        self.assertEqual(guard.inspect(".env.staging.example",data),[])

    def test_rejects_private_key_and_embedded_token(self):
        self.assertIn("private key block",guard.inspect(
            "docs/example.txt",b"-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"))
        self.assertIn("credential-looking token",guard.inspect(
            "README.md",b"token = ghp_" + b"a"*36))

    def test_never_allows_credentials_under_safe_env_example(self):
        self.assertEqual(guard.inspect(".env.staging.example",
            b"SME_DB_ADMIN_PASSWORD=REPLACE_WITH_SECRET\n"),[])
        issues=guard.inspect(".env.staging.example",
            b"SME_DB_ADMIN_PASSWORD=nonplaceholder-value\n")
        self.assertIn("non-placeholder sensitive example setting",issues)

    def test_rejects_sensitive_filenames(self):
        for name in (".env",".env.production","prod.pem","tls.key",
                     ".ssh/id_rsa","config/credentials.json","backup.sqlitedb"):
            with self.subTest(name=name):
                if name=="backup.sqlitedb":
                    self.assertEqual(guard.inspect(name,b"x"),[])
                else:
                    self.assertIn("restricted tracked filename",guard.inspect(name,b"x"))

    def test_tracked_symlinks_and_oversized_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"large.txt").write_bytes(b"x"*(guard.MAX_SCAN_BYTES+1))
            (root/"target.txt").write_bytes(b"dummy")
            (root/"link.txt").symlink_to(root/"target.txt")
            result=guard.checked_files(root,["large.txt","link.txt","target.txt","../outside"])
            self.assertEqual(set(result),{"large.txt","link.txt","../outside"})

    def test_clean_and_forbidden_files_in_real_git_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(["git","init","-q",str(root)],check=True)
            (root/"good.txt").write_text("public")
            subprocess.run(["git","-C",str(root),"add","good.txt"],check=True)
            self.assertEqual(guard.run(root),0)
            (root/".env").write_text("DB_PASSWORD=somevalue")
            subprocess.run(["git","-C",str(root),"add",".env"],check=True)
            self.assertEqual(guard.run(root),1)

    def test_no_git_repository_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(guard.run(Path(d)),2)


if __name__=="__main__":
    unittest.main()
