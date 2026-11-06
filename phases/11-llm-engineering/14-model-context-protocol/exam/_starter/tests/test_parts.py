import asyncio,json,time
from dataclasses import replace
import pytest
from primitiveboard.contracts import Spec,Entry,CatalogNode,RegistrationChange,slot_key
from primitiveboard.registry import Catalog,make_entry,register_batch
from primitiveboard.manifest import save_manifest,load_manifest
from primitiveboard.surface import descriptor,compile_surface
from primitiveboard.invocation import invoke_entry
from primitiveboard.change_driver import publish_changes
from primitiveboard.nested import export_catalog
def spec(kind,name,handler="action",**fields):return Spec(kind,name,"description "+name,handler,**fields)
def fixtures():
    def action(**arguments):return {"value":arguments.get("x",0)}
    def resource():return '{"region":"你好"}'
    def prompt(**arguments):return "Review "+arguments["language"]+":\n"+arguments["code"]
    handlers={"action":action,"resource":resource,"prompt":prompt}
    specs=(spec("tool","shared",input_schema={"type":"object","properties":{"x":{"type":"integer"}}},destructive=True),spec("resource","shared","resource",uri="config://Z/%2F"),spec("prompt","shared","prompt",arguments=("language","code")))
    return specs,handlers
def registration_fixture():
    return tuple(spec(("tool","resource","prompt")[i%3],f"primitive-{i:05}",uri=f"context://{i:05}",arguments=("question",) if i%3==2 else ()) for i in range(5000))
@pytest.mark.skip("Part 1")
def test_registration_inventory():
    """Repair callable registration, independent primitive scopes and responsive full inventory."""
    calls=[]
    def action():calls.append("action");return {"result":"business output"}
    catalog=Catalog({"action":action});first=spec("tool","shared");catalog.register(first)
    assert catalog.entries()[0].handler is action and calls==[],"registration preserves callable references without executing business actions"
    catalog.register(spec("prompt","shared",arguments=("query",)))
    catalog.register(spec("resource","shared",uri="context://one"));catalog.register(spec("resource","shared",uri="context://two"))
    assert catalog.inventory()==(("prompt","shared","action"),("resource","context://one","action"),("resource","context://two","action"),("tool","shared","action")),"tools prompts and URI-addressed resources retain independent registration identities"
    newer=replace(first,description="replacement");catalog.register(newer)
    assert len(catalog.entries())==4 and catalog.get(("tool","shared")).spec==newer,"same-kind registration replaces only its own original identity"
    assert calls==[] and all(callable(entry.handler) for entry in catalog.entries()),"inventory discovery does not invoke any primitive handler"
    specs=registration_fixture();expected=tuple(sorted((s.kind,s.uri if s.kind=="resource" else s.name,s.handler_name) for s in specs));started=time.perf_counter()
    complete,inventory=register_batch(specs,{"action":action})
    assert inventory==expected and tuple(entry.spec for entry in complete.entries())==specs and all(entry.handler is action for entry in complete.entries()) and calls==[],"bulk registration retains every descriptor handler and final deterministic identity view"
    elapsed=time.perf_counter()-started
    assert elapsed<0.2,"large primitive registration batches should stay responsive"
    complete.register(spec("tool","after-export"))
    assert ("tool","after-export","action") in complete.inventory() and len(complete.inventory())==5001,"later registrations refresh the complete exported inventory"
@pytest.mark.skip("Part 2")
def test_named_handler_manifest(tmp_path):
    """Save full primitive specs and rebind only declared safe local handler names."""
    specs,handlers=fixtures();entries=tuple(make_entry(s,handlers) for s in specs);path=tmp_path/"surface.json"
    save_manifest(path,entries);loaded=load_manifest(path,handlers)
    assert tuple(entry.spec for entry in loaded)==specs,"reopened manifests retain primitive kinds URIs schema annotations and ordered prompt arguments"
    assert all(entry.handler is handlers[entry.spec.handler_name] for entry in loaded),"every persisted primitive rebinds to its own declared local handler reference"
    raw=json.loads(path.read_bytes())
    assert raw["entries"][1]["uri"]=="config://Z/%2F" and raw["entries"][2]["arguments"]==["language","code"] and raw["entries"][0]["destructive"] is True,"local manifests preserve exact domain identity and descriptor metadata"
    different=dict(handlers)
    def replacement(**args):return {"new":True}
    different["action"]=replacement
    rebound=load_manifest(path,different)
    assert rebound[0].handler is replacement and rebound[1].handler is handlers["resource"] and rebound[2].handler is handlers["prompt"],"reopening uses the current safe registry without mixing unrelated primitive handlers"
    with pytest.raises(ValueError,match="unavailable local handler: resource"):load_manifest(path,{"action":handlers["action"],"prompt":handlers["prompt"]})
    changed=tuple(make_entry(replace(s,description=s.description+"\n多行"),handlers) for s in specs)
    save_manifest(path,changed);assert tuple(entry.spec for entry in load_manifest(path,handlers))==tuple(entry.spec for entry in changed),"a manifest replacement preserves every newly supplied primitive description"
    save_manifest(path,());assert load_manifest(path,handlers)==(),"an empty local manifest restores an empty registration set"
    precise=make_entry(replace(specs[0],input_schema={"type":"object","properties":{"x":{"type":"integer","enum":[9007199254740993]}}}),handlers)
    save_manifest(path,(precise,))
    assert load_manifest(path,handlers)[0].spec==precise.spec,"organizing a manifest must not coerce complete nested schema values"
