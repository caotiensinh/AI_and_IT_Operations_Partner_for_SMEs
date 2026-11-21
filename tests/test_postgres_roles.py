"""Tests tenant-scoped RBAC tables with real PostgreSQL 16 in disposable CI DB."""
import os
from pathlib import Path
import unittest
from uuid import uuid4
try:
 import psycopg
except ImportError:
 psycopg=None

DSN=os.getenv("SME_TEST_DATABASE_DSN")
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(DSN and psycopg, "Requires PostgreSQL and psycopg")
class PostgresRolesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=psycopg.connect(DSN,autocommit=True)
  # Other test class may have installed migration 0001 first: migrations use IF NOT EXISTS.
  cls.db.execute((ROOT/"migrations/0001_tenant_foundation.sql").read_text())
  cls.db.execute((ROOT/"migrations/0002_scoped_rbac.sql").read_text())
  cls.tenant,cls.other,cls.user,cls.site,cls.dept=[uuid4() for _ in range(5)]
  with cls.db.transaction():
   cls.db.execute("INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,%s),(%s,%s,%s)",(cls.tenant,"auth-"+cls.tenant.hex[:12],"Authorization",cls.other,"auth-"+cls.other.hex[:12],"Other"))
   cls.db.execute("INSERT INTO sme.identities(id,issuer,subject) VALUES (%s,%s,%s)",(cls.user,"https://issuer.example",cls.user.hex))
   cls.db.execute("INSERT INTO sme.memberships(tenant_id,identity_id,status) VALUES (%s,%s,'active')",(cls.tenant,cls.user))
   cls.db.execute("INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,'Site')",(cls.tenant,cls.site))
   cls.db.execute("INSERT INTO sme.departments(tenant_id,id,site_id,label) VALUES (%s,%s,%s,'Department')",(cls.tenant,cls.dept,cls.site))
   cls.db.execute("INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'owner','tenant')",(cls.tenant,uuid4(),cls.user))
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def app_query(self,tenant,sql,params=()):
  with self.db.transaction():
   self.db.execute("SET LOCAL ROLE sme_app")
   if tenant is not None:self.db.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(tenant),))
   return self.db.execute(sql,params).fetchall()
 def test_own_role_visible(self):
  self.assertEqual(self.app_query(self.tenant,"SELECT role FROM sme.role_assignments"),[('owner',)])
 def test_other_tenant_role_invisible(self):
  self.assertEqual(self.app_query(self.other,"SELECT role FROM sme.role_assignments"),[])
 def test_no_tenant_context_role_invisible(self):
  self.assertEqual(self.app_query(None,"SELECT role FROM sme.role_assignments"),[])
 def test_runtime_cannot_self_promote(self):
  with self.assertRaises(psycopg.errors.InsufficientPrivilege):
   self.app_query(self.tenant,"INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'owner','tenant') RETURNING role",(self.tenant,uuid4(),self.user))
 def test_cross_tenant_membership_fk_denies(self):
  with self.assertRaises(psycopg.errors.ForeignKeyViolation):
   with self.db.transaction():
    self.db.execute("INSERT INTO sme.role_assignments(tenant_id,id,identity_id,role,scope_type) VALUES (%s,%s,%s,'manager','tenant')",(self.other,uuid4(),self.user))
 def test_cross_tenant_department_parent_denied(self):
  with self.assertRaises(psycopg.errors.ForeignKeyViolation):
   with self.db.transaction():
    self.db.execute("INSERT INTO sme.departments(tenant_id,id,site_id,parent_id,label) VALUES (%s,%s,%s,%s,'Bad')",(self.other,uuid4(),self.site,self.dept))
