from . import add, ok, bad

add("tokens", "文本归一化与分词", "tokenize(text)",
    "Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching.",
    "return re.findall(r'[a-z0-9]+',text.casefold())",
    [ok(('Hello, WORLD!',),['hello','world']),ok(('',),[]),ok(('a-b_2',),['a','b','2']),ok(('2026 AI',),['2026','ai']),ok(('你好',),[]),ok(('A  A',),['a','a'])])

add("bow", "词袋向量", "bag_of_words(tokens, vocabulary)",
    "Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization.",
    """if len(set(vocabulary))!=len(vocabulary):raise ValueError('duplicate vocabulary')
counts=Counter(tokens)
return [counts[t] for t in vocabulary]""",
    [ok((['a','a','x'],['a','b']),[2,0]),ok(([],['a']),[0]),ok((['a'],[]),[]),ok((['a','b'],['b','a']),[1,1]),bad(([],['a','a'])),ok((['A'],['a']),[0])])

add("ngrams", "N-gram 计数", "ngram_counts(tokens, n)",
    "n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError.",
    """if type(n) is not int or n<=0:raise ValueError('n')
return dict(Counter(json.dumps(tokens[i:i+n]) for i in range(len(tokens)-n+1)))""",
    [ok((['a','b','a'],1),{'["a"]':2,'["b"]':1}),ok((['a','b','a'],2),{'["a", "b"]':1,'["b", "a"]':1}),ok(([],2),{}),ok((['a'],2),{}),bad((['a'],0)),bad((['a'],True))])

add("bpe", "BPE 相邻 Pair 合并", "merge_pair(tokens, pair)",
    "pair must contain exactly two strings. Scan tokens left to right, replacing each non-overlapping adjacent match with concatenation. Preserve unmatched tokens. Invalid pair raises ValueError; input lists do not mutate.",
    """if len(pair)!=2 or any(not isinstance(x,str) for x in pair):raise ValueError('pair')
result=[];i=0
while i<len(tokens):
    if tokens[i:i+2]==list(pair):result.append(pair[0]+pair[1]);i+=2
    else:result.append(tokens[i]);i+=1
return result""",
    [ok((['a','b','a','b'],['a','b']),['ab','ab']),ok((['a','a','a'],['a','a']),['aa','a']),ok(([],['a','b']),[]),ok((['x'],['a','b']),['x']),bad(([],['a'])),ok((['a','b','b'],['a','b']),['ab','b'])])

add("chunks", "重叠窗口切块", "chunk_tokens(tokens, size, overlap)",
    "Require exact integers size>0 and 0<=overlap<size. Return windows starting at 0 then advancing size-overlap; include a short final window, stop once a window reaches the end. Empty tokens yields []. Invalid configuration raises ValueError.",
    """if type(size) is not int or type(overlap) is not int or size<=0 or not 0<=overlap<size:raise ValueError('window')
result=[];start=0
while start<len(tokens):
    result.append(tokens[start:start+size])
    if start+size>=len(tokens):break
    start+=size-overlap
return result""",
    [ok(([1,2,3,4,5],3,1),[[1,2,3],[3,4,5]]),ok(([1,2,3,4],3,0),[[1,2,3],[4]]),ok(([],2,1),[]),ok(([1],3,1),[[1]]),bad(([1],2,2)),bad(([1],0,0))])

add("cosine", "Embedding 余弦相似度", "cosine(a, b)",
    "Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError.",
    """if len(a)!=len(b):raise ValueError('shape')
den=math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
return sum(x*y for x,y in zip(a,b))/den if den else 0""",
    [ok(([1,0],[1,0]),1),ok(([1,0],[0,1]),0),ok(([1],[-1]),-1),ok(([0],[1]),0),ok(([],[]),0),bad(([1],[]))])

add("retrieval", "检索指标", "retrieval_metrics(ranked, relevant, k)",
    "ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError.",
    """if type(k) is not int or k<=0 or len(set(ranked))!=len(ranked):raise ValueError('ranking')
rel=set(relevant);top=ranked[:k];hits=sum(x in rel for x in top);first=next((i for i,x in enumerate(top,1) if x in rel),None)
return {'precision':hits/k,'recall':hits/len(rel) if rel else 0,'reciprocal_rank':1/first if first else 0}""",
    [ok((['a','b'],['b'],2),{'precision':.5,'recall':1,'reciprocal_rank':.5}),ok((['a'],['a','b'],2),{'precision':.5,'recall':.5,'reciprocal_rank':1}),ok(([],[],1),{'precision':0,'recall':0,'reciprocal_rank':0}),ok((['a'],[],1),{'precision':0,'recall':0,'reciprocal_rank':0}),bad((['a','a'],['a'],2)),bad(([],[],0))])

