"""Role-owned clarification obligations, selective invalidation and blocked-step replay."""
from dataclasses import replace
from .models import Question
from .flow_support import step_named,replace_step,required_missing,field_owner,question_id,answered_revision
from .service import VerificationDesk

def required_field_questions(state,step_id):
    """Block only this step on explicitly missing required fields; ask each owning role.

    Presence and finite field lookup helpers are supplied. Do not guess a value,
    ask about unrelated optional fields or discard another step's retained work.
    """
    raise NotImplementedError

def apply_clarification_answer(state,answer):
    """Accept a matching active question/owner/base revision and revise its declared field.

    Preserve unrelated artifacts/reports. Invalidate only step slots whose
    declared inputs include the changed field, then renew unresolved questions
    against the new revision. No source text or missing field is inferred.
    """
    raise NotImplementedError

def resume_blocked_step(state,step_id,executor):
    """Resume just the requested ready step; run its executor once, then repaired critic/verifier.

    Missing requirements produce questions without executing. Retained complete
    slots are reused. A critic note is never deterministic pass evidence.
    """
    raise NotImplementedError
