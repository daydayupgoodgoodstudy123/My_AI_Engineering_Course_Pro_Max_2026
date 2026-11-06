# 测验 · KV Cache、Flash Attention 与 Inference 优化（KV Cache, Flash Attention & Inference Optimization）

> **阶段 07 · Transformers 深入 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练与推理的瓶颈不同 | 训练并行、受算力（FLOP）限制；推理逐 token 串行、受显存带宽限制，需要不同的优化手段 |
| 2 | KV cache | 因果掩码下前缀 token 的 K、V 一经算出就不再改变；缓存它们，新 token 只需一个 query 对缓存做 attention，每步从 O(N²) 降到 O(N) |
| 3 | KV cache 大小 | `2 × N × 层数 × KV 头数 × d_head × 字节数`；Llama 3 70B（80 层、8 个 KV 头、d_head=128、fp16）每 token 每层 4 KB，32K 上下文约 10.7 GB |
| 4 | GQA / MLA | 让多个 query 头共享 KV 头（GQA），或把 KV 压缩成低维潜向量（MLA），是长上下文推理可负担的关键 |
| 5 | FlashAttention | 分块（tiling）计算，N×N 分数矩阵从不写回 HBM，softmax 和矩阵乘都在 SRAM 中完成；显存从 O(N²) 降到 O(N)，结果是**精确**的 |
| 6 | Online softmax | 跨块维护 `(max, sum)`，新最大值出现时用 `exp(m_old − m_new)` 重新缩放旧的和与输出，最终归一化与一次性 softmax 数学上相同 |
| 7 | 硬件层级 | H100 上 HBM 约 3 TB/s，SRAM 约 30 TB/s；每次 HBM 往返都比片上计算慢一个数量级 |
| 8 | 服务端优化 | continuous batching（随时换入换出请求）、PagedAttention（16 token 块 + 页表管理 KV）、prefix caching（共享前缀复用 KV） |
| 9 | Speculative decoding | 草稿模型提议多个 token，大模型一次并行验证；EAGLE 2 / Medusa 等集成草稿头可得 2–3× 加速 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现 KV-cached 解码，并验证与"无缓存、每步重算整个前缀"的输出完全一致，同时统计两者的投影次数与 attention 次数
- [ ] 实现 `tiled_softmax_dot`（online softmax），对 tile = 1、2、4、8、32 验证与标准 attention 的误差在 1e-15 量级
- [ ] 能手算任意模型在给定上下文长度、batch、dtype 下的 KV cache 大小，并据此估算一张卡能并发多少请求
- [ ] 能解释 MHA → GQA → MLA 对 KV cache 的影响，并给出压缩倍数
- [ ] 能说清 FlashAttention 为什么"FLOPs 没减少却更快"，以及它为什么是精确而不是近似算法
- [ ] 能为一个部署场景选出服务框架、attention 实现、KV dtype、是否开启 prefix caching 与 speculative decoding

---

## 二、基础自测（选择题）

**Q1.** 讲义说"训练是并行且受算力限制的，推理是串行且受显存带宽限制的"。decode 阶段受显存带宽限制的主要原因是：

- A. decode 阶段的矩阵乘法比训练更复杂
- B. 每一步只为 1 个（或少数几个）新 token 做计算，却要把全部权重和 KV cache 从 HBM 读一遍，算术强度很低
- C. decode 阶段不能使用 GPU
- D. decode 阶段要做反向传播

**Q2.** Llama 3 70B：80 层、GQA 8 个 KV 头、`d_head = 128`、fp16。单个请求 32K 上下文的 KV cache 约为：

- A. 512 MB
- B. 约 10.7 GB
- C. 约 86 GB
- D. 约 1.3 TB

**Q3.** 同样是 Llama 3 70B 的层数和 `d_head`，如果不用 GQA，而是 64 个 KV 头的标准 MHA，KV cache 会变为 GQA 的：

- A. 1/8
- B. 2 倍
- C. 8 倍
- D. 64 倍

**Q4.** 关于 FlashAttention，下列说法**正确**的是：