@pytest.mark.skip("Part 3")
def test_three_primitive_compilation():
    """Compile distinct descriptor fields and content contents messages result shapes."""
    specs,handlers=fixtures();entries=tuple(make_entry(s,handlers) for s in specs)
    extra=make_entry(spec("tool","alpha"),handlers);resource=make_entry(spec("resource","first label","resource",uri="config://A"),handlers)
    surface=compile_surface((entries[2],entries[1],entries[0],extra,resource))
    assert surface["tools"]==[{"name":"alpha","description":"description alpha","inputSchema":{},"annotations":{}},{"name":"shared","description":"description shared","inputSchema":specs[0].input_schema,"annotations":{"destructiveHint":True}}],"tool descriptors preserve schema and destructive annotations in their own surface"
    assert surface["resources"]==[{"uri":"config://A","name":"first label","description":"description first label"},{"uri":"config://Z/%2F","name":"shared","description":"description shared"}],"resource descriptors are URI-addressed content ordered independently of display labels"
    assert surface["prompts"]==[{"name":"shared","description":"description shared","arguments":[{"name":"language","required":True},{"name":"code","required":True}]}],"prompt descriptors retain the declared ordered required argument sequence"
    assert surface["capabilities"]=={"tools":{},"resources":{},"prompts":{}} and compile_surface(())["capabilities"]==surface["capabilities"],"the supplied source support declarations are independent of catalog emptiness"
    surface["tools"][1]["inputSchema"]["properties"]["x"]["type"]="string"
    assert specs[0].input_schema["properties"]["x"]["type"]=="integer","exported descriptor containers cannot rewrite registered metadata"
    assert entries[0].spec.input_schema["properties"]["x"]["type"]=="integer","descriptor export cannot mutate the registered entry schema"
    tool=invoke_entry(entries[0],{"x":7});read=invoke_entry(entries[1],{});prompt=invoke_entry(entries[2],{"language":"Python","code":"print('你好')"})
    assert json.loads(tool["content"][0]["text"])=={"value":7} and tool["isError"] is False and "contents" not in tool and "messages" not in tool,"tool results publish action output under text content"
    assert read["contents"]==[{"uri":"config://Z/%2F","mimeType":"text/plain","text":'{"region":"你好"}'}] and "content" not in read,"resource reads retain their exact URI and source content collection"
    assert prompt["messages"]==[{"role":"user","content":{"type":"text","text":"Review Python:\nprint('你好')"}}] and "content" not in prompt,"prompt results produce user messages rather than tool or resource content collections"
    assert all(r["resultType"]=="complete" and r["_meta"]["io.modelcontextprotocol/serverInfo"]["name"]=="local-board" for r in (tool,read,prompt)) and read["cacheScope"]=="private" and "ttlMs" not in tool and "ttlMs" not in prompt,"given result wrappers retain the source per-operation metadata policy"
