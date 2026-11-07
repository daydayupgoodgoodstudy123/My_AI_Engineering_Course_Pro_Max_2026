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
        scenarios=validate_scenarios(scenarios);decisions=tuple(decisions)
        keys=[key for key,value in decisions]
        if len(keys)!=len(set(keys)) or set(keys)!={x.case_id for x in scenarios}:raise ValueError('evidence binding')
        config=parser()
        for row in scenarios:
            config[row.case_id]={'label':text_json(row.label),'total_llm_calls':str(row.problem.total_llm_calls),**{key:'yes' if getattr(row.problem,key) else 'no' for key in FLAGS}}
        self.root.mkdir(parents=True,exist_ok=True)
        write_ini(self.root/'scenarios.ini',config)
        write_evidence(self.root/'decisions.json',decisions)
    def load(self):
        """Return ordered (Scenario, Decision) pairs; missing flags default false.

        INI booleans use ConfigParser's explicit accepted yes/no/true/false/1/0
        grammar. Missing call count defaults to one. Text JSON and no-interpolation
        primitives are given. Evidence keys must be an exact scenario bijection.
        """
        config=read_ini(self.root/'scenarios.ini');evidence=read_evidence(self.root/'decisions.json');rows=[]
        for case_id in config.sections():
            fields={key:config.getboolean(case_id,key,fallback=False) for key in FLAGS}
            fields['total_llm_calls']=config.getint(case_id,'total_llm_calls',fallback=1)
            problem=Problem(**normalized_problem(fields))
            scenario=Scenario(case_id,text_from_json(config.get(case_id,'label')),problem)
            rows.append((scenario,evidence[case_id]))
        validate_scenarios(row[0] for row in rows)
        if set(evidence)!={row[0].case_id for row in rows}:raise ValueError('evidence binding')
        return tuple(rows)
