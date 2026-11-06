from . import add, ok, bad

add("iou", "边框 IoU", "box_iou(a, b)",
    "Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection.",
    """if any(len(x)!=4 or x[2]<x[0] or x[3]<x[1] for x in (a,b)):raise ValueError('box')
intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
return intersection/union if union else 0""",
    [ok(([0,0,2,2],[0,0,2,2]),1),ok(([0,0,1,1],[1,0,2,1]),0),ok(([0,0,2,2],[1,1,3,3]),1/7),ok(([0,0,0,0],[0,0,0,0]),0),bad(([2,0,1,1],[0,0,1,1])),bad(([1],[0,0,1,1]))])

add("nms", "非极大值抑制", "nms(boxes, scores, threshold)",
    "Return kept original box indices, selecting descending score with original-index ties. Suppress candidates with IoU strictly >threshold against a kept box. Boxes are valid positive-area xyxy; reject unequal lengths or threshold outside [0,1]. Empty inputs return [].",
    """if len(boxes)!=len(scores) or not 0<=threshold<=1:raise ValueError('contract')
kept=[]
for i in sorted(range(len(boxes)),key=lambda i:(-scores[i],i)):
    keep=True
    for j in kept:
        a,b=boxes[i],boxes[j];inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
        if inter/union>threshold:keep=False;break
    if keep:kept.append(i)
return kept""",
    [ok(([[0,0,1,1],[0,0,1,1]],[.5,.9],.5),[1]),ok(([[0,0,1,1],[2,2,3,3]],[.5,.5],0),[0,1]),ok(([],[],.5),[]),ok(([[0,0,1,1],[0,0,1,1]],[1,1],1),[0,1]),bad(([],[1],.5)),bad(([],[],2))])

add("dice", "分割 Dice", "dice(predicted, expected)",
    "Require equal-length exact-bool masks. Dice=2*intersection/(predicted positives+expected positives); if both have no positives return 1. Invalid masks raise ValueError.",
    """if len(predicted)!=len(expected) or any(type(x) is not bool for x in predicted+expected):raise ValueError('mask')
den=sum(predicted)+sum(expected)
return 2*sum(a and b for a,b in zip(predicted,expected))/den if den else 1""",
    [ok(([True,False],[True,False]),1),ok(([True,False],[False,True]),0),ok(([True,True],[True,False]),2/3),ok(([],[]),1),bad(([True],[])),bad(([1],[True]))])

add("patches", "图像 Patch 切分", "patchify(image, patch_size)",
    "image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError.",
    """if type(patch_size) is not int or patch_size<=0 or not image or not image[0] or any(len(r)!=len(image[0]) for r in image) or len(image)%patch_size or len(image[0])%patch_size:raise ValueError('patch shape')
p=patch_size
return [[image[r+i][c+j] for i in range(p) for j in range(p)] for r in range(0,len(image),p) for c in range(0,len(image[0]),p)]""",
    [ok(([[1,2],[3,4]],2),[[1,2,3,4]]),ok(([[1,2],[3,4]],1),[[1],[2],[3],[4]]),ok(([[1,2,3,4],[5,6,7,8]],2),[[1,2,5,6],[3,4,7,8]]),bad(([],1)),bad(([[1,2]],2)),bad(([[1]],0))])

add("frame_sample", "视频均匀采样", "sample_frames(length, count)",
    "Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError.",
    """if type(length) is not int or type(count) is not int or not 0<=count<=length:raise ValueError('frames')
if count==0:return []
if count==1:return [0]
return [i*(length-1)//(count-1) for i in range(count)]""",
    [ok((10,3),[0,4,9]),ok((5,1),[0]),ok((0,0),[]),ok((3,3),[0,1,2]),bad((2,3)),bad((-1,0))])

add("rle", "掩码游程编码", "rle_encode(values)",
    "Return consecutive [value,count] runs for a list of exact booleans. Empty list returns []; reject non-bool elements with ValueError. Preserve runs and original order.",
    """if any(type(x) is not bool for x in values):raise ValueError('mask')
runs=[]
for x in values:
    if runs and runs[-1][0]==x:runs[-1][1]+=1
    else:runs.append([x,1])
return runs""",
    [ok(([False,False,True],),[[False,2],[True,1]]),ok(([],),[]),ok(([True],),[[True,1]]),ok(([True,False,True],),[[True,1],[False,1],[True,1]]),bad(([1],)),ok(([False]*4,),[[False,4]])])

add("heatmap", "热图坐标解码", "heatmap_peak(heatmap)",
    "Return [row,column] of the maximum in a nonempty rectangular 2D numeric heatmap. Ties choose earliest row-major cell. Empty or ragged heatmaps raise ValueError.",
    """if not heatmap or not heatmap[0] or any(len(r)!=len(heatmap[0]) for r in heatmap):raise ValueError('heatmap')
return list(max(((i,j) for i in range(len(heatmap)) for j in range(len(heatmap[0]))),key=lambda p:heatmap[p[0]][p[1]]))""",
    [ok(([[0,1],[3,2]],),[1,0]),ok(([[1,1]],),[0,0]),ok(([[-2,-1]],),[0,1]),ok(([[0]],),[0,0]),bad(([],)),bad(([[1],[1,2]],))])

