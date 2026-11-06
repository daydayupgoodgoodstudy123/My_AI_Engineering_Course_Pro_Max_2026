from . import add, ok, bad

add("topology", "依赖计划拓扑排序", "topological_order(dependencies)",
    "dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns [].",
    """pending={n:set(ds) for n,ds in dependencies.items()}
for ds in dependencies.values():
    for name in ds:pending.setdefault(name,set())
result=[]
while pending:
    ready=sorted(n for n,ds in pending.items() if not ds)
    if not ready:raise ValueError('cycle')
    n=ready[0];result.append(n);del pending[n]
    for ds in pending.values():ds.discard(n)
return result""",
    [ok(({'b':['a'],'c':['a']},),['a','b','c']),ok(({},),[]),ok(({'b':[],'a':[]},),['a','b']),bad(({'a':['b'],'b':['a']},)),ok(({'a':['x','x']},),['x','a']),bad(({'a':['a']},))])

add("bfs", "最短路径搜索", "shortest_path(graph, start, goal)",
    "graph maps string nodes to neighbor lists; missing nodes have no neighbors. Use BFS with neighbors sorted lexicographically and return the first shortest path including endpoints; return None if unreachable. start==goal returns [start]. Cycles must terminate.",
    """queue=deque([[start]]);seen={start}
while queue:
    path=queue.popleft();node=path[-1]
    if node==goal:return path
    for nxt in sorted(graph.get(node,[])):
        if nxt not in seen:seen.add(nxt);queue.append(path+[nxt])
return None""",
    [ok(({'a':['c','b'],'b':['d'],'c':['d']},'a','d'),['a','b','d']),ok(({},'a','a'),['a']),ok(({},'a','b'),None),ok(({'a':['b'],'b':['a']},'a','c'),None),ok(({'a':['b']},'a','b'),['a','b']),ok(({'x':['y'],'y':['z']},'x','z'),['x','y','z'])])

add("state_machine", "合法状态转换", "transition(state, target)",
    "Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves.",
    """edges={'queued':{'running','canceled'},'running':{'waiting','completed','failed','canceled'},'waiting':{'running','canceled'}}
if target not in edges.get(state,set()):raise ValueError('transition')
return target""",
    [ok(('queued','running'),'running'),ok(('running','completed'),'completed'),ok(('waiting','canceled'),'canceled'),bad(('queued','completed')),bad(('completed','running')),bad(('running','running'))])

add("idempotency", "幂等请求账本", "replay_requests(requests)",
    "Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal.",
    """seen={};executed=[];replayed=[]
for r in requests:
    payload=json.dumps(r['payload'],sort_keys=True,separators=(',',':'))
    if r['id'] in seen:
        if seen[r['id']]!=payload:raise ValueError('conflict')
        replayed.append(r['id'])
    else:seen[r['id']]=payload;executed.append(r['id'])
return {'executed':executed,'replayed':replayed}""",
    [ok(([{'id':'a','payload':1},{'id':'a','payload':1}],),{'executed':['a'],'replayed':['a']}),ok(([],),{'executed':[],'replayed':[]}),bad(([{'id':'a','payload':1},{'id':'a','payload':2}],)),bad(([{'id':'a','payload':1},{'id':'a','payload':True}],)),ok(([{'id':'b','payload':{}},{'id':'a','payload':{}}],),{'executed':['b','a'],'replayed':[]}),ok(([{'id':'a','payload':{'b':2,'a':1}},{'id':'a','payload':{'a':1,'b':2}}],),{'executed':['a'],'replayed':['a']})])

add("queue", "优先级任务调度", "schedule_jobs(jobs, capacity)",
    "Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError.",
    """if type(capacity) is not int or capacity<0 or len({j['id'] for j in jobs})!=len(jobs):raise ValueError('queue')
return [j['id'] for j in sorted((j for j in jobs if j['status']=='queued'),key=lambda j:(-j['priority'],j['created'],j['id']))[:capacity]]""",
    [ok(([{'id':'a','priority':1,'created':0,'status':'queued'},{'id':'b','priority':2,'created':1,'status':'queued'}],1),['b']),ok(([],1),[]),ok(([{'id':'a','priority':1,'created':0,'status':'running'}],1),[]),ok(([{'id':'a','priority':1,'created':0,'status':'queued'}],0),[]),bad(([],-1)),bad(([{'id':'a','priority':0,'created':0,'status':'queued'}]*2,1))])

add("routing", "角色与工具选择", "route_task(routes, query_tokens, role)",
    "Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie.",
    """if len({r['name'] for r in routes})!=len(routes):raise ValueError('duplicate route')
scores=[(len(set(r['keywords'])&set(query_tokens)),r['name']) for r in routes if role in r['roles']];best=max((s for s,n in scores),default=0);names=[n for s,n in scores if s==best]
return names[0] if best>0 and len(names)==1 else None""",
    [ok(([{'name':'read','roles':['user'],'keywords':['notes']}],['notes'],'user'),'read'),ok(([],['x'],'user'),None),ok(([{'name':'read','roles':['admin'],'keywords':['notes']}],['notes'],'user'),None),ok(([{'name':'a','roles':['u'],'keywords':['x']},{'name':'b','roles':['u'],'keywords':['x']}],['x'],'u'),None),ok(([{'name':'a','roles':['u'],'keywords':['x']}],['y'],'u'),None),bad(([{'name':'a','roles':[],'keywords':[] }]*2,[],'u'))])

