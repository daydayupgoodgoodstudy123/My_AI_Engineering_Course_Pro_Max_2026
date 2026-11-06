import asyncio
import hashlib
import json
import time

import pytest
from voyager.curriculum import Gap, Recipe, propose, rank_tasks
from voyager.lock import VersionConflict, resolve
from voyager.refine import Draft, Task, refine
from voyager.skills import Skill, SkillLibrary
from voyager.store import StoreError, load, save

MINE_V1 = '''\
def run(world):
    world["resources"]["ore"] = world["resources"].get("ore", 0) + 3
    return "+3 ore"
'''

MINE_V2 = '''\
def run(world):
    if "iron_pickaxe" not in world["inventory"]:
        raise RuntimeError("need an iron_pickaxe to mine this fast")
    world["resources"]["ore"] = world["resources"].get("ore", 0) + 5
    return "+5 ore"
'''

STICKS_V1 = '''\
def run(world):
    world["resources"]["stick"] = world["resources"].get("stick", 0) + 2
    return "+2 stick"
'''

STICKS_V2 = '''\
def run(world):
    world["resources"]["stick"] = world["resources"].get("stick", 0) + 4
    return "+4 stick"
'''

TABLE = '''\
def run(world):
    world["has_table"] = True
    return "placed crafting table"
'''

PICKAXE = '''\
def run(world):
    res = world["resources"]
    if not world.get("has_table"):
        raise RuntimeError("no crafting table")
    ore, stick = res.get("ore", 0), res.get("stick", 0)
    if ore < 3 or stick < 2:
        raise RuntimeError(f"need 3 ore and 2 stick, have {ore} and {stick}")
    res["ore"], res["stick"] = ore - 3, stick - 2
    world["inventory"].append("iron_pickaxe")
    return "crafted iron_pickaxe"
'''

READY = '''\
def run(world):
    return "ready"
'''

STEP = '''\
def run(world):
    world["runs"] = world.get("runs", 0) + 1
    return "ok"
'''


def crafting_library() -> SkillLibrary:
    lib = SkillLibrary()
    lib.register("mine_ore", "mine iron ore from nearby rock", MINE_V1, tags=("gather", "ore"))
    lib.register("gather_sticks", "gather sticks from trees", STICKS_V1, tags="gather")
    lib.register("place_table", "place a crafting table", TABLE, tags="setup")
    return lib


VERBS = ("mine", "craft", "smelt", "gather", "build", "chop", "place")
ITEMS = ("iron", "stone", "wood", "coal", "wool", "sand", "gold", "clay", "glass", "string", "leather")
USES = ("tools", "shelter", "rails", "armor", "food", "light", "bridges", "boats", "signs", "maps", "beds", "fences", "doors")


def large_library() -> SkillLibrary:
    """50,000 skills such as mine_iron_tools_7007, 'mine iron for tools'; kit000 to kit999 hold 50 each."""
    lib = SkillLibrary()
    for i in range(50_000):
        verb, item, use = VERBS[i % 7], ITEMS[i % 11], USES[i % 13]
        lib.register(f"{verb}_{item}_{use}_{i}", f"{verb} {item} for {use}", STEP, tags=f"kit{i % 1000:03d}")
    return lib


