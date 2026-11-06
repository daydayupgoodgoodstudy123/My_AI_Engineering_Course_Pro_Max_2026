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
        raise NotImplementedError
    def load_run(self,run_id):
        """Reopen metadata and every ordered observation without numeric roundtripping."""
        raise NotImplementedError
