import asyncio,json,math
from dataclasses import replace
from time import perf_counter
import pytest
from speechact.models import ACLMessage,RequestState,SubscriptionState,Atom,Quoted,SList
from speechact.translation import translate_acl,mcp_resources_read_to_acl
from speechact.codec import render_acl,encode_acl
from speechact.service import SpeechService
from speechact.wire_support import parse_envelope,wire_fields,quoted
from speechact.journal import ACLJournal
from speechact.conversations import advance_request_obligation,advance_subscription_obligation,recognize_conversations
from speechact.stream import ACLFramer,stream_envelopes
from speechact.content import parse_content,render_content

def acl(act,conv,protocol="fipa-request",content="",sender="client",receiver="worker"):
    return ACLMessage(act,sender,receiver,content,"JSON","desk",protocol,conv)

def wire_fixture(message):
    return (f"({message.performative} "+" ".join(f":{name} "+quoted(value) for name,value in wire_fields(message))+")").encode("utf-8")

def large_message():
    return ACLMessage("inform","agent世界","reader",'field "quoted" \\path (世界)\n'*10000,"TEXT","local","fipa-request","001","reply-9")

@pytest.mark.skip("Part 1")
def test_translation_and_complete_acl_wire():
    """Repair source-shaped intent/language projections and a complete finite ACL codec."""
    service=SpeechService()
    request={"id":"001","method":"tools/call","params":{"name":"lookup","arguments":{"key":"x"}}}
    assert service.require_tool_reply(request)=="msg-001", "a translated tool request creates its own reply obligation"
    uri={"id":43,"method":"resources/read","params":{"uri":"file:///local/未读取.txt"}}
    assert service.forward_resource_read(uri)==uri["params"]["uri"], "resource language retains an opaque URI reference without accessing it"
    message=ACLMessage("inform","a世界","b",'quote " \\ path (not a delimiter)\nnext',"TEXT","notes","p","001","r")
    wire,restored=service.roundtrip(message)
    assert restored==message and wire==wire_fixture(message), "quoted content and all original envelope labels survive the complete local wire"
    for content in ("",None,0,False,[],{}):
        empty=replace(message,content=content,protocol="",conversation_id="",reply_with="")
        assert service.roundtrip(empty)[1]==empty, "empty content and present empty labels remain original data"
    big=large_message();expected=wire_fixture(big)
    start=perf_counter();wire,restored=service.roundtrip(big)
    assert wire==expected and restored==big and restored.content==big.content, "complete long ACL output retains every payload character and envelope field"
    elapsed=perf_counter()-start
    assert elapsed<0.1, "a complete local ACL encode and receiving parse remains responsive"
    assert request["params"]["arguments"]=={"key":"x"} and uri["params"]["uri"].endswith(".txt"), "translation leaves caller fixtures unchanged"

@pytest.mark.skip("Part 2")
def test_append_acl_journal(tmp_path):
    """Append and reopen exact envelopes, optional metadata and typed content in order."""
    path=tmp_path/"events.aclj";journal=ACLJournal(path)
    messages=[ACLMessage("request","agent世界","tool",{"ratio":1/3,"big":2**70+9,"zero":-0.0,"empty":""},"JSON","tools","","001",""),ACLMessage("query-ref","agent世界","resource","file:///local/a b","URI","resource",None,"1",None),ACLMessage("inform","a","b","","opaque", "",None,None,"")]
    for message in messages:journal.append(message)
    reopened=ACLJournal(path).read_all()
    assert reopened==messages, "journal reopening retains every original message in append order"
    assert reopened[0].protocol=="" and reopened[1].protocol is None and reopened[2].reply_with=="" and reopened[2].conversation_id is None, "absent optional metadata and present empty labels remain distinct"
    assert [row.conversation_id for row in reopened]==["001","1",None], "conversation labels retain their original spelling and type"
    assert reopened[0].content["ratio"].hex()==(1/3).hex() and reopened[0].content["zero"].hex()==(-0.0).hex() and type(reopened[0].content["big"]) is int, "the supplied tagged payload codec retains exact finite numeric values"
    extra=replace(messages[0],content=["  line\r\n",None,False,[],{}],conversation_id="001")
    ACLJournal(path).append(extra)
    assert ACLJournal(path).read_all()==messages+[extra], "later append retains earlier records and repeated conversation entries"
    assert ACLJournal(tmp_path/"missing").read_all()==[], "an absent local journal has no invented message"
    with path.open("ab") as output:output.write(b"\x00")
    with pytest.raises(ValueError,match="truncated local journal"):ACLJournal(path).read_all()
    identities=replace(messages[0],sender=" Agent A ",receiver=" TOOL ",language="OPAQUE ",ontology=" Domain ")
    identity_journal=ACLJournal(tmp_path/"identities.aclj");identity_journal.append(identities)
    assert identity_journal.read_all()==[identities], "journal preserves opaque identity whitespace"
    values=[None,False,0,[],{}]
    root_messages=[replace(messages[0],content=value) for value in values]
    root_journal=ACLJournal(tmp_path/"roots.aclj")
    for item in root_messages:root_journal.append(item)
    roots=[item.content for item in root_journal.read_all()]
    assert roots==values and [type(value) for value in roots]==[type(value) for value in values], "journal preserves every typed empty payload root"
    live=ACLJournal(tmp_path/"live.aclj");live.append(messages[0]);first_read=live.read_all();live.append(messages[1])
    assert first_read==messages[:1] and live.read_all()==messages[:2], "journal reads include later appends on the same handle"

