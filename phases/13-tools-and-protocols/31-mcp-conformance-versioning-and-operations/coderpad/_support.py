"""Select a local implementation; importing it never fills in learner TODOs."""
import importlib.util
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
implementation = os.environ.get("CODERPAD_IMPLEMENTATION", "starter")
if implementation not in ("starter", "solution"):
    raise ValueError("CODERPAD_IMPLEMENTATION must be starter or solution")
spec = importlib.util.spec_from_file_location("coderpad_target", root / implementation / "main.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
