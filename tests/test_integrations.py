import unittest
from uuid import uuid4
from sme_partner.integrations import (
    AdapterRegistry, AdapterManifest, Domain, Principal,
    CapabilityDenied, TenantBoundaryError, CANDIDATE_ADAPTERS,
)

class TestTenantAdapterBoundary(unittest.TestCase):
    def setUp(self):
        self.a, self.b = uuid4(), uuid4()
        self.principal = Principal(uuid4(), self.a, frozenset({'document.extract'}))
        self.manifest = AdapterManifest('billumi-ocr', 'caotiensinh/Billumi', Domain.OFFICE, frozenset({'document.extract'}), enabled=True)
        self.registry = AdapterRegistry((self.manifest,))

    def test_authorized_operation_has_tenant_context(self):
        inv = self.registry.authorize(principal=self.principal, requested_tenant_id=self.a, adapter_id='billumi-ocr', capability='document.extract', resource_id=uuid4())
        self.assertEqual(inv.tenant_id, self.a)
        self.assertEqual(inv.principal_id, self.principal.subject_id)

    def test_cross_tenant_denied(self):
        with self.assertRaises(TenantBoundaryError):
            self.registry.authorize(principal=self.principal, requested_tenant_id=self.b, adapter_id='billumi-ocr', capability='document.extract', resource_id=uuid4())

    def test_unknown_adapter_denied(self):
        with self.assertRaises(CapabilityDenied):
            self.registry.authorize(principal=self.principal, requested_tenant_id=self.a, adapter_id='unknown', capability='document.extract', resource_id=uuid4())

    def test_ungranted_capability_denied(self):
        with self.assertRaises(CapabilityDenied):
            self.registry.authorize(principal=self.principal, requested_tenant_id=self.a, adapter_id='billumi-ocr', capability='device.control', resource_id=uuid4())

    def test_disabled_by_default(self):
        registry = AdapterRegistry(CANDIDATE_ADAPTERS)
        with self.assertRaises(CapabilityDenied):
            registry.authorize(principal=self.principal, requested_tenant_id=self.a, adapter_id='billumi-ocr', capability='document.extract', resource_id=uuid4())

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            AdapterRegistry((self.manifest, self.manifest))

    def test_empty_permissions_denied(self):
        p = Principal(uuid4(), self.a, frozenset())
        with self.assertRaises(CapabilityDenied):
            self.registry.authorize(principal=p, requested_tenant_id=self.a, adapter_id='billumi-ocr', capability='document.extract', resource_id=uuid4())

if __name__ == '__main__':
    unittest.main()
