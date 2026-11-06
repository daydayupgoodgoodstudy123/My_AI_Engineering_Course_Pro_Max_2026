from . import add, ok, bad

add("dot", "向量内积", "dot(a, b)",
    "Return the dot product of equal-length numeric lists. Empty lists return 0. Unequal lengths raise ValueError. Do not mutate inputs.",
    """if len(a)!=len(b): raise ValueError('shape')
return sum(x*y for x,y in zip(a,b))""",
    [ok(([1,2],[3,4]),11),ok(([],[]),0),ok(([0],[9]),0),ok(([-1,2],[3,-4]),-11),bad(([1],[])),ok(([.5],[2]),1)])

add("matmul", "矩阵乘法", "matmul(a, b)",
    "Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError.",
    """if not a or not b or not a[0] or not b[0] or any(len(r)!=len(a[0]) for r in a) or any(len(r)!=len(b[0]) for r in b) or len(a[0])!=len(b): raise ValueError('shape')
return [[sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]""",
    [ok(([[1,2]],[[3],[4]]),[[11]]),ok(([[1,0],[0,1]],[[2,3],[4,5]]),[[2,3],[4,5]]),ok(([[0]],[[9]]),[[0]]),bad(([],[[1]])),bad(([[1,2]],[[1,2]])),bad(([[1],[2,3]],[[1]]))])

add("transpose", "矩阵转置", "transpose(rows)",
    "Return a new list-of-lists transpose. Empty input returns []. Ragged rows raise ValueError. A rectangular matrix of empty rows transposes to [].",
    """if not rows:return []
if any(len(r)!=len(rows[0]) for r in rows):raise ValueError('ragged')
return [list(c) for c in zip(*rows)]""",
    [ok(([[1,2],[3,4]],),[[1,3],[2,4]]),ok(([],),[]),ok(([[1,2,3]],),[[1],[2],[3]]),ok(([[],[]],),[]),bad(([[1],[1,2]],)),ok(([[0]],),[[0]])])

add("normalize", "L2 归一化", "normalize(values)",
    "Return a new vector divided by its L2 norm. Empty or all-zero vectors raise ValueError. Inputs are finite numbers.",
    """norm=math.sqrt(sum(x*x for x in values))
if norm==0:raise ValueError('zero norm')
return [x/norm for x in values]""",
    [ok(([3,4],),[.6,.8]),ok(([1],),[1]),ok(([-2],),[-1]),bad(([],)),bad(([0,0],)),ok(([1,1],),[2**-.5,2**-.5])])

add("distance", "距离与形状校验", "distance(a, b, metric='l2')",
    "Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError.",
    """if len(a)!=len(b) or metric not in ('l1','l2','linf'):raise ValueError('contract')
d=[abs(x-y) for x,y in zip(a,b)]
return sum(d) if metric=='l1' else math.sqrt(sum(x*x for x in d)) if metric=='l2' else max(d,default=0)""",
    [ok(([0,0],[3,4]),5),ok(([0,0],[3,4],'l1'),7),ok(([0,0],[3,4],'linf'),4),ok(([],[]),0),bad(([1],[])),bad(([1],[1],'other'))])

add("softmax", "数值稳定的 Softmax", "softmax(values)",
    "Return stable softmax probabilities for a nonempty list of finite logits, preserving order. Subtract the maximum before exponentiation. Empty input raises ValueError.",
    """if not values:raise ValueError('empty')
maximum=max(values);weights=[math.exp(x-maximum) for x in values];total=sum(weights)
return [x/total for x in weights]""",
    [ok(([0,0],),[.5,.5]),ok(([1000,1000],),[.5,.5]),ok(([-1000,-1000],),[.5,.5]),ok(([9],),[1]),bad(([],)),ok(([0,0.6931471805599453],),[1/3,2/3])])

add("logsumexp", "稳定 LogSumExp", "logsumexp(values)",
    "For nonempty finite logits return log(sum(exp(x))) using max subtraction. Empty input raises ValueError.",
    """if not values:raise ValueError('empty')
m=max(values)
return m+math.log(sum(math.exp(x-m) for x in values))""",
    [ok(([0],),0),ok(([0,0],),.6931471805599453),ok(([1000,1000],),1000.6931471805599),ok(([-1000],),-1000),bad(([],)),ok(([1],),1)])

add("entropy", "概率分布熵", "entropy(probabilities)",
    "Return Shannon entropy in bits. Require a nonempty list of numeric probabilities in [0,1] summing to 1 within 1e-9, else ValueError. Define 0*log2(0)=0.",
    """if not probabilities or any(p<0 or p>1 for p in probabilities) or abs(sum(probabilities)-1)>1e-9:raise ValueError('distribution')
return -sum(p*math.log2(p) for p in probabilities if p)""",
    [ok(([.5,.5],),1),ok(([1,0],),0),ok(([.25]*4,),2),bad(([],)),bad(([.2,.2],)),bad(([-1,2],))])

