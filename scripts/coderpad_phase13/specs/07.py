SPEC = dict(
 title="Finish a notes tool server", zh_title="笔记工具服务", level="基础到中等",
 brief="实现一个内存笔记服务，练习服务端工具发现、创建、读取和错误后的状态恢复。网络和协议包装已经移出题目。",
 scenario="The RPC transport exists. Finish the in-memory application service used by the notes tools.",
 contract="""NotesServer starts with no notes and next_id=1. call(name, args): notes_create requires exactly {'title': str}, trimmed length 1..80; on success allocate consecutive integer id and return {'ok':True,'value':{'id':id,'title':trimmed}}. notes_get requires exactly {'id': exact int}; missing id returns {'ok':False,'error':'not_found'}. Invalid args return error 'invalid_arguments'; unknown tool returns error 'unknown_tool' before checking args. Rejected creates must not consume ids or change data. Returned note dicts are copies, so callers cannot mutate internal state. Repeated gets are read-only.""",
 bonus="list_tools() returns ['notes_create','notes_get']; search(query) returns copied matching notes sorted by id, using case-insensitive substring search in titles. Empty query matches all notes.",
 stubs=["NotesServer.call", "NotesServer.list_tools", "NotesServer.search"],
 code=r'''class NotesServer:
    def __init__(self):
        self.notes={}
        self.next_id=1
    def call(self,name,args):
        if name not in ("notes_create","notes_get"):return {"ok":False,"error":"unknown_tool"}
        key="title" if name=="notes_create" else "id"
        if not isinstance(args,dict) or set(args)!={key}:return {"ok":False,"error":"invalid_arguments"}
        v=args[key]
        if name=="notes_create":
            if not isinstance(v,str) or not 1<=len(v.strip())<=80:return {"ok":False,"error":"invalid_arguments"}
            note={"id":self.next_id,"title":v.strip()};self.notes[self.next_id]=note;self.next_id+=1
        else:
            if type(v) is not int:return {"ok":False,"error":"invalid_arguments"}
            if v not in self.notes:return {"ok":False,"error":"not_found"}
            note=self.notes[v]
        return {"ok":True,"value":note.copy()}
    def list_tools(self):return ["notes_create","notes_get"]
    def search(self,query):return [n.copy() for _,n in sorted(self.notes.items()) if query.casefold() in n["title"].casefold()]
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def setUp(self):self.s=m.NotesServer()
    def test_create_and_get(self):
        self.assertEqual(self.s.call("notes_create",{"title":" A "}),{"ok":True,"value":{"id":1,"title":"A"}})
        self.assertEqual(self.s.call("notes_get",{"id":1})["value"]["title"],"A")
    def test_invalid_no_id_consumed(self):
        for a in ({"title":" "},{"title":1},{"title":"x"*81},{"title":"a","id":1}):
            with self.subTest(a=a):self.assertEqual(self.s.call("notes_create",a)["error"],"invalid_arguments")
        self.assertEqual(self.s.call("notes_create",{"title":"good"})["value"]["id"],1)
    def test_not_found(self):self.assertEqual(self.s.call("notes_get",{"id":1}),{"ok":False,"error":"not_found"})
    def test_strict_id(self):self.assertEqual(self.s.call("notes_get",{"id":True})["error"],"invalid_arguments")
    def test_unknown(self):self.assertEqual(self.s.call("delete",None)["error"],"unknown_tool")
    def test_defensive_copy(self):
        self.s.call("notes_create",{"title":"a"})["value"]["title"]="bad"
        r=self.s.call("notes_get",{"id":1});r["value"]["title"]="also bad"
        self.assertEqual(self.s.call("notes_get",{"id":1})["value"]["title"],"a")
class BonusTests(unittest.TestCase):
    def test_discovery(self):self.assertEqual(m.NotesServer().list_tools(),["notes_create","notes_get"])
    def test_search(self):
        s=m.NotesServer()
        for title in ("Beta","ALPHA","alphabet"):s.call("notes_create",{"title":title})
        self.assertEqual([n["id"] for n in s.search("alpha")],[2,3])
''',
 followups=["内存实现换成数据库时，分配 id 的位置要怎样改变？", "工具业务失败和 RPC 协议错误应该怎样区分？"],
 explanation="先校验，后写状态；失败不分配 id。复制返回对象避免外部调用者越过工具边界修改服务内部数据。"
)
