import asyncio
import copy
import csv
import io
import json
import time
from dataclasses import asdict

import pytest
from fcbridge.bridge import Bridge, ProviderError
from fcbridge.canonical import WEATHER, AssistantTurn, Call, Tool, ToolChoice, ToolResult, UserTurn
from fcbridge.limits import LimitError, check_depth, schema_depth
from fcbridge.probe import equivalence_probe
from fcbridge.render import render
from fcbridge.store import ConversationStore
from fcbridge.strict import strict_tool
from fcbridge.translate import parse_openai, to_gemini, tool_fields

OPENAPI_TYPES = ("STRING", "NUMBER", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT")


def openapi_problem(schema, path: str) -> str | None:
    """What Gemini's API would reject in a declaration's parameters (the OpenAPI 3.0 subset)."""
    if not isinstance(schema, dict):
        return f"{path}: expected a schema object, got {schema!r}"
    if "additionalProperties" in schema:
        return f"{path}: unknown field additionalProperties"
    if schema.get("type") not in OPENAPI_TYPES:
        return f"{path}.type: expected one of {', '.join(OPENAPI_TYPES)}, got {schema.get('type')!r}"
    if not isinstance(schema.get("nullable", False), bool):
        return f"{path}.nullable: expected true or false"
    children = [(f"{path}.properties.{name}", sub) for name, sub in schema.get("properties", {}).items()]
    if "items" in schema:
        children.append((f"{path}.items", schema["items"]))
    for child_path, child in children:
        problem = openapi_problem(child, child_path)
        if problem:
            return problem
    return None


def request_problem(provider: str, request: dict) -> str | None:
    """What the provider's API would reject in a request body, or None if it would accept it."""
    if provider == "openai":
        names = {tool["function"]["name"] for tool in request["tools"]}
        choice = request.get("tool_choice", "auto")
        if choice in ("auto", "none", "required"):
            return None
        if isinstance(choice, dict) and choice.get("type") == "function" and choice["function"].get("name") in names:
            return None
        return f"tool_choice: unsupported value {choice!r}"
    if provider == "anthropic":
        names = {tool["name"] for tool in request["tools"]}
        choice = request.get("tool_choice", {"type": "auto"})
        if not isinstance(choice, dict):
            return f"tool_choice: expected an object, got {choice!r}"
        if choice.get("type") not in ("auto", "any", "tool", "none"):
            return f"tool_choice.type: {choice.get('type')!r} is not one of 'auto', 'any', 'tool', 'none'"
        if choice["type"] == "tool" and choice.get("name") not in names:
            return f"tool_choice.name: {choice.get('name')!r} is not a declared tool"
        return None
    tools = request["tools"]
    if len(tools) != 1 or list(tools[0]) != ["functionDeclarations"]:
        return "tools: declare every function in one functionDeclarations list"
    for i, declaration in enumerate(tools[0]["functionDeclarations"]):
        problem = openapi_problem(declaration["parameters"], f"functionDeclarations[{i}].parameters")
        if problem:
            return problem
    mode = request["tool_config"]["function_calling_config"]["mode"]
    if mode not in ("AUTO", "ANY", "NONE"):
        return f"tool_config.function_calling_config.mode: unsupported value {mode!r}"
    return None


class FakeProvider:
    """A scripted provider. It checks each request the way its API would, waits `delay` seconds,
    then answers with the next reply of its script, raising it if the reply is an exception."""

    def __init__(self, name: str, *replies, delay: float = 0.0) -> None:
        self.name = name
        self.replies = list(replies)
        self.delay = delay
        self.requests: list[dict] = []
        self.finished = False
        self.cancelled = False

    async def complete(self, request: dict) -> dict:
        problem = request_problem(self.name, request)
        if problem:
            raise ProviderError(f"{self.name} rejected the request: 400 {problem}")
        self.requests.append(request)
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        self.finished = True
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)


def openai_reply(*calls: tuple, refusal: str | None = None) -> dict:
    """A Chat Completions reply. Each call is (id, name, arguments text)."""
    message: dict = {"role": "assistant", "content": None}
    if calls:
        message["tool_calls"] = [
            {"id": i, "type": "function", "function": {"name": n, "arguments": a}} for i, n, a in calls
        ]
    if refusal is not None:
        message["refusal"] = refusal
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def anthropic_reply(text: str | None, *calls: tuple) -> dict:
    """A Messages reply. Each call is (id, name, input)."""
    content = [{"type": "text", "text": text}] if text else []
    content += [{"type": "tool_use", "id": i, "name": n, "input": a} for i, n, a in calls]
    return {"id": "msg_01", "type": "message", "role": "assistant", "content": content, "stop_reason": "tool_use"}


def gemini_reply(*calls: tuple) -> dict:
    """A generateContent reply. Each call is (id, name, args)."""
    parts = [{"functionCall": {"id": i, "name": n, "args": a}} for i, n, a in calls]
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}]}