add("rrf", "倒数排名融合", "rrf(rankings, constant=60)",
    "For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields [].",
    """if constant<0:raise ValueError('constant')
scores={}
for ranking in rankings:
    seen=set()
    for rank,item in enumerate(ranking,1):
        if item not in seen:scores[item]=scores.get(item,0)+1/(constant+rank);seen.add(item)
return sorted(scores,key=lambda x:(-scores[x],x))""",
    [ok(([['a','b'],['b','a']],0),['a','b']),ok(([['b','a']],0),['b','a']),ok(([],),[]),ok(([[],[]],),[]),ok(([['a','a','b']],0),['a','b']),bad(([],-1))])

add("token_f1", "问答 Token F1", "token_f1(reference, answer)",
    "Inputs are token lists; count overlap as multiset intersection. Both empty ->1; exactly one empty ->0. Otherwise return harmonic mean of overlap/len(answer) and overlap/len(reference).",
    """if not reference or not answer:return 1 if not reference and not answer else 0
overlap=sum((Counter(reference)&Counter(answer)).values());p=overlap/len(answer);r=overlap/len(reference)
return 2*p*r/(p+r) if p+r else 0""",
    [ok((['a','b'],['a']),2/3),ok(([],[]),1),ok(([],['a']),0),ok((['a','a'],['a']),2/3),ok((['a'],['b']),0),ok((['a','b'],['b','a']),1)])

add("bio", "BIO 标签到实体片段", "bio_spans(labels)",
    "Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities.",
    """result=[];active=None;start=0
for i,label in enumerate(labels+['O']):
    if label=='O':kind,typ='O',None
    elif isinstance(label,str) and len(label)>2 and label[:2] in ('B-','I-'):kind,typ=label[0],label[2:]
    else:raise ValueError('BIO')
    continuation=kind=='I' and typ==active
    if active is not None and not continuation:result.append({'type':active,'start':start,'end':i});active=None
    if kind!='O' and not continuation:active=typ;start=i
return result""",
    [ok((['B-PER','I-PER','O'],),[{'type':'PER','start':0,'end':2}]),ok((['I-X'],),[{'type':'X','start':0,'end':1}]),ok((['B-X','B-X'],),[{'type':'X','start':0,'end':1},{'type':'X','start':1,'end':2}]),ok(([],),[]),ok((['O'],),[]),bad((['PER'],))])

add("dialogue", "对话槽位更新", "update_slots(state, changes)",
    "state and changes are dicts with only cuisine, area, people. Unknown keys in either raise ValueError. Changes with None delete a slot; other values replace it. Return a new merged dict without mutating either input. Value typing is upstream.",
    """allowed={'cuisine','area','people'}
if not set(state)<=allowed or not set(changes)<=allowed:raise ValueError('slot')
result=copy.deepcopy(state)
for key,value in changes.items():
    if value is None:result.pop(key,None)
    else:result[key]=copy.deepcopy(value)
return result""",
    [ok(({'area':'west'},{'area':'east'}),{'area':'east'}),ok(({'people':2},{'people':None}),{}),ok(({},{}),{}),ok(({}, {'cuisine':'Thai'}),{'cuisine':'Thai'}),bad(({}, {'secret':'x'})),ok(({}, {'area':None}),{})])

add("context", "上下文预算装箱", "select_context(items, budget)",
    "items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError.",
    """if type(budget) is not int or budget<0 or any(type(x['tokens']) is not int or x['tokens']<0 for x in items):raise ValueError('budget')
result=[]
for item in sorted(items,key=lambda x:(-x['score'],x['id'])):
    if item['tokens']<=budget:result.append(item['id']);budget-=item['tokens']
return result""",
    [ok(([{'id':'a','tokens':9,'score':2},{'id':'b','tokens':2,'score':1}],3),['b']),ok(([],0),[]),ok(([{'id':'a','tokens':0,'score':0}],0),['a']),bad(([],-1)),bad(([{'id':'a','tokens':True,'score':1}],1)),ok(([{'id':'b','tokens':1,'score':1},{'id':'a','tokens':1,'score':1}],1),['a'])])

add("masked", "受限解码分布", "masked_probabilities(logits, allowed)",
    "allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation.",
    """if not logits or not allowed or any(type(i) is not int or not 0<=i<len(logits) for i in allowed) or len(set(allowed))!=len(allowed):raise ValueError('mask')
maximum=max(logits[i] for i in allowed);weights={i:math.exp(logits[i]-maximum) for i in allowed};total=sum(weights.values())
return [weights.get(i,0)/total for i in range(len(logits))]""",
    [ok(([0,0,0],[0,2]),[.5,0,.5]),ok(([1000,1],[0]),[1,0]),ok(([0],[0]),[1]),bad(([0],[])),bad(([0],[1])),bad(([0],[0,0]))])

add("perplexity", "Perplexity 与长度", "perplexity(probabilities)",
    "Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep.",
    """if not probabilities or any(not 0<p<=1 for p in probabilities):raise ValueError('probabilities')
return math.exp(-sum(math.log(p) for p in probabilities)/len(probabilities))""",
    [ok(([1],),1),ok(([.5,.5],),2),ok(([.25],),4),ok(([1,.25],),2),bad(([],)),bad(([0],))])