@pytest.mark.skip("Part 4")
def test_registration_change_artifacts():
    """Audit actual descriptor field changes through a supplied local NDJSON driver."""
    specs,handlers=fixtures();tool,resource,prompt=specs
    edits=(RegistrationChange("upsert",tool),RegistrationChange("upsert",resource),RegistrationChange("upsert",prompt),RegistrationChange("upsert",replace(resource,description="new resource")),RegistrationChange("upsert",replace(prompt,arguments=("code","language"))),RegistrationChange("remove",resource))
    pulled=[];closed=[]
    async def source():
        try:
            for change in edits:pulled.append(change);yield change
        finally:closed.append(True)
    async def run():
        stream=publish_changes(source(),handlers);first_line=await stream.__anext__();first=json.loads(first_line)
        assert len(pulled)==1 and first_line.endswith("\n") and first_line.count("\n")==1 and first["kind"]=="tool" and first["identity"]=="shared","the supplied artifact driver publishes one complete current registration change before pulling later input"
        assert first["operation"]=="add" and first["changed_fields"]==["name","description","inputSchema","annotations"] and first["descriptor"]["annotations"]=={"destructiveHint":True},"add artifacts retain all declared fields of the actual primitive descriptor"
        rows=[json.loads(line) async for line in stream]
        resource_update=rows[2];prompt_update=rows[3];removed=rows[4];final=rows[5]
        assert resource_update["kind"]=="resource" and resource_update["identity"]==resource.uri and resource_update["changed_fields"]==["description"] and resource_update["descriptor"]["description"]=="new resource","update artifacts report only the actual changed source descriptor fields"
        assert prompt_update["changed_fields"]==["arguments"] and prompt_update["descriptor"]["arguments"]==[{"name":"code","required":True},{"name":"language","required":True}],"prompt argument order changes remain visible in local change evidence"
        assert removed["operation"]=="remove" and removed["changed_fields"]==["uri","name","description"] and removed["descriptor"] is None,"removal artifacts contain a tombstone rather than a stale live descriptor"
        assert final["type"]=="manifest" and final["surface"]["resources"]==[] and len(final["surface"]["tools"])==len(final["surface"]["prompts"])==1 and closed==[True],"the supplied final manifest reflects actual independent primitive registrations and source closure"
        pulled.clear();closed.clear();early=publish_changes(source(),handlers);await early.__anext__();await early.aclose()
        assert len(pulled)==1 and closed==[True],"early close stops the supplied registration driver before a later change"
    asyncio.run(run())
    changed_tool=replace(tool,description="new tool",input_schema={"type":"object","properties":{"x":{"type":"string"}}},destructive=False)
    async def nested_updates():
        for change in (RegistrationChange("upsert",tool),RegistrationChange("upsert",changed_tool)):yield change
    async def collect_updates():return [json.loads(line) async for line in publish_changes(nested_updates(),handlers)]
    updated=asyncio.run(collect_updates())[1]
    assert updated["changed_fields"]==["description","inputSchema","annotations"] and updated["descriptor"]=={"name":"shared","description":"new tool","inputSchema":changed_tool.input_schema,"annotations":{}},"audit updates compare nested descriptor values and preserve source field order"
@pytest.mark.skip("Part 5")
def test_local_catalog_paths():
    """Retain own entries and nested local catalog paths for all three primitive kinds."""
    specs,handlers=fixtures();tool,resource,prompt=tuple(make_entry(s,handlers) for s in specs)
    root=CatalogNode("root",(tool,), (CatalogNode("left",(resource,), (CatalogNode("shared",(prompt,)),)),CatalogNode("right",(),(CatalogNode("shared",(tool,resource,prompt)),))))
    rows=export_catalog(root)
    assert [(row["catalog_path"],row["kind"],row["identity"]) for row in rows]==[(("root",),"tool","shared"),(("root","left"),"resource","config://Z/%2F"),(("root","left","shared"),"prompt","shared"),(("root","right","shared"),"tool","shared"),(("root","right","shared"),"resource","config://Z/%2F"),(("root","right","shared"),"prompt","shared")],"nested local catalogs retain complete preorder paths and all primitive kinds"
    assert [row["handler"] for row in rows]==[tool.handler,resource.handler,prompt.handler,tool.handler,resource.handler,prompt.handler],"catalog export preserves each original local callable reference"
    assert rows[2]["descriptor"]["arguments"]==[{"name":"language","required":True},{"name":"code","required":True}] and rows[4]["descriptor"]["uri"]==resource.spec.uri,"nested descriptors retain their primitive-specific source fields"
    with pytest.raises(ValueError,match="duplicate primitive in one catalog scope"):export_catalog(CatalogNode("root",(tool,tool)))
    assert len(export_catalog(CatalogNode("root",(tool,prompt))))==2,"the supplied duplicate scope rule keeps equal names across primitive kinds independent"
    assert export_catalog(CatalogNode("empty"))==(),"an empty local catalog yields no descriptor rows"
    left=make_entry(replace(specs[0],description="left own",input_schema={"type":"object","properties":{"left":{"type":"string"}}}),handlers)
    right=make_entry(replace(specs[0],description="right own",input_schema={"type":"object","properties":{"right":{"type":"integer"}}},destructive=False),handlers)
    scoped=export_catalog(CatalogNode("root",(),(CatalogNode("left",(left,)),CatalogNode("right",(right,)))))
    assert [row["descriptor"]["description"] for row in scoped]==["left own","right own"] and [row["descriptor"]["inputSchema"] for row in scoped]==[left.spec.input_schema,right.spec.input_schema] and [row["descriptor"]["annotations"] for row in scoped]==[{"destructiveHint":True},{}],"equal primitive identities in different catalog scopes retain their own descriptors"