add("depth", "深度估计相对误差", "depth_error(predicted, expected)",
    "Lists have equal lengths. Evaluate only positions where expected>0; return mean(abs(pred-true)/true). No valid ground truth or mismatched lengths raises ValueError.",
    """if len(predicted)!=len(expected):raise ValueError('shape')
errors=[abs(p-t)/t for p,t in zip(predicted,expected) if t>0]
if not errors:raise ValueError('no valid depth')
return sum(errors)/len(errors)""",
    [ok(([2,4],[1,4]),.5),ok(([9,2],[0,2]),0),ok(([1],[2]),.5),bad(([3],[-1])),bad(([],[])),bad(([1],[]))])

add("ctc", "CTC 贪心解码", "ctc_decode(tokens, blank=0)",
    "Collapse adjacent repeated tokens first, then remove blank tokens. A blank separates repetitions, so [1,0,1] decodes to [1,1]. Tokens and blank are provided scalar ids; empty input returns [].",
    """result=[];previous=object()
for token in tokens:
    if token!=previous and token!=blank:result.append(token)
    previous=token
return result""",
    [ok(([1,1,0,1,2,2],),[1,1,2]),ok(([0,0],),[]),ok(([],),[]),ok(([2,2,2],),[2]),ok(([1,9,1],9),[1,1]),ok(([1,2,1],),[1,2,1])])

add("edit_distance", "编辑距离", "edit_distance(reference, hypothesis)",
    "Return Levenshtein distance between two token lists, using unit insertion/deletion/substitution costs. Inputs are lists of scalar tokens. Empty sequences are valid; no transposition operation.",
    """previous=list(range(len(hypothesis)+1))
for i,a in enumerate(reference,1):
    current=[i]
    for j,b in enumerate(hypothesis,1):current.append(min(previous[j]+1,current[-1]+1,previous[j-1]+(a!=b)))
    previous=current
return previous[-1]""",
    [ok((['a','b'],['a','c']),1),ok(([],['a']),1),ok((['a'],[]),1),ok(([],[]),0),ok((['a','b'],['b','a']),2),ok((['a'],['a']),0)])

add("frames", "音频分帧", "audio_frames(samples, width, hop)",
    "width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError.",
    """if any(type(x) is not int or x<=0 for x in (width,hop)):raise ValueError('window')
return [samples[i:i+width] for i in range(0,len(samples)-width+1,hop)]""",
    [ok(([1,2,3,4,5],3,2),[[1,2,3],[3,4,5]]),ok(([1,2],3,1),[]),ok(([],1,1),[]),ok(([1,2,3],1,2),[[1],[3]]),bad(([1],0,1)),bad(([1],1,True))])

add("rms", "能量 VAD 边界", "energy_vad(chunks, threshold)",
    "For each numeric audio chunk, return RMS>=threshold; an empty chunk has RMS 0. threshold must be >=0 or raise ValueError. No model or microphone access.",
    """if threshold<0:raise ValueError('threshold')
return [math.sqrt(sum(x*x for x in c)/len(c))>=threshold if c else 0>=threshold for c in chunks]""",
    [ok(([[0,0],[1,-1]],.5),[False,True]),ok(([[]],.1),[False]),ok(([],1),[]),ok(([[1]],1),[True]),ok(([[]],0),[True]),bad(([[1]],-1))])

add("mel", "频率与 Mel 转换", "hz_to_mel(frequencies)",
    "Return 2595*log10(1+f/700) per nonnegative frequency. Any negative frequency raises ValueError; empty input yields [].",
    """if any(f<0 for f in frequencies):raise ValueError('frequency')
return [2595*math.log10(1+f/700) for f in frequencies]""",
    [ok(([0],),[0]),ok(([700],),[781.1728387480317]),ok(([],),[]),ok(([0,0],),[0,0]),bad(([-1],)),ok(([1000],),[999.9855371396244])])

add("codebook", "向量量化最近码字", "quantize_codebook(vectors, codebook)",
    "Codebook must be a nonempty set of same-dimensional numeric rows. All vectors must have that dimension. Return nearest codeword index per vector by squared Euclidean distance, ties to lower index. Invalid dimensions or empty codebook raises ValueError.",
    """if not codebook or any(len(c)!=len(codebook[0]) for c in codebook) or any(len(v)!=len(codebook[0]) for v in vectors):raise ValueError('codebook')
return [min(range(len(codebook)),key=lambda i:sum((a-b)**2 for a,b in zip(v,codebook[i]))) for v in vectors]""",
    [ok(([[1],[9]],[[0],[10]]),[0,1]),ok(([[5]],[[0],[10]]),[0]),ok(([],[[1]]),[]),bad(([[1]],[])),bad(([[1,2]],[[1]])),ok(([[0,0]],[[0,0],[1,1]]),[0])])

add("watermark", "水印比特一致率", "bit_accuracy(expected, observed)",
    "Require equal-length nonempty lists of exact integer bits 0 or 1 (bool invalid). Return fraction matching. Invalid lists raise ValueError. This bit check does not establish provenance authenticity.",
    """if not expected or len(expected)!=len(observed) or any(type(x) is not int or x not in (0,1) for x in expected+observed):raise ValueError('bits')
return sum(a==b for a,b in zip(expected,observed))/len(expected)""",
    [ok(([0,1],[0,1]),1),ok(([0,1],[1,1]),.5),ok(([0],[1]),0),bad(([],[])),bad(([True],[1])),bad(([0],[0,1]))])
