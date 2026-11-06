"""What a LoRA fine-tune trains, counted on a model's module tree.

A module tree mirrors the PyTorch module hierarchy:

- a dict with a "type" key is a layer, and its other keys are its parameters: each is a
  shape (a list of ints) or the dotted path of the parameter it is tied to;
- any other dict holds named submodules, and a list holds numbered ones (an nn.ModuleList).

Paths join the names with dots, e.g. "model.decoder.layers.0.encoder_attn.q_proj".
"""
from __future__ import annotations

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
    raise NotImplementedError
