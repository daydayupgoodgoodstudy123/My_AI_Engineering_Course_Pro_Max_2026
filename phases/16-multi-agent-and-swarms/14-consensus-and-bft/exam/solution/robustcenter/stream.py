"""Projection of actual signed proposal/probe evidence; framing and origin binding are supplied."""
from .wire_support import fraction_pair,numeric_fields,probe_payload
def proposal_payload(observation):
    """Preserve this proposal's original numeric-unit text, explicit kind and complete actual probe provenance."""
    p=observation['proposal'];position,unit=numeric_fields(observation)
    return {'kind':observation['kind'],'proposal_uid':p.uid,'agent':p.agent,'answer':p.answer,'position':position,'unit':unit,'self_confidence':fraction_pair(p.self_confidence),**probe_payload(observation)}