- A. 它是一种近似 attention，用精度换速度
- B. 它通过减少浮点运算次数来加速
- C. 它把计算分块放在 SRAM 中完成，避免把 N×N 的分数矩阵写回 HBM，减少的是显存读写；结果在数学上与标准 attention 相同
- D. 它只能用于推理，不能用于训练

**Q5.** 在 online softmax 中，处理到新的一块分数后最大值从 `m_old` 变为 `m_new`。此时对之前累计的和 `s` 与输出 `out` 应该：

- A. 不做任何处理，直接加上新块的贡献
- B. 都乘以 `exp(m_old − m_new)` 后再加上新块的贡献
- C. 都乘以 `exp(m_new − m_old)` 后再加上新块的贡献
- D. 清零后重新从第一块开始计算

**Q6.** Continuous batching 相比传统静态批处理的主要改进是：

- A. 把所有请求合并成一个超长序列
- B. 某个序列一结束就立刻把新请求换入 batch，而不是等整批中最慢的序列结束
- C. 把 batch size 固定为 1，降低延迟
- D. 用 CPU 替代 GPU 处理短请求

**Q7.** vLLM 的 PagedAttention 解决的核心问题是：

- A. attention 的计算复杂度太高
- B. KV cache 若按最大长度连续预分配会产生大量碎片和浪费；按固定大小块分配并用页表映射后，可以按需分配、在并行采样/前缀复用时共享块
- C. 模型权重太大放不进显存
- D. tokenizer 速度太慢

**Q8.** 下面哪种场景**最**能从 prefix caching 中获益？

- A. 每个请求都是完全不同的随机短文本
- B. 一个 agent 应用，每次调用都带着相同的长 system prompt 和工具说明
- C. 只运行一次的离线批量翻译，每段文本互不相同
- D. 模型训练阶段

---

## 三、动手 / 代码题

**Q9.** 运行 `code/main.py` 得到：

```text
naive attention ops:  55  (O(N^2) = 55)
cached attention ops: 55  (O(N) with per-step cost, unchanged)
```

讲义 Build It 第 3 步却说"Naive: O(N²) = 5050. Cached: O(N) = 100"。(1) 阅读下面的 `decode_naive`，解释为什么代码里两者的计数相同。(2) 写一个**真正不使用缓存**的解码器（每一步都把整个前缀重新做 K/V 投影，并重算所有前缀位置的 attention），分别统计"投影次数"和"attention 点积次数"，与缓存版对比。

```python
def decode_naive(all_K, all_V, all_queries):
    outputs = []
    ops = 0
    for t, q in enumerate(all_queries):
        Ks = all_K[:t + 1]
        Vs = all_V[:t + 1]
        out = attention_full(q, Ks, Vs)
        ops += t + 1
        outputs.append(out)
    return outputs, ops
```

**Q10.** 阅读 `tiled_softmax_dot` 的核心循环：

```python
    for start in range(0, len(Ks), tile):
        k_block = Ks[start:start + tile]
        v_block = Vs[start:start + tile]
        scores = [dot(q, k) * scale for k in k_block]
        new_m = max(m, *scores)
        if m == float("-inf"):
            exp_old = 0.0
        else:
            exp_old = math.exp(m - new_m)
        exp_new = [math.exp(sc - new_m) for sc in scores]
        s = s * exp_old + sum(exp_new)
        for j in range(d_head):
            out[j] = out[j] * exp_old + sum(e * v[j] for e, v in zip(exp_new, v_block))
        m = new_m
    return [o / s for o in out]
```

(1) 为什么第一块要特判 `m == float("-inf")`？如果去掉特判直接写 `math.exp(m - new_m)` 会怎样？(2) 如果忘了对 `out` 乘 `exp_old`（只对 `s` 乘），结果会错在哪里？(3) 在带因果掩码的场景中，如果某一整块分数都是 `-inf`（全部被屏蔽）且这是第一块，这段代码会出什么问题？

