from . import add, ok, bad

add("redact", "结构化日志脱敏", "redact(value)",
    "Recursively copy JSON values; replace the entire value of any dict key whose casefolded spelling is token,password,api_key,authorization with '[REDACTED]'. Other scalar values stay unchanged. This key-based policy does not discover secrets embedded in free text.",
    """if isinstance(value,dict):return {k:'[REDACTED]' if k.casefold() in {'token','password','api_key','authorization'} else redact(v) for k,v in value.items()}
if isinstance(value,list):return [redact(v) for v in value]
return value""",
    [ok(({'Token':'s','x':1},),{'Token':'[REDACTED]','x':1}),ok(([{'password':'s'}],),[{'password':'[REDACTED]'}]),ok((None,),None),ok(({},),{}),ok(({'token':{'nested':'s'}},),{'token':'[REDACTED]'}),ok(({'text':'keep'},),{'text':'keep'})])

add("permissions", "独立权限与批准", "permission_decision(capability, granted, side_effect, approved)",
    "If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes.",
    """if type(side_effect) is not bool or type(approved) is not bool:raise ValueError('flags')
if capability not in granted:return 'deny'
return 'ask' if side_effect and not approved else 'allow'""",
    [ok(('write',['write'],True,False),'ask'),ok(('write',['write'],True,True),'allow'),ok(('write',[],True,True),'deny'),ok(('read',['read'],False,False),'allow'),bad(('x',[],1,False)),ok(('x',[],False,False),'deny')])

add("gate", "证据分层 Gate", "evidence_gate(evidence, required)",
    "For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed.",
    """failed=sorted(k for k in set(required) if evidence.get(k) is not True)
return {'ready':not failed,'failed':failed}""",
    [ok(({'tests':True},['tests']),{'ready':True,'failed':[]}),ok(({},['tests']),{'ready':False,'failed':['tests']}),ok(({'tests':1},['tests']),{'ready':False,'failed':['tests']}),ok(({},[]),{'ready':True,'failed':[]}),ok(({'a':False,'b':True},['a','b']),{'ready':False,'failed':['a']}),ok(({'a':False},['z','b','z']),{'ready':False,'failed':['b','z']})])

add("risk", "风险登记与排序", "prioritize_risks(risks)",
    "Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria.",
    """if len({r['id'] for r in risks})!=len(risks) or any(type(r[k]) is not int or not 1<=r[k]<=5 for r in risks for k in ('severity','likelihood')):raise ValueError('risk')
return [r['id'] for r in sorted(risks,key=lambda r:(-r['severity']*r['likelihood'],-r['severity'],r['id']))]""",
    [ok(([{'id':'a','severity':2,'likelihood':3},{'id':'b','severity':4,'likelihood':2}],),['b','a']),ok(([],),[]),ok(([{'id':'b','severity':2,'likelihood':2},{'id':'a','severity':4,'likelihood':1}],),['a','b']),bad(([{'id':'a','severity':0,'likelihood':1}],)),bad(([{'id':'a','severity':True,'likelihood':1}],)),bad(([{'id':'a','severity':1,'likelihood':1}]*2,))])

add("fairness", "分组选择率差异", "selection_gap(groups, selected)",
    "Equal-length nonempty lists; groups are strings and selected exact booleans. Return {'rates':group->selected_count/group_count,'gap':max(rate)-min(rate)}. Invalid length/labels raises ValueError. This is descriptive demographic-parity evidence, not a complete fairness judgment.",
    """if not groups or len(groups)!=len(selected) or any(type(x) is not bool for x in selected):raise ValueError('groups')
counts=Counter(groups);positives=Counter(g for g,s in zip(groups,selected) if s);rates={g:positives[g]/n for g,n in sorted(counts.items())}
return {'rates':rates,'gap':max(rates.values())-min(rates.values())}""",
    [ok((['a','a','b'],[True,False,True]),{'rates':{'a':.5,'b':1},'gap':.5}),ok((['a'],[True]),{'rates':{'a':1},'gap':0}),ok((['a','b'],[False,False]),{'rates':{'a':0,'b':0},'gap':0}),bad(([],[])),bad((['a'],[1])),bad((['a'],[]))])

