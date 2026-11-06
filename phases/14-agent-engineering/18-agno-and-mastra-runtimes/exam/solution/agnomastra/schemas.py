"""Typed workflow steps: can each step's output schema be handed to the next step's input schema?

Schemas are written as plain data:

    "string" | "number" | "integer" | "boolean"
    {"optional": S}                       the value may be missing (meaningful as an object field)
    {"array": S}                          a list of S
    {"union": [S1, S2, ...]}              any one of the members
    {"object": {field: S, ...}}           extra fields are allowed and ignored
    {"object": {...}, "strict": True}     extra fields are rejected
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

Schema = Any

PRIMITIVES = ("string", "number", "integer", "boolean")


@dataclass(frozen=True)
class Mismatch:
    path: str  # "$", "$.items[].price", ...
    reason: str


@dataclass(frozen=True)
class Step:
    name: str
    input: Schema
    output: Schema


@dataclass(frozen=True)
class Flow:
    """A workflow. A Flow can be a step of another Flow."""

    name: str
    steps: list[Union[Step, "Flow"]]


@dataclass(frozen=True)
class Break:
    producer: str  # qualified name of the step whose output does not fit
    consumer: str  # qualified name of the step whose input rejects it
    mismatch: Mismatch


def _kind(schema: Schema) -> str:
    if isinstance(schema, str) and schema in PRIMITIVES:
        return schema
    if isinstance(schema, dict):
        for key in ("optional", "array", "union", "object"):
            if key in schema:
                return key
    raise ValueError(f"not a schema: {schema!r}")


def first_mismatch(src: Schema, dst: Schema, path: str = "$") -> Mismatch | None:
    """The first place where a value of schema src would be rejected by schema dst, or None.

    - "integer" fits "number"; otherwise a primitive fits only the same primitive.
    - A union src fits when every member fits; this is checked before looking at a union dst.
      A non-union src fits a union dst when it fits at least one member.
    - An optional src fits only an optional dst; any src that fits S fits {"optional": S}.
    - Arrays fit when their items fit; the items' path is path + "[]".
    - Objects: the fields of dst are checked in dst's order, at path + "." + field. A field that
      dst requires must be in src and not optional there. Fields src has and dst lacks are fine,
      unless dst is strict: then the first of them, in src's order, is the mismatch.
    """
    sk, dk = _kind(src), _kind(dst)
    if sk == "optional":
        if dk != "optional":
            return Mismatch(path, "may be missing")
        return first_mismatch(src["optional"], dst["optional"], path)
    if dk == "optional":
        return first_mismatch(src, dst["optional"], path)
    if sk == "union":
        for member in src["union"]:
            found = first_mismatch(member, dst, path)
            if found is not None:
                return found
        return None
    if dk == "union":
        if any(first_mismatch(src, member, path) is None for member in dst["union"]):
            return None
        return Mismatch(path, "no member of the union accepts it")
    if sk != dk:
        if (sk, dk) == ("integer", "number"):
            return None
        return Mismatch(path, f"expected {dk}, got {sk}")
    if sk == "array":
        return first_mismatch(src["array"], dst["array"], path + "[]")
    if sk == "object":
        fields = src["object"]
        for name, want in dst["object"].items():
            here = f"{path}.{name}"
            if name not in fields:
                if _kind(want) == "optional":
                    continue
                return Mismatch(here, "missing")
            found = first_mismatch(fields[name], want, here)
            if found is not None:
                return found
        if dst.get("strict"):
            for name in fields:
                if name not in dst["object"]:
                    return Mismatch(f"{path}.{name}", "not allowed by a strict object")
    return None


def check_flow(flow: Flow) -> Break | None:
    """The first link in flow whose producer's output does not fit its consumer's input.

    A nested Flow takes the input of its first step and gives the output of its last step,
    looking through any depth of nesting. Links are checked in the order data crosses them:
    the link into a step comes before the links inside it. Steps are named by their qualified
    name, outermost flow first: "pipeline/enrich/score". The structure is checked before any
    link: an empty flow anywhere, or a flow that contains itself, raises ValueError.
    """
    def validate(current: Flow, open_flows: frozenset[int]) -> None:
        if id(current) in open_flows:
            raise ValueError(f"flow {current.name!r} contains itself")
        if not current.steps:
            raise ValueError(f"flow {current.name!r} has no steps")
        for step in current.steps:
            if isinstance(step, Flow):
                validate(step, open_flows | {id(current)})

    def leaf(step: Step | Flow, prefix: str, index: int) -> tuple[str, Step]:
        while isinstance(step, Flow):
            prefix, step = f"{prefix}{step.name}/", step.steps[index]
        return prefix + step.name, step

    def visit(current: Flow, prefix: str) -> Break | None:
        inner = f"{prefix}{current.name}/"
        for i, step in enumerate(current.steps):
            if i > 0:
                producer, out_step = leaf(current.steps[i - 1], inner, -1)
                consumer, in_step = leaf(step, inner, 0)
                mismatch = first_mismatch(out_step.output, in_step.input)
                if mismatch is not None:
                    return Break(producer, consumer, mismatch)
            if isinstance(step, Flow):
                found = visit(step, inner)
                if found is not None:
                    return found
        return None

    validate(flow, frozenset())
    return visit(flow, "")