add("memory", "有界记忆保留", "compact_memory(records, limit)",
    "Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError.",
    """if type(limit) is not int or limit<0:raise ValueError('limit')
latest={}
for r in records:
    if r['id'] not in latest or r['timestamp']>=latest[r['id']]['timestamp']:latest[r['id']]=r
return copy.deepcopy(sorted(latest.values(),key=lambda r:(-r['timestamp'],r['id']))[:limit])""",
    [ok(([{'id':'a','timestamp':1,'text':'old'},{'id':'a','timestamp':2,'text':'new'}],1),[{'id':'a','timestamp':2,'text':'new'}]),ok(([],1),[]),ok(([{'id':'a','timestamp':1,'text':'x'}],0),[]),ok(([{'id':'b','timestamp':1,'text':'b'},{'id':'a','timestamp':1,'text':'a'}],1),[{'id':'a','timestamp':1,'text':'a'}]),bad(([],-1)),ok(([{'id':'a','timestamp':1,'text':'x'},{'id':'a','timestamp':1,'text':'y'}],1),[{'id':'a','timestamp':1,'text':'y'}])])

add("consensus", "Quorum 与重复选票", "quorum_vote(votes, members, required)",
    "votes is [[member,value],...]; members is a unique member-id list. Ignore exact repeated votes; conflicting votes from one member or a nonmember raise ValueError. required exact int >len(members)/2 and <=len(members). Return the value with at least required distinct voters, else None. Values are strings.",
    """if type(required) is not int or not len(members)/2<required<=len(members):raise ValueError('quorum')
seen={}
for member,value in votes:
    if member not in members or member in seen and seen[member]!=value:raise ValueError('vote')
    seen[member]=value
counts=Counter(seen.values())
return next((v for v,n in counts.items() if n>=required),None)""",
    [ok(([['a','yes'],['b','yes']],['a','b','c'],2),'yes'),ok(([['a','yes'],['a','yes']],['a','b','c'],2),None),ok(([],['a'],1),None),bad(([['x','yes']],['a'],1)),bad(([['a','yes'],['a','no']],['a'],1)),bad(([],['a','b'],1))])

add("handoff", "可验证任务交接", "validate_handoff(bundle)",
    "Required nonempty string fields: objective, state, next_action. checks must be a nonempty list of nonempty strings. Return sorted missing/invalid field names (among those four). Extra fields allowed; whitespace-only strings are invalid. Do not execute next_action.",
    """issues=[k for k in ('objective','state','next_action') if not isinstance(bundle.get(k),str) or not bundle[k].strip()]
checks=bundle.get('checks')
if not isinstance(checks,list) or not checks or any(not isinstance(x,str) or not x.strip() for x in checks):issues.append('checks')
return sorted(issues)""",
    [ok(({'objective':'o','state':'s','next_action':'n','checks':['test']},),[]),ok(({},),['checks','next_action','objective','state']),ok(({'objective':' ','state':'s','next_action':'n','checks':['t']},),['objective']),ok(({'objective':'o','state':'s','next_action':'n','checks':[]},),['checks']),ok(({'objective':'o','state':'s','next_action':'n','checks':[1]},),['checks']),ok(({'objective':'o','state':'s','next_action':'n','checks':['t'],'extra':1},),[])])

add("rpc", "JSON-RPC 请求包", "rpc_request(request_id, method, params)",
    "id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution.",
    """if not (type(request_id) is int or isinstance(request_id,str) and request_id) or not isinstance(method,str) or not method or not isinstance(params,dict):raise ValueError('request')
return {'jsonrpc':'2.0','id':request_id,'method':method,'params':copy.deepcopy(params)}""",
    [ok((0,'tools/list',{}),{'jsonrpc':'2.0','id':0,'method':'tools/list','params':{}}),ok(('a','call',{'x':1}),{'jsonrpc':'2.0','id':'a','method':'call','params':{'x':1}}),bad((True,'call',{})),bad((1,'',{})),bad((1,'call',[])),bad(('', 'call',{}))])

add("tool_schema", "工具参数校验", "validate_arguments(schema, arguments)",
    "schema maps required field name -> one of string,integer,boolean. arguments must be a dict with exactly these keys, with str/exact int/exact bool respectively. Return True when valid, False otherwise. Unknown schema type is invalid. No coercion.",
    """types={'string':str,'integer':int,'boolean':bool}
return isinstance(arguments,dict) and set(arguments)==set(schema) and all(kind in types and type(arguments[k]) is types[kind] for k,kind in schema.items())""",
    [ok(({'x':'integer'},{'x':2}),True),ok(({'x':'integer'},{'x':True}),False),ok(({'x':'string'},{'x':'a','extra':1}),False),ok(({},{}),True),ok(({'x':'boolean'},{'x':1}),False),ok(({'x':'number'},{'x':1}),False)])

add("retry", "有限指数退避", "retry_delays(attempts, base, cap)",
    "Return [min(cap,base*2**i) for i in range(attempts)]. attempts exact int 0..30; base/cap nonnegative numeric. Invalid input raises ValueError. No sleeping, randomness or calls are performed.",
    """if type(attempts) is not int or not 0<=attempts<=30 or base<0 or cap<0:raise ValueError('retry')
return [min(cap,base*2**i) for i in range(attempts)]""",
    [ok((4,1,3),[1,2,3,3]),ok((0,1,3),[]),ok((3,0,3),[0,0,0]),ok((2,5,2),[2,2]),bad((-1,1,3)),bad((2,-1,3))])
