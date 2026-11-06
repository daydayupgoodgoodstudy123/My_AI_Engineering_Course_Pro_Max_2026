"""A pair of CSV tables is one saved assumption map."""
from __future__ import annotations
import csv
from pathlib import Path
from .model import Assumption, Evidence, Experiment

class MapStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def save(self, items: list[Assumption], experiments: list[Experiment]) -> None:
        """Replace both tables. Preserve input order, raw text/timestamps, optional
        evidence (None differs from empty Evidence), exact float thresholds and types.
        Tables have fixed filenames, so opaque ids never become filesystem paths.
        No atomic multi-file transaction is promised.
        """
        self.directory.mkdir(parents=True,exist_ok=True)
        with (self.directory/'assumptions.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f)
            for x in items:
                writer.writerow([x.id,x.kind,x.statement,x.impact,x.uncertainty,x.irreversibility,
                                 '0' if x.evidence is None else '1',
                                 x.evidence.verdict if x.evidence is not None else '',
                                 x.evidence.text if x.evidence is not None else ''])
        with (self.directory/'experiments.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f)
            for x in experiments:
                writer.writerow([x.id,x.assumption_id,x.population,x.observable,x.direction,repr(x.threshold),x.sample_size,
                                 x.registered_at,x.pass_action,x.fail_action,x.ambiguous_action])

    def load(self) -> tuple[list[Assumption], list[Experiment]]:
        """Reopen both CSV tables as independent typed objects in saved order."""
        items=[]
        with (self.directory/'assumptions.csv').open(newline='',encoding='utf-8') as f:
            for row in csv.reader(f):
                key,kind,text,impact,uncertainty,irreversibility,present,verdict,evidence=row
                items.append(Assumption(key,kind,text,int(impact),int(uncertainty),int(irreversibility),
                                        Evidence(verdict,evidence) if present=='1' else None))
        experiments=[]
        with (self.directory/'experiments.csv').open(newline='',encoding='utf-8') as f:
            for row in csv.reader(f):
                key,aid,pop,observable,direction,threshold,count,at,passed,failed,ambiguous=row
                experiments.append(Experiment(key,aid,pop,observable,direction,float(threshold),int(count),at,passed,failed,ambiguous))
        return items,experiments
