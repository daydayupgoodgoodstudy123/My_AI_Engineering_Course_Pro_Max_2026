from . import add, ok, bad

add("returns", "折扣回报", "discounted_returns(rewards, gamma)",
    "Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns [].",
    """if not 0<=gamma<=1:raise ValueError('gamma')
result=[];running=0
for reward in reversed(rewards):running=reward+gamma*running;result.append(running)
return list(reversed(result))""",
    [ok(([1,1,1],.5),[1.75,1.5,1]),ok(([1,2],0),[1,2]),ok(([1,2],1),[3,2]),ok(([],.5),[]),ok(([-1,1],1),[0,1]),bad(([1],2))])

add("bellman", "Bellman 最优备份", "bellman_backup(actions, gamma)",
    "Each action is a nonempty list of [probability,reward,next_value] transitions. Probabilities per action must be nonnegative and sum to 1 within 1e-9. Return max over actions of sum(p*(r+gamma*v)). Require at least one action and gamma in [0,1], else ValueError.",
    """if not actions or not 0<=gamma<=1 or any(not a or any(t[0]<0 for t in a) or abs(sum(t[0] for t in a)-1)>1e-9 for a in actions):raise ValueError('MDP')
return max(sum(p*(r+gamma*v) for p,r,v in action) for action in actions)""",
    [ok(([[[1,1,2]],[[1,2,0]]],.5),2),ok(([[[.5,0,2],[.5,2,0]]],1),2),ok(([[[1,-1,0]]],0),-1),bad(([],.5)),bad(([[[.5,1,0]]],.5)),bad(([[[1,0,0]]],2))])

add("q_update", "Q-learning 更新", "q_update(current, reward, next_values, alpha, gamma, terminal=False)",
    "Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError.",
    """if not 0<=alpha<=1 or not 0<=gamma<=1 or not terminal and not next_values:raise ValueError('transition')
target=reward+(0 if terminal else gamma*max(next_values))
return current+alpha*(target-current)""",
    [ok((0,1,[2],.5,.9),1.4),ok((2,1,[],1,1,True),1),ok((3,1,[9],0,1),3),ok((0,-1,[-2],1,.5),-2),bad((0,0,[],1,1)),bad((0,0,[1],2,1))])

add("ppo", "PPO Clipped Surrogate", "ppo_objective(ratios, advantages, epsilon)",
    "Return mean(min(ratio*A,clip(ratio,1-epsilon,1+epsilon)*A)). Require equal nonempty lists, ratios>=0, and 0<=epsilon<1; otherwise ValueError. Keep the sign of advantages.",
    """if not ratios or len(ratios)!=len(advantages) or any(r<0 for r in ratios) or not 0<=epsilon<1:raise ValueError('PPO')
return sum(min(r*a,max(1-epsilon,min(1+epsilon,r))*a) for r,a in zip(ratios,advantages))/len(ratios)""",
    [ok(([1],[2],.2),2),ok(([2],[1],.2),1.2),ok(([.1],[-1],.2),-.8),ok(([1,1],[1,-1],.2),0),bad(([],[],.2)),bad(([1],[1],1))])

add("dpo", "偏好对的稳定 Loss", "dpo_loss(chosen_logp, rejected_logp, reference_margin, beta)",
    "Require beta>0. z=beta*(chosen_logp-rejected_logp-reference_margin). Return log(1+exp(-z)) stably as max(0,-z)+log1p(exp(-abs(z))). Inputs are finite scalar log probabilities.",
    """if beta<=0:raise ValueError('beta')
z=beta*(chosen_logp-rejected_logp-reference_margin)
return max(0,-z)+math.log1p(math.exp(-abs(z)))""",
    [ok((0,0,0,1),.6931471805599453),ok((1000,0,0,1),0),ok((-1000,0,0,1),1000),ok((2,1,1,.5),.6931471805599453),bad((0,0,0,0)),ok((.6931471805599453,0,0,1),.4054651081081644)])

add("ucb", "探索与利用调度", "select_ucb(means, visits, total, exploration)",
    "means/visits must be same-length nonempty lists; visits are exact nonnegative ints; total exact int >=1, exploration>=0. Return first unvisited index if any; else maximize mean+c*sqrt(log(total)/visits), ties lower index. Invalid input raises ValueError.",
    """if not means or len(means)!=len(visits) or type(total) is not int or total<1 or exploration<0 or any(type(v) is not int or v<0 for v in visits):raise ValueError('UCB')
if 0 in visits:return visits.index(0)
return max(range(len(means)),key=lambda i:means[i]+exploration*math.sqrt(math.log(total)/visits[i]))""",
    [ok(([.1,.9],[1,0],2,1),1),ok(([.1,.9],[2,2],4,0),1),ok(([1,1],[1,1],2,0),0),ok(([0,0],[10,1],11,1),1),bad(([],[],1,1)),bad(([0],[True],1,1))])

