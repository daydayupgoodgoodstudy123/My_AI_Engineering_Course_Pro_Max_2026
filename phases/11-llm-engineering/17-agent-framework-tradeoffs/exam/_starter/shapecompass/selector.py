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
    raise NotImplementedError('Part 3: ordered recommendation and actual evaluation evidence')
