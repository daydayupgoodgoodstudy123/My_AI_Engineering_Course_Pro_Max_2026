SPEC = dict(
 title="Bind a continuation to its request", zh_title="续传状态绑定与防篡改", level="中等",
 brief="为多轮工作流实现 HMAC 状态凭证，绑定 principal、method、arguments 与过期时间。密钥和时间由测试注入。",
 scenario="A continuation token must not be reusable for a different user or tool call. Implement integrity and request binding using the supplied stdlib helpers.",
 contract="""seal(state,secret) returns urlsafe-base64(canonical JSON bytes)+'.'+hex HMAC-SHA256 of those bytes. Provided canonical() defines sorted compact JSON. Keep standard base64 padding.
verify(token,secret,principal,method,arguments,now) returns the decoded state dict only if signature matches, state.principal/method/arguments exactly match the supplied values under canonical JSON equality, and expires has exact type int with now < expires. Otherwise raise ValueError, including malformed token/base64/JSON. Expected state keys are principal,method,arguments,expires. This integrity token is not encrypted and does not prevent replay by itself.""",
 bonus="next_round(current,maximum) returns current+1 when 0<=current<maximum; otherwise raises ValueError. Both values must have exact type int and maximum>0.",
 stubs=["seal", "verify", "next_round"],
 code=r'''import base64
import hashlib
import hmac
import json
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def seal(state,secret):
    raw=canonical(state)
    return base64.urlsafe_b64encode(raw).decode()+"."+hmac.new(secret,raw,hashlib.sha256).hexdigest()
def verify(token,secret,principal,method,arguments,now):
    try:
        encoded,signature=token.split(".")
        raw=base64.b64decode(encoded,altchars=b"-_",validate=True)
        if not hmac.compare_digest(signature,hmac.new(secret,raw,hashlib.sha256).hexdigest()):raise ValueError("signature")
        state=json.loads(raw)
        if not isinstance(state,dict) or canonical([state.get("principal"),state.get("method"),state.get("arguments")])!=canonical([principal,method,arguments]):raise ValueError("binding")
        if type(state.get("expires")) is not int or now>=state["expires"]:raise ValueError("expiry")
        return state
    except (TypeError,KeyError,UnicodeError,AttributeError) as exc:raise ValueError("token") from exc
def next_round(current,maximum):
    if type(current) is not int or type(maximum) is not int or maximum<=0 or not 0<=current<maximum:raise ValueError("round")
    return current+1
''',
 tests=r'''STATE={"principal":"a","method":"summarize","arguments":{"id":1},"expires":10}
class CoreTests(unittest.TestCase):
    def token(self):return m.seal(STATE,b"test-secret")
    def test_roundtrip(self):self.assertEqual(m.verify(self.token(),b"test-secret","a","summarize",{"id":1},9),STATE)
    def test_canonical(self):self.assertEqual(m.seal({"b":2,"a":1},b"s"),m.seal({"a":1,"b":2},b"s"))
    def test_binding(self):
        for p,method,args in (("b","summarize",{"id":1}),("a","delete",{"id":1}),("a","summarize",{"id":2}),("a","summarize",{"id":True})):
            with self.subTest(p=p,method=method,args=args),self.assertRaises(ValueError):m.verify(self.token(),b"test-secret",p,method,args,0)
    def test_expired(self):
        with self.assertRaises(ValueError):m.verify(self.token(),b"test-secret","a","summarize",{"id":1},10)
    def test_tamper_and_wrong_key(self):
        with self.assertRaises(ValueError):m.verify(self.token()+"0",b"test-secret","a","summarize",{"id":1},0)
        with self.assertRaises(ValueError):m.verify(self.token(),b"wrong","a","summarize",{"id":1},0)
    def test_malformed(self):
        for token in ("bad","@@@.x",".."):
            with self.subTest(token=token),self.assertRaises(ValueError):m.verify(token,b"s","a","m",{},0)
class BonusTests(unittest.TestCase):
    def test_round(self):self.assertEqual(m.next_round(0,2),1)
    def test_limit(self):
        for a,b in ((2,2),(-1,2),(0,0),(True,2)):
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):m.next_round(a,b)
''',
 followups=["为什么有有效签名仍然需要绑定参数和 principal？", "单次消费凭证需要增加什么存储？"],
 explanation="签名保护字节完整性，绑定检查保护业务上下文。HMAC 不提供保密性；防重放还需要原子消费记录。"
)