add("bayes", "贝叶斯更新", "bayes(prior, likelihood_positive, likelihood_negative)",
    "For three probabilities in [0,1], return P(H|E)=prior*likelihood_positive/(prior*likelihood_positive+(1-prior)*likelihood_negative). Out-of-range values or zero evidence probability raise ValueError.",
    """if any(not 0<=x<=1 for x in (prior,likelihood_positive,likelihood_negative)):raise ValueError('probability')
den=prior*likelihood_positive+(1-prior)*likelihood_negative
if den==0:raise ValueError('impossible evidence')
return prior*likelihood_positive/den""",
    [ok((.5,.8,.2),.8),ok((.1,.9,.1),.5),ok((1,.5,.2),1),ok((0,.5,.2),0),bad((.5,0,0)),bad((2,.5,.5))])

add("statistics", "均值与总体方差", "summary(values)",
    "Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError.",
    """if not values:raise ValueError('empty')
mean=sum(values)/len(values)
return {'mean':mean,'variance':sum((x-mean)**2 for x in values)/len(values),'min':min(values),'max':max(values)}""",
    [ok(([1,2,3],),{'mean':2,'variance':2/3,'min':1,'max':3}),ok(([5],),{'mean':5,'variance':0,'min':5,'max':5}),ok(([0,0],),{'mean':0,'variance':0,'min':0,'max':0}),ok(([-1,1],),{'mean':0,'variance':1,'min':-1,'max':1}),bad(([],)),ok(([2,4],),{'mean':3,'variance':1,'min':2,'max':4})])

add("gradient", "数值梯度", "quadratic_gradient(weights, target)",
    "For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError.",
    """if len(weights)!=len(target):raise ValueError('shape')
return [2*(w-t) for w,t in zip(weights,target)]""",
    [ok(([1,2],[0,0]),[2,4]),ok(([1],[1]),[0]),ok(([],[]),[]),ok(([-1],[1]),[-4]),bad(([1],[])),ok(([.5],[0]),[1])])

add("gd", "梯度下降一步更新", "gradient_step(weights, gradients, rate)",
    "Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid.",
    """if len(weights)!=len(gradients) or rate<0:raise ValueError('contract')
return [w-rate*g for w,g in zip(weights,gradients)]""",
    [ok(([1,2],[2,4],.1),[.8,1.6]),ok(([1],[9],0),[1]),ok(([],[],1),[]),ok(([0],[-1],2),[2]),bad(([1],[],1)),bad(([1],[1],-1))])

add("eigen", "2×2 实特征值", "eigenvalues_2x2(matrix)",
    "Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice.",
    """if len(matrix)!=2 or any(len(r)!=2 for r in matrix):raise ValueError('shape')
a,b=matrix[0];c,d=matrix[1];disc=(a+d)**2-4*(a*d-b*c)
if disc<0:raise ValueError('complex roots')
return [(a+d-math.sqrt(disc))/2,(a+d+math.sqrt(disc))/2]""",
    [ok(([[2,0],[0,3]],),[2,3]),ok(([[1,0],[0,1]],),[1,1]),ok(([[0,1],[1,0]],),[-1,1]),ok(([[0,0],[0,0]],),[0,0]),bad(([[1]],)),bad(([[0,-1],[1,0]],))])

add("linear_solve", "2×2 线性方程", "solve_2x2(matrix, rhs)",
    "Solve A*x=rhs using a 2x2 matrix and two-element rhs. Invalid shapes or abs(det)<1e-12 raises ValueError. Return [x0,x1].",
    """if len(matrix)!=2 or any(len(r)!=2 for r in matrix) or len(rhs)!=2:raise ValueError('shape')
a,b=matrix[0];c,d=matrix[1];det=a*d-b*c
if abs(det)<1e-12:raise ValueError('singular')
return [(rhs[0]*d-b*rhs[1])/det,(a*rhs[1]-rhs[0]*c)/det]""",
    [ok(([[1,0],[0,1]],[2,3]),[2,3]),ok(([[2,0],[0,4]],[4,8]),[2,2]),ok(([[1,1],[1,-1]],[3,1]),[2,1]),bad(([[1,2],[2,4]],[1,2])),bad(([[1]],[1])),ok(([[1,0],[0,1]],[0,0]),[0,0])])

add("transform", "二维仿射变换", "transform(points, matrix, offset)",
    "Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns [].",
    """if len(matrix)!=2 or any(len(r)!=2 for r in matrix) or len(offset)!=2 or any(len(p)!=2 for p in points):raise ValueError('shape')
return [[sum(matrix[i][j]*p[j] for j in range(2))+offset[i] for i in range(2)] for p in points]""",
    [ok(([[1,2]],[[1,0],[0,1]],[0,0]),[[1,2]]),ok(([[1,0]],[[0,-1],[1,0]],[0,0]),[[0,1]]),ok(([[1,2]],[[2,0],[0,3]],[1,-1]),[[3,5]]),ok(([],[[1,0],[0,1]],[0,0]),[]),bad(([[1]],[[1,0],[0,1]],[0,0])),bad(([],[[1]],[0,0]))])
