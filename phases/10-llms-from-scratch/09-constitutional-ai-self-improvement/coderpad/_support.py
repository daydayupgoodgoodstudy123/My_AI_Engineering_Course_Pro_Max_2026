"""Local implementation selection and strict fixture assertions, no network."""
import builtins
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
selected = os.environ.get("CODERPAD_IMPLEMENTATION", "starter")
if selected not in ("starter", "solution"):
    raise ValueError("Unknown implementation")
spec = importlib.util.spec_from_file_location("coderpad_target", root / selected / "main.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

class ContractCase(unittest.TestCase):
    def assert_contract_value(self, actual, expected):
        if type(expected) is bool or expected is None:
            self.assertIs(actual, expected)
        elif type(expected) in (int, float):
            self.assertIn(type(actual), (int, float))
            self.assertTrue(math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8), f"{actual!r} != {expected!r}")
        elif isinstance(expected, list):
            self.assertIsInstance(actual, list)
            self.assertEqual(len(actual), len(expected))
            for a, e in zip(actual, expected):
                self.assert_contract_value(a, e)
        elif isinstance(expected, dict):
            self.assertIsInstance(actual, dict)
            self.assertEqual(set(actual), set(expected))
            for k, e in expected.items():
                self.assert_contract_value(actual[k], e)
        else:
            self.assertEqual(type(actual), type(expected))
            self.assertEqual(actual, expected)

    def run_contract(self, function, case):
        args = copy.deepcopy(case["args"])
        before = copy.deepcopy(args)
        if "raises" in case:
            with self.assertRaises(getattr(builtins, case["raises"])):
                getattr(m, function)(*args)
        else:
            self.assert_contract_value(getattr(m, function)(*args), case["expected"])
        self.assertEqual(json.dumps(args, sort_keys=True), json.dumps(before, sort_keys=True), "Input mutation")
