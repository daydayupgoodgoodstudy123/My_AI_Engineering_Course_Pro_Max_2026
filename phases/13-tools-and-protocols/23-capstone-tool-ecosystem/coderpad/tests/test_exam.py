"""Behavior tests for 23-capstone-tool-ecosystem; default target is starter."""
import unittest
from _support import m

class Client:

    def __init__(self, results):
        self.results = iter(results)
        self.seen = []

    def discover(self):
        self.seen.append('discover')
        return ['job']

    def call(self, t, a):
        self.seen.append('call')
        return next(self.results)

    def poll(self, t):
        self.seen.append('poll')
        return next(self.results)

class CoreTests(unittest.TestCase):

    def test_immediate(self):
        self.assertEqual(m.run(Client([{'status': 'completed', 'value': 0}]), 'job', {}, {'job'}), {'status': 'completed', 'value': 0, 'trace': ['discover', 'call']})

    def test_poll(self):
        c = Client([{'status': 'working', 'task_id': 't'}, {'status': 'completed', 'value': 'r'}])
        r = m.run(c, 'job', {}, {'job'})
        self.assertEqual(r['trace'], ['discover', 'call', 'poll'])
        self.assertEqual(r['value'], 'r')

    def test_timeout_budget(self):
        c = Client([{'status': 'working', 'task_id': 't'}] * 4)
        r = m.run(c, 'job', {}, {'job'}, 2)
        self.assertEqual(r['status'], 'timeout')
        self.assertEqual(c.seen.count('poll'), 2)

    def test_failed(self):
        self.assertEqual(m.run(Client([{'status': 'failed'}]), 'job', {}, {'job'})['status'], 'failed')

    def test_denied_no_calls(self):
        c = Client([])
        with self.assertRaises(PermissionError):
            m.run(c, 'job', {}, set())
        self.assertEqual(c.seen, [])

    def test_unknown(self):
        c = Client([])
        with self.assertRaises(KeyError):
            m.run(c, 'missing', {}, {'missing'})
        self.assertEqual(c.seen, ['discover'])

    def test_budget(self):
        with self.assertRaises(ValueError):
            m.run(Client([]), 'job', {}, {'job'}, True)

class BonusTests(unittest.TestCase):

    def test_evidence(self):
        self.assertEqual(m.evidence({'status': 'completed', 'trace': ['discover', 'call', 'poll']}), {'completed': True, 'polls': 1, 'live_integration': False})

    def test_timeout(self):
        self.assertFalse(m.evidence({'status': 'timeout', 'trace': []})['completed'])
