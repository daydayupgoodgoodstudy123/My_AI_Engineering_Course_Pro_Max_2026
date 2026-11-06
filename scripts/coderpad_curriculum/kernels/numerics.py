from . import add, ok, bad

add("differentiate", "多项式求导与链式法则", "polynomial_derivative(coefficients, x)",
    "coefficients[i] multiplies x**i. Return the derivative at x, with [] and constant polynomials returning 0. Inputs are finite numbers.",
    "return sum(i*c*x**(i-1) for i,c in enumerate(coefficients) if i)",
    [ok(([1,2,3],2),14),ok(([],3),0),ok(([7],2),0),ok(([0,0,1],-2),-4),ok(([0,1],0),1),ok(([0,0,0,1],2),12)])

add("dft", "离散傅里叶变换", "dft(samples)",
    "Compute unnormalized forward DFT of real samples using exp(-2*pi*i*k*n/N). Return one [real,imaginary] pair per frequency bin. Empty input returns []. No FFT library.",
    """n=len(samples)
return [[sum(x*math.cos(-2*math.pi*k*j/n) for j,x in enumerate(samples)),sum(x*math.sin(-2*math.pi*k*j/n) for j,x in enumerate(samples))] for k in range(n)]""",
    [ok(([],),[]),ok(([1],),[[1,0]]),ok(([1,1],),[[2,0],[0,0]]),ok(([1,0],),[[1,0],[1,0]]),ok(([0,0],),[[0,0],[0,0]]),ok(([1,-1],),[[0,0],[2,0]])])

add("sample_cdf", "逆 CDF 抽样", "inverse_cdf(probabilities, uniforms)",
    "Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called.",
    """if not probabilities or any(p<0 for p in probabilities) or abs(sum(probabilities)-1)>1e-9 or any(not 0<=u<1 for u in uniforms):raise ValueError('distribution')
result=[]
for u in uniforms:
    cumulative=0
    for i,p in enumerate(probabilities):
        cumulative+=p
        if u<cumulative:result.append(i);break
    else:result.append(len(probabilities)-1)
return result""",
    [ok(([.5,.5],[0,.49,.5,.99]),[0,0,1,1]),ok(([0,1],[0,.9]),[1,1]),ok(([1],[]),[]),bad(([.1,.2],[.1])),bad(([1],[1])),bad(([],[]))])

add("markov", "马尔可夫状态分布", "markov_step(distribution, transition)",
    "Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition.",
    """n=len(distribution)
if not n or len(transition)!=n or any(len(r)!=n for r in transition) or any(p<0 for r in [distribution]+transition for p in r) or any(abs(sum(r)-1)>1e-9 for r in [distribution]+transition):raise ValueError('stochastic matrix')
return [sum(distribution[i]*transition[i][j] for i in range(n)) for j in range(n)]""",
    [ok(([1,0],[[.8,.2],[.1,.9]]),[.8,.2]),ok(([.5,.5],[[0,1],[1,0]]),[.5,.5]),ok(([1],[[1]]),[1]),bad(([1],[[.5]])),bad(([],[])),bad(([1,0],[[1,0]]))])

add("conv", "一维卷积窗口", "convolve(signal, kernel, stride=1)",
    "Compute valid 1D cross-correlation (kernel is NOT reversed) using exact positive integer stride. Empty kernel or invalid stride raises ValueError. Kernel longer than signal yields [].",
    """if not kernel or type(stride) is not int or stride<=0:raise ValueError('window')
return [sum(a*b for a,b in zip(signal[i:i+len(kernel)],kernel)) for i in range(0,len(signal)-len(kernel)+1,stride)]""",
    [ok(([1,2,3],[1,1]),[3,5]),ok(([1,2,3,4],[1,-1],2),[-1,-1]),ok(([1],[1,2]),[]),ok(([],[1]),[]),bad(([1],[])),bad(([1],[1],0))])

