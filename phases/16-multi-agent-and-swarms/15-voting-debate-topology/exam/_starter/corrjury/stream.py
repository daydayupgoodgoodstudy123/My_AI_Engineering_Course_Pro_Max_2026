"""Project each completed trial's own evidence; sampled classification and TSV driver are supplied."""
from .wire_support import canonical_outcome_field,cost_field
def trial_fields(report):
    """Return own trial/config, supplied family outcomes, observed seat tally, distinct costs and simulated marker."""
    raise NotImplementedError
