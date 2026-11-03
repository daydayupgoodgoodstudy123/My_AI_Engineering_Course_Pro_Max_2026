SPEC = dict(
 title="Validate authorization bindings", zh_title="授权凭证绑定", level="中等",
 brief="实现 PKCE challenge 和已验证 claims 的业务检查。签名验证由上游负责，本题不手写 JWT/OAuth 服务。",
 scenario="The identity layer already verified a token signature. Enforce issuer, resource, expiry, and scope bindings at the resource boundary.",
 contract="""challenge(verifier) returns base64url(SHA256(ASCII verifier)) without '=' padding. Verifier is a provided valid ASCII string.
authorize(claims,issuer,resource,required,now) returns {'ok':True} or {'ok':False,'error':code}. Check in order: iss exactly equals issuer ('issuer'); aud equals resource as a string OR is a list containing resource ('audience'); exp has exact type int and now<exp ('expired'); scope is a space-separated string whose tokens include all required scopes ('scope'). Missing claims fail their respective check. Extra scopes are allowed. No case folding. claims is a dict; required is a set of strings. This is not signature verification or a full OAuth implementation.""",
 bonus="step_up(current,required) returns a sorted list of missing scopes, where current and required are sets; do not request already granted scopes.",
 stubs=["challenge", "authorize", "step_up"],
 code=r'''import hashlib,base64
def challenge(verifier):return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
def authorize(claims,issuer,resource,required,now):
    def fail(code):return {"ok":False,"error":code}
    if claims.get("iss")!=issuer:return fail("issuer")
    aud=claims.get("aud")
    if not (isinstance(aud,str) and aud==resource or isinstance(aud,list) and resource in aud):return fail("audience")
    if type(claims.get("exp")) is not int or now>=claims["exp"]:return fail("expired")
    if not isinstance(claims.get("scope"),str) or not required<=set(claims["scope"].split()):return fail("scope")
    return {"ok":True}
def step_up(current,required):return sorted(required-current)
''',
 tests=r'''CLAIMS={"iss":"https://issuer","aud":"notes","exp":10,"scope":"read write"}
def check(c,required={"read"},now=9):return m.authorize(c,"https://issuer","notes",required,now)
class CoreTests(unittest.TestCase):
    def test_challenge(self):self.assertEqual(m.challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),"E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    def test_valid(self):self.assertEqual(check(CLAIMS),{"ok":True})
    def test_issuer_first(self):self.assertEqual(check(dict(CLAIMS,iss="evil",aud="other"))["error"],"issuer")
    def test_audience(self):
        self.assertEqual(check(dict(CLAIMS,aud=["other","notes"])),{"ok":True})
        self.assertEqual(check(dict(CLAIMS,aud="notes-extra"))["error"],"audience")
    def test_expiry(self):
        for exp in (True,10.0,None,9):
            with self.subTest(exp=exp):self.assertEqual(check(dict(CLAIMS,exp=exp))["error"],"expired")
        self.assertEqual(check(CLAIMS,now=10)["error"],"expired")
    def test_scope(self):
        self.assertEqual(check(CLAIMS,{"admin"})["error"],"scope")
        self.assertEqual(check(dict(CLAIMS,scope="reader"))["error"],"scope")
class BonusTests(unittest.TestCase):
    def test_missing(self):self.assertEqual(m.step_up({"read"},{"read","write","admin"}),["admin","write"])
    def test_none(self):self.assertEqual(m.step_up({"read"},{"read"}),[])
''',
 followups=["为什么 issuer 正确还要检查 audience？", "这里哪一层负责验证 token 签名？"],
 explanation="身份凭证的有效性与资源授权是两个边界。scope 使用集合比较，不能使用子串；exp 的相等时刻已经过期。"
)
