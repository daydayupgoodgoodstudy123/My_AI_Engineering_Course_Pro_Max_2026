"""The sleep-time agent: memory work that runs between turns, off the critical path."""
from __future__ import annotations

from .archival import Archival
from .blocks import BlockStore, summarize


class SleepTimeAgent:
    """Condenses near-limit blocks and invalidates contradicted archival records.

    The primary agent never waits for it, so it can afford to be slow and thorough.
    """

    def __init__(self, blocks: BlockStore, archival: Archival) -> None:
        self.blocks = blocks
        self.archival = archival
        self.trace: list[str] = []

    def run(self, contradictions: list[tuple[str, str]]) -> None:
        """One sleep-time pass.

        Every block at or past 80% of its limit is condensed to at most half its limit, so the
        primary agent has room to write again. A block whose newest line alone is longer than
        that is left as it is. Then every valid archival record that contains a contradicted
        claim (ignoring case) is invalidated with the claim's reason and kept for audit.
        """
        self.trace.append("sleep-time pass start")
        for label in self.blocks.labels():
            block = self.blocks.get(label)
            if block.near_limit():
                summary = summarize(block.value, block.limit // 2)
                if summary:
                    self.trace.append(f"  consolidate {label}: {block.rewrite(summary)}")
        for claim, reason in contradictions:
            needle = claim.lower()
            for record in self.archival.all_records():
                if record.valid and needle in record.text.lower():
                    self.archival.invalidate(record.rid, reason)
                    self.trace.append(f"  invalidate {record.rid} ({reason})")
        self.trace.append("sleep-time pass end")
