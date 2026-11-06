"""Run audit records: one XML document per workflow run.

Workflows beat agents on compliance-bound tasks because auditors can read the graph instead of
inferring it from a trajectory. Each run is kept as its own XML file that opens in any XML tool:
the pattern, every step with its input and output in order, the branch a router took and the
run's final output.
"""
from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .patterns import Step

RUN_ID = re.compile(r"[A-Za-z0-9_-]+")
# Characters an XML 1.0 document cannot hold at all, plus CR, which a parser reads back as LF.
NEEDS_ENCODING = re.compile("[^\t\n\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


@dataclass(frozen=True)
class Run:
    """One run of a workflow, as the audit record keeps it."""

    run_id: str
    pattern: str
    steps: list[Step]
    branch: str | None = None
    output: str | None = None


class AuditLog:
    """A directory of run records, one XML document per run, named <run_id>.xml, with root element <run>.

    Text goes into the document as plain XML text wherever XML can hold it exactly, so an auditor
    reads it as it is. XML cannot hold every string: control characters other than tab and line
    feed are not allowed in an XML document at all, and a parser reads a carriage return in element
    text back as a line feed. Such values are stored encoded, marked so that read() can undo it.

    read() gives back exactly what write() was given: every character of every input and output,
    the steps in their order (step names may repeat), and None kept apart from the empty string.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write(self, run: Run) -> Path:
        """Store a run and return the path of its document.

        Run ids are made of ASCII letters, digits, "-" and "_"; anything else raises ValueError.
        """
        path = self._path(run.run_id)
        root = ET.Element("run", {"id": run.run_id, "pattern": run.pattern})
        for step in run.steps:
            node = ET.SubElement(root, "step", {"name": step.name})
            _put(node, "input", step.input)
            _put(node, "output", step.output)
        _put(root, "branch", run.branch)
        _put(root, "output", run.output)
        ET.indent(root)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def read(self, run_id: str) -> Run:
        """Read a stored run back. A run id with no document raises KeyError."""
        path = self._path(run_id)
        try:
            root = ET.parse(path).getroot()
        except FileNotFoundError:
            raise KeyError(run_id) from None
        steps = [
            Step(node.get("name", ""), _get(node.find("input")) or "", _get(node.find("output")) or "")
            for node in root.findall("step")
        ]
        return Run(
            run_id=root.get("id", ""),
            pattern=root.get("pattern", ""),
            steps=steps,
            branch=_get(root.find("branch")),
            output=_get(root.find("output")),
        )

    def _path(self, run_id: str) -> Path:
        if not RUN_ID.fullmatch(run_id):
            raise ValueError(f"run ids are letters, digits, '-' and '_', got {run_id!r}")
        return self.directory / f"{run_id}.xml"


def _put(parent: ET.Element, tag: str, value: str | None) -> None:
    """Add <tag> holding value; no element at all stands for None."""
    if value is None:
        return
    node = ET.SubElement(parent, tag)
    if NEEDS_ENCODING.search(value):
        node.set("encoding", "base64")
        node.text = base64.b64encode(value.encode("utf-8")).decode("ascii")
    else:
        node.text = value


def _get(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    text = node.text or ""
    if node.get("encoding") == "base64":
        return base64.b64decode(text).decode("utf-8")
    return text
