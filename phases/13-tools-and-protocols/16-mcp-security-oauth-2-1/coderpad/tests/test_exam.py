"""Behavior tests for 16-mcp-security-oauth-2-1; default target is starter."""
import unittest
from _support import m

CLAIMS = {'iss': 'https://issuer', 'aud': 'notes', 'exp': 10, 'scope': 'read write'}

def check(c, required={'read'}, now=9):
    return m.authorize(c, 'https://issuer', 'notes', required, now)

class CoreTests(unittest.TestCase):

    def test_challenge(self):
        self.assertEqual(m.challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'), 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM')

    def test_valid(self):
        self.assertEqual(check(CLAIMS), {'ok': True})

    def test_issuer_first(self):
        self.assertEqual(check(dict(CLAIMS, iss='evil', aud='other'))['error'], 'issuer')

    def test_audience(self):
        self.assertEqual(check(dict(CLAIMS, aud=['other', 'notes'])), {'ok': True})
        self.assertEqual(check(dict(CLAIMS, aud='notes-extra'))['error'], 'audience')

    def test_expiry(self):
        for exp in (True, 10.0, None, 9):
            with self.subTest(exp=exp):
                self.assertEqual(check(dict(CLAIMS, exp=exp))['error'], 'expired')
        self.assertEqual(check(CLAIMS, now=10)['error'], 'expired')

    def test_scope(self):
        self.assertEqual(check(CLAIMS, {'admin'})['error'], 'scope')
        self.assertEqual(check(dict(CLAIMS, scope='reader'))['error'], 'scope')

class BonusTests(unittest.TestCase):

    def test_missing(self):
        self.assertEqual(m.step_up({'read'}, {'read', 'write', 'admin'}), ['admin', 'write'])

    def test_none(self):
        self.assertEqual(m.step_up({'read'}, {'read'}), [])
