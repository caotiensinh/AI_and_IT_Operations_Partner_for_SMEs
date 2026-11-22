import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from sme_partner.adapters.asahi import DeviceBinding
from sme_partner.asahi_ingest import IngestAuthorization
from sme_partner.asahi_leased_worker import (
    LeaseTickPolicy,run_leased_ingest_tick,
)


class _Cursor:
    def __init__(self,result):
        self.result=result
    def fetchone(self):
        return (self.result,)


class _Conn:
    def __init__(self,results,commands):
        self.results=results
        self.commands=commands
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def transaction(self):
        return self
    def execute(self,sql,args=None):
        self.commands.append((sql,args))
        if sql.startswith("SELECT sme."):
            return _Cursor(self.results.pop(0))
        return _Cursor(None)


class WorkerTickTests(unittest.TestCase):
    def setUp(self):
        self.commands=[]
        self.results=[]
        self.binding=DeviceBinding(uuid4(),uuid4(),uuid4())
        self.auth=IngestAuthorization(uuid4(),"z"*43,self.binding)
        self.worker=uuid4()
        self.now=datetime.now(timezone.utc)
        self.connect=lambda: _Conn(self.results,self.commands)
        self.args=dict(poller=object(),connect=self.connect,auth=self.auth,
                       worker_id=self.worker,observed_at=self.now)
    def test_busy_does_not_poll(self):
        self.results=[False]
        with patch("sme_partner.asahi_leased_worker.ingest_one") as action:
            self.assertEqual(run_leased_ingest_tick(**self.args),"not_due")
            action.assert_not_called()
    def test_success_completes_lease(self):
        self.results=[True,True]
        with patch("sme_partner.asahi_leased_worker.ingest_one",return_value=True):
            self.assertEqual(run_leased_ingest_tick(**self.args),"inserted")
        self.assertEqual(self.commands[-1][1][3],True)
    def test_duplicate_not_misreported_as_new(self):
        self.results=[True,True]
        with patch("sme_partner.asahi_leased_worker.ingest_one",return_value=False):
            self.assertEqual(run_leased_ingest_tick(**self.args),"duplicate")
    def test_poll_failure_marks_retry_then_propagates(self):
        self.results=[True,True]
        with patch("sme_partner.asahi_leased_worker.ingest_one",side_effect=TimeoutError("offline")):
            with self.assertRaises(TimeoutError):
                run_leased_ingest_tick(**self.args)
        self.assertEqual(self.commands[-1][1][3],False)
    def test_completion_failure_is_not_success(self):
        self.results=[True,False]
        with patch("sme_partner.asahi_leased_worker.ingest_one",return_value=True):
            with self.assertRaisesRegex(RuntimeError,"completion"):
                run_leased_ingest_tick(**self.args)
    def test_bad_worker_id_fails_closed(self):
        with self.assertRaises(ValueError):
            run_leased_ingest_tick(**{**self.args,"worker_id":uuid4().__class__(int=0)})
    def test_policy_bounds(self):
        for kwargs in ({"lease_seconds":4},{"lease_seconds":301},
                       {"interval_seconds":9},{"retry_seconds":0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LeaseTickPolicy(**kwargs)
