import unittest
from uuid import uuid4
from sme_partner.tenant_context import ActiveMembership, VerifiedIdentity, TenantAccessDenied, authorize_tenant

class TenantContextTests(unittest.TestCase):
    def setUp(self):
        self.user,self.another,self.a,self.b=uuid4(),uuid4(),uuid4(),uuid4()
        self.identity=VerifiedIdentity(self.user,'https://issuer.example')
        self.members=(ActiveMembership(self.user,self.a,True),ActiveMembership(self.user,self.b,False),ActiveMembership(self.another,self.b,True))
    def test_active_tenant(self):
        self.assertEqual(authorize_tenant(self.identity,self.a,self.members).tenant_id,self.a)
    def test_inactive_tenant(self):
        with self.assertRaises(TenantAccessDenied):authorize_tenant(self.identity,self.b,self.members)
    def test_unrelated_identity(self):
        with self.assertRaises(TenantAccessDenied):authorize_tenant(VerifiedIdentity(uuid4(),'https://issuer.example'),self.a,self.members)
    def test_no_membership(self):
        with self.assertRaises(TenantAccessDenied):authorize_tenant(self.identity,self.a,())
    def test_missing_issuer(self):
        with self.assertRaises(TenantAccessDenied):authorize_tenant(VerifiedIdentity(self.user,''),self.a,self.members)