**Q11.** 讲义的 KV cache 示例写道："7B 模型，32 层、32 个头、`d_head=128`、fp16：每 token 每层 = 2 × 128 × 2 = 512 bytes；每 token（32 层）= 16 KB；32K 上下文 = 512 MB"。(1) 用 `kv_cache_bytes` 的公式重新计算，指出讲义算错的地方。(2) 对 Llama-3-8B（32 层、8 个 KV 头、`d_head=128`），如果给 KV cache 留 20 GB 显存，每个请求 8K 上下文，fp16 下最多能并发多少个请求？换成 fp8 KV cache 呢？

---

## 四、面试高频题

**Q12.**（基础必考）什么是 KV cache？为什么可以缓存 K、V 而不缓存 Q？请写出 KV cache 显存公式，并区分 prefill 与 decode 两个阶段。

**Q13.**（原理深挖）讲讲 FlashAttention 的原理。它的 FLOPs 并没有减少（反向时还会重算），为什么反而更快？为什么说它是精确的？

**Q14.**（原理深挖）MHA、MQA、GQA、MLA 在 KV cache 上有什么区别？各自的代价是什么？

**Q15.**（工程实践）vLLM 为什么比"HF `generate()` + 一个 for 循环"吞吐高很多？请说出至少三项关键技术及其作用。

**Q16.**（场景设计）用 4 张 A100-80GB 部署 Llama-3-70B（bf16），要求支持 32K 上下文、峰值约 50 个并发会话。请做显存预算，并给出可行的配置方案。

**Q17.**（追问型）为什么 decode 阶段增大 batch size 几乎"免费"提升吞吐？这个"免费"什么时候会失效？

---

## 五、参考答案与解析

### Q1 — 答案：B

decode 每步只处理一个新 token：每层的矩阵乘本质上是"向量 × 矩阵"，计算量很小，但为了算这一点点，必须把整层权重以及该序列的全部 KV cache 从 HBM 读进来。每字节数据只做极少的运算（算术强度低），GPU 的计算单元大部分时间在等数据。训练则一次处理大量 token，矩阵乘的算术强度高，受算力限制。

### Q2 — 答案：B

`2（K 和 V）× 32768 × 80 × 8 × 128 × 2 字节 = 10,737,418,240 字节 ≈ 10.7 GB`（讲义写约 10.4 GB，代码表格打印 10.74 GB）。A 是讲义 7B 示例中把"每个头"误当成"每层"后得到的数字；C 是 64 头 MHA 的结果（见 Q3）；D 是 671B 模型的 fp16 权重大小。

### Q3 — 答案：C

KV cache 与 KV 头数成正比：64 / 8 = 8 倍，32K 上下文约 86 GB——单卡根本放不下。讲义说"MHA with 64 heads would be 32 GB"，按同一公式算应为约 86 GB（这里以公式为准）。这正是讲义"GQA is the KV-cache win"的含义。

### Q4 — 答案：C

FlashAttention 是 IO 感知（IO-aware）的**精确**算法：分块把 Q、K、V 载入 SRAM，在片上完成分数计算、online softmax 与加权求和，只把最终输出写回 HBM。它减少的是 HBM 读写，而不是 FLOPs（B 错）；结果与标准 attention 数学上相同，只有浮点运算顺序带来的微小差异（A 错）。FlashAttention 1–3 都支持训练（D 错）；讲义提到的是 Flash 4 在发布时仅支持前向。

### Q5 — 答案：B

此前累计的每一项都是 `exp(score − m_old)`，要把它们统一换算到新的基准 `m_new` 上：`exp(score − m_old) × exp(m_old − m_new) = exp(score − m_new)`。因为 `m_new ≥ m_old`，这个因子 ≤ 1，不会溢出。`s` 和 `out` 都是这些指数项的（加权）和，所以都要乘同一个因子。C 的因子 ≥ 1，方向反了；D 失去了分块的意义。

### Q6 — 答案：B

传统静态批处理要等整批里最长的序列生成完才能开始下一批，先结束的短序列占着位置空转。continuous batching（Orca 首创，vLLM、TensorRT-LLM、SGLang 都已采用）在每个解码步都可以把已完成的序列换出、把新请求换入，讲义给出的量级是典型聊天负载下 5–10× 的吞吐提升。

### Q7 — 答案：B

