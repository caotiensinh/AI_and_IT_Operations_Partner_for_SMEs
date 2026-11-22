import unittest
from threading import Event
from sme_partner.asahi_worker_service import (
    AsahiWorkerLoop,WorkerLoopPolicy,WorkerLoopExhausted,
)


class FakeStop:
    def __init__(self, after):
        self.after=after
        self.waits=[]
        self.stopped=False
    def is_set(self):
        return self.stopped
    def wait(self, seconds):
        self.waits.append(seconds)
        if len(self.waits)>=self.after:
            self.stopped=True
        return self.stopped


class WorkerServiceTests(unittest.TestCase):
    def test_safe_shutdown_and_counters(self):
        outcomes=iter(("inserted","not_due","duplicate"))
        stop=FakeStop(3)
        snapshots=[]
        result=AsahiWorkerLoop(lambda:next(outcomes),on_snapshot=snapshots.append).run(stop)
        self.assertEqual((result.state,result.completed_ticks,result.failed_ticks),("stopped",3,0))
        self.assertEqual(stop.waits,[30,30,30])
        self.assertEqual(result.last_outcome,"duplicate")
        self.assertIn("running",[s.state for s in snapshots])

    def test_retry_delay_and_recovery(self):
        attempts=[0]
        def job():
            attempts[0]+=1
            if attempts[0]==1: raise TimeoutError("DO_NOT_PRINT_SECRET")
            return "inserted"
        stop=FakeStop(2)
        result=AsahiWorkerLoop(job).run(stop)
        self.assertEqual(result.state,"stopped")
        self.assertEqual((result.completed_ticks,result.failed_ticks,result.consecutive_failures),(1,1,0))
        self.assertEqual(stop.waits,[5,30])
        self.assertNotIn("DO_NOT_PRINT_SECRET",str(result))

    def test_exhausted_failures_are_error(self):
        def offline(): raise ConnectionError("secret-in-exception")
        stop=FakeStop(100)
        service=AsahiWorkerLoop(offline,policy=WorkerLoopPolicy(max_consecutive_failures=2))
        with self.assertRaises(WorkerLoopExhausted):
            service.run(stop)
        self.assertEqual(service.snapshot.state,"failed")
        self.assertEqual(service.snapshot.failed_ticks,2)
        self.assertEqual(stop.waits,[5])
        self.assertNotIn("secret-in-exception",str(service.snapshot))

    def test_unexpected_failure_propagates(self):
        service=AsahiWorkerLoop(lambda: (_ for _ in ()).throw(PermissionError("revoked")))
        with self.assertRaises(PermissionError):
            service.run(FakeStop(1))
        self.assertEqual(service.snapshot.state,"failed")

    def test_invalid_tick_outcome_fails_closed(self):
        service=AsahiWorkerLoop(lambda:"mystery")
        with self.assertRaises(ValueError):
            service.run(FakeStop(1))
        self.assertEqual(service.snapshot.state,"failed")

    def test_already_stopped_does_not_poll(self):
        stop=FakeStop(1)
        stop.stopped=True
        calls=[]
        status=AsahiWorkerLoop(lambda:calls.append(1) or "inserted").run(stop)
        self.assertEqual(calls,[])
        self.assertEqual(status.state,"stopped")

    def test_reentrant_run_rejected(self):
        stop=FakeStop(1)
        loop=None
        def nested():
            with self.assertRaises(RuntimeError):
                loop.run(stop)
            return "not_due"
        loop=AsahiWorkerLoop(nested)
        self.assertEqual(loop.run(stop).completed_ticks,1)

    def test_policy_boundary(self):
        for kw in ({"interval_seconds":0},{"retry_delay_seconds":-1},
                   {"max_consecutive_failures":0},{"max_consecutive_failures":21},
                   {"retry_delay_seconds":float("nan")},{"interval_seconds":"1"}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                WorkerLoopPolicy(**kw)