CLOCK = Tool(
    "get_time",
    "Use when the user asks for the current time.",
    {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
)

FLEET = Tool(
    "find_vehicle",
    "Use when the user asks where a company vehicle is.",
    {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["car", "van", "bike"]},
            "plate": {"type": ["null", "string"]},
        },
        "required": ["type", "plate"],
        "additionalProperties": False,
    },
)


def nested(levels: int) -> dict:
    """An object schema `levels` objects deep: each object has a name and holds the next one."""
    schema: dict = {"type": "object", "properties": {"name": {"type": "string"}}}
    for _ in range(levels - 1):
        schema = {"type": "object", "properties": {"name": {"type": "string"}, "child": schema}}
    return schema


def folders(levels: int) -> dict:
    """A folder tree `levels` folders deep: each folder lists its files and its sub-folders."""
    files = {"type": "array", "items": {"type": "string"}}
    schema: dict = {"type": "object", "properties": {"name": {"type": "string"}, "files": files}}
    for _ in range(levels - 1):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "files": files, "folders": {"type": "array", "items": schema}},
        }
    return schema


@pytest.mark.skip("Part 1")
def test_edge_translators() -> None:
    """One question, three providers: every request is accepted and every reply parses to the same call."""
    city = {"city": "Bengaluru", "units": "celsius"}
    bridge = Bridge(
        {
            "openai": FakeProvider(
                "openai",
                openai_reply(("call_abc123", "get_weather", '{"city":"Bengaluru","units":"celsius"}')),
                openai_reply(("call_def456", "get_time", "")),
            ),
            "anthropic": FakeProvider("anthropic", anthropic_reply("Looking that up.", ("toolu_xyz789", "get_weather", city))),
            "gemini": FakeProvider("gemini", gemini_reply(("fc-9a3d", "get_weather", city))),
        }
    )
    tools = [WEATHER, FLEET, CLOCK]
    asked = {
        provider: asyncio.run(bridge.ask(provider, tools, "Weather in Bengaluru?", ToolChoice("required")))
        for provider in ("openai", "anthropic", "gemini")
    }
    assert asked == {
        "openai": [Call("call_abc123", "get_weather", city, '{"city":"Bengaluru","units":"celsius"}')],
        "anthropic": [Call("toolu_xyz789", "get_weather", city)],
        "gemini": [Call("fc-9a3d", "get_weather", city)],
    }, "the same call, whichever provider made it"
    anthropic, gemini = (bridge.providers[p].requests[0] for p in ("anthropic", "gemini"))
    assert (anthropic["tool_choice"], gemini["tool_config"]) == (
        {"type": "any"},
        {"function_calling_config": {"mode": "ANY"}},
    ), "required means the model must call a tool: any for Anthropic, ANY for Gemini"

    params = to_gemini(FLEET)["functionDeclarations"][0]["parameters"]
    kind, plate = params["properties"]["type"], params["properties"]["plate"]
    assert (params["type"], kind["type"], kind["enum"], plate["type"], plate.get("nullable")) == (
        "OBJECT",
        "STRING",
        ["car", "van", "bike"],
        "STRING",
        True,
    ), "one upper-case type plus nullable: true; a property may be called type"
    with pytest.raises(ValueError):
        to_gemini(Tool("lookup", "Use when the user gives a key.", {"type": "object", "properties": {"key": {"type": ["string", "integer"]}}}))

    assert asyncio.run(bridge.ask("openai", tools, "What time is it?", ToolChoice("force", "get_time"))) == [
        Call("call_def456", "get_time", {}, "")
    ], "empty arguments text means no arguments"
    with pytest.raises(ValueError):
        parse_openai(openai_reply(("call_bad", "get_weather", '{"city": "Bengaluru",}')))

    plan = Tool("plan_trip", "Use when the user wants an itinerary.", nested(8))
    expedition = Tool("plan_expedition", "Use when the user plans a multi-stage expedition.", nested(12))
    assert [schema_depth(t.input_schema) for t in (WEATHER, plan, expedition)] == [1, 8, 12], "report the exact depth"
    with pytest.raises(LimitError, match="openai"):
        check_depth("openai", [WEATHER, plan])
    check_depth("anthropic", [WEATHER, plan])
    with pytest.raises(LimitError, match="anthropic"):
        check_depth("anthropic", [expedition])
    check_depth("gemini", [expedition])

    tree = folders(10)
    start = time.perf_counter()
    depth = schema_depth(tree)
    elapsed = time.perf_counter() - start
    assert depth == 10, "report the exact depth"
    assert elapsed < 0.03, "the depth check runs before every request: it must be fast on deep schemas"


