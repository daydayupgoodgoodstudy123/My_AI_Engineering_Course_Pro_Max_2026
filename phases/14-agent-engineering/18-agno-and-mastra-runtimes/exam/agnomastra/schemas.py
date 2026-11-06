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
    raise NotImplementedError


def check_flow(flow: Flow) -> Break | None:
    """The first link in flow whose producer's output does not fit its consumer's input.

    A nested Flow takes the input of its first step and gives the output of its last step,
    looking through any depth of nesting. Links are checked in the order data crosses them:
    the link into a step comes before the links inside it. Steps are named by their qualified
    name, outermost flow first: "pipeline/enrich/score". The structure is checked before any
    link: an empty flow anywhere, or a flow that contains itself, raises ValueError.
    """
    raise NotImplementedError
