<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="serving-engine-internals--pagedattention-continuous-batching-chunked-prefill"></a>

# 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill

> 现代发动机输送 rests 三个复合默认, 一个也没有。 始终在使用 。 Continuous batching 在解码迭代之间的活动批次中输入新的请求 。 Chunked prefill 切片长 prompts 解码 tokens 永远不饿,打开三张 Llama 3.3 70B FP8对一架H100 SXM5推2,200-2,400吨/秒,同时128吨——约高于25% vLLM自己的默认 3 -4x天真 PyTorch 循环。 此课读取调度器 attention 内核 vLLM 三种技术的参考引擎,在您可以绘制的级别上,最后是玩具连续分批器 `code/main.py` 时间表 prefill 解码 vLLM does.

**类型:** 学习
**语言:** Python (斯迪利布,玩具) continuous batching scheduler)
**先修要求:** 阶段17 · 01 (Model Serving阶段11(LLM Engineering)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 将打印的注意解释为 KV cache 分配符:块块、块表,以及为什么在生产负荷时碎片仍保持在4%以下。
- Diagram continuous batching 循环层:完成的序列是如何离开批次和新的组合,不排水。
- Describe chunked prefill 在一个句子和名称中,它保护的是哪个潜伏度(内含:它是TTFT尾巴,不是表示输送量)。
- 检查a vLLM feature 组合到您版本的兼容性矩阵中,然后立即启用每一次优化。

<a id="the-problem"></a>

## 问题

这么天真 PyTorch 一次服务循环运行一个请求: 表示 , prefill,解码到 EOS ,返回。在一个用户中,这个功能可以工作。在100个用户中,它是一个病人的排队。很明显的固定方法——静态分批处理——将每个请求都贴到最长 prompt 将每个解码都插入到最长久的预期输出中, 并让整批数据按最慢的顺序拖动。 您支付您从未使用的粘贴费, 快速请求等待慢的 。

vLLM 立即解决三个问题。 Paged 停止注意 KV cache 食用60-80%的 GPU 记忆中经典的连带分配方式。 Continuous batching 要求加入,然后在每组解码迭代之间离开, 所以批次总是充满了真正的工作。 Chunked prefill 换个32公里token prompt 至~512token 切开中间的解码,那么长 prompt 不冻结每个解码 token 在 GPU.

2026 年的默认生产是全部三个。 您需要了解每个文件都做什么, 因为失败模式都在调度器上, 而不是模型上 。

<a id="the-concept"></a>

## 概念

<a id="pagedattention-as-a-virtual-memory-system"></a>

### 以虚拟存储系统发送

一个 KV cache 是 `num_layers × 2 × num_heads × head_dim × seq_len × bytes_per_element` 用于 Llama 3.3 70B, 时值8192 tokens,大约是BF16中每顺序1.25GB。如果每次请求都预留8192个空位,但平均请求只使用 1500 tokens,您浪费了您保留的大约82%的 HBM。典型的批量支付这种废物。

页面搜索从OS虚拟内存中借用了这个想法 。 KV cache 并非按顺序毗连。它被分配到固定大小区块(默认 16) tokens。每个序列都有块表,用于绘制其逻辑 token 位置为物理区块 ID。 当一个序列经过其分配区块后, 将添加一个区块。 当它完成时, 其区块将返回到池中 。

分裂从60-80%(经典)下降到4%以下(预告使用率)。您不启用带有国旗的页面跟踪 — — 这是唯一的分隔符 vLLM 舰艇。 按钮是 `--gpu-memory-utilization` (默认0.9),该表示 vLLM 装载后为 KV 区块保留多少 HBM weights 和激活。

<a id="continuous-batching-at-the-iteration-level"></a>

### Continuous batching 循环水平的

旧的 "dynamic batching" 等待一个窗口(10毫秒)填满一批,然后运行 prefill + 解码 + 解码 + 解码 + 直到每个序列完成。快速序列提前离开, 闲置于空闲状态中 GPU 慢速的都结束了

Continuous batching 调用运行序列 `RUNNING` 列表中。在每次迭代时:

1. 任何序列 `RUNNING` 击中了EOS或最大_标记已被删除 。
2. 排程器查看等待队列。 如果有空 KV 区块, 它会接受新的序列( NAME OF TRANSLATORS) (NEW)prefill 或续会)
3. 该 forward pass 运行在现在的 `RUNNING`,释放一个新的 token 每一个序列。

该 batch size 其输出位置不同, 序列共享一个连接到前方 。 vLLM 这叫" `V1 scheduler`。关键变量:排程器按每次解码重复运行一次,而不是按每次请求运行一次。

<a id="chunked-prefill-protects-ttft-tail"></a>

### Chunked prefill 保护 TTFT 尾巴

Prefill 计算。token prompt 在 Llama 3.3 70B 纯度~800毫秒 prefill 在一个H100。 prefill 运行, 解码 tokens 批量中的其他序列都等待。 在服务循环中, 第一种-token 长长的延迟时间 prompt 变成 inter-token latency 给其他几十个用户的点击

Chunked prefill splits prefill 默认为 512 块 tokens和每个块的排程作为单位。在块间,排程器可以提前一个解码序列 token。你交换一个小绝对值 prefill 低得多的解码时间紧张时, 延迟点会击中( 每块几毫秒) 。 在已公布的基准中, 混合负荷下的 P99 国际交易日志从~ 50毫秒下降到~ 15毫秒 。

<a id="the-three-defaults-interact"></a>

### 三个默认的相互作用

三个都 features 使用定位系统给调度器一个精细的 KV 资源进行交易。 Continuous batching 需要精细的配置资源 所以承认新的序列 并不迫使全球进行重组 Chunked prefill 是排程器在同一位置上做出的决定 `RUNNING` 列表中——它是一个额外的排程政策,而不是一个单独的系统。

