"""The explicitly declared fixed-course recommendation policy."""
from .contracts import FLAGS,RuleEvaluation,finish_decision,normalized_problem
def recommend(problem):
    """Evaluate hard, tiny, dialogue, roles, session, typed, fallback in order.

    Hard = resume OR interrupt OR fanout. Tiny = calls<=2 and all seven flags
    false. Dialogue/roles each exclude typed state; dialogue wins their tie.
    Session requires memory and neither roles nor dialogue, before typed state.
    Record only the evaluated prefix through its first match. Evidence contains
    every named predicate operand, even false values. Requirements contain all
    true signals in FLAGS order. finish_decision provides fixed reason formatting.
    """
    values=normalized_problem(vars(problem));trace=[]
    requirements=tuple(key for key in FLAGS if values[key])
    def record(rule,matched,keys):
        trace.append(RuleEvaluation(rule,matched,tuple((key,values[key]) for key in keys)))
        return matched
    if record('hard',any(values[key] for key in ('needs_resume','needs_human_interrupt','has_parallel_fanout')),('needs_resume','needs_human_interrupt','has_parallel_fanout')):return finish_decision('hard',requirements,trace)
    if record('tiny',values['total_llm_calls']<=2 and not any(values[key] for key in FLAGS),('total_llm_calls',)+FLAGS):return finish_decision('tiny',requirements,trace)
    if record('dialogue',values['has_dialogue'] and not values['has_typed_state'],('has_dialogue','has_typed_state')):return finish_decision('dialogue',requirements,trace)
    if record('roles',values['has_roles'] and not values['has_typed_state'],('has_roles','has_typed_state')):return finish_decision('roles',requirements,trace)
    if record('session',values['needs_session_memory'] and not values['has_roles'] and not values['has_dialogue'],('needs_session_memory','has_roles','has_dialogue')):return finish_decision('session',requirements,trace)
    if record('typed',values['has_typed_state'],('has_typed_state',)):return finish_decision('typed',requirements,trace)
    record('fallback',True,())
    return finish_decision('fallback',requirements,trace)