SAO_PAULO = {"city": "São Paulo", "max_price": 180, "currency": "BRL"}
GEMINI_ID = "8f14e45f-ceea-4672-a8b1-2c3d4e5f6a7b"
RATE_LIMITED = {"error": "429 for account ops@example.com, retry in 20 s"}
HOTELS_FOUND = {"hotels": [{"name": "Ibis Paulista", "price": 140.0, "booking_ref": 18446744073709551617}]}

TRIP = [
    UserTurn("Is São Paulo or Tōkyō warmer right now? Then find me a hotel under 180 there."),
    AssistantTurn(
        "openai",
        None,
        [
            Call("call_Ww9mQ4", "get_weather", {"city": "São Paulo", "units": "celsius"}, '{"city": "S\\u00E3o Paulo" ,"units":"celsius"}'),
            Call("call_Hk2pR7", "get_weather", {"city": "Tōkyō", "units": None}, '{"city":"Tōkyō","units":null}'),
        ],
    ),
    ToolResult("call_Ww9mQ4", "get_weather", {"temp_c": 24.5, "summary": "humid"}),
    ToolResult("call_Hk2pR7", "get_weather", {"temp_c": 9, "summary": "clear"}),
    AssistantTurn(
        "anthropic",
        "São Paulo is warmer. Looking for hotels.",
        [Call("toolu_01A09q90qw90lq917835lq9", "search_hotels", SAO_PAULO)],
    ),
    ToolResult("toolu_01A09q90qw90lq917835lq9", "search_hotels", RATE_LIMITED, is_error=True),
    AssistantTurn("gemini", None, [Call(GEMINI_ID, "search_hotels", SAO_PAULO)]),
    ToolResult(GEMINI_ID, "search_hotels", HOTELS_FOUND),
    AssistantTurn("gemini", "Ibis Paulista has a room for 140 BRL a night.", []),
]

STANDUP = [
    UserTurn("What time is it?"),
    AssistantTurn("openai", None, [Call("call_q2Lr7", "get_time", {}, "")]),
    ToolResult("call_q2Lr7", "get_time", {"utc": "2026-11-02T09:00:00Z"}),
    AssistantTurn("openai", "It is 09:00 UTC.", []),
    UserTurn("And in Tōkyō?"),
    AssistantTurn("openai", "It is 18:00 in Tōkyō.", []),
]


def calls_in(turns: list, *providers: str) -> list[Call]:
    return [call for t in turns if isinstance(t, AssistantTurn) and t.provider in providers for call in t.calls]


def exact(turns: list) -> str:
    """The turns as JSON text. Unlike ==, it tells True from 1, 140.0 from 140, and one key order from another."""
    return json.dumps([[type(t).__name__, asdict(t)] for t in turns], ensure_ascii=False)


@pytest.mark.skip("Part 2")
def test_conversation_store(tmp_path) -> None:
    """Conversations come back from the store exactly as each provider sent them, in order."""
    path = str(tmp_path / "conversations.sqlite3")
    store = ConversationStore(path)
    assert [store.append("trip", turn) for turn in TRIP[:4]] == [0, 1, 2, 3], "append returns positions 0, 1, 2, ..."
    assert [store.append("standup", turn) for turn in STANDUP] == [0, 1, 2, 3, 4, 5], "positions count from 0 in each conversation"
    assert [store.append("trip", turn) for turn in TRIP[4:]] == [4, 5, 6, 7, 8]
    with pytest.raises(ValueError):
        store.append("trip", AssistantTurn("mistral", "Bonjour", []))
    store.close()

    store = ConversationStore(path)
    trip, standup = store.turns("trip"), store.turns("standup")
    assert (len(trip), len(standup)) == (len(TRIP), len(STANDUP)), "a reopened store sees every turn"
    assert [c.id for c in calls_in(trip, "openai")] == ["call_Ww9mQ4", "call_Hk2pR7"], (
        "parallel calls come back in the order they were made"
    )
    assert [c.raw_arguments for c in calls_in(trip + standup, "openai")] == [
        '{"city": "S\\u00E3o Paulo" ,"units":"celsius"}',
        '{"city":"Tōkyō","units":null}',
        "",
    ], "OpenAI's arguments text comes back byte for byte"
    assert [(c.args, c.raw_arguments) for c in calls_in(trip, "anthropic", "gemini")] == [(SAO_PAULO, None)] * 2, (
        "Anthropic and Gemini sent objects, not text"
    )
    assert trip == TRIP and standup == STANDUP, "every turn round-trips"
    assert exact(trip) == exact(TRIP) and exact(standup) == exact(STANDUP), (
        "turns round-trip exactly as JSON: is_error is still a bool, keys keep their order"
    )
    assert store.turns("weekend") == [], "an unknown conversation has no turns"

    redacted = ToolResult("toolu_01A09q90qw90lq917835lq9", "search_hotels", {"error": "429 for account [redacted], retry in 20 s"}, is_error=True)
    store.replace("trip", 5, redacted)
    assert store.append("trip", UserTurn("Book it.")) == 9
    with pytest.raises(KeyError):
        store.replace("trip", 10, redacted)
    store.close()

    store = ConversationStore(path)
    assert store.turns("trip") == TRIP[:5] + [redacted] + TRIP[6:] + [UserTurn("Book it.")], (
        "a replaced turn keeps its place"
    )
    assert store.turns("standup") == STANDUP, "replace changes only its own conversation"
    store.close()


