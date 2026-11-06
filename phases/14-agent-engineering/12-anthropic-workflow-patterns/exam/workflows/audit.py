"""Run audit records: one XML document per workflow run.

Workflows beat agents on compliance-bound tasks because auditors can read the graph instead of
inferring it from a trajectory. Each run is kept as its own XML file that opens in any XML tool:
the pattern, every step with its input and output in order, the branch a router took and the
run's final output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .patterns import Step


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
        raise NotImplementedError

    def read(self, run_id: str) -> Run:
        """Read a stored run back. A run id with no document raises KeyError."""
        raise NotImplementedError