add("pool", "池化与补齐", "max_pool(values, width)",
    "Use non-overlapping windows of exact positive integer width. Include a shorter final window. Return max per window; empty input yields []. Invalid width raises ValueError.",
    """if type(width) is not int or width<=0:raise ValueError('width')
return [max(values[i:i+width]) for i in range(0,len(values),width)]""",
    [ok(([1,3,2,4,0],2),[3,4,0]),ok(([-3,-2],2),[-2]),ok(([],2),[]),ok(([1],3),[1]),bad(([1],0)),ok(([1,2],1),[1,2])])

add("quantize", "对称整数化", "quantize(values, bits)",
    "bits must be exact int 2..8. Set bound=2**(bits-1)-1, scale=max(abs(values))/bound (or 1 for empty/all-zero input). Return {'values':[rounded x/scale clipped to -bound..bound], 'scale':scale}. Python round (ties to even) defines rounding.",
    """if type(bits) is not int or not 2<=bits<=8:raise ValueError('bits')
bound=2**(bits-1)-1;maximum=max((abs(x) for x in values),default=0);scale=maximum/bound if maximum else 1
return {'values':[max(-bound,min(bound,round(x/scale))) for x in values],'scale':scale}""",
    [ok(([-1,0,1],2),{'values':[-1,0,1],'scale':1}),ok(([-7,0,7],4),{'values':[-7,0,7],'scale':1}),ok(([0,0],8),{'values':[0,0],'scale':1}),ok(([],8),{'values':[],'scale':1}),bad(([1],1)),bad(([1],True))])

add("attention", "单头注意力", "attention(query, keys, values)",
    "query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists.",
    """if not query or not keys or len(keys)!=len(values) or any(len(k)!=len(query) for k in keys) or not values[0] or any(len(v)!=len(values[0]) for v in values):raise ValueError('shape')
scores=[sum(a*b for a,b in zip(query,k))/math.sqrt(len(query)) for k in keys];maximum=max(scores);weights=[math.exp(s-maximum) for s in scores];total=sum(weights)
return [sum(w*v[j] for w,v in zip(weights,values))/total for j in range(len(values[0]))]""",
    [ok(([0],[[1],[2]],[[2],[4]]),[3]),ok(([1],[[0]],[[3,4]]),[3,4]),ok(([0,0],[[1,0],[0,1]],[[1,0],[0,1]]),[.5,.5]),bad(([],[[1]],[[1]])),bad(([1],[[1,2]],[[1]])),bad(([1],[[1]],[]))])

add("causal_mask", "因果与窗口 Attention Mask", "causal_mask(length, window=None)",
    "Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError.",
    """if type(length) is not int or length<0 or window is not None and (type(window) is not int or window<=0):raise ValueError('shape')
return [[j<=i and (window is None or i-j<window) for j in range(length)] for i in range(length)]""",
    [ok((2,),[[True,False],[True,True]]),ok((2,1),[[True,False],[False,True]]),ok((0,),[]),ok((1,3),[[True]]),bad((-1,)),bad((2,0))])

add("positions", "Sinusoidal 位置编码", "position_encoding(position, dimensions)",
    "dimensions is exact positive even int and position is numeric >=0. Return sin(position/10000**(2*i/dimensions)) then cos of the same angle for i=0..dimensions/2-1, interleaved. Invalid configuration raises ValueError.",
    """if position<0 or type(dimensions) is not int or dimensions<=0 or dimensions%2:raise ValueError('dimensions')
result=[]
for i in range(dimensions//2):
    angle=position/10000**(2*i/dimensions);result.extend([math.sin(angle),math.cos(angle)])
return result""",
    [ok((0,2),[0,1]),ok((0,4),[0,1,0,1]),ok((1.5707963267948966,2),[1,0]),bad((1,3)),bad((-1,2)),bad((0,0))])