HOTELS = Tool(
    "search_hotels",
    "Use when the user wants hotels in a city under a nightly price.",
    {
        "type": "object",
        "properties": {"city": {"type": "string"}, "max_price": {"type": "integer"}, "currency": {"type": "string"}},
        "required": ["city", "max_price", "currency"],
        "additionalProperties": False,
    },
)

NOTES = Tool(
    "save_note",
    "Use when the user asks to keep a summary for later.",
    {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False},
)


def text(value) -> str:
    return json.dumps(value, ensure_ascii=False)


OPENAI_MESSAGES = [
    {"role": "user", "content": TRIP[0].text},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "call_Ww9mQ4", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "S\\u00E3o Paulo" ,"units":"celsius"}'}},
            {"id": "call_Hk2pR7", "type": "function", "function": {"name": "get_weather", "arguments": '{"city":"Tōkyō","units":null}'}},
        ],
    },
    {"role": "tool", "tool_call_id": "call_Ww9mQ4", "content": text({"temp_c": 24.5, "summary": "humid"})},
    {"role": "tool", "tool_call_id": "call_Hk2pR7", "content": text({"temp_c": 9, "summary": "clear"})},
    {
        "role": "assistant",
        "content": "São Paulo is warmer. Looking for hotels.",
        "tool_calls": [
            {"id": "toolu_01A09q90qw90lq917835lq9", "type": "function", "function": {"name": "search_hotels", "arguments": text(SAO_PAULO)}}
        ],
    },
    {"role": "tool", "tool_call_id": "toolu_01A09q90qw90lq917835lq9", "content": text(RATE_LIMITED)},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": GEMINI_ID, "type": "function", "function": {"name": "search_hotels", "arguments": text(SAO_PAULO)}}],
    },
    {"role": "tool", "tool_call_id": GEMINI_ID, "content": text(HOTELS_FOUND)},
    {"role": "assistant", "content": "Ibis Paulista has a room for 140 BRL a night."},
]

ANTHROPIC_MESSAGES = [
    {"role": "user", "content": TRIP[0].text},
    {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "call_Ww9mQ4", "name": "get_weather", "input": {"city": "São Paulo", "units": "celsius"}},
            {"type": "tool_use", "id": "call_Hk2pR7", "name": "get_weather", "input": {"city": "Tōkyō", "units": None}},
        ],
    },
    {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_Ww9mQ4", "content": text({"temp_c": 24.5, "summary": "humid"})},
            {"type": "tool_result", "tool_use_id": "call_Hk2pR7", "content": text({"temp_c": 9, "summary": "clear"})},
        ],
    },
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "São Paulo is warmer. Looking for hotels."},
            {"type": "tool_use", "id": "toolu_01A09q90qw90lq917835lq9", "name": "search_hotels", "input": SAO_PAULO},
        ],
    },
    {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "toolu_01A09q90qw90lq917835lq9", "content": text(RATE_LIMITED), "is_error": True}],
    },
    {"role": "assistant", "content": [{"type": "tool_use", "id": GEMINI_ID, "name": "search_hotels", "input": SAO_PAULO}]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": GEMINI_ID, "content": text(HOTELS_FOUND)}]},
    {"role": "assistant", "content": [{"type": "text", "text": "Ibis Paulista has a room for 140 BRL a night."}]},
]

GEMINI_CONTENTS = [
    {"role": "user", "parts": [{"text": TRIP[0].text}]},
    {
        "role": "model",
        "parts": [
            {"functionCall": {"id": "call_Ww9mQ4", "name": "get_weather", "args": {"city": "São Paulo", "units": "celsius"}}},
            {"functionCall": {"id": "call_Hk2pR7", "name": "get_weather", "args": {"city": "Tōkyō", "units": None}}},
        ],
    },
    {
        "role": "user",
        "parts": [
            {"functionResponse": {"id": "call_Ww9mQ4", "name": "get_weather", "response": {"temp_c": 24.5, "summary": "humid"}}},
            {"functionResponse": {"id": "call_Hk2pR7", "name": "get_weather", "response": {"temp_c": 9, "summary": "clear"}}},
        ],
    },
    {
        "role": "model",
        "parts": [
            {"text": "São Paulo is warmer. Looking for hotels."},
            {"functionCall": {"id": "toolu_01A09q90qw90lq917835lq9", "name": "search_hotels", "args": SAO_PAULO}},
        ],
    },
    {
        "role": "user",
        "parts": [{"functionResponse": {"id": "toolu_01A09q90qw90lq917835lq9", "name": "search_hotels", "response": RATE_LIMITED}}],
    },
    {"role": "model", "parts": [{"functionCall": {"id": GEMINI_ID, "name": "search_hotels", "args": SAO_PAULO}}]},
    {"role": "user", "parts": [{"functionResponse": {"id": GEMINI_ID, "name": "search_hotels", "response": HOTELS_FOUND}}]},
    {"role": "model", "parts": [{"text": "Ibis Paulista has a room for 140 BRL a night."}]},
]