@pytest.mark.skip("Part 1")
def test_skill_library() -> None:
    """Skills keep every version, compose in dependency order, fail without side effects, and a tag narrows a search."""
    lib = crafting_library()
    first_mine = lib.get("mine_ore")
    lib.register(
        "craft_pickaxe", "craft an iron pickaxe from ore and sticks", PICKAXE,
        tags=("craft", "tooling"), depends_on=("place_table", "gather_sticks", "mine_ore"),
    )
    found = lib.search("gather sticks or ore", tag_filter="gather")
    assert [s.name for _, s in found] == ["gather_sticks", "mine_ore"], "a tag given as one string is one tag"
    assert lib.search("gather sticks", tag_filter="g") == [], "a tag filter matches whole tags"
    assert lib.get("gather_sticks").tags == ("gather",), "a tag given as one string is one tag"

    lib.register("starter_kit", "mine ore and gather sticks to start", READY, depends_on=("mine_ore@1", "gather_sticks"))
    assert lib.execute("starter_kit", {"resources": {}, "inventory": []}).ok, "starter_kit runs before its skills are refined"
    lib.register("mine_ore", "mine iron ore with an iron pickaxe", MINE_V2, tags=("gather", "ore"))
    lib.register("gather_sticks", "gather sticks from trees two at a time", STICKS_V2, tags="gather")
    world = {"resources": {}, "inventory": []}
    run = lib.execute("starter_kit", world)
    assert run.ok, "a parent pinned to mine_ore@1 keeps running version 1\n" + str(run.error)
    assert world["resources"] == {"ore": 3, "stick": 4}, "an unpinned dependency runs its latest version"
    assert run.log == [
        "ran mine_ore v1: +3 ore",
        "ran gather_sticks v2: +4 stick",
        "ran starter_kit v1: ready",
    ], "dependencies run first, in the order they are written"
    assert (first_mine.version, first_mine.code) == (1, MINE_V1), "a registered version never changes"
    assert [(s.version, s.description) for s in lib.versions("mine_ore")] == [
        (1, "mine iron ore from nearby rock"),
        (2, "mine iron ore with an iron pickaxe"),
    ], "every version keeps what it was registered with"
    with pytest.raises(KeyError):
        lib.get("mine_ore", 3)
    found = lib.search("mine iron ore", top_k=5)
    assert [(s.name, s.version) for _, s in found] == [
        ("mine_ore", 2),
        ("starter_kit", 1),
        ("craft_pickaxe", 1),
    ], "search returns each skill once, at its latest version"
    found = lib.search("gather sticks or ore", tag_filter="gather")
    assert [(s.name, s.version) for _, s in found] == [("gather_sticks", 2), ("mine_ore", 2)], (
        "a tag filter finds each skill once, at its latest version"
    )
    assert [s.name for _, s in lib.search("two at a time")] == ["gather_sticks", "place_table"], (
        "search reads the latest description"
    )

    world = {"resources": {"ore": 1}, "inventory": ["torch"]}
    run = lib.execute("craft_pickaxe", world)
    assert (run.ok, run.failed) == (False, "mine_ore@2"), "craft_pickaxe uses the latest mine_ore, which needs a pickaxe"
    assert world == {"resources": {"ore": 1}, "inventory": ["torch"]}, "a failed run leaves the world as it was"
    assert run.log == [
        "ran place_table v1: placed crafting table",
        "ran gather_sticks v2: +4 stick",
    ], "a failed run still reports what ran before it failed"
    assert run.error.startswith("Traceback (most recent call last):"), "the error carries the stack trace"
    assert run.error.rstrip().endswith("RuntimeError: need an iron_pickaxe to mine this fast")

    lib.register(
        "stock_up", "gather sticks then craft a spare pickaxe", READY,
        depends_on=("gather_sticks@1", "place_table", "craft_pickaxe"),
    )
    world = {"resources": {}, "inventory": ["iron_pickaxe"]}
    run = lib.execute("stock_up", world)
    assert run.log == [
        "ran gather_sticks v1: +2 stick",
        "ran place_table v1: placed crafting table",
        "ran gather_sticks v2: +4 stick",
        "ran mine_ore v2: +5 ore",
        "ran craft_pickaxe v1: crafted iron_pickaxe",
        "ran stock_up v1: ready",
    ], "each skill version runs once, and two versions of one skill are two steps"

    ladder = SkillLibrary()
    ladder.register("s0", "first step", STEP)
    below = ("s0",)
    for i in range(1, 19):
        ladder.register(f"a{i}", f"step {i} a", STEP, depends_on=below)
        ladder.register(f"b{i}", f"step {i} b", STEP, depends_on=below)
        below = (f"a{i}", f"b{i}")
    ladder.register("top", "last step", STEP, depends_on=below)
    world = {}
    start = time.perf_counter()
    run = ladder.execute("top", world)
    elapsed = time.perf_counter() - start
    assert run.ok and world == {"runs": 38}, "every skill version runs once"
    assert elapsed < 0.05, "composing skills that share sub-skills should be fast"

    shelf = large_library()
    # in kit007, two skills share three words with the query and eleven share two
    found = shelf.search("craft iron for tools", top_k=8, tag_filter="kit007")
    assert [s.name for _, s in found] == [
        "craft_string_tools_20007", "mine_iron_tools_7007",
        "craft_coal_fences_48007", "craft_gold_doors_34007", "craft_leather_light_41007",
        "craft_sand_boats_13007", "craft_stone_shelter_6007", "craft_wood_bridges_27007",
    ], "equal scores go to the alphabetically first name"
    start = time.perf_counter()
    for kit in range(30):
        shelf.search("craft iron for tools", top_k=5, tag_filter=f"kit{kit:03d}")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.03, "searching one tag of a large library should be fast"
    shelf.register("mine_iron_tools_7007", "mine iron for tools", STEP, tags="kit999")
    kit007 = [s.name for _, s in shelf.search("mine iron for tools", top_k=50, tag_filter="kit007")]
    assert len(kit007) == 49 and "mine_iron_tools_7007" not in kit007, "a refined skill leaves the tags its latest version dropped"
    assert [(s.name, s.version) for _, s in shelf.search("mine iron for tools", top_k=1, tag_filter="kit999")] == [
        ("mine_iron_tools_7007", 2),
    ], "a refined skill is found under its new tag, at its latest version"


