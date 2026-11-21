import unittest
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from dataclasses import replace

from sme_partner.adapters.asahi import NormalizedTelemetry
from sme_partner.asahi_alerts import AsahiAlertEvaluator, MetricAlertPolicy


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b,self.site,self.device=[uuid4() for _ in range(4)]
        self.start=datetime(2026,11,22,tzinfo=timezone.utc)
        self.engine=AsahiAlertEvaluator()

    def sample(self,n,cpu=92,memory=20,tenant=None,device=None):
        return NormalizedTelemetry(tenant_id=tenant or self.a,site_id=self.site,
            device_id=device or self.device,sampled_at=self.start+timedelta(seconds=n),
            hostname="lab-node",cpu_percent=cpu,memory_percent=memory,
            uptime_seconds=100,disk_mounts=())

    def test_consecutive_threshold_and_no_duplicate(self):
        self.assertEqual(self.engine.evaluate(self.sample(0)),())
        first=self.engine.evaluate(self.sample(1))
        self.assertEqual([(e.metric,e.transition) for e in first],[("cpu","triggered")])
        self.assertEqual(self.engine.evaluate(self.sample(2,cpu=99)),())

    def test_clear_hysteresis_then_rearm(self):
        self.engine.evaluate(self.sample(0))
        self.engine.evaluate(self.sample(1))
        self.assertEqual(self.engine.evaluate(self.sample(2,cpu=85)),())
        cleared=self.engine.evaluate(self.sample(3,cpu=80))
        self.assertEqual(cleared[0].transition,"cleared")
        self.assertEqual(self.engine.evaluate(self.sample(4,cpu=92)),())
        triggered=self.engine.evaluate(self.sample(5,cpu=95))
        self.assertEqual(triggered[0].transition,"triggered")

    def test_duplicate_and_out_of_order_ignored(self):
        self.engine.evaluate(self.sample(1))
        self.assertEqual(self.engine.evaluate(self.sample(1)),())
        self.assertEqual(self.engine.evaluate(self.sample(0)),())
        self.assertEqual(self.engine.evaluate(self.sample(2))[0].transition,"triggered")

    def test_tenant_isolation(self):
        self.engine.evaluate(self.sample(1,tenant=self.a))
        self.assertEqual(self.engine.evaluate(self.sample(2,tenant=self.b)),())
        triggered=self.engine.evaluate(self.sample(3,tenant=self.a))
        self.assertEqual(triggered[0].tenant_id,self.a)

    def test_device_isolation(self):
        different=uuid4()
        self.engine.evaluate(self.sample(1))
        self.assertEqual(self.engine.evaluate(self.sample(2,device=different)),())
        self.assertEqual(self.engine.evaluate(self.sample(3))[0].device_id,self.device)

    def test_cpu_memory_independent(self):
        self.engine.evaluate(self.sample(0,cpu=92,memory=95))
        events=self.engine.evaluate(self.sample(1,cpu=92,memory=95))
        self.assertEqual({e.metric for e in events},{"cpu","memory"})

    def test_missing_sensor_is_not_zero_or_recovery(self):
        self.engine.evaluate(self.sample(0))
        self.engine.evaluate(self.sample(1))
        self.assertEqual(self.engine.evaluate(self.sample(2,cpu=None)),())
        self.assertEqual(self.engine.evaluate(self.sample(3,cpu=84)),())

    def test_invalid_policy(self):
        for kwargs in ({"cpu_critical":float("nan")},{"memory_critical":101},
                       {"clear_margin":99},{"consecutive_breaches":0},{"max_devices":0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                MetricAlertPolicy(**kwargs)

    def test_state_capacity_fails_closed(self):
        engine=AsahiAlertEvaluator(MetricAlertPolicy(max_devices=1))
        engine.evaluate(self.sample(1))
        with self.assertRaises(RuntimeError):
            engine.evaluate(self.sample(2,device=uuid4()))

    def test_naive_sample_rejected(self):
        malformed=replace(self.sample(0),sampled_at=datetime(2026,11,22))
        with self.assertRaises(ValueError):
            self.engine.evaluate(malformed)

    def test_invalid_metric_rejected(self):
        malformed=replace(self.sample(0),cpu_percent=float("nan"))
        with self.assertRaises(ValueError):
            self.engine.evaluate(malformed)