def limit_problem(provider: str, tools: list, conversation: list) -> str | None:
    """render's LimitError message, or None when the request is within the provider's limits."""
    try:
        render(provider, tools, conversation, ToolChoice("auto"))
    except LimitError as exc:
        return str(exc)
    return None


def note_from_gemini(summary: str) -> list:
    """Two notes Gemini saved in one turn, in a conversation that now continues on another provider."""
    return [
        UserTurn("Summarise the reviews and keep the summary, and a one-line version too."),
        AssistantTurn(
            "gemini",
            None,
            [
                Call("2c5d7a1e-9b3f-4e8a-b6d0-1f2e3a4b5c6d", "save_note", {"summary": summary}),
                Call("5e8f0a2c-7d4b-4f1e-9a3c-6b5d4e3f2a1b", "save_note", {"summary": "Mostly positive."}),
            ],
        ),
    ]


@pytest.mark.skip("Part 3")
def test_render_requests(tmp_path) -> None:
    """One canonical conversation renders into each provider's request, within each provider's limits."""
    tools = [WEATHER, HOTELS]
    auto = ToolChoice("auto")

    openai = render("openai", tools, TRIP, auto)
    sent = [call["function"]["arguments"] for m in openai["messages"] for call in m.get("tool_calls") or []]
    assert all(isinstance(arguments, str) for arguments in sent), "OpenAI takes the arguments as JSON text"
    assert sent[:2] == [call.raw_arguments for call in TRIP[1].calls], "OpenAI's own arguments text goes back unchanged"
    assert sent[2:] == [text(SAO_PAULO)] * 2, "a call from another provider goes to OpenAI as json_text(args)"
    assert [m["role"] for m in openai["messages"]] == ["user", "assistant", "tool", "tool"] + ["assistant", "tool"] * 2 + [
        "assistant"
    ], "OpenAI takes one tool message per result"
    assert openai == {**tool_fields("openai", tools, auto), "messages": OPENAI_MESSAGES}, (
        "OpenAI's request, message by message; a turn without calls has no tool_calls key"
    )
    standup = render("openai", [CLOCK], STANDUP, auto)
    assert standup["messages"][1]["tool_calls"][0]["function"]["arguments"] == "", (
        "an empty arguments text goes back unchanged too"
    )

    anthropic = render("anthropic", tools, TRIP, auto)
    assert [m["role"] for m in anthropic["messages"]] == ["user", "assistant"] * 4, (
        "Anthropic takes all the results of one turn in one user message"
    )
    used = [b.get("input") for m in anthropic["messages"][1::2] for b in m["content"] if b.get("type") == "tool_use"]
    assert all(isinstance(value, dict) for value in used), "Anthropic's input is the arguments object, whoever made the call"
    assert anthropic == {**tool_fields("anthropic", tools, auto), "messages": ANTHROPIC_MESSAGES}, (
        "Anthropic's request, block by block: text before tool_use, is_error on a failed result"
    )

    gemini = render("gemini", tools, TRIP, auto)
    assert [c["role"] for c in gemini["contents"]] == ["user", "model"] * 4, (
        "Gemini's turns are user and model, with all the results of one turn in one user content"
    )
    assert gemini == {**tool_fields("gemini", tools, auto), "contents": GEMINI_CONTENTS}, (
        "Gemini's request, part by part: functionCall and functionResponse carry the call's id and objects"
    )

    many = [Tool(f"job_{i:03d}", f"Use for batch job {i}.", {"type": "object", "properties": {}}) for i in range(129)]
    for provider, cap in (("openai", 128), ("anthropic", 64), ("gemini", 64)):
        assert limit_problem(provider, many[:cap], TRIP[:1]) is None, f"{cap} tools is within {provider}'s limit"
        assert provider in (limit_problem(provider, many[: cap + 1], TRIP[:1]) or ""), (
            "one tool too many raises a LimitError that names the provider"
        )
    for provider, cap in (("openai", 5), ("anthropic", 10)):
        plan = [Tool("plan_trip", "Use when the user wants an itinerary.", nested(cap))]
        assert limit_problem(provider, plan, TRIP[:1]) is None, f"{cap} levels deep is within {provider}'s limit"
        deeper = [Tool("plan_trip", "Use when the user wants an itinerary.", nested(cap + 1))]
        assert provider in (limit_problem(provider, deeper, TRIP[:1]) or ""), (
            "render checks the schema depth too, against each provider's limit"
        )

    exactly = "大" * 2725 + "ab"  # as json_text: 8192 bytes of UTF-8, 2742 characters
    assert limit_problem("openai", [NOTES], note_from_gemini(exactly)) is None, (
        "8192 bytes of UTF-8 is within OpenAI's limit"
    )
    assert "openai" in (limit_problem("openai", [NOTES], note_from_gemini(exactly + "c")) or ""), (
        "the limit counts UTF-8 bytes, not characters"
    )
    assert limit_problem("anthropic", [NOTES], note_from_gemini(exactly + "c")) is None, (
        "only OpenAI caps the arguments text"
    )

    path = str(tmp_path / "trip.sqlite3")
    store = ConversationStore(path)
    for turn in TRIP:
        store.append("trip", turn)
    store.close()
    store = ConversationStore(path)
    stored = store.turns("trip")
    store.close()
    for provider in ("openai", "anthropic", "gemini"):
        assert json.dumps(render(provider, tools, stored, auto)) == json.dumps(render(provider, tools, TRIP, auto)), (
            "a stored conversation renders exactly like the original"
        )


