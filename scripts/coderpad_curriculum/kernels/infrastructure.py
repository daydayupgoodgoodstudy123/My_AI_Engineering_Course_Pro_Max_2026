from . import add, ok, bad

add("ttl", "TTL 缓存回放", "cache_replay(events, ttl)",
    "Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological.",
    """if ttl<0:raise ValueError('ttl')
cache={};output=[]
for e in events:
    if e['op']=='put':cache[e['key']]=(e['time']+ttl,copy.deepcopy(e['value']))
    elif e['op']=='get':
        entry=cache.get(e['key']);output.append(copy.deepcopy(entry[1]) if entry is not None and e['time']<entry[0] else None)
    else:raise ValueError('operation')
return output""",
    [ok(([{'op':'put','key':'a','time':0,'value':1},{'op':'get','key':'a','time':1},{'op':'get','key':'a','time':2}],2),[1,None]),ok(([{'op':'get','key':'a','time':0}],1),[None]),ok(([],1),[]),ok(([{'op':'put','key':'a','time':0,'value':0},{'op':'get','key':'a','time':0}],0),[None]),bad(([],-1)),bad(([{'op':'delete','key':'a','time':0}],1))])

add("budget", "成本预算治理", "budget_decisions(costs, limit)",
    "Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge.",
    """if limit<0 or any(c<0 for c in costs):raise ValueError('budget')
spent=0;accepted=[]
for cost in costs:
    allow=spent+cost<=limit;accepted.append(allow)
    if allow:spent+=cost
return {'accepted':accepted,'spent':spent}""",
    [ok(([2,4,1],3),{'accepted':[True,False,True],'spent':3}),ok(([],0),{'accepted':[],'spent':0}),ok(([0,1],0),{'accepted':[True,False],'spent':0}),ok(([5],5),{'accepted':[True],'spent':5}),bad(([-1],1)),bad(([],-1))])

add("rate_limit", "滑动窗口限流", "rate_limit(times, window, maximum)",
    "Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot.",
    """if window<=0 or type(maximum) is not int or maximum<=0 or any(a>b for a,b in zip(times,times[1:])):raise ValueError('limiter')
accepted=deque();result=[]
for now in times:
    while accepted and accepted[0]<=now-window:accepted.popleft()
    allow=len(accepted)<maximum;result.append(allow)
    if allow:accepted.append(now)
return result""",
    [ok(([0,0,1,10],10,2),[True,True,False,True]),ok(([],1,1),[]),ok(([0,1],1,1),[True,True]),ok(([0,0,0],1,1),[True,False,False]),bad(([1,0],1,1)),bad(([],0,1))])

add("latency", "分位数与 Goodput", "latency_report(latencies, deadline)",
    "Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError.",
    """if not latencies or any(t<0 for t in latencies) or deadline<0:raise ValueError('latency')
ordered=sorted(latencies);n=len(ordered)
return {'p50':ordered[math.ceil(.5*n)-1],'p95':ordered[math.ceil(.95*n)-1],'goodput_fraction':sum(t<=deadline for t in latencies)/n}""",
    [ok(([1,2,3,4],2),{'p50':2,'p95':4,'goodput_fraction':.5}),ok(([5],5),{'p50':5,'p95':5,'goodput_fraction':1}),ok(([3,1],0),{'p50':1,'p95':3,'goodput_fraction':0}),ok(([0,0],0),{'p50':0,'p95':0,'goodput_fraction':1}),bad(([],1)),bad(([-1],1))])

add("canary", "灰度发布判定", "canary_decision(samples, max_error_rate, max_p95)",
    "Each sample has ok exact bool and latency>=0. Empty samples returns 'insufficient'. Validate thresholds 0<=max_error_rate<=1,max_p95>=0 and samples; invalid input raises ValueError. Compute nearest-rank p95. Return 'rollback' if error rate>threshold or p95>threshold; otherwise 'promote'. These are local decisions, no deployment.",
    """if not 0<=max_error_rate<=1 or max_p95<0 or any(type(s['ok']) is not bool or s['latency']<0 for s in samples):raise ValueError('evidence')
if not samples:return 'insufficient'
rate=sum(not s['ok'] for s in samples)/len(samples);p95=sorted(s['latency'] for s in samples)[math.ceil(.95*len(samples))-1]
return 'rollback' if rate>max_error_rate or p95>max_p95 else 'promote'""",
    [ok(([{'ok':True,'latency':5}],0,5),'promote'),ok(([{'ok':False,'latency':1}],0,5),'rollback'),ok(([{'ok':True,'latency':6}],0,5),'rollback'),ok(([],0,5),'insufficient'),bad(([],2,5)),ok(([{'ok':True,'latency':1},{'ok':False,'latency':1}],.5,5),'promote')])

