from . import add, ok, bad

add("mse", "回归误差与形状", "mse(predicted, expected)",
    "Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError.",
    """if not predicted or len(predicted)!=len(expected):raise ValueError('shape')
return sum((a-b)**2 for a,b in zip(predicted,expected))/len(predicted)""",
    [ok(([1,2],[1,4]),2),ok(([0],[0]),0),ok(([-1],[1]),4),ok(([1,3],[2,2]),1),bad(([],[])),bad(([1],[]))])

add("sigmoid", "稳定 Sigmoid", "sigmoid(value)",
    "Return logistic sigmoid for a finite scalar, avoiding overflow for large positive or negative magnitudes.",
    """if value>=0:return 1/(1+math.exp(-value))
exp=math.exp(value)
return exp/(1+exp)""",
    [ok((0,),.5),ok((1000,),1),ok((-1000,),0),ok((.6931471805599453,),2/3),ok((-.6931471805599453,),1/3),ok((1,),.7310585786300049)])

add("activation", "激活函数前向", "activation(values, kind='relu', slope=0.01)",
    "Map numeric values through relu, leaky_relu, or tanh. relu=max(0,x); leaky_relu uses slope*x only for x<0. Unknown kind or negative slope raises ValueError; empty input returns [].",
    """if kind not in ('relu','leaky_relu','tanh') or slope<0:raise ValueError('activation')
return [max(0,x) if kind=='relu' else (x if x>=0 else slope*x) if kind=='leaky_relu' else math.tanh(x) for x in values]""",
    [ok(([-2,0,3],),[0,0,3]),ok(([-2,0,3],'leaky_relu',.1),[-.2,0,3]),ok(([0],'tanh'),[0]),ok(([],),[]),bad(([1],'unknown')),bad(([1],'relu',-1))])

add("linear", "线性层前向", "linear(features, weights, bias)",
    "weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield [].",
    """if len(weights)!=len(bias) or any(len(r)!=len(features) for r in weights):raise ValueError('shape')
return [sum(x*w for x,w in zip(features,row))+b for row,b in zip(weights,bias)]""",
    [ok(([1,2],[[1,0],[0,1]],[0,1]),[1,3]),ok(([2],[[3]],[1]),[7]),ok(([],[[]],[2]),[2]),ok(([1],[],[]),[]),bad(([1],[[1,2]],[0])),bad(([1],[[1]],[]))])

add("gini", "决策树分裂纯度", "gini(labels)",
    "Return 1-sum(class_fraction^2) for hashable labels. Empty labels returns 0. Labels may be strings or integers.",
    """if not labels:return 0
counts=Counter(labels)
return 1-sum((n/len(labels))**2 for n in counts.values())""",
    [ok(([],),0),ok((['a'],),0),ok((['a','b'],),.5),ok(([0,0,1,1],),.5),ok(([1,2,3,4],),.75),ok((['x']*3+['y'],),.375)])

add("knn", "确定性的最近邻", "nearest(query, points, k)",
    "Return indices of the k nearest points by squared Euclidean distance; ties use lower original index. All points must match query dimension. k is an exact int in [0,len(points)], otherwise ValueError. k=0 returns [].",
    """if type(k) is not int or not 0<=k<=len(points) or any(len(p)!=len(query) for p in points):raise ValueError('contract')
return sorted(range(len(points)),key=lambda i:(sum((a-b)**2 for a,b in zip(query,points[i])),i))[:k]""",
    [ok(([0],[[3],[1],[2]],2),[1,2]),ok(([0],[[-1],[1]],2),[0,1]),ok(([0],[],0),[]),bad(([0],[[1]],2)),bad(([0],[[1,2]],1)),bad(([0],[[1]],True))])

add("standardize", "训练统计量与变换", "standardize(train, values)",
    "Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError.",
    """if not train:raise ValueError('empty train')
mean=sum(train)/len(train);scale=math.sqrt(sum((x-mean)**2 for x in train)/len(train)) or 1
return {'mean':mean,'scale':scale,'values':[(x-mean)/scale for x in values]}""",
    [ok(([0,2],[0,2,4]),{'mean':1,'scale':1,'values':[-1,1,3]}),ok(([5,5],[5,6]),{'mean':5,'scale':1,'values':[0,1]}),ok(([1],[]),{'mean':1,'scale':1,'values':[]}),bad(([],[1])),ok(([-1,1],[0]),{'mean':0,'scale':1,'values':[0]}),ok(([2],[0]),{'mean':2,'scale':1,'values':[-2]})])

add("classification", "分类混淆矩阵指标", "classification(expected, predicted)",
    "Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError.",
    """if len(expected)!=len(predicted) or any(type(x) is not bool for x in expected+predicted):raise ValueError('labels')
tp=sum(a and b for a,b in zip(expected,predicted));fp=sum(not a and b for a,b in zip(expected,predicted));fn=sum(a and not b for a,b in zip(expected,predicted));tn=len(expected)-tp-fp-fn
p=tp/(tp+fp) if tp+fp else 0;r=tp/(tp+fn) if tp+fn else 0
return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':p,'recall':r,'f1':2*p*r/(p+r) if p+r else 0}""",
    [ok(([True],[True]),dict(tp=1,fp=0,fn=0,tn=0,precision=1,recall=1,f1=1)),ok(([],[]),dict(tp=0,fp=0,fn=0,tn=0,precision=0,recall=0,f1=0)),ok(([False],[True]),dict(tp=0,fp=1,fn=0,tn=0,precision=0,recall=0,f1=0)),ok(([False],[False]),dict(tp=0,fp=0,fn=0,tn=1,precision=0,recall=0,f1=0)),bad(([True],[])),bad(([1],[True]))])

