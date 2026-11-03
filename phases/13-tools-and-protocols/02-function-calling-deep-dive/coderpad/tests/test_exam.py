"""Behavior tests for 02-function-calling-deep-dive; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_openai(self):
        self.assertEqual(m.normalize('openai', {'tool_calls': [{'id': 'a', 'function': {'name': 'sum', 'arguments': '{"x":2}'}}]}), [{'id': 'a', 'name': 'sum', 'arguments': {'x': 2}}])

    def test_anthropic_order(self):
        data = {'content': [{'type': 'text', 'text': 'thinking'}, {'type': 'tool_use', 'id': 'b', 'name': 'f', 'input': {}}, {'type': 'tool_use', 'id': 'a', 'name': 'g', 'input': {'v': 0}}]}
        self.assertEqual([x['id'] for x in m.normalize('anthropic', data)], ['b', 'a'])

    def test_gemini(self):
        self.assertEqual(m.normalize('gemini', {'parts': [{'text': 'hi'}, {'functionCall': {'id': 'g1', 'name': 'f', 'args': {}}}]}), [{'id': 'g1', 'name': 'f', 'arguments': {}}])

    def test_missing_collections(self):
        for provider in ('openai', 'anthropic', 'gemini'):
            with self.subTest(provider=provider):
                self.assertEqual(m.normalize(provider, {}), [])

    def test_bad_json_and_nonobject(self):
        for raw in ('{', '[]', 'null', '7'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                m.normalize('openai', {'tool_calls': [{'id': 'a', 'function': {'name': 'f', 'arguments': raw}}]})

    def test_malformed(self):
        for payload in ({'tool_calls': None}, {'tool_calls': [{}]}, {'tool_calls': [{'id': '', 'function': {'name': 'f', 'arguments': '{}'}}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                m.normalize('openai', payload)

    def test_no_mutation(self):
        from copy import deepcopy
        p = {'content': [{'type': 'tool_use', 'id': 'a', 'name': 'f', 'input': {'nested': [1]}}]}
        before = deepcopy(p)
        m.normalize('anthropic', p)
        self.assertEqual(p, before)

    def test_modes(self):
        for mode, a, g in (('auto', 'auto', 'AUTO'), ('none', 'none', 'NONE'), ('required', 'any', 'ANY')):
            with self.subTest(mode=mode):
                self.assertEqual(m.choice('openai', mode), mode)
                self.assertEqual(m.choice('anthropic', mode), {'type': a})
                self.assertEqual(m.choice('gemini', mode), {'mode': g})

    def test_force(self):
        self.assertEqual(m.choice('openai', 'force', 'f'), {'type': 'function', 'function': {'name': 'f'}})
        self.assertEqual(m.choice('anthropic', 'force', 'f'), {'type': 'tool', 'name': 'f'})
        self.assertEqual(m.choice('gemini', 'force', 'f'), {'mode': 'ANY', 'allowed_function_names': ['f']})

    def test_bad_choice(self):
        for args in (('other', 'auto'), ('openai', 'bad'), ('gemini', 'force'), ('anthropic', 'force', '')):
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.choice(*args)

class BonusTests(unittest.TestCase):

    def test_deduplicate(self):
        a = {'id': 'a', 'name': 'f', 'arguments': {}}
        self.assertEqual(m.unique_calls([a, a.copy()]), [a])

    def test_conflicting_ids(self):
        with self.assertRaises(ValueError):
            m.unique_calls([{'id': 'a', 'name': 'f', 'arguments': {}}, {'id': 'a', 'name': 'g', 'arguments': {}}])
