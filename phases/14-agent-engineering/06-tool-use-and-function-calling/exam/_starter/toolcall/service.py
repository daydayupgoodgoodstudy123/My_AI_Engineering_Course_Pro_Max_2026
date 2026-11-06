"""Glue for the CI job: cases come from the bank, answers from the model, TAP goes out."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .cases import CaseBank
from .pipeline import Model, run_suite


class EvalService:
    def __init__(self, bank: CaseBank, concurrency: int = 4) -> None:
        self.bank = bank
        self.concurrency = concurrency

    def run(self, model: Model, category: str | None = None) -> AsyncIterator[str]:
        """TAP for every stored case, or for one category's, as run_suite writes it."""
        return run_suite(self.bank.cases(category), model, self.concurrency)