你不需要知道每面旗帜。你需要知道排程器最优化的是什么: goodput 依据科索沃选民集团预算 chunked prefill slicing.

<a id="check-the-compatibility-matrix"></a>

### 检查兼容矩阵

检查每个 feature 组合对准您精确的兼容矩阵 vLLM 版本,然后同时启用所有这些版本, 因为什么构成释放之间的变化。 v. 1. 1.8 中 feature 矩阵标记 speculative decoding 符合 chunked prefill 和 prefix caching,而投机解码页面列出了两种已知的不兼容性: pipeline parallelism 2026年的默认违约往往是EAGLE-3(EAGLE-3),而2026年的假设是,在2026年的预设中,使用该方法本身就出现了一种“模拟投机”法。`"method": "eagle3"`),第17阶段:05年。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- Llama 3.3 70B FP8, H100 SXM5,128同时,三枚在2 200-2 400吨/秒。
- 同一模型, 默认 vLLM (否 chunked prefill:~1 800吨/秒。
- 同样的模型,天真 PyTorch 前进循环:~ 600 吨/秒。
- 生产负荷中被标注为“目标”的KV碎裂废物: < 4%。
- 混合负荷下的P99国际交易日志:~15毫秒 chunked prefill~50毫秒没有

<a id="what-the-scheduler-looks-like"></a>

### 排程器长什么样

```
while True:
    finished = [s for s in RUNNING if s.is_done()]
    for s in finished: release_blocks(s); RUNNING.remove(s)

    while WAITING and have_free_blocks_for(WAITING[0]):
        s = WAITING.pop(0)
        allocate_initial_blocks(s)
        RUNNING.append(s)

    # schedule prefill chunks + decode in one batch
    batch = []
    for s in RUNNING:
        if s.in_prefill:
            batch.append(next_prefill_chunk(s))   # e.g. 512 tokens
        else:
            batch.append(decode_one_token(s))     # 1 token

    run_forward(batch)                            # one fused GPU call
```

`code/main.py` 是否正中此链条 Python 装假的 token 计数并伪造前身。运行它可以显示 chunked prefill 保持解码序列在很长一段时间内有效 prefill.

```figure
tensor-parallel
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟a vLLM- 具有可切换性的方式排程器 features运行它看:

- `NAIVE` 模式:一次一次请求,不批量。
- `STATIC` 模式:垫和等待,典型的批量。
- `CONTINUOUS` 模式:迭代级别接收和释放。
- `CONTINUOUS + CHUNKED` mode: prefill 切片与解码交错

产出显示总输送量( 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位: 单位:tokens e. 与国际交易日志的运行有关的软件。 `CONTINUOUS + CHUNKED` 混杂交通应该由行来主宰

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-vllm-scheduler-reader.md`。给定服务配置(batch size, KV 内存利用率, chunked prefill 大小, 投机配置), 它产生一个调度器诊断, 列出三个默认值中哪一个是瓶颈, 以及调制什么 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`比较 `STATIC` 以 `CONTINUOUS` 工作量既长又短,需求也复杂。 prefill 效率,解码效率,或 tail latency?
2. 修改玩具调度程序以添加 `--max-num-batched-tokens`。H100运行的正确值是什么? Llama 3.3 70B FP8? (提示:它是KV区块大小和自由区块数的函数,而不是原始的 HBM 。)
3. 重读 vLLM v0.18.0 发布音符。 哪些旗帜组合是相互排斥的? 请列出它们 。
4. 计算 KV cache 废物的碎裂 trace 请求数1 000次,平均产出1 500次 tokens,标准600 tokens,在(a)下,每项请求的连续分配额最多为8192个,(b) 标注16-token blocks.
5. 在一个段落中解释为什么 chunked prefill 帮助 P99 国际交易日志, 但不是孤立的吞吐。 吞吐量从实践中从哪里获得?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 分页注意力 | "KV戏法" | 固定大小块分配器 KV cache;碎裂 < 4% |
| 块表 | "页表" | 从逻辑中逐顺序映射 token 位置为物理 KV 块 |
| Continuous batching | "dynamic batching,但右侧" | 每一次解码重复都作出承认/释放决定 |
| Chunked prefill | "prefill splitting" | 断开长 prefill 改为 512token 切片间断,并解码 |
| TTFT | "first token 时间" | Prefill +队列+网络;以 prefill 长 prompts |
| ITL | "inter-token latency" | 连续解码间隔时间 tokens; 由 batch size |
| Goodput | "与SLO相遇的通量" | Tokens/秒,每个请求仍然达到TTFT和国际交易日志的目标 |
| V1 排程器 | "新订时器" | vLLM'2026 排程器; 运行 continuous batching 与 chunked prefill |
| `--gpu-memory-utilization` | "记忆把手" | 用于 KV 区块的 HBM 分数 weights 和激活 |

<a id="further-reading"></a>

## 进一步阅读

- [vLLM 文档 - Speculative Decoding](https://docs.vllm.ai/en/latest/features/spec_decode/) - 官方来源在块prefill 和投机-解码兼容性。
- [vLLM 发行说明(荷兰盾)](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/index.html) - 2026年发布 cadense 和版本特定的行为。
- [vLLM 博客-页面浏览](https://blog.vllm.ai/2023/06/20/vllm.html) 原始的写法 仍然定义如何思考分配器。
- [打印纸(arXiv:2309.06180)](https://arxiv.org/abs/2309.06180) 分散分析和排期设计。
- [阿列克萨·戈尔迪奇——内部 vLLM](https://www.aleksagordic.com/blog/vllm) - 详细的V1排程器,用火焰图进行穿透。
