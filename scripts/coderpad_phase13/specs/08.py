SPEC = dict(
 title="Merge and route remote tools", zh_title="合并与路由远端工具", level="中等",
 brief="给客户端实现 namespaced 工具目录。发现顺序不应影响最终目录，名称冲突和未知目标必须明确失败。",
 scenario="A client connects to several fake peers. Merge discovered tools and route calls without silent overwrites.",
 contract="""Client(peers) receives a dict peer_name -> object exposing list_tools() and call(tool,args). discover() asks each peer once, validates every tool descriptor has a nonempty string name, and builds public names peer_name+'::'+tool_name. Peer and tool names must not contain '::'. Duplicate local tool names within one peer raise ValueError. Publish the new catalog only after ALL peers succeed; failures preserve the previous catalog. Return sorted public names. Initial catalog is empty. call(public_name,args) routes only a previously discovered name to its owning peer using the unprefixed local name, returns the peer's result, and propagates peer exceptions. Unknown public name raises KeyError. The peers dict itself is provided valid except names may contain the forbidden delimiter.""",
 bonus="descriptor(public_name) returns a deep copy of the original descriptor with name replaced by public_name. Unknown public name raises KeyError.",
 stubs=["Client.discover", "Client.call", "Client.descriptor"],
 code=r'''from copy import deepcopy
class Client:
    def __init__(self,peers):self.peers=peers;self.catalog={}
    def discover(self):
        catalog={}
        for peer_name,peer in self.peers.items():
            if not peer_name or "::" in peer_name:raise ValueError("peer name")
            for d in peer.list_tools():
                name=d.get("name")
                if not isinstance(name,str) or not name or "::" in name:raise ValueError("tool name")
                public=peer_name+"::"+name
                if public in catalog:raise ValueError("duplicate")
                catalog[public]=(peer_name,name,deepcopy(d))
        self.catalog=catalog
        return sorted(catalog)
    def call(self,public_name,args):
        peer,name,_=self.catalog[public_name]
        return self.peers[peer].call(name,args)
    def descriptor(self,public_name):
        d=deepcopy(self.catalog[public_name][2]);d["name"]=public_name;return d
''',
 tests=r'''class Peer:
    def __init__(self,names):self.tools=[{"name":n,"schema":{}} for n in names];self.seen=[]
    def list_tools(self):return self.tools
    def call(self,name,args):self.seen.append((name,args));return {"peer_result":name}
class CoreTests(unittest.TestCase):
    def test_merge_and_route(self):
        a,b=Peer(["read"]),Peer(["read"]);c=m.Client({"b":b,"a":a})
        self.assertEqual(c.discover(),["a::read","b::read"])
        self.assertEqual(c.call("b::read",{"id":1}),{"peer_result":"read"})
        self.assertEqual(a.seen,[]);self.assertEqual(b.seen,[("read",{"id":1})])
    def test_before_discovery(self):
        with self.assertRaises(KeyError):m.Client({"a":Peer(["read"])}).call("a::read",{})
    def test_duplicate(self):
        with self.assertRaises(ValueError):m.Client({"a":Peer(["read","read"])}).discover()
    def test_delimiter(self):
        for peers in ({"a::b":Peer(["r"])},{"a":Peer(["b::r"])}):
            with self.subTest(peers=peers),self.assertRaises(ValueError):m.Client(peers).discover()
    def test_atomic_refresh(self):
        p=Peer(["read"]);c=m.Client({"a":p});c.discover();p.tools=[{"name":"new"},{"name":"new"}]
        with self.assertRaises(ValueError):c.discover()
        self.assertEqual(c.call("a::read",{}),{"peer_result":"read"})
    def test_empty(self):self.assertEqual(m.Client({}).discover(),[])
class BonusTests(unittest.TestCase):
    def test_descriptor_copy(self):
        c=m.Client({"a":Peer(["read"])});c.discover();d=c.descriptor("a::read");d["schema"]["x"]=1
        self.assertEqual(c.descriptor("a::read"),{"name":"a::read","schema":{}})
    def test_unknown(self):
        with self.assertRaises(KeyError):m.Client({}).descriptor("missing")
''',
 followups=["为什么 discovery 应该原子发布？", "一个 peer 失效时，是否应该继续使用旧目录？需要什么策略？"],
 explanation="先在局部构建目录，再一次替换，防止半成品暴露。公共名称保留来源信息，调用时只去掉自己维护的命名空间。"
)