add("ensemble", "集成投票与并列", "majority_votes(predictions)",
    "Input is model-by-example label matrix of strings. Return one majority label per example; ties choose lexicographically smallest label. Empty model list returns []; ragged rows raise ValueError.",
    """if not predictions:return []
if any(len(r)!=len(predictions[0]) for r in predictions):raise ValueError('shape')
return [min(Counter(column),key=lambda x:(-Counter(column)[x],x)) for column in zip(*predictions)]""",
    [ok(([['a','b'],['a','a'],['b','b']],),['a','b']),ok(([['z'],['a']],),['a']),ok(([],),[]),ok(([[],[]],),[]),bad(([['a'],[]],)),ok(([['x']],),['x'])])

add("grid", "超参数网格与预算", "grid(parameters, limit)",
    "Enumerate Cartesian products with parameter keys sorted lexicographically and option order preserved. Return at most limit dicts; limit is exact nonnegative int. Empty parameter dict produces [{}] if limit>0. Any empty option list produces []. Invalid limit raises ValueError.",
    """if type(limit) is not int or limit<0:raise ValueError('limit')
keys=sorted(parameters)
return [dict(zip(keys,values)) for values in itertools.islice(itertools.product(*(parameters[k] for k in keys)),limit)]""",
    [ok(({'b':[1,2],'a':['x']},3),[{'a':'x','b':1},{'a':'x','b':2}]),ok(({},1),[{}]),ok(({'x':[]},5),[]),ok(({'x':[1]},0),[]),bad(({},-1)),bad(({},True))])

add("lag", "时间序列滞后特征", "lag_features(series, window)",
    "window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError.",
    """if type(window) is not int or window<=0:raise ValueError('window')
return {'x':[series[i-window:i] for i in range(window,len(series))],'y':series[window:]}""",
    [ok(([1,2,3,4],2),{'x':[[1,2],[2,3]],'y':[3,4]}),ok(([1,2],1),{'x':[[1]],'y':[2]}),ok(([],2),{'x':[],'y':[]}),ok(([1],3),{'x':[],'y':[]}),bad(([1],0)),bad(([1],True))])

add("anomaly", "阈值异常检测", "zscore_flags(values, threshold)",
    "Use population mean/variance from values; flag abs(z)>threshold (strict). Constant or empty lists yield all False/empty. Negative threshold raises ValueError.",
    """if threshold<0:raise ValueError('threshold')
if not values:return []
mean=sum(values)/len(values);sd=math.sqrt(sum((x-mean)**2 for x in values)/len(values))
return [abs(x-mean)/sd>threshold if sd else False for x in values]""",
    [ok(([0,0,0,4],1.5),[False,False,False,True]),ok(([1,1],0),[False,False]),ok(([],1),[]),ok(([-1,1],1),[False,False]),ok(([-1,1],.5),[True,True]),bad(([1],-1))])

add("weights", "类别权重", "class_weights(labels)",
    "Return string label -> n/(number_of_classes*class_count). Empty labels returns {}. Labels are provided strings; do not alter input order or labels.",
    """counts=Counter(labels)
return {label:len(labels)/(len(counts)*n) for label,n in sorted(counts.items())}""",
    [ok((['a','a','b'],),{'a':.75,'b':1.5}),ok(([],),{}),ok((['a'],),{'a':1}),ok((['a','b'],),{'a':1,'b':1}),ok((['x']*4,),{'x':1}),ok((['a','b','c'],),{'a':1,'b':1,'c':1})])

add("schedule", "Warmup 与余弦学习率", "learning_rate(step, total, warmup, peak)",
    "Require exact integer total>0, 0<=warmup<total, step>=0, and peak>=0. If step<warmup return peak*step/warmup; otherwise peak*(1+cos(pi*min(1,(step-warmup)/(total-warmup))))/2. Invalid configuration raises ValueError.",
    """if any(type(x) is not int for x in (step,total,warmup)) or total<=0 or not 0<=warmup<total or step<0 or peak<0:raise ValueError('schedule')
if step<warmup:return peak*step/warmup
return peak*(1+math.cos(math.pi*min(1,(step-warmup)/(total-warmup))))/2""",
    [ok((0,10,2,1),0),ok((1,10,2,1),.5),ok((2,10,2,1),1),ok((10,10,2,1),0),ok((99,10,0,1),0),bad((0,2,2,1))])

add("clip", "梯度范数裁剪", "clip_gradients(gradients, maximum)",
    "Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid.",
    """if maximum<0:raise ValueError('maximum')
norm=math.sqrt(sum(g*g for g in gradients));scale=min(1,maximum/norm) if norm else 1
return [g*scale for g in gradients]""",
    [ok(([3,4],1),[.6,.8]),ok(([1],2),[1]),ok(([0,0],0),[0,0]),ok(([],1),[]),ok(([3,4],0),[0,0]),bad(([1],-1))])

add("cross_entropy", "分类交叉熵", "cross_entropy(probabilities, target)",
    "Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError.",
    """if not probabilities or any(p<0 or p>1 for p in probabilities) or abs(sum(probabilities)-1)>1e-9 or type(target) is not int or not 0<=target<len(probabilities):raise ValueError('contract')
return -math.log(max(1e-12,probabilities[target]))""",
    [ok(([1,0],0),0),ok(([.5,.5],1),.6931471805599453),ok(([0,1],0),27.631021115928547),bad(([.1,.1],0)),bad(([1],True)),bad(([],0))])