请求的最终长度事先未知，若按最大长度连续预分配 KV cache，会出现大量内部碎片和预留浪费。PagedAttention 像操作系统的虚拟内存一样：KV cache 按 16 个 token 一块分配，用页表把逻辑位置映射到物理块，按需分配、用完归还；多个采样分支或共享前缀的请求还能共享同一批物理块。讲义给出的量级是比朴素连续分配约 4× 的吞吐提升。

### Q8 — 答案：B

prefix caching 复用的是**跨请求共享的前缀**的 KV。agent 每次调用都重复相同的 system prompt 和工具说明，这部分 KV 只需计算一次。讲义：对带重复工具提示的 agent 负载，prefix caching 常常带来 5× 吞吐提升；配套 skill 也要求有重复 system prompt 的 agent 部署必须开启它。A、C 没有共享前缀；D 与推理缓存无关。

### Q9 — 参考答案

(1) 代码里的 `decode_naive` 并没有"重算"任何东西：它直接从预先算好的 `all_K`、`all_V` 中切片，并且每一步只为**当前这个** query 做一次 attention——这本身就是 KV cache 的做法（缓存 = 预先存好的 `all_K/all_V`）。所以两者每步都做 `t + 1` 次点积，总数都是 `1 + 2 + … + 10 = 55`。代码打印的注释也承认了这一点："naive has same per-step cost; saving comes from not REcomputing earlier hidden states"。讲义说的 5050 vs 100 是 N = 100 时的设想，与代码（N = 10、两者相同）不一致。

(2) 真正不用缓存的解码器（复用 `code/main.py` 的 `dot` 与 `attention_full`）：

```python
def project(x, W):                      # x @ W，W 为 d × d
    return [dot(x, [row[j] for row in W]) for j in range(len(W[0]))]

def decode_no_cache(X, Wq, Wk, Wv):
    """每一步都把整个前缀重新跑一遍：重算所有 K/V，并重算所有位置的 attention。"""
    proj_ops = attn_ops = 0
    outputs = []
    for t in range(len(X)):
        prefix = X[:t + 1]
        Q = [project(x, Wq) for x in prefix]
        K = [project(x, Wk) for x in prefix]
        V = [project(x, Wv) for x in prefix]
        proj_ops += t + 1
        for i in range(t + 1):           # 因果：位置 i 只看 0..i
            out = attention_full(Q[i], K[:i + 1], V[:i + 1])
            attn_ops += i + 1
        outputs.append(out)              # 只有最后一个位置的输出是"新的"
    return outputs, proj_ops, attn_ops

def decode_with_cache(X, Wq, Wk, Wv):
    Kc, Vc, outputs = [], [], []
    proj_ops = attn_ops = 0
    for x in X:
        q, k, v = project(x, Wq), project(x, Wk), project(x, Wv)
        Kc.append(k); Vc.append(v)
        proj_ops += 1
        outputs.append(attention_full(q, Kc, Vc))
        attn_ops += len(Kc)
    return outputs, proj_ops, attn_ops
```

在 N = 10、d = 8 的随机数据上运行（已验证，两者输出最大差为 0.0）：

| 版本 | 投影次数 | attention 点积次数 | 渐近复杂度（生成 N 个 token） |
|------|---------|-------------------|---------------------------|
| 无缓存 | 55 = N(N+1)/2 | 220 = N(N+1)(N+2)/6 | 投影 O(N²)，attention O(N³) |
| 有缓存 | 10 = N | 55 = N(N+1)/2 | 投影 O(N)，attention O(N²) |

也就是讲义说的"每个生成步从 O(N²) 降到 O(N)"：无缓存时第 t 步要做 O(t²) 的 attention，有缓存时只做 O(t)。在真实模型里，"投影"还包括每层的 FFN 等全部计算，节省更加可观。

### Q10 — 参考答案

(1) 初始 `m = -inf`。如果直接算 `math.exp(m - new_m)`，在 `new_m` 有限时是 `exp(-inf) = 0.0`，其实也没问题；但特判让意图更清楚（"之前没有任何累计"），并且防住了 `new_m` 也是 `-inf` 的情况（见第 3 问）。此时 `s` 和 `out` 都是 0，乘以 0 等价于"从新块开始"。