DC = {"city": "Washington, D.C.", "units": "celsius"}
GEMINI_DC = "c0ffee00-1d2e-4f5a-8b9c-0d1e2f3a4b5c"


def records(chunks: list[str]) -> list[dict]:
    """Parse the probe's output with the csv module, checking that each chunk is one whole record
    and that only ok records fill in a call."""
    assert chunks and next(csv.reader(io.StringIO(chunks[0])), None) == ["provider", "call_id", "name", "arguments_json", "status"], (
        "the report starts with its header"
    )
    for chunk in chunks:
        assert chunk.endswith("\n") and len(list(csv.reader(io.StringIO(chunk)))) == 1, "each chunk is one whole CSV record"
    rows = list(csv.DictReader(io.StringIO("".join(chunks))))
    assert all(None not in row and None not in row.values() for row in rows), (
        "every record has the header's five fields: quote fields that hold commas or quotes"
    )
    assert all(r["call_id"] == r["name"] == r["arguments_json"] == "" for r in rows if r["status"] != "ok"), (
        "error, timeout and summary records leave call_id, name and arguments_json empty"
    )
    return rows


def probe(fakes: dict, timeout_s: float = 5.0, watch: str = "openai") -> tuple[list[dict], list[bool], float, dict]:
    """Run the probe once. Returns its records, whether `watch` had finished as each record came,
    the time taken, and which providers had been cancelled by the time the report ended."""

    async def run():
        chunks, finished = [], []
        start = time.perf_counter()
        async for chunk in equivalence_probe(
            Bridge(fakes), [WEATHER], "Weather in Washington, D.C.?", ToolChoice("force", "get_weather"), timeout_s=timeout_s
        ):
            chunks.append(chunk)
            finished.append(fakes[watch].finished)
        elapsed = time.perf_counter() - start
        await asyncio.sleep(0)
        return chunks, finished, elapsed, {name: fake.cancelled for name, fake in fakes.items()}

    chunks, finished, elapsed, cancelled = asyncio.run(run())
    return records(chunks), finished[1:], elapsed, cancelled


