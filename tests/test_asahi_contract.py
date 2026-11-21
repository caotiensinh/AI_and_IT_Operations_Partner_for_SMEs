import unittest
from datetime import datetime,timezone,timedelta
from uuid import uuid4

from sme_partner.adapters.asahi import (
    DeviceBinding,MetricRejected,normalize_asahi_snapshot,
)

class AsahiContractTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.bound=DeviceBinding(uuid4(),uuid4(),uuid4())
        self.payload={
            "hostname":"asahi-node","timestamp":int(self.now.timestamp()),
            "cpu_pct":42.5,"memory_pct":71.8,"uptime_s":500,
            "disks":[{"mount":"/","used_pct":55.0}],
        }
    def normalize(self,payload=None,binding=None,observed=None):
        return normalize_asahi_snapshot(payload=payload if payload is not None else self.payload,
                                         binding=binding if binding is not None else self.bound,
                                         observed_at=observed if observed is not None else self.now)
    def test_valid_metrics_assigned_to_trusted_tenant(self):
        m=self.normalize()
        self.assertEqual((m.tenant_id,m.site_id,m.device_id),
                         (self.bound.tenant_id,self.bound.site_id,self.bound.device_id))
        self.assertEqual(m.cpu_percent,42.5)
        self.assertEqual(m.disk_mounts,(("/",55.0),))
    def test_legacy_time_field_accepted(self):
        p=dict(self.payload);p["time"]=p.pop("timestamp")
        self.assertEqual(self.normalize(p).sampled_at,self.now)
    def test_agent_supplied_tenant_id_ignored(self):
        p=dict(self.payload);p["tenant_id"]=str(uuid4());p["site_id"]=str(uuid4())
        m=self.normalize(p)
        self.assertEqual(m.tenant_id,self.bound.tenant_id)
        self.assertEqual(m.site_id,self.bound.site_id)
    def test_unknown_payload_fields_discarded(self):
        p=dict(self.payload);p["secret"]="not for persistence";p["network"]=[{"ips":["192.168.1.1"]}]
        self.assertFalse(hasattr(self.normalize(p),"secret"))
        self.assertFalse(hasattr(self.normalize(p),"network"))
    def test_invalid_percentage_denied(self):
        for val in (-1,101,float("nan"),float("inf"),True,"99"):
            p=dict(self.payload);p["cpu_pct"]=val
            with self.subTest(val=val),self.assertRaises(MetricRejected):self.normalize(p)
    def test_old_and_future_samples_denied(self):
        for delta in (-301,301):
            p=dict(self.payload);p["timestamp"]=int(self.now.timestamp())+delta
            with self.assertRaises(MetricRejected):self.normalize(p)
    def test_non_utc_observed_time_normalized(self):
        observed=self.now.astimezone(timezone(timedelta(hours=9)))
        self.assertEqual(self.normalize(observed=observed).sampled_at,self.now)
    def test_duplicate_disk_mount_denied(self):
        p=dict(self.payload);p["disks"]=[{"mount":"/"},{"mount":"/"}]
        with self.assertRaises(MetricRejected):self.normalize(p)
    def test_too_many_disks_denied(self):
        p=dict(self.payload);p["disks"]=[{"mount":f"/mnt/{n}"} for n in range(33)]
        with self.assertRaises(MetricRejected):self.normalize(p)
    def test_malformed_binding_rejected(self):
        with self.assertRaises(MetricRejected):
            self.normalize(binding=DeviceBinding("tenant",uuid4(),uuid4()))
    def test_empty_hostname_rejected(self):
        p=dict(self.payload);p["hostname"]=""
        with self.assertRaises(MetricRejected):self.normalize(p)
    def test_unavailable_metrics_are_null(self):
        p=dict(self.payload);p.pop("cpu_pct");p["memory_pct"]=None;p["disks"]=[]
        m=self.normalize(p)
        self.assertIsNone(m.cpu_percent)
        self.assertIsNone(m.memory_percent)
    def test_timezone_required(self):
        with self.assertRaises(MetricRejected):self.normalize(observed=datetime.now())