add("layernorm", "LayerNorm 前向", "layer_norm(values, epsilon=1e-5)",
    "For a nonempty vector compute (x-mean)/sqrt(population_variance+epsilon). epsilon must be >0. Invalid inputs raise ValueError; return a new list.",
    """if not values or epsilon<=0:raise ValueError('contract')
mean=sum(values)/len(values);variance=sum((x-mean)**2 for x in values)/len(values)
return [(x-mean)/math.sqrt(variance+epsilon) for x in values]""",
    [ok(([1,1],),[0,0]),ok(([5],),[0]),ok(([-1,1],3),[-.5,.5]),ok(([1,3],3),[-.5,.5]),bad(([],)),bad(([1],0))])

add("lora", "LoRA 增量与参数量", "lora_delta(a, b, alpha)",
    "A is nonempty output-by-rank, B is rank-by-input, both rectangular with nonempty rows. Return (alpha/rank)*A@B; alpha is finite numeric. Invalid shapes raise ValueError. No base weights are modified.",
    """if not a or not b or not a[0] or not b[0] or any(len(r)!=len(a[0]) for r in a) or any(len(r)!=len(b[0]) for r in b) or len(a[0])!=len(b):raise ValueError('shape')
return [[alpha/len(b)*sum(row[k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for row in a]""",
    [ok(([[2]],[[3]],1),[[6]]),ok(([[1,0],[0,1]],[[2,3],[4,5]],2),[[2,3],[4,5]]),ok(([[1]],[[2,3]],0),[[0,0]]),bad(([],[[1]],1)),bad(([[1,2]],[[1]],1)),ok(([[1]],[[1]],-1),[[-1]])])

add("shards", "均衡参数分片", "shard_bounds(total, workers)",
    "Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed.",
    """if type(total) is not int or type(workers) is not int or total<0 or workers<=0:raise ValueError('shape')
q,r=divmod(total,workers);start=0;result=[]
for i in range(workers):
    end=start+q+(i<r);result.append([start,end]);start=end
return result""",
    [ok((5,2),[[0,3],[3,5]]),ok((2,3),[[0,1],[1,2],[2,2]]),ok((0,2),[[0,0],[0,0]]),ok((3,1),[[0,3]]),bad((3,0)),bad((-1,2))])

add("reduce", "集体归约", "allreduce(vectors, average=False)",
    "Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking.",
    """if not vectors or any(len(v)!=len(vectors[0]) for v in vectors):raise ValueError('shape')
return [sum(column)/(len(vectors) if average else 1) for column in zip(*vectors)]""",
    [ok(([[1,2],[3,4]],),[4,6]),ok(([[1,2],[3,4]],True),[2,3]),ok(([[],[]],),[]),ok(([[1]],),[1]),bad(([],)),bad(([[1],[]],))])

add("diffusion", "前向加噪", "diffuse(clean, noise, alpha_bar)",
    "For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG.",
    """if len(clean)!=len(noise) or not 0<=alpha_bar<=1:raise ValueError('contract')
return [math.sqrt(alpha_bar)*x+math.sqrt(1-alpha_bar)*z for x,z in zip(clean,noise)]""",
    [ok(([1,2],[3,4],1),[1,2]),ok(([1,2],[3,4],0),[3,4]),ok(([2],[2],.5),[2.8284271247461903]),ok(([],[],.5),[]),bad(([1],[],.5)),bad(([1],[1],2))])

add("flow", "Rectified Flow 一步积分", "flow_step(state, velocity, delta)",
    "Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid.",
    """if len(state)!=len(velocity) or not 0<=delta<=1:raise ValueError('contract')
return [x+delta*v for x,v in zip(state,velocity)]""",
    [ok(([0,1],[2,-2],.5),[1,0]),ok(([1],[2],0),[1]),ok(([1],[2],1),[3]),ok(([],[],.1),[]),bad(([1],[],.5)),bad(([1],[1],-1))])
