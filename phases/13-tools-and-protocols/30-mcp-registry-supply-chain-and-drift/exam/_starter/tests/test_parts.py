import asyncio
import gc
import hashlib
import itertools
import json
import time
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from regadmit.admission import Decision, decide
from regadmit.evidence import (
    OFFICIAL_META_KEY,
    PROTOCOL_VERSION,
    PUBLISHER_META_KEY,
    REGISTRY_SOURCE,
    SERVER_INFO_KEY,
    canonical_json,
    digest,
    listed_version,
    namespace_for_domain,
    toolset_digest,
)
from regadmit.ledger import GENESIS, AdmissionLedger, LedgerError, LedgerFile
from regadmit.reconcile import reconcile
from regadmit.rollback import fold, rollback
from regadmit.service import AdmissionController
from regadmit.state import RouteState

INVENTORY = "com.example/inventory"
BILLING = "com.example/billing"
SEARCH = "com.example/search"
NAMESPACE = "com.example"
SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"

TOOLS = [
    {
        "name": "inventory_search",
        "description": "Search inventory items by keyword",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "inventory_get",
        "description": "Fetch one inventory item",
        "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
    },
    {
        "name": "inventory_list",
        "description": "List the items in one warehouse",
        "inputSchema": {
            "type": "object",
            "properties": {
                "warehouse": {"type": "string"},
                "state": {"type": "string", "enum": ["in_stock", "backordered", "discontinued"]},
            },
        },
    },
]


def ticks():
    """A clock that moves on one second per call."""
    start = datetime.fromisoformat("2026-11-01T09:00:00+00:00")
    counter = itertools.count()
    return lambda: (start + timedelta(seconds=next(counter))).isoformat()


def record(version: str, name: str = INVENTORY, **fields) -> dict:
    """A server.json record with one PyPI package, as the lesson's sample publishes it."""
    rec = {
        "$schema": SCHEMA,
        "name": name,
        "version": version,
        "description": "Read-only inventory lookup tools",
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "example-mcp-" + name.partition("/")[2],
                "version": version,
                "transport": {"type": "stdio"},
            }
        ],
        "_meta": {PUBLISHER_META_KEY: {"tier": "internal-approved"}},
    }
    rec.update(fields)
    return rec


def listing(rec: dict, status: str | None = "active") -> dict:
    """One Registry listing item: the record, with the Registry's response metadata beside it."""
    return {"server": rec, "_meta": {} if status is None else {OFFICIAL_META_KEY: {"status": status}}}


def discover(version: str, name: str = INVENTORY, tools: list = TOOLS, **fields) -> dict:
    """A server/discover result with the endpoint's tool descriptors."""
    live = {
        "resultType": "complete",
        "supportedVersions": [PROTOCOL_VERSION],
        "capabilities": {"tools": {"listChanged": False}},
        "tools": deepcopy(tools),
        "_meta": {SERVER_INFO_KEY: {"name": name, "version": version}},
    }
    live.update(fields)
    return live


def wheel(identifier: str, version: str) -> str:
    """The digest the artifact verifier calculates for a fetched wheel."""
    return hashlib.sha256(f"{identifier}-{version}-py3-none-any.whl".encode()).hexdigest()


def evidence_for(rec: dict, **fields) -> dict:
    """The artifact verifier's result for the record's first package."""
    package = rec["packages"][0]
    ev = {
        "kind": "package",
        "registryType": package["registryType"],
        "identifier": package["identifier"],
        "version": package["version"],
        "transportType": package["transport"]["type"],
        "digest": wheel(package["identifier"], package["version"]),
        "digestFrom": "fetch",
        "verified": True,
    }
    ev.update(fields)
    return ev


def pin_for(rec: dict, ev: dict, live: dict, source: dict | None = None) -> dict:
    """The pin decide() makes, built the way its docstring describes."""
    if source is None:
        joined = (ev["registryType"], ev["identifier"], ev["version"])
        package = next(p for p in rec["packages"] if (p["registryType"], p["identifier"], p["version"]) == joined)
        source = {"kind": "package", **package}
    provenance = {
        "registrySource": REGISTRY_SOURCE,
        "server": rec["name"],
        "registryVersion": rec["version"],
        "recordDigest": digest(rec),
        "source": source,
        "sourceDigest": ev["digest"],
    }
    return {
        "server": rec["name"],
        "version": rec["version"],
        "registryStatus": "active",
        "recordDigest": digest(rec),
        "source": source,
        "sourceDigest": ev["digest"],
        "toolsetDigest": toolset_digest(live["tools"]),
        "provenanceDigest": digest(provenance),
        "reportedServerInfo": live["_meta"][SERVER_INFO_KEY],
    }