add("advantage", "Actor-Critic Advantage", "advantages(rewards, values, gamma)",
    "values contains one more element than rewards. Return one-step TD advantage r[t]+gamma*v[t+1]-v[t]. Require gamma in [0,1] and exact length relation; otherwise ValueError. Empty rewards plus one value returns [].",
    """if len(values)!=len(rewards)+1 or not 0<=gamma<=1:raise ValueError('trajectory')
return [r+gamma*values[i+1]-values[i] for i,r in enumerate(rewards)]""",
    [ok(([1,2],[0,1,0],1),[2,1]),ok(([1],[2,3],0),[-1]),ok(([],[0],.9),[]),ok(([0],[1,1],1),[0]),bad(([1],[0],1)),bad(([],[0],2))])

add("pareto", "多目标候选筛选", "pareto_front(candidates)",
    "Candidates have unique id strings, quality higher-is-better, cost lower-is-better. Return sorted ids not dominated by another candidate that is no worse in both and strictly better in at least one. Equal quality/cost entries both survive; empty input yields [].",
    "return sorted(a['id'] for a in candidates if not any(b['quality']>=a['quality'] and b['cost']<=a['cost'] and (b['quality']>a['quality'] or b['cost']<a['cost']) for b in candidates))",
    [ok(([{'id':'a','quality':2,'cost':1},{'id':'b','quality':1,'cost':2}],),['a']),ok(([],),[]),ok(([{'id':'a','quality':1,'cost':1},{'id':'b','quality':1,'cost':1}],),['a','b']),ok(([{'id':'x','quality':1,'cost':2}],),['x']),ok(([{'id':'a','quality':2,'cost':2},{'id':'b','quality':1,'cost':1}],),['a','b']),ok(([{'id':'z','quality':1,'cost':1},{'id':'a','quality':2,'cost':1}],),['a'])])

add("amdahl", "并行加速上限", "amdahl(serial_fraction, speedup)",
    "Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput.",
    """if not 0<=serial_fraction<=1 or speedup<1:raise ValueError('parameters')
return 1/(serial_fraction+(1-serial_fraction)/speedup)""",
    [ok((.5,2),4/3),ok((0,4),4),ok((1,9),1),ok((.2,1),1),bad((-.1,2)),bad((.5,.5))])

add("params", "模型参数与内存估算", "parameter_memory(shapes, bytes_per_parameter)",
    "Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError.",
    """if type(bytes_per_parameter) is not int or bytes_per_parameter<=0 or any(type(d) is not int or d<=0 for shape in shapes for d in shape):raise ValueError('shape')
return sum(math.prod(shape) for shape in shapes)*bytes_per_parameter""",
    [ok(([[2,3],[3]],4),36),ok(([[]],2),2),ok(([],4),0),ok(([[1]],1),1),bad(([[0]],4)),bad(([[1]],True))])

add("kv", "KV Cache 内存预算", "kv_bytes(layers, tokens, kv_heads, head_dimension, batch, bytes_per_element)",
    "All arguments are exact ints. layers,kv_heads,head_dimension,batch,bytes_per_element must be >0; tokens>=0. Return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element. Invalid input raises ValueError. No allocator overhead is included.",
    """values=[layers,tokens,kv_heads,head_dimension,batch,bytes_per_element]
if any(type(v) is not int for v in values) or tokens<0 or any(v<=0 for v in [layers,kv_heads,head_dimension,batch,bytes_per_element]):raise ValueError('dimensions')
return 2*layers*tokens*kv_heads*head_dimension*batch*bytes_per_element""",
    [ok((1,2,1,4,1,2),32),ok((2,0,1,4,1,2),0),ok((2,3,2,4,1,1),96),ok((1,1,1,1,2,1),4),bad((0,1,1,1,1,1)),bad((1,1,True,1,1,1))])

add("speculative", "推测解码前缀验收", "accept_prefix(draft, verified)",
    "Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled.",
    """i=0
while i<min(len(draft),len(verified)) and draft[i]==verified[i]:i+=1
return {'accepted':draft[:i],'next':verified[i] if i<len(verified) else None}""",
    [ok(([1,2,3],[1,2,9]),{'accepted':[1,2],'next':9}),ok(([1],[1,2]),{'accepted':[1],'next':2}),ok(([],[2]),{'accepted':[],'next':2}),ok(([1],[]),{'accepted':[],'next':None}),ok(([1],[1]),{'accepted':[1],'next':None}),ok(([1],[2]),{'accepted':[],'next':2})])

add("topk", "稀疏路由 Top-K", "top_k(scores, k)",
    "Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns [].",
    """if type(k) is not int or not 0<=k<=len(scores):raise ValueError('k')
return sorted(range(len(scores)),key=lambda i:(-scores[i],i))[:k]""",
    [ok(([1,3,2],2),[1,2]),ok(([1,1],1),[0]),ok(([],0),[]),ok(([-1,-2],2),[0,1]),bad(([1],2)),bad(([1],True))])
