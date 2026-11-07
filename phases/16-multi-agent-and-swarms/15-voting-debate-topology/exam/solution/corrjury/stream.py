"""Project each completed trial's own evidence; sampled classification and TSV driver are supplied."""
from .wire_support import canonical_outcome_field,cost_field
def trial_fields(report):
    """Return own trial/config, supplied family outcomes, observed seat tally, distinct costs and simulated marker."""
    return (report.trial_id,report.config.uid,canonical_outcome_field(report),report.tally.correct_seats,report.tally.total_seats,report.tally.passed,cost_field(report.cost.generation),cost_field(report.cost.reading),cost_field(report.cost.total),report.simulated)
