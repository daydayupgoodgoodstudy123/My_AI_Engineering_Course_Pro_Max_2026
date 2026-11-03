SPEC = dict(
 title="Isolate token and key caches", zh_title="Token 缓存隔离与轮换", level="中等",
 brief="按 issuer/resource 隔离缓存，并为 key 轮换实现一次刷新。所有网络依赖都由 fetch fake 注入。",
 scenario="Production authorization failures came from a token cache keyed only by user and a stale signing-key cache. Repair these isolated cache boundaries.",
 contract="""token_for(cache,issuer,resource,now) looks up tuple (issuer,resource). Return the token record only if exp has exact type int and now<exp; else None. Return a copy. Records contain token and exp; do not reuse another issuer/resource entry.
KeyCache(ttl) has keys={}, expires=0. get(kid,now,fetch) refreshes by calling fetch() once when now>=expires OR kid is absent from cached keys. A successful fetch replaces the entire key map and sets expires=now+ttl. Return keys[kid], raising KeyError if still absent. Fetch errors propagate; do not serve stale keys on refresh failure and do not modify cache on that failure. At most one fetch per get, including unknown kid. fetch returns a dict; ttl>0 and time values are provided valid integers. Cryptographic signature checking is outside this exercise.""",
 bonus="invalidate(cache,issuer) removes every token cache entry for that issuer and returns the number removed; preserve other issuers.",
 stubs=["token_for", "KeyCache.get", "invalidate"],
 code=r'''def token_for(cache,issuer,resource,now):
    record=cache.get((issuer,resource))
    return record.copy() if record is not None and type(record.get("exp")) is int and now<record["exp"] else None
class KeyCache:
    def __init__(self,ttl):self.ttl=ttl;self.keys={};self.expires=0
    def get(self,kid,now,fetch):
        if now>=self.expires or kid not in self.keys:
            keys=fetch();self.keys=keys.copy();self.expires=now+self.ttl
        return self.keys[kid]
def invalidate(cache,issuer):
    keys=[k for k in cache if k[0]==issuer]
    for k in keys:del cache[k]
    return len(keys)
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_token_isolation(self):
        c={("i","r"):{"token":"secret","exp":10}}
        self.assertEqual(m.token_for(c,"i","r",9),c[("i","r")]);self.assertIsNone(m.token_for(c,"other","r",9));self.assertIsNone(m.token_for(c,"i","other",9))
    def test_expired(self):self.assertIsNone(m.token_for({("i","r"):{"token":"t","exp":10}},"i","r",10))
    def test_copy(self):
        c={("i","r"):{"token":"t","exp":10}};m.token_for(c,"i","r",0)["token"]="changed";self.assertEqual(c[("i","r")]["token"],"t")
    def test_cache_hit(self):
        c=m.KeyCache(10);seen=[]
        def fetch():seen.append(1);return {"k":"key"}
        self.assertEqual(c.get("k",0,fetch),"key");self.assertEqual(c.get("k",9,fetch),"key");self.assertEqual(len(seen),1)
    def test_rotation_and_unknown(self):
        c=m.KeyCache(10);c.get("old",0,lambda:{"old":"v1"});self.assertEqual(c.get("new",1,lambda:{"new":"v2"}),"v2")
        seen=[]
        with self.assertRaises(KeyError):c.get("missing",2,lambda:seen.append(1) or {"new":"v2"})
        self.assertEqual(len(seen),1)
    def test_refresh_failure(self):
        c=m.KeyCache(10);c.get("k",0,lambda:{"k":"v"})
        def fail():raise RuntimeError("offline")
        with self.assertRaises(RuntimeError):c.get("k",10,fail)
        self.assertEqual(c.keys,{"k":"v"});self.assertEqual(c.expires,10)
class BonusTests(unittest.TestCase):
    def test_invalidate(self):
        c={("i","a"):1,("i","b"):2,("j","a"):3};self.assertEqual(m.invalidate(c,"i"),2);self.assertEqual(c,{("j","a"):3})
    def test_no_matches(self):self.assertEqual(m.invalidate({},"i"),0)
''',
 followups=["未知 kid 导致的刷新风暴可以怎样限制？", "token 过期前撤销，缓存还需要什么新鲜度策略？"],
 explanation="token 键包含 issuer 和 resource；key 缓存刷新后不保留已移除旧 key。失败关闭保证依赖故障不会被误判成鉴权成功。"
)