(2) `out` 中累计的是 `Σ exp(score − m_old) · v`，基准仍是旧最大值；而 `s` 已经换算到新基准。最后 `out / s` 时分子分母的基准不一致：旧块的贡献会被放大 `exp(m_new − m_old)` 倍，权重不再正确（相当于给早先的 token 分配了过多注意力）。只有当最大值从未改变时结果才碰巧正确，所以这种 bug 在某些输入上测不出来，非常隐蔽。

(3) 若第一块全为 `-inf`：`new_m = max(-inf, -inf, …) = -inf`，`exp_new = [math.exp(-inf - (-inf))] = [math.exp(nan)] = [nan]`，`s` 和 `out` 都变成 NaN，并一直传染到结果。（已验证 `math.exp(float('-inf') - float('-inf'))` 得到 `nan`。）真实的 FlashAttention kernel 会对这种情况做专门处理：因果掩码下整块都在对角线上方的块直接**跳过**不计算（这也是 causal 模式能省一半计算的原因），并对全屏蔽行做保护。修复思路：`if new_m == float("-inf"): continue`。

### Q11 — 参考答案

(1) 公式：`2 × N × 层数 × KV 头数 × d_head × 字节数`。7B（MHA，32 个 KV 头）：

- 每 token 每层：`2 × 32 × 128 × 2 = 16,384 字节 = 16 KB`（讲义的 512 字节是**单个头**的大小，漏乘了 32 个头）
- 每 token（32 层）：`16 KB × 32 = 512 KB`
- 32K 上下文：`512 KB × 32768 ≈ 17.2 GB`（16 GiB），而不是 512 MB——差了 32 倍。

这也解释了为什么 7B 级的 MHA 模型做长上下文同样很吃显存，以及为什么 Llama 3 系列连 8B 都改用了 GQA。

(2) Llama-3-8B：每 token = `2 × 32 × 8 × 128 × 2 = 131,072 字节`（128 KiB）；8K 上下文 = `131072 × 8192 ≈ 1.07 GB`。

- fp16：`20 GB / 1.07 GB ≈ 18.6`，最多 **18** 个请求；
- fp8：每请求约 0.54 GB，最多 **37** 个请求。

注意这是按"每个请求都用满 8K"算的上限；配合 PagedAttention 按需分配，实际平均长度更短时并发可以更高。配套 skill 要求：开 fp8 KV cache 前必须在目标任务上评测质量影响。

### Q12 — 参考回答要点

- **定义**：在自回归生成中，把每一层、每个 KV 头上所有已处理 token 的 K、V 向量保存下来；生成新 token 时，只计算新 token 的 Q、K、V，把新的 K、V 追加到缓存，再用新 Q 对整个缓存做 attention。
- **为什么能缓存**：因果掩码保证位置 i 的表示只依赖 `≤ i` 的 token，后来的 token 不会改变前缀的 K、V（讲义："Every hidden state of a prefix token is deterministic once computed"）。
- **为什么不缓存 Q**：每个 query 只在它自己那一步被用一次（新 token 去"查询"历史），之后再也用不到；而 K、V 会被之后所有 token 反复读取。
- **公式**：`bytes = 2 × N × L × n_kv_heads × d_head × dtype_bytes × batch`。
- **prefill vs decode**：prefill 阶段一次性并行处理整个 prompt，填充 KV cache，矩阵乘规模大、受算力限制；decode 阶段每步一个 token，读权重和 KV cache，受带宽限制。首 token 延迟（TTFT）主要由 prefill 决定，之后每个 token 的延迟由 decode 决定。
- **常见误区**：以为 KV cache 降低了"总"复杂度到 O(N)——它把每步从 O(N²) 降到 O(N)，生成 N 个 token 的总 attention 仍是 O(N²)，而且显存随 N 线性增长。

### Q13 — 参考回答要点

