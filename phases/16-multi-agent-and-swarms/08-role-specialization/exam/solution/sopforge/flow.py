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
    step=step_named(state,step_id);missing=required_missing(state.spec,step.requires)
    questions=tuple(Question(question_id(state.spec,step_id,f),state.spec.spec_id,state.spec.revision,step_id,f,field_owner(state.spec,f))for f in missing)
    other=tuple(q for q in state.questions if q.step_id!=step_id)
    status='blocked'if missing else step.status
    return replace(replace_step(state,replace(step,status=status)),questions=other+questions,blocked_step=step_id if missing else state.blocked_step)

def apply_clarification_answer(state,answer):
    """Accept a matching active question/owner/base revision and revise its declared field.

    Preserve unrelated artifacts/reports. Invalidate only step slots whose
    declared inputs include the changed field, then renew unresolved questions
    against the new revision. No source text or missing field is inferred.
    """
    matches=[q for q in state.questions if (q.question_id,q.spec_id,q.spec_revision,q.field,q.owner)==(answer.question_id,answer.spec_id,answer.spec_revision,answer.field,answer.owner)]
    if len(matches)!=1 or (answer.spec_id,answer.spec_revision)!=(state.spec.spec_id,state.spec.revision):raise ValueError('answer does not match active role question')
    question=matches[0];spec=answered_revision(state.spec,answer.field,answer.value)
    steps=tuple(replace(step,bundle=None,status='waiting')if answer.field in step.requires else step for step in state.steps)
    revised=replace(state,spec=spec,history=state.history+(spec,),steps=steps,questions=(),blocked_step=question.step_id)
    pending_steps=tuple(dict.fromkeys(q.step_id for q in state.questions))
    for step_id in pending_steps:revised=required_field_questions(revised,step_id)
    return replace(revised,blocked_step=question.step_id)

def resume_blocked_step(state,step_id,executor):
    """Resume just the requested ready step; run its executor once, then repaired critic/verifier.

    Missing requirements produce questions without executing. Retained complete
    slots are reused. A critic note is never deterministic pass evidence.
    """
    step=step_named(state,step_id)
    if state.blocked_step is not None and state.blocked_step!=step_id:raise ValueError('another step is blocked')
    if required_missing(state.spec,step.requires):return required_field_questions(state,step_id)
    if step.bundle is not None:return state
    artifact=executor(state.spec,step_id);bundle=VerificationDesk().inspect(state.spec,artifact)
    status='complete'if bundle.critic.approved and bundle.verifier.executed and bundle.verifier.passed else 'rejected'
    updated=replace_step(state,replace(step,bundle=bundle,runs=step.runs+1,status=status))
    return replace(updated,questions=tuple(q for q in updated.questions if q.step_id!=step_id),blocked_step=None if updated.blocked_step==step_id else updated.blocked_step)