@pytest.mark.skip("Part 3")
def test_local_speech_act_obligations(tmp_path):
    """Recognize named request and subscription obligations by intent, stage and parties."""
    messages=[acl("request","001"),acl("request","1"),acl("subscribe","001","fipa-subscribe"),acl("subscribe","1","fipa-subscribe"),acl("agree","001",sender="worker",receiver="client"),acl("refuse","1",sender="worker",receiver="client"),acl("inform","001","fipa-subscribe",content={"ok":False},sender="worker",receiver="client"),acl("inform","1","fipa-subscribe",sender="worker",receiver="client"),acl("failure","001",sender="worker",receiver="client"),acl("cancel","001","fipa-subscribe"),acl("inform","1","fipa-subscribe",sender="worker",receiver="client"),acl("request","other"),acl("inform","other",content={"ok":False},sender="worker",receiver="client")]
    journal=ACLJournal(tmp_path/"protocol.aclj")
    for message in messages:journal.append(SpeechService().roundtrip(message)[1])
    report=recognize_conversations(ACLJournal(journal.path).read_all())
    assert [(row["protocol"],row["conversation_id"]) for row in report]==[("fipa-request","001"),("fipa-request","1"),("fipa-subscribe","001"),("fipa-subscribe","1"),("fipa-request","other")], "protocol and exact conversation labels identify independent interactions in first-seen order"
    assert [(row["status"],row["outstanding"],row["notifications"]) for row in report]==[("failed",False,0),("refused",False,0),("cancelled",False,1),("active",True,2),("done",False,0)], "speech acts determine stage and outstanding obligations independently of payload shape"
    initial=advance_request_obligation(None,acl("request","x"))
    agreed=advance_request_obligation(initial,acl("agree","x",sender="worker",receiver="client"))
    assert initial==RequestState("client","worker","pending") and agreed.status=="agreed", "an acknowledgement retains the request parties and an outstanding execution obligation"
    with pytest.raises(ValueError,match="request act outside local stage"):advance_request_obligation(initial,acl("failure","x",sender="worker",receiver="client"))
    with pytest.raises(ValueError,match="request act outside local stage"):advance_request_obligation(agreed,acl("refuse","x",sender="worker",receiver="client"))
    with pytest.raises(ValueError,match="request reply parties"):advance_request_obligation(initial,acl("inform","x",sender="intruder",receiver="client"))
    subscription=advance_subscription_obligation(None,acl("subscribe","s","fipa-subscribe"))
    notification=advance_subscription_obligation(subscription,acl("inform","s","fipa-subscribe",sender="worker",receiver="client"))
    assert notification==SubscriptionState("client","worker",True,1), "a notification increments its subscription while keeping it active"
    cancelled=advance_subscription_obligation(notification,acl("cancel","s","fipa-subscribe"))
    with pytest.raises(ValueError,match="subscription already cancelled"):advance_subscription_obligation(cancelled,acl("inform","s","fipa-subscribe",sender="worker",receiver="client"))
    with pytest.raises(ValueError,match="subscription act or parties"):advance_subscription_obligation(subscription,acl("cancel","s","fipa-subscribe",sender="worker",receiver="client"))
    request=translate_acl({"id":"unanswered","params":{"name":"work","arguments":{}}})
    assert recognize_conversations([request])[0]["outstanding"] and recognize_conversations([])==[], "repaired translation feeds the recognizer without inventing a response"
    terminal_states=(advance_request_obligation(initial,acl("inform","x",sender="worker",receiver="client")),advance_request_obligation(initial,acl("refuse","x",sender="worker",receiver="client")),advance_request_obligation(agreed,acl("failure","x",sender="worker",receiver="client")))
    for terminal in terminal_states:
        with pytest.raises(ValueError,match="request act outside local stage"):advance_request_obligation(terminal,acl("inform","x",sender="worker",receiver="client"))
    with pytest.raises(ValueError,match="request reply parties"):advance_request_obligation(initial,acl("inform","x",sender="worker",receiver="other"))
    with pytest.raises(ValueError,match="subscription act or parties"):advance_subscription_obligation(subscription,acl("subscribe","s","fipa-subscribe"))