add("autoscale", "容量与副本数", "replicas(arrival_rate, capacity_per_replica, target_utilization, minimum, maximum)",
    "Compute ceil(arrival_rate/(capacity_per_replica*target_utilization)), clamped to exact integer minimum..maximum. Require arrival_rate>=0,capacity>0,0<utilization<=1,0<=minimum<=maximum. Invalid input raises ValueError. No Kubernetes call.",
    """if arrival_rate<0 or capacity_per_replica<=0 or not 0<target_utilization<=1 or type(minimum) is not int or type(maximum) is not int or not 0<=minimum<=maximum:raise ValueError('capacity')
return min(maximum,max(minimum,math.ceil(arrival_rate/(capacity_per_replica*target_utilization))))""",
    [ok((100,100,.5,1,10),2),ok((0,100,.5,1,10),1),ok((9999,100,.5,1,3),3),ok((0,100,1,0,3),0),bad((1,0,.5,1,3)),bad((1,1,2,1,3))])

add("batch", "有界批处理装箱", "make_batches(items, maximum)",
    "items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields [].",
    """if type(maximum) is not int or maximum<=0 or any(type(x['tokens']) is not int or not 0<x['tokens']<=maximum for x in items):raise ValueError('batch')
result=[];current=[];size=0
for x in items:
    if size+x['tokens']>maximum:result.append(current);current=[];size=0
    current.append(x['id']);size+=x['tokens']
if current:result.append(current)
return result""",
    [ok(([{'id':'a','tokens':2},{'id':'b','tokens':3},{'id':'c','tokens':1}],5),[['a','b'],['c']]),ok(([],1),[]),ok(([{'id':'a','tokens':1}],1),[['a']]),bad(([{'id':'a','tokens':2}],1)),bad(([],0)),ok(([{'id':'a','tokens':2},{'id':'b','tokens':2}],3),[['a'],['b']])])

add("cost", "Token 成本计费", "token_cost(usage, prices)",
    "usage rows contain provider,input_tokens,output_tokens exact nonnegative ints. prices maps provider to [input_price,output_price] per token, nonnegative. Return {'total':sum,'by_provider':sums}. Unknown provider raises KeyError; negative/invalid counts or prices raises ValueError. Empty usage yields zero totals.",
    """totals={}
for r in usage:
    pin,pout=prices[r['provider']]
    if pin<0 or pout<0 or any(type(r[k]) is not int or r[k]<0 for k in ('input_tokens','output_tokens')):raise ValueError('usage')
    totals[r['provider']]=totals.get(r['provider'],0)+r['input_tokens']*pin+r['output_tokens']*pout
return {'total':sum(totals.values()),'by_provider':totals}""",
    [ok(([{'provider':'a','input_tokens':2,'output_tokens':3}],{'a':[1,2]}),{'total':8,'by_provider':{'a':8}}),ok(([],{}),{'total':0,'by_provider':{}}),bad(([{'provider':'a','input_tokens':-1,'output_tokens':0}],{'a':[1,1]})),bad(([{'provider':'a','input_tokens':True,'output_tokens':0}],{'a':[1,1]})),bad(([{'provider':'x','input_tokens':1,'output_tokens':1}],{}),'KeyError'),ok(([{'provider':'a','input_tokens':0,'output_tokens':0}],{'a':[1,1]}),{'total':0,'by_provider':{'a':0}})])

add("lru", "LRU 缓存淘汰", "lru_keys(accesses, capacity)",
    "Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError.",
    """if type(capacity) is not int or capacity<0:raise ValueError('capacity')
keys=[]
for key in accesses:
    if key in keys:keys.remove(key)
    keys.append(key)
    if len(keys)>capacity:keys.pop(0)
return keys""",
    [ok((['a','b','a','c'],2),['a','c']),ok(([],2),[]),ok((['a'],0),[]),ok((['a','a'],2),['a']),bad(([],-1)),ok((['a','b'],1),['b'])])

add("pipeline", "流水线气泡估算", "pipeline_bubble(stages, microbatches)",
    "Both arguments are exact positive ints. Return idle fraction (stages-1)/(microbatches+stages-1) for a simplified flush schedule; invalid input raises ValueError. No actual distributed execution.",
    """if any(type(x) is not int or x<=0 for x in (stages,microbatches)):raise ValueError('pipeline')
return (stages-1)/(microbatches+stages-1)""",
    [ok((1,1),0),ok((2,1),.5),ok((4,3),.5),ok((2,3),.25),bad((0,1)),bad((1,0))])
