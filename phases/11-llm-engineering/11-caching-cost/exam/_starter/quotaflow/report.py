"""User/model/token-category cost evidence from an admitted-usage ledger."""
from decimal import Decimal,localcontext
from .contracts import validate_usage,validate_prices,decimal_cost
def usage_report(entries,prices):
    """Build ordered user -> model -> three-category usage, plus exact account totals.

    Fixed local prices are Decimal dollars per million tokens. Cached input is a
    subset of total input, billed at its cached rate, not an additional input.
    Keep exact component costs and cache savings through all subtotals. Baseline
    cost equals billed cost plus savings; savings is evidence, not another debit
    or subtraction. Reject unknown models even in denied entries. A denied entry
    contributes request/denial counts but zero usage/cost. For admitted entries,
    stored cost must equal the component bill under this supplied fixture card.
    Preserve first appearance order for users and models; empty input has zeros.
    """
    raise NotImplementedError