@pytest.mark.skip("Part 4")
def test_equivalence_probe() -> None:
    """The same question goes to every provider at once; each reply is reported as soon as it arrives."""
    fakes = {
        "openai": FakeProvider("openai", openai_reply(("call_7Gm2", "get_weather", '{"units":"celsius","city":"Washington, D.C."}')), delay=0.02),
        "anthropic": FakeProvider("anthropic", anthropic_reply(None, ("toolu_01Wx", "get_weather", DC)), delay=0.5),
        "gemini": FakeProvider("gemini", gemini_reply((GEMINI_DC, "get_weather", DC))),
    }
    rows, slow_done, _, _ = probe(fakes, watch="anthropic")
    assert [r["provider"] for r in rows] == ["gemini", "openai", "anthropic", "equivalence"], (
        "records come in the order the replies arrive"
    )
    assert slow_done[:2] == [False, False], "report each reply as soon as it arrives"
    assert [(r["call_id"], r["name"], r["status"]) for r in rows[:3]] == [
        (GEMINI_DC, "get_weather", "ok"),
        ("call_7Gm2", "get_weather", "ok"),
        ("toolu_01Wx", "get_weather", "ok"),
    ]
    assert [json.loads(r["arguments_json"]) for r in rows[:3]] == [DC] * 3, "arguments_json is the call's arguments as JSON"
    assert rows[3] == {"provider": "equivalence", "call_id": "", "name": "", "arguments_json": "", "status": "same"}, (
        "the summary compares the tools and the parsed arguments, not ids or text"
    )

    fakes = {
        "openai": FakeProvider("openai", openai_reply(refusal="I can't help with that.")),
        "anthropic": FakeProvider(
            "anthropic", anthropic_reply(None, ("toolu_01Wy", "get_weather", {"city": "Washington, D.C.", "units": "fahrenheit"})), delay=0.02
        ),
        "gemini": FakeProvider("gemini", gemini_reply((GEMINI_DC, "get_weather", DC)), delay=0.04),
    }
    rows, _, _, _ = probe(fakes)
    assert rows[0] == {"provider": "openai", "call_id": "", "name": "", "arguments_json": "", "status": "error"}, (
        "a reply without a call is an error record"
    )
    assert [(r["provider"], r["status"]) for r in rows[1:]] == [("anthropic", "ok"), ("gemini", "ok"), ("equivalence", "different")], (
        "two answers that disagree make the probe different"
    )

    fakes = {
        "openai": FakeProvider("openai", openai_reply(("call_8Hn3", "get_weather", '{"city": "Washington, D.C.",}')), delay=0.02),
        "anthropic": FakeProvider("anthropic", anthropic_reply(None, ("toolu_01Wz", "get_weather", DC)), delay=2.0),
        "gemini": FakeProvider("gemini", ProviderError("gemini: 429 RESOURCE_EXHAUSTED")),
    }
    rows, _, elapsed, cancelled = probe(fakes, timeout_s=0.3)
    assert [(r["provider"], r["status"]) for r in rows] == [
        ("gemini", "error"),
        ("openai", "error"),
        ("anthropic", "timeout"),
        ("equivalence", "incomplete"),
    ], "every failure gets its own record, and a hung provider times out"
    assert elapsed < 1.5, "a provider that does not answer within timeout_s is cut off"
    assert cancelled["anthropic"], "the timed-out request is cancelled, not left running"

    fakes = {
        "openai": FakeProvider("openai", openai_reply(("call_9Jp4", "get_weather", '{"city":"Washington, D.C.","units":"celsius"}'))),
        "anthropic": FakeProvider(
            "anthropic",
            anthropic_reply(None, ("toolu_01Xa", "get_weather", DC), ("toolu_01Xb", "get_weather", {"city": "Baltimore", "units": "celsius"})),
            delay=0.02,
        ),
        "gemini": FakeProvider("gemini", gemini_reply((GEMINI_DC, "get_current_weather", DC)), delay=0.04),
    }
    rows, _, _, _ = probe(fakes)
    assert [(r["provider"], r["status"]) for r in rows] == [
        ("openai", "ok"),
        ("anthropic", "error"),
        ("gemini", "ok"),
        ("equivalence", "different"),
    ], "a reply with several calls is an error; a different tool name makes the probe different"

    fakes = {
        "openai": FakeProvider("openai", openai_reply(("call_5Kt8", "get_weather", '{"city":"Washington, D.C.","units":"celsius"}'))),
        "anthropic": FakeProvider("anthropic", anthropic_reply(None, ("toolu_01Xc", "get_weather", DC)), delay=0.4),
        "gemini": FakeProvider("gemini", gemini_reply((GEMINI_DC, "get_weather", DC)), delay=0.2),
    }
    rows, _, _, _ = probe(fakes, timeout_s=0.3)
    assert [(r["provider"], r["status"]) for r in rows[:3]] == [("openai", "ok"), ("gemini", "ok"), ("anthropic", "timeout")], (
        "timeout_s counts from the start, for each provider"
    )
    assert rows[3]["status"] == "incomplete", "same needs an answer from every provider"


ADDRESS = {
    "type": "object",
    "properties": {"street": {"type": "string"}, "city": {"type": "string"}, "postcode": {"type": ["string", "null"]}},
    "required": ["street", "city"],
}

ORDER = Tool(
    "place_order",
    "Use when the user confirms an order.",
    {
        "type": "object",
        "properties": {
            "customer": {"type": "string"},
            "billing": {"$ref": "#/$defs/address"},
            "shipping": {"$ref": "#/$defs/address"},
            "lines": {"type": "array", "items": {"$ref": "#/$defs/line"}},
            "payment": {
                "anyOf": [
                    {"type": "object", "properties": {"card_token": {"type": "string"}}, "required": ["card_token"]},
                    {"type": "object", "properties": {"iban": {"type": "string"}, "reference": {"type": "string"}}, "required": ["iban"]},
                ]
            },
            "speed": {"type": "string", "enum": ["standard", "express"]},
            "gift_note": {"type": "string"},
        },
        "required": ["customer", "billing", "lines"],
        "$defs": {
            "address": ADDRESS,
            "line": {
                "type": "object",
                "properties": {"sku": {"type": "string"}, "quantity": {"type": "integer"}, "ship_to": {"$ref": "#/$defs/address"}},
                "required": ["sku", "quantity"],
            },
        },
    },
    strict=False,  # as written, with $refs and optional properties, strict mode would reject it
)