def admitted(version: str, name: str = INVENTORY) -> dict:
    rec = record(version, name)
    return pin_for(rec, evidence_for(rec), discover(version, name))


def raises(exc: type[Exception], call, *args, **kwargs) -> bool:
    try:
        call(*args, **kwargs)
    except exc:
        return True
    return False


@pytest.mark.skip("Part 1")
def test_evidence_and_ledger() -> None:
    """Each fact comes from the authority that owns it, and the ledger stays tamper-evident and fast."""
    page = [listing(record("1.0.0")), listing(record("1.1.0"), "deprecated"), listing(record("0.9.0"), "deleted")]
    seen = [listed_version(item, NAMESPACE) for item in page]
    assert [v.status for v in seen] == ["active", "deprecated", "deleted"], "the status is the one the Registry manages"
    assert [v.eligible for v in seen] == [True, False, False], "only an active version is eligible"
    assert listed_version(listing(record("1.2.0"), None), NAMESPACE).status == "", (
        "a version the Registry gives no status has none"
    )
    plain = {"server": record("1.2.0"), "_meta": {"status": "active"}}
    assert listed_version(plain, NAMESPACE).status == "", "a plain _meta.status is not the Registry's"
    own_meta = {PUBLISHER_META_KEY: {"tier": "internal-approved"}, OFFICIAL_META_KEY: {"status": "active"}}
    assert listed_version(listing(record("1.2.0", _meta=own_meta), "deprecated"), NAMESPACE).status == "deprecated", (
        "a publisher cannot set its own status"
    )

    squatter = listed_version(listing(record("1.0.0", name="org.attacker/inventory")), NAMESPACE)
    assert not squatter.in_namespace, "the namespace comes from the publisher's authentication, not from the record"
    assert squatter.namespace == "org.attacker", "the namespace the record claims is still what the record says"
    docs = listing(record("1.0.0", name="com.example.docs/search"))
    assert [listed_version(docs, ns).in_namespace for ns in (NAMESPACE, namespace_for_domain("Docs.Example.COM."))] == [
        False,
        True,
    ], "a subdomain is a namespace of its own"
    assert not listed_version(listing(record("1.0.0", name="com.example/")), NAMESPACE).in_namespace, (
        "a name needs a slug after its namespace"
    )

    pinned = toolset_digest(TOOLS)
    assert toolset_digest(TOOLS[::-1]) == pinned, "the order of the tool list is not a change"
    annotated = deepcopy(TOOLS)
    annotated[1]["annotations"] = {"destructiveHint": True}
    assert toolset_digest(annotated) != pinned, "new annotations change the toolset digest"
    titled = deepcopy(TOOLS)
    titled[1]["title"] = "Get one item"
    assert toolset_digest(titled) != pinned, "every descriptor field counts"
    shadow = {**TOOLS[1], "description": "Fetch one inventory item and reserve it", "annotations": {"destructiveHint": True}}
    assert toolset_digest([TOOLS[0], shadow, *TOOLS[1:]]) != pinned, "a second descriptor under a pinned name is a change"
    twins = [TOOLS[1], {**TOOLS[1], "description": "Fetch one inventory item, archived ones too"}]
    assert toolset_digest(twins) == toolset_digest(twins[::-1]), "any order of the same descriptors gives one digest"
    nameless = TOOLS + [{"description": "A tool with no name", "inputSchema": {"type": "object"}}]
    assert toolset_digest(nameless) != pinned, "a malformed tool list still gets a digest"
    assert pinned == "7efd7bf408bc8295019e34b7d41b10fe62536236984e3237d7e0455088262673", (
        "the digest matches the toolsetDigest already pinned for this tool set"
    )

    ledger = AdmissionLedger(ticks())
    first = ledger.append("admission", INVENTORY, "1.0.0", "approved", [], {"pin": {"toolsetDigest": pinned}})
    second = ledger.append("live-check", INVENTORY, "1.0.0", "ok", [], {"toolsetDigest": pinned})
    third = ledger.append(
        "registry-sync",
        INVENTORY,
        "1.0.0",
        "quarantined",
        ["registry-status"],
        {"recordDigest": digest(page[0]["server"]), "status": "deprecated"},
    )
    assert [e["previousHash"] for e in ledger.entries] == [GENESIS, first["entryHash"], second["entryHash"]], (
        "each entry links to the entry before it"
    )
    assert ledger.head() == (3, third["entryHash"]), "the head is the newest entry's sequence and hash"

    long = AdmissionLedger(ticks())
    gc.collect()
    start = time.perf_counter()
    for _ in range(1000):
        long.append("live-check", INVENTORY, "1.0.0", "ok", [], {"toolsetDigest": pinned})
    elapsed = time.perf_counter() - start
    assert long.head() == (1000, long.entries[-1]["entryHash"])
    assert elapsed < 0.1, "append should stay fast on a long ledger"

    long.entries[400]["outcome"] = "quarantined"
    assert not long.verify(), "changing an old entry breaks verification"
    assert raises(LedgerError, long.head), "a broken chain has no head to anchor"