add("privacy", "基础隐私预算组合", "privacy_budget(epsilons, deltas, max_epsilon, max_delta)",
    "Require equal-length nonnegative epsilons/deltas and nonnegative maxima; otherwise ValueError. Basic sequential composition returns {'epsilon':sum eps,'delta':sum deltas,'within_budget':both totals<=maxima}. No advanced accountant or real privacy guarantee is implemented.",
    """if len(epsilons)!=len(deltas) or any(x<0 for x in epsilons+deltas+[max_epsilon,max_delta]):raise ValueError('budget')
e,d=sum(epsilons),sum(deltas)
return {'epsilon':e,'delta':d,'within_budget':e<=max_epsilon and d<=max_delta}""",
    [ok(([1,2],[.01,.01],3,.02),{'epsilon':3,'delta':.02,'within_budget':True}),ok(([2],[0],1,0),{'epsilon':2,'delta':0,'within_budget':False}),ok(([],[],0,0),{'epsilon':0,'delta':0,'within_budget':True}),bad(([1],[],1,1)),bad(([-1],[0],1,1)),ok(([0],[.1],1,0),{'epsilon':0,'delta':.1,'within_budget':False})])

add("calibration", "Expected Calibration Error", "calibration_error(confidences, correct, bins)",
    "Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError.",
    """if not confidences or len(confidences)!=len(correct) or type(bins) is not int or bins<=0 or any(not 0<=p<=1 for p in confidences) or any(type(x) is not bool for x in correct):raise ValueError('calibration')
groups={}
for p,c in zip(confidences,correct):groups.setdefault(min(bins-1,int(p*bins)),[]).append((p,c))
return sum(abs(sum(p for p,c in group)-sum(c for p,c in group))/len(confidences) for group in groups.values())""",
    [ok(([1],[True],10),0),ok(([1],[False],10),1),ok(([.5,.5],[True,False],2),0),ok(([0],[True],1),1),bad(([],[],1)),bad(([.5],[1],1))])

add("moderation", "分类信号合并", "moderation(signals, block_at)",
    "Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called.",
    """if type(block_at) is not int or not 0<=block_at<=3 or any(type(s['severity']) is not int or not 0<=s['severity']<=3 for s in signals):raise ValueError('severity')
categories={}
for s in signals:categories[s['category']]=max(categories.get(s['category'],0),s['severity'])
return {'categories':dict(sorted(categories.items())),'blocked':any(v>=block_at for v in categories.values())}""",
    [ok(([{'category':'x','severity':2},{'category':'x','severity':1}],2),{'categories':{'x':2},'blocked':True}),ok(([],0),{'categories':{},'blocked':False}),ok(([{'category':'x','severity':0}],1),{'categories':{'x':0},'blocked':False}),ok(([{'category':'x','severity':0}],0),{'categories':{'x':0},'blocked':True}),bad(([{'category':'x','severity':4}],2)),bad(([],True))])

add("provenance", "声明与证据绑定", "unsupported_claims(claims, evidence_ids)",
    "Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth.",
    """if len({c['id'] for c in claims})!=len(claims):raise ValueError('duplicate claim')
known=set(evidence_ids)
return sorted(c['id'] for c in claims if not c['references'] or not set(c['references'])<=known)""",
    [ok(([{'id':'a','references':['e']}],['e']),[]),ok(([{'id':'a','references':[]}],['e']),['a']),ok(([{'id':'a','references':['x']}],['e']),['a']),ok(([],[]),[]),ok(([{'id':'b','references':[]},{'id':'a','references':[]}],[]),['a','b']),bad(([{'id':'a','references':[]}]*2,[]))])

add("drift", "评估锚点漂移", "drift_report(baseline, current, tolerance)",
    "baseline/current map identical metric keys to finite numbers. tolerance>=0. Return sorted keys with abs(current-baseline)>tolerance. Missing/additional keys or negative tolerance raises ValueError. Equality with tolerance is allowed.",
    """if set(baseline)!=set(current) or tolerance<0:raise ValueError('metrics')
return sorted(k for k in baseline if abs(current[k]-baseline[k])>tolerance)""",
    [ok(({'a':1},{'a':2},.5),['a']),ok(({'a':1},{'a':2},1),[]),ok(({}, {},0),[]),bad(({'a':1},{},1)),bad(({}, {},-1)),ok(({'z':3,'a':1},{'z':1,'a':3},1),['a','z'])])