MINE_CRLF = 'def run(world):\r\n    world["resources"]["ore"] = world["resources"].get("ore", 0) + 5  \r\n    return "+5 ore"\r\n'
TABLE_TABS = 'def run(world):\n\tworld["has_table"] = True\t\n\treturn "placed crafting table"'
PICKAXE_NOTE = PICKAXE.replace("    res = world", "    # pico de hierro, ⛏ ×1\n    res = world")


def sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@pytest.mark.skip("Part 2")
def test_store_roundtrip(tmp_path) -> None:
    """Every version of every skill reads back exactly, and each distinct code is stored once."""
    root = tmp_path / "skills"
    versions = [
        Skill("mine_ore", 1, "mine iron ore from nearby rock", MINE_V1, ("gather", "ore")),
        Skill("mine_ore", 2, "mine iron ore — five per swing", MINE_CRLF, ("gather", "ore")),
        Skill("mine_ore", 3, "mine iron ore from nearby rock (back to v1)", MINE_V1, ("gather", "ore")),
        Skill("place_table", 1, "place a crafting table", TABLE_TABS, ("setup",)),
        Skill("craft_pickaxe", 1, "craft an iron pickaxe ⛏", PICKAXE_NOTE, ("craft", "tooling"), ("mine_ore@1", "place_table")),
    ]
    save(versions, root)
    objects = sorted(path.name for path in (root / "objects").iterdir())
    assert objects == sorted({sha(MINE_V1), sha(MINE_CRLF), sha(TABLE_TABS), sha(PICKAXE_NOTE)}), (
        "one object per distinct code, named by the SHA-256 of its UTF-8 bytes"
    )
    assert (root / "objects" / sha(MINE_CRLF)).read_bytes() == MINE_CRLF.encode("utf-8"), (
        "an object holds the code byte for byte"
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert [v["code"] for v in manifest["mine_ore"]] == [sha(MINE_V1), sha(MINE_CRLF), sha(MINE_V1)], (
        "the manifest lists each skill's versions in order and refers to code by hash"
    )
    assert manifest["craft_pickaxe"][0]["depends_on"] == ["mine_ore@1", "place_table"], "dependencies keep their pins"

    loaded = load(root)
    assert loaded == {"mine_ore": versions[0:3], "place_table": [versions[3]], "craft_pickaxe": [versions[4]]}, (
        "every version reads back exactly"
    )
    world = {"resources": {}, "inventory": []}
    assert [loaded["mine_ore"][1].fn(world), loaded["place_table"][0].fn(world)] == ["+5 ore", "placed crafting table"], (
        "loaded skills run"
    )
    assert world == {"resources": {"ore": 5}, "inventory": [], "has_table": True}

    stored = (root / "objects" / sha(MINE_V1)).stat().st_mtime_ns
    # the library now has a place_table v2, and craft_pickaxe is gone from it
    versions[4] = Skill("place_table", 2, "place a crafting table near ore", TABLE_TABS, ("setup",), ("mine_ore",))
    save(versions, root)
    assert len(list((root / "objects").iterdir())) == 4, "saving again keeps every object and adds none for code already stored"
    assert (root / "objects" / sha(MINE_V1)).stat().st_mtime_ns == stored, "an object that is already stored is not written again"
    assert load(root) == {"mine_ore": versions[0:3], "place_table": versions[3:5]}, "saving again replaces the manifest"

    (root / "objects" / sha(MINE_CRLF)).write_bytes(MINE_CRLF.replace("5", "7").encode("utf-8"))
    with pytest.raises(StoreError, match="mine_ore@2"):
        load(root)
    (root / "objects" / sha(MINE_CRLF)).unlink()
    with pytest.raises(StoreError, match="mine_ore@2"):
        load(root)


RECIPES = {
    "craft_planks": Recipe({"log": 1}, ("chop_wood",), 1),
    "craft_sticks": Recipe({"plank": 2}, ("craft_planks",), 1),
    "place_table": Recipe({"plank": 4}, ("craft_planks",), 2),
    "craft_ladder": Recipe({"stick": 3}, ("craft_sticks",), 2),
    "craft_bowl": Recipe({"plank": 1}, ("craft_planks",), 2),
    "craft_wooden_pickaxe": Recipe({"plank": 3, "stick": 2}, ("craft_sticks", "place_table"), 3),
    "mine_stone": Recipe({}, ("craft_wooden_pickaxe",), 2),
    "craft_stone_pickaxe": Recipe({"cobblestone": 3, "stick": 5}, ("mine_stone", "craft_sticks", "place_table"), 5),
    "craft_furnace": Recipe({"cobblestone": 8}, ("mine_stone", "place_table"), 4),
    "mine_iron": Recipe({}, ("craft_stone_pickaxe",), 5),
    "smelt_iron": Recipe({"iron_ore": 1, "coal": 1}, ("craft_furnace", "mine_iron", "collect_coal"), 6),
    "craft_bucket": Recipe({"iron_ingot": 3}, ("smelt_iron", "craft_furnace"), 5),
    "craft_shield": Recipe({"plank": 2, "iron_ingot": 1}, ("smelt_iron", "place_table"), 4),
}


@pytest.mark.skip("Part 3")
def test_curriculum() -> None:
    """Propose the task just above what the library can do, and say what each task is missing."""
    library = {"craft_planks", "craft_sticks", "place_table", "craft_bowl", "craft_wooden_pickaxe", "mine_stone"}
    inventory = {"plank": 1, "stick": 4, "cobblestone": 2, "iron_ore": 1}
    ranked = rank_tasks(RECIPES, library, inventory)
    gaps = {gap.task: gap for gap in ranked}
    assert not gaps.keys() & library, "a task whose skill the library already has is not a candidate"
    assert all("chop_wood" not in gap.missing for gap in ranked), (
        "a skill the library has needs nothing more: craft_planks is known, so chop_wood is not missing"
    )
    assert gaps["mine_iron"].missing == ("craft_stone_pickaxe", "mine_iron"), (
        "a task's own skill is missing, and so are the missing skills it needs"
    )
    assert gaps["mine_iron"].short == {}, "short is for the task's own recipe, not for the skills it is missing"
    assert gaps["smelt_iron"].missing == ("collect_coal", "craft_furnace", "craft_stone_pickaxe", "mine_iron", "smelt_iron"), (
        "missing skills are followed through missing prerequisites, including ones with no recipe"
    )
    assert gaps["craft_bucket"].missing == (
        "collect_coal", "craft_bucket", "craft_furnace", "craft_stone_pickaxe", "mine_iron", "smelt_iron",
    ), "a skill that two paths need is missing once"
    assert gaps["craft_stone_pickaxe"].short == {"cobblestone": 1, "stick": 1}, (
        "short counts what is missing: 3 cobblestone with 2 in hand is 1 short"
    )
    assert gaps["smelt_iron"].short == {"coal": 1}, (
        "exactly enough is not short; a material the inventory lacks is short by the full count"
    )
    assert gaps["craft_shield"].short == {"plank": 1, "iron_ingot": 1}, "short counts what is missing"
    assert [gap.task for gap in ranked] == [
        "craft_ladder",
        "craft_stone_pickaxe",
        "craft_furnace",
        "mine_iron",
        "smelt_iron",
        "craft_bucket",
        "craft_shield",
    ], "fewest missing skills first, then materials in hand, then value, then name"
    assert propose(RECIPES, library, inventory) == Gap("craft_ladder", ("craft_ladder",), {})
    assert propose(RECIPES, library - {"craft_bowl"}, inventory) == Gap("craft_bowl", ("craft_bowl",), {}), (
        "ties on value go to the name"
    )
    assert propose(RECIPES, set(RECIPES), inventory) is None, "nothing left to propose"


class ScriptedWriter:
    """Stands in for the model that writes skill code: replies from a script and keeps what it was shown."""

    def __init__(self, drafts: list[Draft]) -> None:
        self.drafts = drafts
        self.seen: list = []

    async def __call__(self, task: Task, feedback):
        if len(self.seen) == len(self.drafts):
            raise AssertionError("the loop asked for more rounds than the script has")
        self.seen.append(feedback)
        return self.drafts[len(self.seen) - 1]


def has_iron_pickaxe(world) -> tuple[bool, str]:
    if "iron_pickaxe" in world["inventory"]:
        return True, "inventory has an iron_pickaxe"
    return False, f"no iron_pickaxe in inventory {world['inventory']}"


WRONG_KEY = '''\
def run(world):
    if not world.get("table"):
        world["waiting_for"] = "crafting table"
        return "skipped: no crafting table yet"
    world["resources"]["ore"] -= 3
    world["resources"]["stick"] -= 2
    world["inventory"].append("iron_pickaxe")
    return "crafted iron_pickaxe"
'''

NO_COLON = 'def run(world)\n    return "crafted iron_pickaxe"\n'
DEPS = ("mine_ore", "gather_sticks", "place_table")


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


@pytest.mark.skip("Part 4")
def test_refinement_stream() -> None:
    """Each round of iterative refinement is streamed as one NDJSON line as soon as it ends."""
    lib = crafting_library()
    lib.register("craft_pickaxe", "craft a wooden pickaxe", READY)
    task = Task("craft_pickaxe", "craft an iron pickaxe from ore and sticks", has_iron_pickaxe, ("craft", "tooling"))
    writer = ScriptedWriter([
        Draft(NO_COLON),
        Draft(PICKAXE, ("mine_ore", "place_table")),
        Draft(WRONG_KEY, DEPS),
        Draft(PICKAXE, ("mine_ore", "place_table")),
        Draft(PICKAXE, DEPS),
    ])
    world = {"resources": {}, "inventory": []}
    lines = collect(refine(lib, task, writer, world, max_rounds=6))
    events = [json.loads(line) for line in "".join(lines).splitlines()]
    assert len(events) == len(lines), "one JSON object per line"
    assert events[0]["signal"] == "error" and events[0]["detail"].startswith("Traceback (most recent call last):"), (
        "a draft that does not compile is an error, with its stack trace"
    )
    assert "SyntaxError" in events[0]["detail"]
    assert events[1]["signal"] == "error" and events[1]["detail"].startswith("Traceback (most recent call last):"), (
        "an error carries the stack trace"
    )
    assert events[1]["detail"].rstrip().endswith("RuntimeError: need 3 ore and 2 stick, have 3 and 0")
    assert events[2] == {
        "round": 3, "signal": "self_verification_failure", "version": None, "detail": "no iron_pickaxe in inventory []",
    }, "a run that finishes but fails verification is a self-verification failure"
    assert events[3]["signal"] == "error", "every round starts from the world as it was when refine was called"
    assert events[4] == {"round": 5, "signal": "success", "version": 2, "detail": "inventory has an iron_pickaxe"}, (
        "a draft that passes verification is registered as the next version"
    )
    assert [e["round"] for e in events] == [1, 2, 3, 4, 5], "the loop stops at the first success"
    assert writer.seen == [None] + events[:4], "the writer sees the previous round's event"
    assert [s.version for s in lib.versions("craft_pickaxe")] == [1, 2], "only the draft that succeeded goes into the library"
    assert lib.get("craft_pickaxe") == Skill("craft_pickaxe", 2, task.description, PICKAXE, ("craft", "tooling"), DEPS), (
        "the registered version is the draft that succeeded, with the task's description and tags"
    )
    assert world == {"resources": {"ore": 0, "stick": 0}, "inventory": ["iron_pickaxe"], "has_table": True}, (
        "after a success the world holds what that round did"
    )
    assert lib.execute("craft_pickaxe", {"resources": {}, "inventory": []}).ok, "the registered skill works on a fresh world"

    writer = ScriptedWriter([Draft(WRONG_KEY, DEPS), Draft(WRONG_KEY, DEPS)])
    world = {"resources": {"ore": 1}, "inventory": ["torch"]}
    events = [json.loads(line) for line in collect(refine(lib, task, writer, world, max_rounds=2))]
    assert [e["signal"] for e in events] == ["self_verification_failure"] * 2, "stop after max_rounds"
    assert world == {"resources": {"ore": 1}, "inventory": ["torch"]}, "a task that never succeeds leaves the world as it started"
    assert [s.version for s in lib.versions("craft_pickaxe")] == [1, 2], "a failed draft never goes into the library"

    writer = ScriptedWriter([Draft(WRONG_KEY, DEPS), Draft(PICKAXE, DEPS)])
    world = {"resources": {}, "inventory": []}

    async def first_line(writer: ScriptedWriter) -> str:
        agen = refine(lib, task, writer, world, max_rounds=2)
        line = await agen.__anext__()
        assert len(writer.seen) == 1, "stream each round as soon as it ends"
        await agen.aclose()
        return line

    assert json.loads(asyncio.run(first_line(writer)))["signal"] == "self_verification_failure"
    assert world == {"resources": {}, "inventory": []}, "a stream closed early leaves the world as it started"
    assert json.loads(asyncio.run(first_line(ScriptedWriter([Draft(PICKAXE, DEPS)]))))["signal"] == "success"
    assert world == {"resources": {"ore": 0, "stick": 0}, "inventory": ["iron_pickaxe"], "has_table": True}, (
        "a stream closed right after a success keeps what that round did"
    )


INDEX = {
    "chop_wood": {1: []},
    "craft_planks": {1: ["chop_wood"]},
    "strip_bark": {1: ["chop_wood"]},
    "craft_sticks": {1: ["craft_planks"], 2: ["craft_planks", "strip_bark"]},
    "place_table": {1: ["craft_planks"]},
    "craft_wooden_pickaxe": {1: ["craft_sticks", "place_table"]},
    "place_torch": {1: ["craft_sticks"]},
    "mine_stone": {1: ["craft_wooden_pickaxe"], 2: ["craft_wooden_pickaxe", "place_torch"]},
    "craft_stone_pickaxe": {
        1: ["mine_stone@1", "craft_sticks@1", "place_table"],
        2: ["mine_stone", "craft_sticks", "place_table"],
    },
    "fletch_arrows": {1: ["craft_sticks@2", "chop_wood"]},
    "mine_iron": {1: ["craft_stone_pickaxe"]},
    "craft_tools": {1: ["craft_wooden_pickaxe", "craft_stone_pickaxe@1"]},
    "craft_rails": {1: ["mine_iron", "craft_stone_pickaxe@1"]},
    "craft_kit": {1: ["craft_stone_pickaxe@1", "fletch_arrows"]},
}


@pytest.mark.skip("Part 5")
def test_version_lock() -> None:
    """Lock a composed skill to one version of every skill it needs, dependencies first."""
    assert resolve(INDEX, "craft_wooden_pickaxe") == [
        "chop_wood@1", "craft_planks@1", "strip_bark@1", "craft_sticks@2", "place_table@1", "craft_wooden_pickaxe@1",
    ], "a bare reference takes the latest version; dependencies come first, in the order they are written"
    assert resolve(INDEX, "craft_stone_pickaxe") == [
        "chop_wood@1", "craft_planks@1", "strip_bark@1", "craft_sticks@2", "place_table@1",
        "craft_wooden_pickaxe@1", "place_torch@1", "mine_stone@2", "craft_stone_pickaxe@2",
    ], "each locked version brings its own dependencies"
    assert resolve(INDEX, "craft_stone_pickaxe@1") == [
        "chop_wood@1", "craft_planks@1", "craft_sticks@1", "place_table@1",
        "craft_wooden_pickaxe@1", "mine_stone@1", "craft_stone_pickaxe@1",
    ], "a bare reference follows a pin made elsewhere in the tree"
    assert resolve(INDEX, "craft_tools") == [
        "chop_wood@1", "craft_planks@1", "craft_sticks@1", "place_table@1",
        "craft_wooden_pickaxe@1", "mine_stone@1", "craft_stone_pickaxe@1", "craft_tools@1",
    ], "a pin counts even when a bare reference to the same skill comes first"
    assert resolve(INDEX, "craft_rails") == [
        "chop_wood@1", "craft_planks@1", "craft_sticks@1", "place_table@1", "craft_wooden_pickaxe@1",
        "mine_stone@1", "craft_stone_pickaxe@1", "mine_iron@1", "craft_rails@1",
    ], "the pins inside a pinned version count, even when that skill was first reached by a bare reference"
    assert resolve({**INDEX, "craft_kit": {1: ["craft_stone_pickaxe@1", "craft_sticks@1"]}}, "craft_kit") == [
        "chop_wood@1", "craft_planks@1", "craft_sticks@1", "place_table@1",
        "craft_wooden_pickaxe@1", "mine_stone@1", "craft_stone_pickaxe@1", "craft_kit@1",
    ], "the same pin twice is not a conflict"
    with pytest.raises(VersionConflict) as conflict:
        resolve(INDEX, "craft_kit")
    assert "craft_kit@1 -> craft_stone_pickaxe@1 -> craft_sticks@1" in str(conflict.value), "a conflict names both paths"
    assert "craft_kit@1 -> fletch_arrows@1 -> craft_sticks@2" in str(conflict.value), "a conflict names both paths"
    with pytest.raises(KeyError, match="craft_sticks@3"):
        resolve({**INDEX, "fletch_arrows": {1: ["craft_sticks@3"]}}, "fletch_arrows")
    with pytest.raises(KeyError, match="whittle"):
        resolve({**INDEX, "place_torch": {1: ["whittle"]}}, "place_torch")
