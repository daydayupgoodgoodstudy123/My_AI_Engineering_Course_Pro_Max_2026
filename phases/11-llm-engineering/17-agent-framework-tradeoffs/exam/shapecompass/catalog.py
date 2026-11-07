"""Local INI scenario catalog with separate complete decision evidence."""
from pathlib import Path
from .contracts import Scenario,Problem,FLAGS,validate_scenarios,normalized_problem
from .catalog_io import parser,read_ini,write_ini,text_json,text_from_json,write_evidence,read_evidence
class CatalogStore:
    def __init__(self,root):self.root=Path(root)
    def save(self,scenarios,decisions):
        """Save every ordered scenario and exactly one decision per stable case ID.

        The given codec owns complete decision serialization; no policy runs.
        Local single-writer completed saves are supported, not crash atomicity.
        """
        raise NotImplementedError('Part 2: save scenario catalog and bound evidence')
    def load(self):
        """Return ordered (Scenario, Decision) pairs; missing flags default false.

        INI booleans use ConfigParser's explicit accepted yes/no/true/false/1/0
        grammar. Missing call count defaults to one. Text JSON and no-interpolation
        primitives are given. Evidence keys must be an exact scenario bijection.
        """
        raise NotImplementedError('Part 2: reopen scenario catalog and bound evidence')
