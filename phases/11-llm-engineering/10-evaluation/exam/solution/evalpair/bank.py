"""Immutable local CSV observation runs with separate exact JSON metadata."""
import csv,json
from dataclasses import asdict
from .contracts import Observation,RunMeta,indexed_observations,run_folder
HEADER=("case_id","category","criterion","input_text","model_output","reference_present","reference_output","score_present","score_text","reasoning")
class EvalBank:
    def __init__(self,root):self.root=root
    def save_run(self,run_id,meta,observations):
        """Save a new immutable run. Preserve raw text, row order and decimal spelling.

        A missing reference differs from an empty reference; an unjudged score is
        None, while numeric zero is a real score. Reusing a run id raises FileExistsError.
        This local format makes no crash-atomicity or concurrent-writer promise.
        """
        observations=list(observations);indexed_observations(observations)
        folder=run_folder(self.root,run_id);folder.mkdir(parents=True,exist_ok=False)
        (folder/"meta.json").write_text(json.dumps(asdict(meta),ensure_ascii=False),encoding="utf-8")
        with (folder/"observations.csv").open("w",encoding="utf-8",newline="") as handle:
            writer=csv.writer(handle);writer.writerow(HEADER)
            for row in observations:
                writer.writerow([row.case_id,row.category,row.criterion,row.input_text,row.model_output,int(row.reference_output is not None),row.reference_output if row.reference_output is not None else "",int(row.score_text is not None),row.score_text if row.score_text is not None else "",row.reasoning])
    def load_run(self,run_id):
        """Reopen metadata and every ordered observation without numeric roundtripping."""
        folder=run_folder(self.root,run_id);meta=RunMeta(**json.loads((folder/"meta.json").read_text(encoding="utf-8")))
        observations=[]
        with (folder/"observations.csv").open("r",encoding="utf-8",newline="") as handle:
            reader=csv.reader(handle)
            if tuple(next(reader,()))!=HEADER:raise ValueError("observation header")
            for row in reader:
                if len(row)!=len(HEADER) or row[5] not in ("0","1") or row[7] not in ("0","1"):raise ValueError("observation row")
                observations.append(Observation(row[0],row[1],row[2],row[3],row[4],row[6] if row[5]=="1" else None,row[8] if row[7]=="1" else None,row[9]))
        indexed_observations(observations)
        return meta,observations
