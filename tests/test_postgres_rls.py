"""Requires disposable PostgreSQL and SME_TEST_DATABASE_DSN; never run on prod."""
import os
from pathlib import Path
import unittest
from uuid import uuid4
try:
 import psycopg
except ImportError:
 psycopg = None
DSN=os.getenv('SME_TEST_DATABASE_DSN')
SQL=(Path(__file__).resolve().parents[1]/'migrations'/'0001_tenant_foundation.sql').read_text()

@unittest.skipUnless(DSN and psycopg, 'Requires disposable PostgreSQL DSN and psycopg')
class PostgresRLSTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=psycopg.connect(DSN,autocommit=True)
  cls.db.execute(SQL)
  cls.a,cls.b,cls.sa,cls.sb,cls.asset_a,cls.asset_b=[uuid4() for _ in range(6)]
  with cls.db.transaction():
   cls.db.execute('INSERT INTO sme.tenants(id,slug,display_name) VALUES (%s,%s,%s),(%s,%s,%s)',(cls.a,'tenant-a-'+cls.a.hex[:8],'Tenant A',cls.b,'tenant-b-'+cls.b.hex[:8],'Tenant B'))
   cls.db.execute('INSERT INTO sme.sites(tenant_id,id,label) VALUES (%s,%s,%s),(%s,%s,%s)',(cls.a,cls.sa,'Site A',cls.b,cls.sb,'Site B'))
   cls.db.execute('INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,%s),(%s,%s,%s,%s)',(cls.a,cls.asset_a,cls.sa,'Asset A',cls.b,cls.asset_b,cls.sb,'Asset B'))
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def query_as_app(self,tenant=None,statement='SELECT name FROM sme.assets ORDER BY name',params=()):
  with self.db.transaction():
   self.db.execute('SET LOCAL ROLE sme_app')
   if tenant is not None:self.db.execute("SELECT set_config('sme.tenant_id',%s,true)",(str(tenant),))
   return self.db.execute(statement,params).fetchall()
 def test_missing_context_denies(self):self.assertEqual(self.query_as_app(),[])
 def test_each_tenant_only_sees_own(self):
  self.assertEqual(self.query_as_app(self.a),[('Asset A',)])
  self.assertEqual(self.query_as_app(self.b),[('Asset B',)])
 def test_no_context_leak_between_transactions(self):
  self.assertEqual(self.query_as_app(self.a),[('Asset A',)])
  self.assertEqual(self.query_as_app(),[])
 def test_direct_other_tenant_id_not_visible(self):
  self.assertEqual(self.query_as_app(self.a,'SELECT name FROM sme.assets WHERE id=%s',(self.asset_b,)),[])
 def test_cross_tenant_write_denied(self):
  with self.assertRaises(psycopg.errors.InsufficientPrivilege):
   self.query_as_app(self.a,'INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,%s) RETURNING name',(self.b,uuid4(),self.sb,'Injected'))
 def test_cross_tenant_site_fk_denied(self):
  with self.assertRaises(psycopg.errors.ForeignKeyViolation):
   self.query_as_app(self.a,'INSERT INTO sme.assets(tenant_id,id,site_id,name) VALUES (%s,%s,%s,%s) RETURNING name',(self.a,uuid4(),self.sb,'Wrong site'))