PIN_100 = admitted("1.0.0")
HISTORY = [
    ("admission", INVENTORY, "1.0.0", "approved", [], {"pin": PIN_100}),
    (
        "admission",
        INVENTORY,
        "1.1.0",
        "rejected",
        ("digest",),
        {
            "recordDigest": digest(record("1.1.0")),
            "status": "active",
            "verifiedNamespace": NAMESPACE,
            "claimedNamespace": NAMESPACE,
        },
    ),
    ("live-check", INVENTORY, "1.0.0", "ok", [], {"toolsetDigest": PIN_100["toolsetDigest"]}),
    (
        "registry-sync",
        INVENTORY,
        "1.0.0",
        "quarantined",
        ["registry-status"],
        {"recordDigest": PIN_100["recordDigest"], "status": "deprecated"},
    ),
    (
        "rollback",
        INVENTORY,
        "0.9.0",
        "rejected",
        ["unknown"],
        {"from": None, "to": "0.9.0", "reason": "Rücksprung „Lager“"},
    ),
]
FIELDS = {"sequence", "time", "event", "server", "version", "outcome", "reasons", "evidence", "previousHash", "entryHash"}


def write_entries(path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")


def rechain(entries: list[dict]) -> list[dict]:
    """What someone who can write the file does after a change: recompute every hash after it."""
    previous, chained = GENESIS, []
    for entry in entries:
        body = {key: value for key, value in entry.items() if key != "entryHash"}
        body["previousHash"] = previous
        chained.append({**body, "entryHash": digest(body)})
        previous = chained[-1]["entryHash"]
    return chained


@pytest.mark.skip("Part 2")
def test_ledger_file(tmp_path) -> None:
    """The ledger file reads back exactly, and an anchored head catches what the chain alone cannot."""
    path = tmp_path / "admissions.jsonl"
    clock = ticks()
    ledger = LedgerFile(path, clock)
    assert (ledger.entries, ledger.head()) == ([], (0, GENESIS)), "no file yet is an empty ledger"
    for event in HISTORY:
        ledger.append(*event)
    anchor = ledger.head()  # stored in a separate trust domain

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n"), "every entry ends with a newline"
    stored = [json.loads(line) for line in text.split("\n")[:-1]]
    assert stored == ledger.entries, "the file holds every entry, one per line, oldest first"
    for entry in stored:
        assert set(entry) == FIELDS, "an entry has the ten ledger fields"
        body = {key: value for key, value in entry.items() if key != "entryHash"}
        assert entry["entryHash"] == digest(body), "entryHash is the digest of the other nine fields"

    reopened = LedgerFile(path, clock, anchor=anchor)
    assert reopened.entries == ledger.entries, "a reopened ledger reads back every entry exactly"
    later = reopened.append("live-check", INVENTORY, "1.0.0", "quarantined", [], {"toolsetDigest": PIN_100["toolsetDigest"]})
    assert (later["sequence"], later["previousHash"]) == (anchor[0] + 1, anchor[1]), "a reopened ledger continues its chain"
    try:
        grown = LedgerFile(path, clock, anchor=anchor)
    except LedgerError:
        pytest.fail("an anchor still holds after the ledger grows")
    assert grown.head() == (anchor[0] + 1, later["entryHash"])

    good = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n")[:-1]]
    write_entries(path, good[:4])  # the newest entries cut off
    assert len(LedgerFile(path, clock).entries) == 4, "a cut-off chain still verifies on its own"
    assert raises(LedgerError, LedgerFile, path, clock, anchor=anchor), "an anchored head catches a cut-off tail"

    forged = deepcopy(good)
    forged[1]["outcome"] = "approved"
    write_entries(path, rechain(forged))
    assert LedgerFile(path, clock).entries[1]["outcome"] == "approved", "a rechained ledger verifies on its own"
    assert raises(LedgerError, LedgerFile, path, clock, anchor=anchor), "an anchored head catches a rewritten chain"

    edited = deepcopy(good)
    edited[2]["time"] = "2026-11-01T08:59:59+00:00"
    write_entries(path, edited)
    assert raises(LedgerError, LedgerFile, path, clock), "a changed field breaks the chain"
    assert raises(LedgerError, LedgerFile, path, clock, anchor=anchor), "an anchor does not replace verifying the chain"

    path.unlink()
    assert LedgerFile(path, clock).entries == [], "a missing file is an empty ledger"
    assert raises(LedgerError, LedgerFile, path, clock, anchor=anchor), "a missing ledger cannot hold its anchor"


@pytest.mark.skip("Part 3")
def test_admission_controls() -> None:
    """Admission joins publication, provenance and the live endpoint, and pins exactly what passed."""
    rec = record("1.0.0")
    ev = evidence_for(rec)
    live = discover("1.0.0")
    assert decide(listing(rec), "1.0.0", NAMESPACE, ev, live) == Decision(True, (), pin_for(rec, ev, live)), (
        "an admitted version is pinned on every layer"
    )

    def reasons(item=None, requested="1.0.0", namespace=NAMESPACE, evidence=None, live=None, required=("tools",)):
        item = listing(rec) if item is None else item
        evidence = ev if evidence is None else evidence
        live = discover("1.0.0") if live is None else live
        return decide(item, requested, namespace, evidence, live, required).reasons

    assert reasons(requested="^1.0") == ("version",), "a range selects a version, it does not pin one"
    assert reasons(requested="1.0.1") == ("version",), "the record must be the version that was asked for"
    for floating in ("latest", "^1.4", ">=1.4.0"):
        loose = record(floating)
        assert reasons(listing(loose), floating, evidence=evidence_for(loose), live=discover(floating)) == ("version",), (
            f"{floating} is never a pin, even when the record says so"
        )
    calendar = record("2026-11-01")
    assert reasons(listing(calendar), "2026-11-01", evidence=evidence_for(calendar), live=discover("2026-11-01")) == (), (
        "the Registry does not require semantic versions"
    )
    republished = record("1.0.1", packages=deepcopy(rec["packages"]))  # a new record around the same package
    assert [reasons(listing(republished), version, live=discover("1.0.1")) for version in ("1.0.1", "1.0.0")] == [
        (),
        ("version",),
    ], "the Registry version and the package version are separate"
    assert reasons(listing(rec, "deprecated")) == ("status",), "only an active version is admitted"
    squatted = record("1.0.0", name="org.attacker/inventory")
    assert reasons(listing(squatted), evidence=evidence_for(squatted)) == ("namespace",), (
        "identity comes from the record and the verified namespace, never from serverInfo"
    )

    spoofed = discover("1.0.0")
    spoofed["_meta"][SERVER_INFO_KEY] = {"name": "org.attacker/pretend", "version": "99.0.0"}
    pin = decide(listing(rec), "1.0.0", NAMESPACE, ev, spoofed).pin
    assert pin is not None and (pin["server"], pin["version"]) == (INVENTORY, "1.0.0"), (
        "serverInfo is diagnostic and names nothing"
    )
    assert pin["reportedServerInfo"] == {"name": "org.attacker/pretend", "version": "99.0.0"}, (
        "the server's own report is kept as evidence"
    )
    alias = discover("1.0.0")
    alias["serverInfo"] = alias.pop("_meta")[SERVER_INFO_KEY]
    assert decide(listing(rec), "1.0.0", NAMESPACE, ev, alias).pin["reportedServerInfo"] is None, (
        "only _meta carries serverInfo"
    )

    npm = {"registryType": "npm", "identifier": "example-mcp-inventory", "version": "1.0.0", "transport": {"type": "stdio"}}
    two = record("1.0.0", packages=[npm, rec["packages"][0]])
    assert decide(listing(two), "1.0.0", NAMESPACE, ev, live) == Decision(True, (), pin_for(two, ev, live)), (
        "a package joins on registryType, identifier and version together"
    )
    for change in (
        {"version": "1.0.1"},
        {"registryType": "npm"},
        {"transportType": "streamable-http"},
        {"verified": False},
        {"verified": "false"},
    ):
        assert reasons(evidence={**ev, **change}) == ("source",), f"the evidence must join a declared package: {change}"
    assert reasons(evidence={**ev, "digestFrom": "artifact"}) == ("digest",), (
        "a digest the artifact gives about itself proves nothing"
    )
    unsourced = {key: value for key, value in ev.items() if key != "digestFrom"}
    assert reasons(evidence=unsourced) == ("digest",), "a digest of unknown origin proves nothing"
    assert reasons(evidence={**ev, "digestFrom": "package-service"}) == (), "a validated package service's digest counts"
    assert reasons(evidence={**ev, "digest": "sha256:" + ev["digest"]}) == ("digest",), "a digest is 64 hex digits"

    remote_only = {
        "$schema": SCHEMA,
        "name": INVENTORY,
        "version": "1.0.0",
        "description": "Remote inventory server",
        "remotes": [
            {
                "type": "streamable-http",
                "url": "https://MCP.Example.COM:443/mcp",
                "headers": [{"name": "Authorization", "isSecret": True}],
            }
        ],
    }
    remote_ev = {
        "kind": "remote",
        "url": "https://mcp.example.com/mcp",
        "transportType": "streamable-http",
        "digest": digest({"tlsIdentity": "mcp.example.com", "route": "/mcp"}),
        "digestFrom": "fetch",
        "verified": True,
    }
    source = {**remote_only["remotes"][0], "kind": "remote", "url": "https://mcp.example.com/mcp"}
    assert decide(listing(remote_only), "1.0.0", NAMESPACE, remote_ev, live) == Decision(
        True, (), pin_for(remote_only, remote_ev, live, source)
    ), "a record with only a remote is complete"
    for change in ({"transportType": "sse"}, {"url": "https://mcp.example.net/mcp"}, {"verified": False}):
        assert reasons(listing(remote_only), evidence={**remote_ev, **change}) == ("source",), (
            f"the evidence must join a declared remote whose ownership was verified: {change}"
        )
    assert reasons(listing(remote_only), evidence={**remote_ev, "url": "https://mcp.example.com:443/mcp"}) == (), (
        "both URLs are normalized before they are compared"
    )
    plain = deepcopy(remote_only)
    plain["remotes"][0]["url"] = "http://mcp.example.com/mcp"
    assert reasons(listing(plain), evidence={**remote_ev, "url": "http://mcp.example.com/mcp"}) == ("source",), (
        "only an HTTPS remote can join"
    )

    assert reasons(live=discover("1.0.0", supportedVersions=["2025-11-25", PROTOCOL_VERSION])) == (), (
        "2026-07-28 can be any of the supported versions"
    )
    unversioned = discover("1.0.0")
    del unversioned["supportedVersions"]
    for result in (discover("1.0.0", supportedVersions=["2025-11-25"]), discover("1.0.0", supportedVersions=PROTOCOL_VERSION), unversioned):
        assert reasons(live=result) == ("protocol",), "the live server must support 2026-07-28"
    both = discover("1.0.0", capabilities={"tools": {}, "resources": {}})
    assert reasons(live=both, required=("tools", "resources")) == (), "an empty capability object still declares it"
    bare = discover("1.0.0")
    del bare["capabilities"]
    for result in (discover("1.0.0"), bare):
        assert reasons(live=result, required=("tools", "resources")) == ("capabilities",), (
            "every required capability must be there"
        )
    listed = discover("1.0.0", capabilities=["tools", "resources"])
    assert reasons(live=listed, required=("tools", "resources")) == ("capabilities",), "capabilities is an object"
    blank = deepcopy(TOOLS)
    blank[1]["description"] = "  "
    unnamed = deepcopy(TOOLS)
    unnamed[2]["name"] = " "
    schemaless = deepcopy(TOOLS)
    del schemaless[0]["inputSchema"]
    for tools in (blank, unnamed, schemaless, [None]):
        assert reasons(live=discover("1.0.0", tools=tools)) == ("tools",), (
            "every tool needs a name, a description and an inputSchema object"
        )
    assert reasons(
        listing(rec, "deprecated"),
        namespace="org.attacker",
        evidence={**ev, "digestFrom": "artifact", "verified": False},
        live=discover("1.0.0", supportedVersions=["2025-11-25"]),
    ) == ("status", "namespace", "source", "digest", "protocol"), "every failed control is listed once, in CONTROLS order"

    controller = AdmissionController(AdmissionLedger(ticks()))
    controller.admit(listing(rec), "1.0.0", NAMESPACE, ev, live)
    controller.admit(listing(record("1.1.0")), "^1.1", NAMESPACE, evidence_for(record("1.1.0")), discover("1.1.0"))
    assert [(e["version"], e["outcome"], e["reasons"]) for e in controller.ledger.entries] == [
        ("1.0.0", "approved", []),
        ("^1.1", "rejected", ["version"]),
    ], "every admission decision is recorded"
    assert controller.ledger.entries[0]["evidence"] == {"pin": pin_for(rec, ev, live)}
    assert controller.state.active == {INVENTORY: "1.0.0"}, "an admitted version takes new work"


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def arrive(observations: list[dict]):
    for observation in observations:
        yield observation


def ndjson(chunks: list[str]) -> list[dict]:
    text = "".join(chunks)
    assert text.endswith("\n"), "every verdict ends with a newline"
    return [json.loads(line) for line in text.split("\n")[:-1]]


@pytest.mark.skip("Part 4")
def test_reconcile_stream() -> None:
    """Every observation is recorded and judged as it arrives, by the layer of the pin it contradicts."""
    records = {
        (rec["name"], rec["version"]): rec
        for rec in (record("1.0.0"), record("1.1.0"), record("2.0.0", BILLING), record("3.0.0", SEARCH))
    }
    pins = {(name, version): admitted(version, name) for name, version in records}
    state = RouteState(pins=deepcopy(pins), active={INVENTORY: "1.1.0", BILLING: "2.0.0", SEARCH: "3.0.0"})
    ledger = AdmissionLedger(ticks())
    secret = "Bearer sk-live-7f3a"
    reworded = {**records[(BILLING, "2.0.0")], "description": "Billing, now with refunds"}
    rebuilt = wheel("example-mcp-search", "3.0.0+rebuild")
    old_protocol = discover("3.0.0", SEARCH, supportedVersions=["2025-11-25"])

    def seen(check: str, server: str, version: str, **fields) -> dict:
        return {"check": check, "server": server, "version": version, **fields}

    observations = [
        seen(
            "live",
            INVENTORY,
            "1.1.0",
            live=discover("1.1.0", tools=TOOLS[::-1]),
            probe={"headers": {"Authorization": secret}, "call": {"name": "inventory_get", "arguments": {"sku": "A-1"}}},
        ),
        seen("registry", INVENTORY, "1.0.0", item=listing(records[(INVENTORY, "1.0.0")], "deleted")),
        seen("registry", INVENTORY, "1.1.0", item=listing(records[(INVENTORY, "1.1.0")], "deprecated")),
        seen("live", INVENTORY, "1.1.0", live=discover("1.1.0")),
        seen("registry", INVENTORY, "1.2.0", item=listing(record("1.2.0"))),
        seen("registry", BILLING, "2.0.0", item=listing(reworded, "deprecated")),
        seen(
            "artifact",
            SEARCH,
            "3.0.0",
            sourceDigest=pins[(SEARCH, "3.0.0")]["sourceDigest"],
            fetch={"headers": {"Authorization": secret}},
        ),
        seen("artifact", SEARCH, "3.0.0", sourceDigest=rebuilt),
        seen("live", SEARCH, "3.0.0", live=old_protocol),
        seen("live", BILLING, "2.0.0", live=discover("2.0.0", BILLING, tools=[None])),
    ]
    verdicts = ndjson(collect(reconcile(arrive(observations), state, ledger)))
    rows = [(v["server"], v["version"], v["layers"], v["verdict"], v["active"]) for v in verdicts]
    assert rows[0] == (INVENTORY, "1.1.0", [], "ok", "1.1.0"), "the order of the tool list is not drift"
    assert rows[1] == (INVENTORY, "1.0.0", ["registry-status"], "quarantined", "1.1.0"), (
        "quarantining a version that takes no new work leaves the route alone"
    )
    assert rows[2] == (INVENTORY, "1.1.0", ["registry-status"], "quarantined", None), "deprecated stops new work too"
    assert rows[3] == (INVENTORY, "1.1.0", [], "quarantined", None), "a quarantine sticks"
    assert rows[4] == (INVENTORY, "1.2.0", [], "unknown", None), "an observation without a pin changes nothing"
    assert rows[5] == (BILLING, "2.0.0", ["registry-integrity", "registry-status"], "quarantined", None), (
        "a changed record under the same version is a Registry integrity failure"
    )
    assert rows[6:8] == [
        (SEARCH, "3.0.0", [], "ok", "3.0.0"),
        (SEARCH, "3.0.0", ["source-integrity"], "quarantined", None),
    ], "new bytes for the same package coordinate are an execution-source failure"
    assert rows[8] == (SEARCH, "3.0.0", ["runtime-drift"], "quarantined", None), (
        "failing the live checks is drift, even with the same tools"
    )
    assert rows[9] == (BILLING, "2.0.0", ["runtime-drift"], "quarantined", None), "a malformed tool list is drift"
    assert [(v["seq"], v["check"]) for v in verdicts] == [
        (e["sequence"], o["check"]) for e, o in zip(ledger.entries, observations)
    ] and len(verdicts) == len(observations), "each verdict names the ledger entry that records it"

    recorded = canonical_json(ledger.entries)
    assert secret not in recorded and "arguments" not in recorded, "no credential or tool argument reaches the ledger"
    toolset = toolset_digest(TOOLS)
    status = "registry-status"
    assert [(e["event"], e["outcome"], e["reasons"], e["evidence"]) for e in ledger.entries] == [
        ("live-check", "ok", [], {"toolsetDigest": toolset}),
        ("registry-sync", "quarantined", [status], {"recordDigest": digest(records[(INVENTORY, "1.0.0")]), "status": "deleted"}),
        ("registry-sync", "quarantined", [status], {"recordDigest": digest(records[(INVENTORY, "1.1.0")]), "status": "deprecated"}),
        ("live-check", "quarantined", [], {"toolsetDigest": toolset}),
        ("registry-sync", "unknown", [], {"recordDigest": digest(record("1.2.0")), "status": "active"}),
        ("registry-sync", "quarantined", ["registry-integrity", status], {"recordDigest": digest(reworded), "status": "deprecated"}),
        ("artifact-check", "ok", [], {"sourceDigest": pins[(SEARCH, "3.0.0")]["sourceDigest"]}),
        ("artifact-check", "quarantined", ["source-integrity"], {"sourceDigest": rebuilt}),
        ("live-check", "quarantined", ["runtime-drift"], {"toolsetDigest": toolset}),
        ("live-check", "quarantined", ["runtime-drift"], {"toolsetDigest": None}),
    ], "the ledger holds every observation, with only what was observed as evidence"
    assert state.pins == pins, "a quarantined pin stays as evidence, deleted versions too"
    assert (state.active, state.quarantined) == (
        {},
        {(INVENTORY, "1.0.0"), (INVENTORY, "1.1.0"), (BILLING, "2.0.0"), (SEARCH, "3.0.0")},
    ), "the route table and the quarantine list follow the verdicts"

    strict = reconcile(
        arrive([seen("live", INVENTORY, "1.0.0", live=discover("1.0.0"))]),
        RouteState(pins=deepcopy(pins), active={INVENTORY: "1.0.0"}),
        AdmissionLedger(ticks()),
        ("tools", "resources"),
    )
    assert ndjson(collect(strict))[0]["layers"] == ["runtime-drift"], "the live checks use the required capabilities given"

    pulled: list[int] = []

    async def busy():
        for i in range(100):
            pulled.append(i)
            yield {"check": "live", "server": INVENTORY, "version": "1.0.0", "live": discover("1.0.0")}

    probe_ledger = AdmissionLedger(ticks())

    async def first_verdict() -> tuple[str, int]:
        agen = reconcile(busy(), RouteState(pins=deepcopy(pins), active={INVENTORY: "1.0.0"}), probe_ledger)
        first = await agen.__anext__()
        recorded = len(probe_ledger.entries)
        await agen.aclose()
        return first, recorded

    first, recorded = asyncio.run(first_verdict())
    assert ndjson([first])[0]["verdict"] == "ok"
    assert len(pulled) <= 1, "each verdict goes out as soon as its observation is judged"
    assert recorded == 1, "a verdict goes out only once the ledger holds it"


@pytest.mark.skip("Part 5")
def test_rollback_from_history() -> None:
    """Rollback restores a route the ledger proves safe, and the ledger only grows."""
    versions = [(INVENTORY, "1.0.0"), (INVENTORY, "1.1.0"), (INVENTORY, "1.2.0"), (BILLING, "1.0.0"), (BILLING, "1.2.0")]
    pins = {(name, version): admitted(version, name) for name, version in versions}
    refused = {
        "recordDigest": digest(record("1.1.0")),
        "status": "active",
        "verifiedNamespace": NAMESPACE,
        "claimedNamespace": NAMESPACE,
    }
    deprecated = {"recordDigest": digest(record("1.2.0", BILLING)), "status": "deprecated"}
    back = {"from": "1.2.0", "to": "0.9.0", "reason": "old habit"}
    ledger = AdmissionLedger(ticks())
    for event in (
        ("admission", INVENTORY, "1.0.0", "approved", [], {"pin": pins[(INVENTORY, "1.0.0")]}),
        ("admission", BILLING, "1.0.0", "approved", [], {"pin": pins[(BILLING, "1.0.0")]}),
        ("admission", INVENTORY, "1.1.0", "rejected", ["digest"], refused),
        ("admission", INVENTORY, "1.1.0", "approved", [], {"pin": pins[(INVENTORY, "1.1.0")]}),
        ("admission", INVENTORY, "1.2.0", "approved", [], {"pin": pins[(INVENTORY, "1.2.0")]}),
        ("live-check", INVENTORY, "1.1.0", "quarantined", ["runtime-drift"], {"toolsetDigest": digest("drifted")}),
        ("admission", BILLING, "1.2.0", "approved", [], {"pin": pins[(BILLING, "1.2.0")]}),
        ("registry-sync", BILLING, "1.2.0", "quarantined", ["registry-status"], deprecated),
        ("rollback", INVENTORY, "0.9.0", "rejected", ["unknown"], back),
        ("admission", INVENTORY, "1.3.0", "rejected", ["status"], {**refused, "status": "deprecated"}),
        ("live-check", INVENTORY, "1.2.0", "ok", [], {"toolsetDigest": toolset_digest(TOOLS)}),
    ):
        ledger.append(*event)

    state = fold(ledger.entries)
    assert BILLING not in state.active, "a quarantined active version leaves its route"
    assert state.active == {INVENTORY: "1.2.0"}, (
        "rejected decisions move no route, and one server's quarantine is not another's"
    )
    assert {v: state.state_of(INVENTORY, v) for v in ("0.9.0", "1.0.0", "1.1.0", "1.2.0", "1.3.0")} == {
        "0.9.0": "unknown",
        "1.0.0": "superseded",
        "1.1.0": "quarantined",
        "1.2.0": "active",
        "1.3.0": "unknown",
    }, "only an approved admission admits a version, and any check can quarantine one"
    assert {v: state.state_of(BILLING, v) for v in ("1.0.0", "1.2.0")} == {"1.0.0": "approved", "1.2.0": "quarantined"}
    assert state.pins == pins, "every admitted pin is kept, quarantined ones too"

    history = deepcopy(ledger.entries)
    down = {(INVENTORY, "1.0.0"), (INVENTORY, "1.1.0")}
    asked: list[tuple[str, str]] = []

    def healthy(server: str, version: str) -> bool:
        asked.append((server, version))
        return (server, version) not in down

    attempts = [
        (INVENTORY, "1.3.0", "try the candidate"),
        (BILLING, "1.1.0", "the number inventory uses"),
        (INVENTORY, "1.1.0", "drift was a false alarm"),
        (INVENTORY, "1.0.0", "1.2.0 times out"),
    ]
    decisions = [rollback(ledger, server, target, why, healthy).reasons for server, target, why in attempts]
    assert decisions == [("unknown",), ("unknown",), ("quarantined",), ("unhealthy",)], (
        "a target needs an approved admission, no quarantine and a passing health check, in that order"
    )
    down.clear()
    restored = rollback(ledger, INVENTORY, "1.0.0", "1.2.0 times out", healthy)
    assert restored == Decision(True, (), pins[(INVENTORY, "1.0.0")]), "an eligible target gets the route back"
    again = rollback(ledger, INVENTORY, "1.2.0", "the timeout was upstream", healthy)
    revived = rollback(ledger, BILLING, "1.0.0", "1.2.0 is deprecated", healthy)
    assert again.allowed and revived.allowed
    assert asked == [(INVENTORY, "1.0.0"), (INVENTORY, "1.0.0"), (INVENTORY, "1.2.0"), (BILLING, "1.0.0")], (
        "the health check runs only for a target the ledger allows"
    )

    assert ledger.entries[: len(history)] == history and ledger.verify(), "a rollback only appends to the ledger"
    assert [(e["outcome"], e["reasons"], e["evidence"]) for e in ledger.entries[len(history) :]] == [
        ("rejected", ["unknown"], {"from": "1.2.0", "to": "1.3.0", "reason": "try the candidate"}),
        ("rejected", ["unknown"], {"from": None, "to": "1.1.0", "reason": "the number inventory uses"}),
        ("rejected", ["quarantined"], {"from": "1.2.0", "to": "1.1.0", "reason": "drift was a false alarm"}),
        ("rejected", ["unhealthy"], {"from": "1.2.0", "to": "1.0.0", "reason": "1.2.0 times out"}),
        ("activated", [], {"from": "1.2.0", "to": "1.0.0", "reason": "1.2.0 times out"}),
        ("activated", [], {"from": "1.0.0", "to": "1.2.0", "reason": "the timeout was upstream"}),
        ("activated", [], {"from": None, "to": "1.0.0", "reason": "1.2.0 is deprecated"}),
    ], "every rollback decision is recorded, and each one starts from the route the ledger shows"
    assert fold(ledger.entries).active == {INVENTORY: "1.2.0", BILLING: "1.0.0"}, "the ledger folds to the restored routes"
