"""Real PostgreSQL transactions for one-use OIDC state and auth-only session issuance."""
import os
from pathlib import Path
import secrets
import hashlib
import unittest
from uuid import uuid4
try:
 import psycopg
except ImportError:
 psycopg=None
DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(DSN and psycopg,"Requires disposable PostgreSQL + psycopg")
class OIDCFlowPostgresTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=psycopg.connect(DSN,autocommit=True)
  for n in range(1,5):
   pattern=f"000{n}_*.sql"
   for f in sorted((ROOT/"migrations").glob(pattern)):cls.db.execute(f.read_text())
  cls.tenant,cls.user=uuid4(),uuid4()
  cls.issuer="https://id.example"
  cls.subject=cls.user.hex
  cls.db.execute("INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,'OIDC Test')",(cls.tenant,'authflow-'+cls.tenant.hex[:10]))
  cls.db.execute("INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,%s,%s)",(cls.user,cls.issuer,cls.subject))
  cls.db.execute("INSERT INTO sme.memberships(tenant_id,identity_id,status) VALUES (%s,%s,'active')",(cls.tenant,cls.user))
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def as_role(self,role,sql,params=()):
  with self.db.transaction():
   self.db.execute(f"SET LOCAL ROLE {role}")
   return self.db.execute(sql,params).fetchall()
 def test_single_use_state(self):
  state,browser=hashlib.sha256(secrets.token_bytes(32)).digest(),hashlib.sha256(secrets.token_bytes(32)).digest()
  self.as_role('sme_auth',"SELECT sme.begin_oidc_login(%s,%s,%s,%s)",(state,browser,'v'*64,'n'*43))
  self.assertEqual(self.as_role('sme_auth',"SELECT * FROM sme.consume_oidc_login(%s,%s)",(state,b'0'*32)),[])
  self.assertEqual(self.as_role('sme_auth',"SELECT * FROM sme.consume_oidc_login(%s,%s)",(state,browser)),[('v'*64,'n'*43)])
  self.assertEqual(self.as_role('sme_auth',"SELECT * FROM sme.consume_oidc_login(%s,%s)",(state,browser)),[])
 def test_runtime_cannot_issue_session(self):
  with self.assertRaises(psycopg.errors.InsufficientPrivilege):
   self.as_role('sme_app',"SELECT sme.issue_oidc_session(%s,%s,%s,%s)",(self.issuer,self.subject,b'z'*32,3600))
 def test_auth_issues_only_known_active_identity(self):
  digest=hashlib.sha256(secrets.token_bytes(32)).digest()
  self.assertEqual(self.as_role('sme_auth',"SELECT sme.issue_oidc_session(%s,%s,%s,%s)",(self.issuer,self.subject,digest,3600)),[(True,)])
  self.assertEqual(self.as_role('sme_app',"SELECT sme.resolve_session(%s,%s)",(digest,self.tenant)),[(self.user,)])
  self.assertEqual(self.as_role('sme_auth',"SELECT sme.issue_oidc_session(%s,%s,%s,%s)",(self.issuer,'unknown',b'1'*32,3600)),[(False,)])
 def test_auth_role_cannot_read_raw_session(self):
  with self.assertRaises(psycopg.errors.InsufficientPrivilege):
   self.as_role('sme_auth',"SELECT token_digest FROM sme.sessions")
 def test_suspended_membership_prevents_issue(self):
  self.db.execute("UPDATE sme.memberships SET status='disabled' WHERE tenant_id=%s AND identity_id=%s",(self.tenant,self.user))
  try:
   self.assertEqual(self.as_role('sme_auth',"SELECT sme.issue_oidc_session(%s,%s,%s,%s)",(self.issuer,self.subject,b'2'*32,3600)),[(False,)])
  finally:
   self.db.execute("UPDATE sme.memberships SET status='active' WHERE tenant_id=%s AND identity_id=%s",(self.tenant,self.user))
