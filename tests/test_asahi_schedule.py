import unittest
from datetime import datetime, timezone
from threading import Event, Thread

from sme_partner.asahi_schedule import SchedulePolicy, ScheduledIngest


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.mono = 100.0
        self.calls = []
        self.now = lambda: datetime(2026, 11, 22, tzinfo=timezone.utc)

    def schedule(self, func, **kwargs):
        return ScheduledIngest(
            func, now_monotonic=lambda: self.mono, now_utc=self.now,
            policy=SchedulePolicy(interval_seconds=60, retry_delay_seconds=5, max_attempts=2),
            **kwargs,
        )

    def test_first_run_and_interval(self):
        job = self.schedule(lambda t: self.calls.append(t) or True)
        self.assertEqual(job.run_due().outcome, "inserted")
        self.assertEqual(job.run_due().outcome, "not_due")
        self.mono += 60
        self.assertEqual(job.run_due().outcome, "inserted")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(x.tzinfo is not None for x in self.calls))

    def test_duplicate_not_reported_as_insert(self):
        job = self.schedule(lambda t: False)
        self.assertEqual(job.run_due().outcome, "duplicate_or_rejected")

    def test_transient_failure_deferred_then_recovers(self):
        def action(_):
            self.calls.append("called")
            if len(self.calls) == 1:
                raise TimeoutError("network")
            return True
        job = self.schedule(action)
        self.assertEqual(job.run_due().outcome, "retry_scheduled")
        self.assertEqual(job.run_due().outcome, "not_due")
        self.mono += 5
        self.assertEqual(job.run_due().outcome, "inserted")
        self.assertEqual(len(self.calls), 2)

    def test_persistent_failure_not_reported_as_success(self):
        job = self.schedule(lambda t: (_ for _ in ()).throw(ConnectionError("offline")),
                            )
        self.assertEqual(job.run_due().outcome, "retry_scheduled")
        self.mono += 5
        self.assertEqual(job.run_due().outcome, "retry_exhausted")
        self.assertEqual(job.run_due().outcome, "not_due")

    def test_security_failure_propagates(self):
        job = self.schedule(lambda t: (_ for _ in ()).throw(PermissionError("revoked")))
        with self.assertRaises(PermissionError):
            job.run_due()

    def test_parallel_invocation_denied(self):
        entered, release = Event(), Event()
        def blocking(_):
            entered.set()
            release.wait(1)
            return True
        job = self.schedule(blocking)
        thread = Thread(target=job.run_due)
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(job.run_due().outcome, "busy")
        finally:
            release.set()
            thread.join(1)

    def test_policy_bounds(self):
        for config in (
            {"interval_seconds": 1},
            {"retry_delay_seconds": 60},
            {"max_attempts": 0},
            {"max_attempts": 4},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                SchedulePolicy(**config)

    def test_naive_timestamp_rejected(self):
        job = ScheduledIngest(lambda t: True, now_monotonic=lambda: 0,
                              now_utc=lambda: datetime(2026, 11, 22))
        with self.assertRaises(ValueError):
            job.run_due()