- **问题**：标准 attention 要把 `S = QKᵀ`（N×N）写到 HBM，再读出来做 softmax 写回 P，再读出来算 `PV`——三次 HBM 往返。N ≥ 2K 时 attention 在受算力限制之前就先受带宽限制。
- **做法**：①分块（tiling）：把 Q 按块载入 SRAM，对每个 K/V 块计算局部分数；②online softmax：跨块维护每行的运行最大值 m 和指数和 s，新块到来时用 `exp(m_old − m_new)` 重新缩放旧值，块内结果直接累加到输出；③只把最终输出 O（以及反向需要的少量统计量）写回 HBM；④反向传播时不存 N×N 的注意力矩阵，而是利用保存的统计量**重算**——用一些额外 FLOPs 换显存和带宽。
- **为什么 FLOPs 不减反而更快**：瓶颈是 HBM 带宽而不是算力（H100 上 HBM 约 3 TB/s，SRAM 约 30 TB/s），减少 HBM 读写带来的收益远大于多出来的计算。显存占用从 O(N²) 降到 O(N)，使更长的上下文成为可能。
- **为什么精确**：online softmax 的重新缩放是代数恒等变换，最终归一化与一次性 softmax 完全相同，只有浮点运算顺序不同带来的 1e-16 量级差异（本节代码对多种 tile 大小验证了这一点）。
- **加分点**：版本演进——FA2 改进并行与工作划分，FA3 利用 Hopper 的异步与 FP8（FP16 下约 740 TFLOPs），FA4 面向 Blackwell、发布时仅支持前向；causal 模式下整块位于对角线上方的 tile 可以直接跳过。

### Q14 — 参考回答要点

| 方案 | KV 头 / 缓存内容 | KV cache 相对 MHA | 代价 |
|------|----------------|------------------|------|
| MHA | 每个 query 头一组 K、V | 1× | 长上下文显存爆炸 |
| MQA | 所有 query 头共享 1 组 K、V | `1 / n_heads` | 质量可能下降，训练稳定性较差 |
| GQA | 每组 query 头共享一组 K、V（如 64 个 Q 头、8 个 KV 头） | `n_kv_heads / n_heads`（Llama 3 70B 为 1/8） | 介于两者之间，是目前主流 |
| MLA（DeepSeek） | 缓存一个低维潜向量（V3 中为 512 维）加一小段解耦的 RoPE 键，计算时再投影回 K、V | 压缩更多 | 实现复杂，需要专门的 kernel；与 RoPE 的结合需要特殊设计 |

- **加分点**：GQA 可以从 MHA checkpoint 通过对 KV 头做平均池化再少量继续训练得到；本节代码的 DeepSeek-V3 一行用 `h_kv=1, d_h=512` 并乘以 2（K 和 V）只是粗略估算，实际每 token 每层缓存 512 + 64 = 576 个数，比代码估算的 1024 还少。
- **常见误区**：以为 GQA 减少了计算量——它主要减少的是 KV cache 显存和 decode 时的读带宽，query 头数和 attention 计算结构基本不变。

### Q15 — 参考回答要点

- **PagedAttention**：KV cache 以 16 token 的块按需分配，页表映射，几乎没有碎片；并行采样和共享前缀可以共享物理块。显存利用率提高 → 同一张卡能放更多并发请求 → 吞吐提升。
- **Continuous batching**：每个解码步都可以换入新请求、换出完成的请求，GPU 不会因等待最慢的序列而空转。
- **Prefix caching**：相同前缀（system prompt、few-shot、长文档）的 KV 只算一次，跨请求复用，显著降低 prefill 成本（讲义示例命令中的 `--enable-prefix-caching`）。
- **其他**：优化过的 attention kernel（FlashAttention / FlashInfer 等）、张量并行（`--tensor-parallel-size`）、fp8 KV cache（`--kv-cache-dtype fp8`）、chunked prefill、speculative decoding。
- **对比**：朴素的 `generate()` 循环通常是静态 batch、连续预分配 KV cache、没有跨请求复用，GPU 利用率低。
- **加分点**：区分"延迟"和"吞吐"——这些技术主要提升吞吐，单请求延迟还需要 speculative decoding 等手段。

### Q16 — 参考回答要点

