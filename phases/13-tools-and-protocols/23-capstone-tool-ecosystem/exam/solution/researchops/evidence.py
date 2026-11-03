"""Which claims a run proves, and what each one still lacks (Simulation versus production)."""
from __future__ import annotations

# The lesson's handoff table: every boundary and the evidence a real integration must produce.
BOUNDARIES: dict[str, tuple[str, ...]] = {
    "discovery": ("wire transcript", "deterministic order", "schema validation"),
    "authentication": ("issuer tests", "audience tests", "scope tests", "expiry tests", "failure tests"),
    "authorization": ("allow audit cases", "deny audit cases"),
    "search": ("source provenance", "ranking tests", "error tests"),
    "tasks": ("state-transition tests", "input tests", "cancellation tests", "recovery tests"),
    "delegation": ("contract tests", "timeout tests", "retry tests", "opacity tests"),
    "app": ("CSP tests", "permissions tests", "tool-call tests", "browser tests"),
    "telemetry": ("collector receipt", "trace-parent assertions"),
    "sandbox": ("escape tests", "egress tests", "secret tests", "resource-limit tests"),
}


def assess(claims: dict[str, list[str]], run: dict[str, dict]) -> dict[str, list[str]]:
    """Return, for every claim, the evidence this run still lacks; an empty list means proven locally.

    claims maps each claim to what it rests on: boundaries (the keys of BOUNDARIES) and other
    claims. A claim lacks everything the boundaries and claims it rests on lack.

    run maps a boundary to what this run did there: {"mode": "simulated"} or
    {"mode": "real", "evidence": [...]}. A boundary that run leaves out, or that was simulated,
    has none of its evidence: a green simulation validates the simulation only.

    Telemetry is judged at the receiver, from the spans its real entry lists under "received"
    ({"traceId", "spanId", "parentSpanId"}). "collector receipt" holds when the collector got any
    span. "trace-parent assertions" holds when the received spans form one tree: one trace id,
    one root (parentSpanId None), and every other span's parent among the received spans. A shared
    trace id alone does not prove parentage.

    Each missing item reads "<boundary>: <evidence>", listed once, in BOUNDARIES order. Claims
    come back in the order given. A name that is neither a boundary nor a claim, a boundary in run
    that BOUNDARIES does not know, and a claim that rests on itself, directly or through other
    claims, raise ValueError.
    """
    unknown = sorted(set(run) - set(BOUNDARIES))
    if unknown:
        raise ValueError(f"run names unknown boundaries: {unknown}")
    lacking = {boundary: _lacking(boundary, run.get(boundary)) for boundary in BOUNDARIES}
    rank = {
        (boundary, item): (i, j)
        for i, (boundary, items) in enumerate(BOUNDARIES.items())
        for j, item in enumerate(items)
    }
    done: dict[str, frozenset[tuple[str, str]]] = {}

    def needs(claim: str, path: tuple[str, ...]) -> frozenset[tuple[str, str]]:
        if claim in path:
            raise ValueError(f"claim rests on itself: {' -> '.join(path + (claim,))}")
        if claim not in done:
            missing: set[tuple[str, str]] = set()
            for name in claims[claim]:
                if name in BOUNDARIES:
                    missing |= {(name, item) for item in lacking[name]}
                elif name in claims:
                    missing |= needs(name, path + (claim,))
                else:
                    raise ValueError(f"{claim!r} rests on {name!r}, which is neither a boundary nor a claim")
            done[claim] = frozenset(missing)
        return done[claim]

    return {
        claim: [f"{boundary}: {item}" for boundary, item in sorted(needs(claim, ()), key=rank.__getitem__)]
        for claim in claims
    }


def _lacking(boundary: str, entry: dict | None) -> list[str]:
    required = BOUNDARIES[boundary]
    if entry is None or entry.get("mode") != "real":
        return list(required)
    if boundary == "telemetry":
        received = list(entry.get("received", []))
        held = set()
        if received:
            held.add("collector receipt")
        if _one_tree(received):
            held.add("trace-parent assertions")
    else:
        held = set(entry.get("evidence", []))
    return [item for item in required if item not in held]


def _one_tree(spans: list[dict]) -> bool:
    if not spans or len({span["traceId"] for span in spans}) != 1:
        return False
    ids = {span["spanId"] for span in spans}
    roots = [span for span in spans if span["parentSpanId"] is None]
    return len(roots) == 1 and all(
        span["parentSpanId"] in ids for span in spans if span["parentSpanId"] is not None
    )