@pytest.mark.skip("Part 4")
def test_incremental_acl_envelopes():
    """Frame quoted ACL envelopes across text boundaries through a supplied UTF8 driver."""
    messages=[ACLMessage("inform","agent世界","b",'leading ) quote " \\ and (inner)\n)',"TEXT","o",None,"001",""),ACLMessage("request","x","y","","TEXT","o","fipa-request","1",None)]
    wires=[wire_fixture(message) for message in messages]
    text=wires[0].decode("utf-8");cut=text.index(")")+1
    framer=ACLFramer()
    assert framer.feed(text[:cut])==[], "quoted parentheses do not complete an envelope"
    rest=framer.feed(text[cut:]);framer.finish()
    assert [parse_envelope(piece) for piece in rest]==messages[:1], "a completed envelope retains quote and escape state across text chunks"
    together=ACLFramer()
    assert [parse_envelope(piece) for piece in together.feed((wires[0]+wires[1]).decode("utf-8"))]==messages, "adjacent complete envelopes remain separate and in wire order"
    together.finish()
    async def exercise():
        state={"pulled":0,"closed":False}
        async def source():
            try:
                for wire in wires:state["pulled"]+=1;yield wire
            finally:state["closed"]=True
        output=stream_envelopes(source());first=await output.__anext__()
        assert parse_envelope(first)==messages[0] and state["pulled"]==1, "the supplied driver publishes a completed current envelope before a future chunk"
        await output.aclose()
        assert state=={"pulled":1,"closed":True}, "the supplied driver closes its byte source without pulling a future envelope"
        async def fragmented():
            for byte in b" \n"+b"\t".join(wires)+b" \n":yield bytes((byte,))
        restored=[parse_envelope(piece) async for piece in stream_envelopes(fragmented())]
        assert restored==messages, "codepoint and ACL quote boundaries preserve every complete original message"
        async def truncated():yield wires[0][:-1]
        with pytest.raises(ValueError,match="incomplete ACL envelope"):
            async for piece in stream_envelopes(truncated()):pass
        async def empty():
            if False:yield b""
        assert [piece async for piece in stream_envelopes(empty())]==[], "an empty source contains no invented ACL envelope"
    asyncio.run(exercise())
    with pytest.raises(ValueError,match="ACL opening delimiter"):ACLFramer().feed("junk")

@pytest.mark.skip("Part 5")
def test_typed_nested_content(tmp_path):
    """Preserve the typed syntax of finite nested content independently of its envelope."""
    text='(plan (target "IBM (not envelope)") () "" (price 83) "line\\n\\\"end")'
    expected=SList((Atom("plan"),SList((Atom("target"),Quoted("IBM (not envelope)"))),SList(()),Quoted(""),SList((Atom("price"),Atom("83"))),Quoted('line\n"end')))
    message=ACLMessage("request","client","worker",text,"SL0","finance","fipa-request","tree")
    journal=ACLJournal(tmp_path/"nested.aclj");journal.append(SpeechService().roundtrip(message)[1])
    recovered=journal.read_all()[0]
    assert parse_content(recovered.content)==expected, "nested content retains list shape child order and quoted versus bare values"
    assert parse_content(render_content(expected))==expected, "rendered content preserves the complete typed local tree"
    assert parse_content("()")==SList(()) and parse_content('\"\"')==Quoted("") and parse_content("83")==Atom("83"), "empty lists quoted empty text and numeric-looking atoms are distinct syntax"
    assert recognize_conversations([recovered])==[{"protocol":"fipa-request","conversation_id":"tree","status":"pending","outstanding":True,"notifications":0}], "nested payload parentheses do not change the outer speech-act obligation"
    with pytest.raises(ValueError):parse_content("(one (two)")
    with pytest.raises(ValueError,match="multiple content roots"):parse_content("one two")
    with pytest.raises(ValueError,match="unexpected content closing delimiter"):parse_content(")")
    with pytest.raises(ValueError,match="local atom"):render_content(Atom("not one atom"))
    assert expected.items[1].items[1].value=="IBM (not envelope)", "tree operations leave caller-owned typed content unchanged"
    opaque=SList((Atom("00083"),Atom("0.10"),Atom("-0"),Quoted("00083")))
    assert parse_content(render_content(opaque))==opaque, "numeric-looking atom spelling remains opaque syntax"
    repeated=SList((Atom("x"),Atom("x"),SList((Atom("x"),)),SList((Atom("x"),))))
    assert parse_content("(x x (x) (x))")==repeated, "nested syntax retains repeated siblings"
