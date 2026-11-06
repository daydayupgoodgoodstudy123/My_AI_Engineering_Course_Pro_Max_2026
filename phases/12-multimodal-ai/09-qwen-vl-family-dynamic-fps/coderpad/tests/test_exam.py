"""Visible, frozen examples; expected outputs are authored in the kernel source."""
import json
from pathlib import Path
from _support import ContractCase

DATA = json.loads((Path(__file__).resolve().parents[1] / "fixtures.json").read_text())

class CoreTests(ContractCase):
    pass

class BonusTests(ContractCase):
    pass

def make_test(function, case):
    def test(self):
        self.run_contract(function, case)
    return test

for label, cls in (("core", CoreTests), ("bonus", BonusTests)):
    function = DATA[label]["function"]
    for number, case in enumerate(DATA[label]["cases"], 1):
        setattr(cls, f"test_{number:02d}_{function}", make_test(function, case))
# unittest also discovers class aliases left at module scope.
del label, cls, function, number, case
