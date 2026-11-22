import unittest
from uuid import UUID, uuid4
from sme_partner.asahi_delivery_policy import (
    ApprovedDestination, TenantDeliveryPolicy,
)


class DeliveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tenant = uuid4()
        self.event = 42

    def destination(self, **kwargs):
        params = dict(
            tenant_id=self.tenant, channel="email",
            destination_ref="tenant/mail/alerts", secret_ref="tenant/mail/token",
            enabled=True,
        )
        params.update(kwargs)
        return ApprovedDestination(**params)

    def test_approved_tenant_event_bound_and_stable_key(self):
        policy = TenantDeliveryPolicy({self.tenant: self.destination()})
        auth = policy.authorize(tenant_id=self.tenant, event_id=self.event)
        self.assertEqual((auth.tenant_id, auth.event_id), (self.tenant, self.event))
        self.assertEqual(auth.idempotency_key, str(self.event))
        self.assertEqual(auth.event_id, 42)
        self.assertEqual(auth.destination_ref, "tenant/mail/alerts")
        self.assertEqual(auth, policy.authorize(tenant_id=self.tenant, event_id=self.event))

    def test_default_deny_and_disabled(self):
        for policy in (TenantDeliveryPolicy({}), TenantDeliveryPolicy({
            self.tenant: self.destination(enabled=False)
        })):
            with self.assertRaises(PermissionError):
                policy.authorize(tenant_id=self.tenant, event_id=self.event)

    def test_cross_tenant_cannot_reuse_destination(self):
        other = uuid4()
        with self.assertRaises(ValueError):
            TenantDeliveryPolicy({other: self.destination()})
        policy = TenantDeliveryPolicy({self.tenant: self.destination()})
        with self.assertRaises(PermissionError):
            policy.authorize(tenant_id=other, event_id=self.event)

    def test_snapshot_not_affected_by_policy_map_mutation(self):
        source = {self.tenant: self.destination()}
        policy = TenantDeliveryPolicy(source)
        source.clear()
        self.assertEqual(policy.authorize(tenant_id=self.tenant, event_id=self.event).channel, "email")

    def test_invalid_identifiers(self):
        policy = TenantDeliveryPolicy({self.tenant: self.destination()})
        for tenant, event in ((UUID(int=0), self.event), (self.tenant, 0),
                              ("x", self.event), (self.tenant, "x"),
                              (self.tenant, -1), (self.tenant, True),
                              (self.tenant, 9223372036854775808), (self.tenant, uuid4())):
            with self.subTest(tenant=tenant, event=event), self.assertRaises(ValueError):
                policy.authorize(tenant_id=tenant, event_id=event)

    def test_references_fail_closed(self):
        for field, value in (
            ("destination_ref", "https://attacker.example"),
            ("destination_ref", "../unsafe"), ("destination_ref", "/absolute"),
            ("destination_ref", "a b"), ("destination_ref", ""),
            ("secret_ref", "vault://secret"), ("secret_ref", "x" * 129),
            ("secret_ref", "a\\b"), ("secret_ref", "bad:ref"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.destination(**{field: value})

    def test_channel_and_flag_strict(self):
        for kwargs in ({"channel": "sms"}, {"channel": "EMAIL"},
                       {"enabled": 1}, {"enabled": "true"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.destination(**kwargs)

    def test_no_network_or_credentials_in_policy(self):
        auth = TenantDeliveryPolicy({self.tenant: self.destination()}).authorize(
            tenant_id=self.tenant, event_id=self.event
        )
        self.assertFalse(hasattr(auth, "url"))
        self.assertFalse(hasattr(auth, "password"))
        self.assertFalse(hasattr(auth, "token"))


if __name__ == "__main__":
    unittest.main()
