"""Projection of actual signed proposal/probe evidence; framing and origin binding are supplied."""
from .wire_support import fraction_pair,numeric_fields,probe_payload
def proposal_payload(observation):
    """Preserve this proposal's original numeric-unit text, explicit kind and complete actual probe provenance."""
    raise NotImplementedError
