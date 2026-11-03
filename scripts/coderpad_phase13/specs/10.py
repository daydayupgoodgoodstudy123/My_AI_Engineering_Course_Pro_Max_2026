SPEC = dict(
 title="Resources, prompts, and private caches", zh_title="资源、提示模板与私有缓存", level="基础",
 brief="实现带 principal 隔离的资源缓存和提示模板。练习缓存键、过期边界、资源 URI 与模板参数校验。",
 scenario="A resource cache leaked one user's context to another. Repair keying and expiry, then implement a small prompt surface.",
 contract="""Cache.put(principal,uri,value,now,ttl) stores a deep copy under (principal,uri), with expiry=now+ttl. ttl must be >=0 or raise ValueError; now/ttl are provided integers. get(principal,uri,now) returns a deep copy if now < expiry, else None. Different principals and URIs must not collide; None is not used as a stored value.
render(name,args): only name='summarize' is known, otherwise raise KeyError. args must be exactly {'text':nonempty string after trimming}, else ValueError. Return [{'role':'user','content':'Summarize: '+trimmed_text}]. Resource text remains data; no code execution or model call.""",
 bonus="resource_kind(uri) returns 'resource' for a nonempty notes:// URI suffix, 'ui' for a nonempty ui:// suffix, and raises ValueError otherwise. Prefix matching is case-sensitive; no URI normalization is required.",
 stubs=["Cache.put", "Cache.get", "render", "resource_kind"],
 code=r'''from copy import deepcopy
class Cache:
    def __init__(self):self.items={}
    def put(self,principal,uri,value,now,ttl):
        if ttl<0:raise ValueError("ttl")
        self.items[(principal,uri)]=(now+ttl,deepcopy(value))
    def get(self,principal,uri,now):
        item=self.items.get((principal,uri))
        return deepcopy(item[1]) if item is not None and now<item[0] else None
def render(name,args):
    if name!="summarize":raise KeyError(name)
    if not isinstance(args,dict) or set(args)!={"text"} or not isinstance(args["text"],str) or not args["text"].strip():raise ValueError("args")
    return [{"role":"user","content":"Summarize: "+args["text"].strip()}]
def resource_kind(uri):
    for prefix,kind in (("notes://","resource"),("ui://","ui")):
        if isinstance(uri,str) and uri.startswith(prefix) and len(uri)>len(prefix):return kind
    raise ValueError("uri")
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_private_cache(self):
        c=m.Cache();c.put("alice","notes://a",{"text":"secret"},10,5)
        self.assertEqual(c.get("alice","notes://a",14),{"text":"secret"})
        self.assertIsNone(c.get("bob","notes://a",14))
    def test_expiry_boundary(self):
        c=m.Cache();c.put("a","u",1,10,5);self.assertIsNone(c.get("a","u",15))
        c.put("a","z",2,10,0);self.assertIsNone(c.get("a","z",10))
    def test_copy(self):
        c=m.Cache();v={"x":[]};c.put("a","u",v,0,5);v["x"].append(1);c.get("a","u",1)["x"].append(2)
        self.assertEqual(c.get("a","u",1),{"x":[]})
    def test_ttl(self):
        with self.assertRaises(ValueError):m.Cache().put("a","u",1,0,-1)
    def test_render(self):self.assertEqual(m.render("summarize",{"text":" hi "}),[{"role":"user","content":"Summarize: hi"}])
    def test_bad_prompt(self):
        with self.assertRaises(KeyError):m.render("delete",{})
        for a in ({},{"text":" "},{"text":"a","extra":1}):
            with self.subTest(a=a),self.assertRaises(ValueError):m.render("summarize",a)
class BonusTests(unittest.TestCase):
    def test_kinds(self):self.assertEqual([m.resource_kind(x) for x in ("notes://a","ui://b")],["resource","ui"])
    def test_bad_uri(self):
        for uri in ("notes://","https://a",None):
            with self.subTest(uri=uri),self.assertRaises(ValueError):m.resource_kind(uri)
''',
 followups=["缓存 key 除了 principal，还可能需要包含哪些权限信息？", "资源内容和可信指令有什么区别？"],
 explanation="缓存键至少绑定 principal 和 URI，过期用严格小于比较。读写均复制，避免可变对象旁路修改缓存。"
)
