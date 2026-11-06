"""The tool registry, and the lesson's sample tools."""
from __future__ import annotations

import ast
import operator
from typing import Any, Callable

from .messages import ToolCall


class ToolRegistry:
    """Tools the model can call by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def names(self) -> list[str]:
        return sorted(self._tools)

    def dispatch(self, call: ToolCall) -> Any:
        """Run one tool call and return what the tool returned.

        call.args are keyword arguments (a dict) or positional ones (a list, as ReAct text actions
        give them). A problem comes back as an observation string instead of an exception, so the
        model can read it and correct course:

            error: unknown tool 'name'           no tool has that name
            error: bad args for name: <why>      the arguments do not fit the tool's parameters
            error: <ExceptionType>: <message>    the tool raised while it ran
        """
        fn = self._tools.get(call.name)
        if fn is None:
            return f"error: unknown tool {call.name!r}"
        try:
            if isinstance(call.args, dict):
                return fn(**call.args)
            return fn(*call.args)
        except TypeError as e:
            return f"error: bad args for {call.name}: {e}"
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expr: str) -> str:
    """Evaluate numbers with + - * / and parentheses."""

    def value(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](value(node.left), value(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](value(node.operand))
        raise ValueError(f"unsupported expression {expr!r}")

    return str(value(ast.parse(expr, mode="eval").body))


class KVStore:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str:
        return self._store.get(key, f"missing:{key}")

    def set(self, key: str, value: str) -> str:
        self._store[key] = value
        return f"stored {key}"
