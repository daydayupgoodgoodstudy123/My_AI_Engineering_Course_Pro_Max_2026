"""What a LoRA fine-tune trains, counted on a model's module tree.

A module tree mirrors the PyTorch module hierarchy:

- a dict with a "type" key is a layer, and its other keys are its parameters: each is a
  shape (a list of ints) or the dotted path of the parameter it is tied to;
- any other dict holds named submodules, and a list holds numbered ones (an nn.ModuleList).

Paths join the names with dots, e.g. "model.decoder.layers.0.encoder_attn.q_proj".
"""
from __future__ import annotations

import math
from fnmatch import fnmatchcase
from typing import NamedTuple


class LoraReport(NamedTuple):
    adapted: list[str]  # paths of the layers that get an adapter, in tree order
    trainable: int      # adapter parameters; the base model stays frozen
    total: int          # every parameter, adapters included, a tied parameter once


def lora_report(tree: dict, target_modules: list[str], rank: int = 16) -> LoraReport:
    """Put a rank-r LoRA adapter on every Linear layer a target matches, and count.

    Targets match the end of a module's path, the way PEFT matches a list of
    target_modules: a target's dotted names must equal the last names of the path, one
    name at a time. Here a name may also use shell wildcards (* and ?). So "q_proj"
    matches the q_proj of self-attention and of cross-attention alike, and
    "decoder.layers.*.fc?" matches the decoder's fc1 and fc2.
    An adapter on a Linear layer whose weight is [out, in] adds rank * (in + out)
    parameters; biases stay frozen.

    A target that matches no module, or matches a module that is not a Linear layer,
    raises ValueError.
    """
    if rank < 1:
        raise ValueError(f"rank must be at least 1, got {rank}")
    modules: list[tuple[str, object]] = []
    shapes: dict[str, list[int]] = {}
    ties: dict[str, str] = {}

    def walk(node: object, path: str) -> None:
        if path:
            modules.append((path, node))
        if isinstance(node, dict) and "type" in node:
            for name, value in node.items():
                if name == "type":
                    continue
                key = f"{path}.{name}"
                if isinstance(value, str):
                    ties[key] = value
                elif isinstance(value, list) and all(isinstance(d, int) for d in value):
                    shapes[key] = value
                else:
                    raise ValueError(f"parameter {key!r} is neither a shape nor a tie")
            return
        if isinstance(node, dict):
            children = list(node.items())
        elif isinstance(node, list):
            children = [(str(i), child) for i, child in enumerate(node)]
        else:
            raise ValueError(f"module {path!r} is neither a dict nor a list")
        for name, child in children:
            walk(child, f"{path}.{name}" if path else name)

    walk(tree, "")
    for key, target in ties.items():
        if target not in shapes:
            raise ValueError(f"{key!r} is tied to {target!r}, which is not a parameter")

    adapted: set[str] = set()
    for pattern in target_modules:
        names = pattern.split(".")
        hits = [(path, node) for path, node in modules if _matches(path.split("."), names)]
        if not hits:
            raise ValueError(f"target {pattern!r} matches no module")
        for path, node in hits:
            if not (isinstance(node, dict) and node.get("type") == "Linear"):
                raise ValueError(f"target {pattern!r} matches {path!r}, not a Linear layer")
            adapted.add(path)

    ordered = [path for path, _ in modules if path in adapted]
    trainable = 0
    for path in ordered:
        weight = f"{path}.weight"
        out_features, in_features = shapes[ties.get(weight, weight)]
        trainable += rank * (in_features + out_features)
    total = sum(math.prod(shape) for shape in shapes.values()) + trainable
    return LoraReport(ordered, trainable, total)


def _matches(path: list[str], names: list[str]) -> bool:
    return len(path) >= len(names) and all(
        fnmatchcase(part, name) for part, name in zip(path[len(path) - len(names):], names)
    )
