"""Candidate weighted revision, source confidence/history commit and fixed rounds."""
from fractions import Fraction
from .intake import new_agents,frozen_round,requested_rounds
from .service import RoundDesk

def revise_agent(own,others):
    """Compute confidence-weighted own-plus-all-others answer from a frozen vector.

    Inputs are finite binary64 answers and confidences in[0,1]. Reject total
    weight0. Accumulation must preserve representable mixed-scale residuals and
    avoid overflow before the final finite convex mean is rounded to binary64.
    This is numeric toy arithmetic, not a probability or truth guarantee.
    """
    population=(own,)+tuple(others)
    weight=sum((Fraction.from_float(a.confidence) for a in population),Fraction())
    if not weight:raise ValueError('positive total confidence required')
    numerator=sum((Fraction.from_float(a.answer)*Fraction.from_float(a.confidence) for a in population),Fraction())
    return float(numerator/weight)

def commit_numeric_round(agents,snapshot):
    """Commit each frozen-round weighted answer, own capped confidence and new history."""
    revised=[revise_agent(own,tuple(other for j,other in enumerate(snapshot) if j!=i)) for i,own in enumerate(snapshot)]
    for agent,old,answer in zip(agents,snapshot,revised):
        agent.answer=answer;agent.confidence=min(old.confidence*1.05,1.0);agent.history.append(answer)

def run_numeric_debate(initial,rounds,truth=None,tol=0.1):
    """Initialize once, retain round0, and commit exactly the requested extra rounds.

    The correct supplied frozen snapshot follows the lesson prose; live object
    aliasing in source main is not a candidate defect. Do not stop on agreement
    or truth, add an alpha/topology, or infer quality from the scripted dynamics.
    """
    rounds=requested_rounds(rounds);agents=new_agents(initial);desk=RoundDesk()
    for agent in agents:agent.history.append(agent.answer)
    reports=[desk.record(0,frozen_round(agents),truth,tol)]
    for index in range(1,rounds+1):
        snapshot=frozen_round(agents);commit_numeric_round(agents,snapshot)
        reports.append(desk.record(index,frozen_round(agents),truth,tol))
    return {'agents':tuple(agents),'rounds':tuple(reports)}
