"""Original, offline interview kernels with hand-authored input/output contracts."""
import ast
import importlib
from pathlib import Path
import textwrap

KERNELS = {}

def ok(args, expected):
    return {"args": list(args), "expected": expected}

def bad(args, exception="ValueError"):
    return {"args": list(args), "raises": exception}

def add(name, label, signature, contract, body, cases, explanation=""):
    if name in KERNELS:
        raise ValueError(f"Duplicate kernel: {name}")
    code = "def " + signature + ":\n" + textwrap.indent(textwrap.dedent(body).strip(), "    ") + "\n"
    ast.parse(code)
    if len(cases) < 5:
        raise ValueError(f"At least five independent cases required: {name}")
    KERNELS[name] = {"name": name, "label": label, "signature": signature,
                     "contract": contract, "code": code, "cases": cases,
                     "function": signature.split("(")[0], "explanation": explanation or contract}

def load():
    for path in sorted(Path(__file__).parent.glob("*.py")):
        if path.name != "__init__.py":
            importlib.import_module("kernels." + path.stem)
    return KERNELS
