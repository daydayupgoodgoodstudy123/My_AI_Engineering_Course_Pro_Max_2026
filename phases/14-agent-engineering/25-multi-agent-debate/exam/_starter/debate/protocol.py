"""The lesson's debate runner: scripted debaters on a full mesh or a star.

Ported from the lesson's code/main.py. Critique ops are the cost proxy: one op is one
debater reading one peer's previous answer.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

TOPOLOGIES = ("full_mesh", "star")


@dataclass
class Debater:
    name: str
    # drift(question, peer_votes) -> the debater's next answer. peer_votes counts the
    # previous-round answers of the peers it reads: {answer: number of peers holding it}.
    drift: Callable[[str, Counter], str]


def majority(votes: Counter) -> str:
    """The most common answer. A tie goes to the alphabetically first answer, so the
    seating order of the debaters never decides."""
    return votes.most_common(1)[0][0]


def make_debater(name: str, bias: str, corrections: dict[str, str]) -> Debater:
    """A scripted debater with an opinion drift, as in the lesson.

    It holds corrections.get(question, bias) and switches to its peers' majority when that
    majority is neither its current answer nor its bias.
    """

    def drift(question: str, peer_votes: Counter) -> str:
        current = corrections.get(question, bias)
        if peer_votes:
            common = majority(peer_votes)
            if common != current and common != bias:
                return common
        return current

    return Debater(name=name, drift=drift)


def full_mesh_round(
    debaters: list[Debater], question: str, prior: dict[str, str]
) -> tuple[dict[str, str], int]:
    """Every debater reads every other debater's previous answer.

    Returns the new answers and the critique ops spent (N debaters reading N - 1 peers each).
    """
    new_answers: dict[str, str] = {}
    ops = 0
    for debater in debaters:
        votes = Counter(prior[d.name] for d in debaters if d.name != debater.name)
        new_answers[debater.name] = debater.drift(question, votes)
        ops += sum(votes.values())
    return new_answers, ops


def sparse_star_round(
    hub: Debater, spokes: list[Debater], question: str, prior: dict[str, str]
) -> tuple[dict[str, str], int]:
    """Star topology: every spoke reads only the hub; the hub reads no one.

    The lesson's count: a star with N = 5 and R = 3 costs 4 x 3 = 12 critique ops.
    """
    new_answers: dict[str, str] = {}
    ops = 0
    spoke_names = [s.name for s in spokes]
    new_answers[hub.name] = hub.drift(question, Counter(prior[n] for n in spoke_names))
    ops += len(spoke_names)
    for spoke in spokes:
        new_answers[spoke.name] = spoke.drift(question, Counter([prior[hub.name]]))
        ops += 1
    return new_answers, ops


def run_debate(
    debaters: list[Debater], question: str, rounds: int, topology: str
) -> tuple[str, int, int]:
    """Opening answers (no peers), then `rounds` critique rounds on "full_mesh" or "star"
    (debaters[0] is the hub).

    Returns (answer, converged_round, total_ops):
      answer          the majority of the final answers, ties as in majority();
      converged_round the first round from which every debater held the same answer through
                      the final round, or -1 when they still disagree at the end;
      total_ops       critique ops over all rounds.
    """
    if topology not in TOPOLOGIES:
        raise ValueError(f"topology must be one of {TOPOLOGIES}, got {topology!r}")
    prior: dict[str, str] = {}
    for debater in debaters:
        prior[debater.name] = debater.drift(question, Counter())
    total_ops = 0
    converged_round = -1
    hub, spokes = debaters[0], debaters[1:]
    for r in range(rounds):
        if topology == "full_mesh":
            new, ops = full_mesh_round(debaters, question, prior)
        else:
            new, ops = sparse_star_round(hub, spokes, question, prior)
        total_ops += ops
        if all(v == list(new.values())[0] for v in new.values()) and converged_round == -1:
            converged_round = r + 1
        prior = new
    return majority(Counter(prior.values())), converged_round, total_ops