- **权重**：70B × 2 字节 ≈ 140 GB，4 卡张量并行（TP=4）后每卡约 35 GB。
- **可用于 KV 的显存**：总计 320 GB − 140 GB 权重 − 激活、CUDA graph、通信缓冲等开销（预留约 10%–15%）≈ 140–160 GB。
- **KV 需求**：每个 32K 会话约 10.7 GB（fp16），50 个会话都用满需约 537 GB，**远超预算**；160 GB 只够约 15 个满长度会话。
- **可行方案**（组合使用）：
  - 开启 PagedAttention 按需分配：多数会话的实际长度远小于 32K，按真实分布估算并发能力；
  - fp8 KV cache：每个满长度会话降至约 5.4 GB，容量翻倍（需评测质量）；
  - 权重量化（如 AWQ / GPTQ 4-bit，权重降到约 35–40 GB），释放出约 100 GB 给 KV；
  - prefix caching：多会话共享的 system prompt 只存一份；
  - 设置 `--max-model-len 32768` 和合理的最大并发数，超出时排队或降级；监控 KV 使用率与抢占（preemption）次数。
- **加分点**：给出"满长度并发上限"和"按平均长度的典型并发"两个数字；说明 Llama 3 70B 若没有 GQA（64 头 MHA），单个 32K 会话就要约 86 GB，这个部署根本不可能——配套 skill 明确要标出"70B+ 无 GQA 在 32K+ 上下文时 KV cache 不可控"。

### Q17 — 参考回答要点

- **为什么近乎免费**：decode 受带宽限制——每一步都要把整个模型权重从 HBM 读一遍。batch 里放 1 个序列还是 32 个序列，权重只需读一次，多出来的只是少量计算和各序列自己的 KV cache 读取。在算术强度达到硬件的"屋脊点"（roofline 拐点）之前，增大 batch 几乎不增加单步耗时，吞吐近似线性增长。
- **何时失效**：①算术强度超过屋脊点，变成受算力限制，单步时间开始随 batch 增长；②KV cache 读取量随 batch × 上下文长度增长，长上下文时 KV 读取会取代权重读取成为主要带宽消耗，batch 越大越慢；③显存装不下更多 KV cache（这正是 PagedAttention、GQA、fp8 KV 要解决的问题）；④延迟 SLO 限制——batch 太大会拉长每个 token 的延迟。
- **加分点**：这就是 continuous batching 和 speculative decoding 的共同逻辑——在带宽受限的区间里，用"多处理几个 token"换"几乎不增加的时间"。speculative decoding 是在**单个请求内部**并行验证多个 token，对低并发场景尤其有效。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：`softmax(QKᵀ/√d)V` 的计算过程。
- [阶段 07 · 03 多头 Attention](../../03-multi-head-attention/docs/zh.md)：多头结构，理解 KV 头数对缓存的影响。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：因果掩码是 KV cache 成立的前提，"自回归税"是本节要解决的问题。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：softmax 减最大值的技巧，online softmax 的基础。

### 本节被哪些后续内容用到
- [阶段 07 · 15 Attention 变体](../../15-attention-variants/docs/zh.md)：滑动窗口、稀疏 attention 进一步降低 KV 与计算。
- [阶段 07 · 16 Speculative Decoding](../../16-speculative-decoding/docs/zh.md)：草稿-验证的完整实现。
- [阶段 10 · 12 推理优化](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：在自己的模型上落地这些优化。
- [阶段 10 · 11 量化](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：权重与 KV cache 量化。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：PagedAttention 与 continuous batching 的工程实现。
- [阶段 17 · 06 SGLang RadixAttention](../../../17-infrastructure-and-production/06-sglang-radixattention/docs/zh.md)：基于前缀树的 KV 复用。
- [阶段 17 · 17 Prefill / Decode 分离部署](../../../17-infrastructure-and-production/17-disaggregated-prefill-decode/docs/zh.md)：针对两个阶段不同瓶颈的部署架构。
- [阶段 11 · 15 Prompt Caching](../../../11-llm-engineering/15-prompt-caching/docs/zh.md)：API 层面的前缀缓存。

### 延伸关键词
`roofline model` · `arithmetic intensity` · `TTFT / TPOT` · `chunked prefill` · `FlashInfer` · `RadixAttention` · `KV cache quantization` · `sliding window attention` · `StreamingLLM / attention sink`
