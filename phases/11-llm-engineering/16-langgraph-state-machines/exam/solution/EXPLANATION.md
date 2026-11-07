# 参考实现说明

这是一套stdlib本地模拟器：课程支持显式checkpoint/thread、partial reducer、Send/fork概念；本题不运行LangGraph、Anthropic或真实工具。

## Part 1

choose_checkpoint使用完整(thread_id,from_id)，不能自动latest。错误snapshot自身是合法记录，但缺少请求选定的pending action；KeyError在正确consumer中暴露，修正选择生产者即可。fork state要deepcopy，pop_pending合法修改新分支；不能影响父state。merge_single对append拼接完整list，包含重复值；overwrite只替换自己字段。ancestry沿实际scoped parent回到root，反转为root-to-head，记录path内seen；用catalog index而非每步重扫全log。公开fork_and_trace包含catalog关系/index构造、真实本地action、fork commit和完整路径结果，不重跑早期节点。

## Part 2

load_all只按lineage index恢复完整artifact，核对实际thread/id；save以完整scoped ID判断不可变重试，parent可属于同thread的其他branch。先完整writer，再发布index，注入失败时没有悬空记录。Given atomicwriter、codec和哈希安全路径不是候选的格式或精度主核；这里只保证单writer本地调用边界，允许未index孤立artifact，不声称分布式事务或断电durability。load_all不扫描孤立artifact补记录；每个索引项指向的文件内容必须有相同thread/checkpoint身份。

## Part 3

按completion_order运行本地worker仅模拟到达，每个收到同一prestate的独立deepcopy。所有delta收齐后，先判断任一overwrite字段是否多个writer；即使值相等也按明确合同拒绝。再按workers声明序调用正确P1 single reducer。StepResult同时保存声明序updates和到达序，不把两者混合。输入state从未成为临时累加对象，emptybatch保留完整state。arrival序列必须让每个已声明worker恰好出现一次，不能仅比较名称set。

## Part 4

由已修P3产生的完整committed pair进入Given driver。候选只比较exact parent和child state，逐field生成有界operations；encode pointer segment先替换`~`成`~0`再替换`/`成`~1`。append且原list是child前缀时，逐新项发`add /field/-`，重复也保留；其他changed field按parent存在性replace/add，未变字段不发。新字段发add，append字段的旧list不再是前缀时发完整replace，不能截取伪tail。partial worker deltas不是可观察的commit。driver绑定每个实际checkpoint/parent，做JSON行/pull-through/close，不用候选重写通用异步包装。

## Part 5

Given guard检查合法scoped parent与真实cycle，sharedancestor本来合法。候选沿两个head回溯，保留完整Checkpoint，再翻转。比较共同前缀的最后位置得最近共同祖先，suffix排除交点；祖先head的suffix可空，同thread断开root的common为None。global插入序和branch标签均不能替代parent链。相同head本身就是最近共同点，两条suffix都为空；不同checkpoint即使共用branch标签仍可分歧。

## 来源与教学替代

source docs state/reducer/time-travel/Send和Exercise2–3是概念锚点；main41–42声明messages reducer、78–106建graph、147–166传旧config fork。main没有实际Send fanout实现，本题明确增加local superstep模型；completion_order不是线程性能/SDK语义证明。source run在fork后再次传earliest config而非fork后最新config，本题latest替代requestedold是概念导出的brownfield回归，不冒充原代码的同一bug。simpleappend不包含完整add_messages ID替换/RemoveMessage语义。

Checkpoint typed构造给定有限JSON/field-reducer检查；计时输入是已构造记录，计时覆盖公开fork服务与全部结果，不包含JSON字节解析/模型生成。state通过fork/commit推进，返回trace是只读证据，未实现通用Python对象递归冻结。immutable文件/index、JSON-line patch、Divergence报告均为显式本地工程扩展，不称LangGraph wire、完整数据库checkpointer或任意reducer代数。旧14/13的interrupt-marker/router次数、外部RNG/API record-replay、嵌套child resume均给定或排除，coderpad transition/topological核不复刻。

本机性能证据：完整公开fork_and_trace接收18,000个typed checkpoint，计时包含MemoryBook全关系检查/index构建、选定本地pending action、branch拷贝/reducer/commit、全部18,001祖先与完整records/字段消费。连续三慢1.765368/1.670122/1.843338秒，三快0.011500/0.011422/0.012592秒，限值0.2秒，最差双侧8.351×/15.883×，单慢最大1.843秒。输入typed构造、JSON解析和模型生成不在这个公开API计时范围，不声称SDK/生产吞吐。证据见SCOPE。
