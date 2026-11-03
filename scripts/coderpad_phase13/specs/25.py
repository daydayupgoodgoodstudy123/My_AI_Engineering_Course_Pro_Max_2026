SPEC = dict(
 title="Route or abstain", zh_title="Skill 显式调用与路由弃权", level="中等",
 brief="区分 human/model eligibility，处理显式调用、隐式关键词路由、并列和 near miss。匹配不够确定时要弃权。",
 scenario="A router activates skills too aggressively. Separate actor eligibility from selection and abstain on ambiguous matches.",
 contract="""route(skills,query,actor,explicit=None): skills are dicts {'name':unique str,'human':bool,'model':bool,'keywords':set of lowercase tokens}. actor must be 'human' or 'model', otherwise ValueError. Eligibility is the skill's boolean for that actor. If explicit is non-None, return {'name':explicit,'reason':'explicit'} only for an eligible exact name; otherwise {'name':None,'reason':'ineligible'} (includes unknown name). Do not fall back to keyword routing after explicit rejection. For implicit routing, tokenize query with regex [a-z0-9]+ after casefolding and score each eligible skill by count of intersecting keyword tokens. Unique maximum >0 returns reason 'matched'. Tied positive maxima return name None/reason 'ambiguous'. No positive score returns name None/reason 'no_match'. Input order must not resolve ties.""",
 bonus="matrix(skills) returns {'human':sorted eligible names,'model':sorted eligible names}, preserving the independence of the two actor policies.",
 stubs=["route", "matrix"],
 code=r'''import re
def route(skills,query,actor,explicit=None):
    if actor not in ("human","model"):raise ValueError("actor")
    eligible=[s for s in skills if s[actor]]
    if explicit is not None:return {"name":explicit,"reason":"explicit"} if any(s["name"]==explicit for s in eligible) else {"name":None,"reason":"ineligible"}
    tokens=set(re.findall(r"[a-z0-9]+",query.casefold()));scores=[(len(tokens&s["keywords"]),s["name"]) for s in eligible];best=max((x[0] for x in scores),default=0)
    if best==0:return {"name":None,"reason":"no_match"}
    names=[n for score,n in scores if score==best]
    return {"name":names[0],"reason":"matched"} if len(names)==1 else {"name":None,"reason":"ambiguous"}
def matrix(skills):return {actor:sorted(s["name"] for s in skills if s[actor]) for actor in ("human","model")}
''',
 tests=r'''SKILLS=[{"name":"review","human":True,"model":True,"keywords":{"review","notes"}},{"name":"export","human":True,"model":False,"keywords":{"export","notes"}}]
class CoreTests(unittest.TestCase):
    def test_explicit(self):self.assertEqual(m.route(SKILLS,"nothing","human","export"),{"name":"export","reason":"explicit"})
    def test_explicit_ineligible_no_fallback(self):self.assertEqual(m.route(SKILLS,"review","model","export"),{"name":None,"reason":"ineligible"})
    def test_implicit(self):self.assertEqual(m.route(SKILLS,"Please REVIEW notes!","human"),{"name":"review","reason":"matched"})
    def test_tie(self):self.assertEqual(m.route(list(reversed(SKILLS)),"notes","human"),{"name":None,"reason":"ambiguous"})
    def test_near_miss(self):self.assertEqual(m.route(SKILLS,"reviewer notebook","human"),{"name":None,"reason":"no_match"})
    def test_actor_policy(self):self.assertEqual(m.route(SKILLS,"notes","model")["name"],"review")
    def test_invalid_actor(self):
        with self.assertRaises(ValueError):m.route(SKILLS,"review","plugin")
class BonusTests(unittest.TestCase):
    def test_matrix(self):self.assertEqual(m.matrix(SKILLS),{"human":["export","review"],"model":["review"]})
    def test_empty(self):self.assertEqual(m.matrix([]),{"human":[],"model":[]})
''',
 followups=["human 可见是否代表 model 可以自动调用？", "如何构造 near-miss 数据评估过度激活？"],
 explanation="eligibility 先过滤，selection 再比较。显式失败不悄悄换成别的 skill；并列时弃权而不是依赖列表顺序。"
)