def strict_address(nullable: bool) -> dict:
    return {
        "type": ["object", "null"] if nullable else "object",
        "properties": {"street": {"type": "string"}, "city": {"type": "string"}, "postcode": {"type": ["string", "null"]}},
        "required": ["street", "city", "postcode"],
        "additionalProperties": False,
    }


STRICT_ORDER = {
    "type": "object",
    "properties": {
        "customer": {"type": "string"},
        "billing": strict_address(False),
        "shipping": strict_address(True),
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"sku": {"type": "string"}, "quantity": {"type": "integer"}, "ship_to": strict_address(True)},
                "required": ["sku", "quantity", "ship_to"],
                "additionalProperties": False,
            },
        },
        "payment": {
            "anyOf": [
                {"type": "object", "properties": {"card_token": {"type": "string"}}, "required": ["card_token"], "additionalProperties": False},
                {
                    "type": "object",
                    "properties": {"iban": {"type": "string"}, "reference": {"type": ["string", "null"]}},
                    "required": ["iban", "reference"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        },
        "speed": {"type": ["string", "null"], "enum": ["standard", "express", None]},
        "gift_note": {"type": ["string", "null"]},
    },
    "required": ["customer", "billing", "shipping", "lines", "payment", "speed", "gift_note"],
    "additionalProperties": False,
}


def objects_in(schema: dict) -> list[dict]:
    """Every object schema in a compiled schema, the root included."""
    kind = schema.get("type", [])
    found = [schema] if "object" in ([kind] if isinstance(kind, str) else kind) else []
    children = list(schema.get("properties", {}).values()) + list(schema.get("anyOf", []))
    if isinstance(schema.get("items"), dict):
        children.append(schema["items"])
    for child in children:
        found += objects_in(child)
    return found


def org_chart(levels: int) -> Tool:
    """A tool whose $defs nest `levels` objects deep once inlined; before inlining it is 1 deep."""
    defs = {
        f"level{i}": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "reports": {"$ref": f"#/$defs/level{i + 1}"}},
            "required": ["name"],
        }
        for i in range(1, levels - 1)
    }
    defs[f"level{levels - 1}"] = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    schema = {"type": "object", "properties": {"ceo": {"$ref": "#/$defs/level1"}}, "required": ["ceo"], "$defs": defs}
    return Tool("org_chart", "Use when the user asks who reports to whom.", schema)


@pytest.mark.skip("Part 5")
def test_strict_compiler() -> None:
    """A schema with shared $defs compiles to the form OpenAI strict mode accepts."""
    before = copy.deepcopy(ORDER.input_schema)
    compiled = strict_tool(ORDER)
    schema = compiled.input_schema
    assert ORDER.input_schema == before, "strict_tool leaves its input alone"
    assert (compiled.name, compiled.description, compiled.strict) == (ORDER.name, ORDER.description, True), (
        "the same tool, marked strict"
    )
    assert "$defs" not in schema and "$ref" not in json.dumps(schema), "strict mode allows no $ref"

    objects = objects_in(schema)
    assert len(objects) == 7 and all(o.get("additionalProperties") is False for o in objects), (
        "every object gets additionalProperties: false, in array items and anyOf branches too"
    )
    assert all(o.get("required") == list(o["properties"]) for o in objects), "required lists every property, in order"

    props = schema["properties"]
    assert (props["gift_note"], props["speed"], props["payment"]["anyOf"][-1]) == (
        {"type": ["string", "null"]},
        {"type": ["string", "null"], "enum": ["standard", "express", None]},
        {"type": "null"},
    ), "an optional property becomes nullable, and its enum must allow None"
    assert props["billing"]["properties"]["postcode"] == {"type": ["string", "null"]}, (
        "a type that already allows null keeps one null"
    )
    assert (props["billing"]["type"], props["shipping"]["type"]) == ("object", ["object", "null"]), (
        "shipping is optional, so its copy of the address is nullable; billing's copy is not"
    )
    assert schema == STRICT_ORDER, "the compiled order schema"

    props["billing"]["properties"]["street"]["minLength"] = 1
    assert "minLength" not in props["shipping"]["properties"]["street"] and ORDER.input_schema == before, (
        "the copies share nothing with each other or with the input"
    )

    assert strict_tool(WEATHER).input_schema["properties"]["units"] == {
        "type": ["string", "null"],
        "enum": ["celsius", "fahrenheit", None],
    }, "WEATHER's units may be null, so its enum must list None"

    with pytest.raises(LimitError, match="openai"):
        strict_tool(org_chart(6))
    assert schema_depth(strict_tool(org_chart(5)).input_schema) == 5, "five levels once inlined is within the limit"
