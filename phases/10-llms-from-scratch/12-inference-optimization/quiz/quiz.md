# 测验 · Inference Optimization（Inference Optimization）

> **阶段 10 · 从零构建 LLM · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 Rust 版 [code/main.rs](../code/main.rs)，结构与 Python 版对应） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Prefill vs Decode | prefill 并行处理整个 prompt，算力受限（compute-bound），决定 TTFT；decode 每步只出 1 个 token，却要读一遍全部权重，显存带宽受限（memory-bound） |
| 2 | Decode 的下限 | 单步时间 ≥ 权重字节数 / 显存带宽：70B FP16 = 140 GB，A100 带宽 2 TB/s → 约 70 ms/步 |
| 3 | KV cache | 缓存历史 token 的 K、V，避免每步重算；每 token 大小 `2 × 层数 × KV头数 × head_dim × 字节`，Llama 3 70B（GQA，8 个 KV 头）为 320 KB/token，128K 上下文约 40 GB |
| 4 | Continuous batching | 每个 decode 步重新组 batch，完成的请求立刻腾出槽位给排队请求；输出长度差异越大，相对 static batching 的收益越大（讲义：2–5 倍） |
| 5 | PagedAttention | 借鉴 OS 虚拟内存，把 KV cache 切成固定大小的页（常见 16 token/页），用页表映射，消除碎片，支持共享前缀的 copy-on-write；讲义：浪费从 60–80% 降到约 4% |
| 6 | Speculative decoding | 草稿模型连续猜 K 个 token，目标模型一次前向并行验证；按 `min(1, p/q)` 接受、拒绝时从残差分布重采样，输出分布与目标模型**完全一致** |
| 7 | 投机解码变体 | 独立草稿模型（讲义：70–85% 接受率）、EAGLE（在目标模型隐藏状态上训练轻量头，75–90%）、N-gram 查表（40–60%，几乎零开销） |
| 8 | Prefix caching | 共享前缀（系统提示、RAG 上下文、few-shot）的 KV 只算一次；SGLang 的 RadixAttention 用基数树支持部分前缀匹配 |
| 9 | ops:byte（算术强度） | 每读 1 字节做多少运算；A100 拐点 = 312 TFLOPS / 2 TB/s = 156；低于拐点受带宽限制，高于拐点受算力限制 |
| 10 | 三大推理引擎 | vLLM（PagedAttention + continuous batching，通用首选）、SGLang（RadixAttention、结构化生成）、TensorRT-LLM（NVIDIA kernel 融合与 FP8） |

### 核心技能（能动手做到）

- [ ] 用 NumPy 实现带 KV cache 的多头注意力，并验证"缓存解码"与"全量重算"的输出一致
- [ ] 按配置手算任意模型的 KV cache 大小与给定显存下的最大并发数（注意 GQA 与 GiB）
- [ ] 写一个 static / continuous batching 调度模拟器，并计算延迟分位数与吞吐
- [ ] 推导投机解码的期望接受长度与加速比，指出本节模拟器"接受率"列为何与配置值不一致
- [ ] 写出投机解码真正的接受—拒绝规则，并解释它为什么是无损的
- [ ] 用 roofline / ops:byte 判断一个场景受算力还是带宽限制，并选择对应的优化手段

---

## 二、基础自测（选择题）

**Q1.** 关于 prefill 与 decode，下列说法正确的是：

- A. prefill 逐 token 进行，是带宽瓶颈；decode 一次处理整个 prompt，是算力瓶颈
- B. prefill 并行处理所有 prompt token，偏算力瓶颈；decode 每步只生成一个 token 却要读取全部权重，偏显存带宽瓶颈
- C. 两个阶段都是算力瓶颈，换更快的 GPU 核心就能等比例加速
- D. decode 阶段不需要读取权重，只读取 KV cache

**Q2.** Llama 3 70B：80 层、8 个 KV 头（GQA）、head_dim = 128、BF16。每个 token 的 KV cache 是：

- A. 约 2.5 MB
- B. 约 40 KB
- C. 约 160 KB
- D. 约 320 KB（327,680 字节）

**Q3.** 70B 模型 FP16 权重 140 GB，部署在带宽 2 TB/s 的 GPU 上（假设放得下），batch = 1 时单个 decode 步的理论下限约为：

- A. 70 ms，即每秒最多约 14 个 token
- B. 0.45 ms
- C. 7 ms
- D. 1.8 s

**Q4.** 关于 continuous batching，下列说法正确的是：

- A. 它把多个请求的 prompt 拼接成一个长 prompt 一起处理
- B. 它要求所有请求的输出长度相同才有收益
- C. 在每个 decode 迭代重新评估 batch，任一请求完成后立刻插入等待中的请求，使 GPU 槽位不空闲；输出长度差异越大，收益越明显
- D. 它是一种减少 KV cache 显存的技术

**Q5.** PagedAttention 解决的核心问题是：

- A. 注意力计算的 O(N²) 复杂度
- B. 投机解码的接受率太低
- C. 模型权重太大放不进单卡
- D. 为每个请求预留连续的大块 KV cache 显存会造成碎片和浪费；改为固定大小的页 + 页表映射后，页可以散落在物理显存任意位置，并能让多个请求共享同一前缀的页

**Q6.** 投机解码中，目标模型对位置 i 的分布为 p，草稿模型为 q，草稿 token 为 x。保证输出分布与目标模型**完全相同**的规则是：

- A. 以概率 `min(1, p(x)/q(x))` 接受 x；若拒绝，从归一化的 `max(0, p − q)` 中重新采样，并丢弃后续草稿
- B. 只要 `p(x) > 0` 就接受
- C. 以固定概率（如 0.8）接受，拒绝时从 p 中重新采样
- D. 只接受 `x = argmax p` 的 token，否则重新生成全部草稿

**Q7.** A100 的拐点 ops:byte = 156。用 FP16 权重做 batch = 32 的 decode（只看权重读取），它处于：

- A. 算力受限，应做 kernel 融合
- B. 正好在拐点上
- C. 带宽受限，算力利用率上限约 32/156 ≈ 20.5%；应增大 batch 或减少读取量（量化等）
- D. 无法判断，ops:byte 与 batch 无关

**Q8.** Llama 3 70B 有 64 个 query 头、8 个 KV 头。相比"64 个 KV 头"的标准多头注意力，GQA 让 KV cache：

- A. 不变，GQA 只减少计算量
- B. 缩小为 1/8
- C. 缩小为 1/2
- D. 增大 8 倍

---

## 三、动手 / 代码题

**Q9.** 本节投机解码模拟器的实际输出：

```text
  Strategy                   Accept Rate   Avg Accept    Speedup
  Draft-target (8B->70B)          50.8%         2.54      2.08x
  EAGLE                           59.0%         3.54      2.52x
  N-gram lookup                   22.5%         0.90      1.19x
```

配置的接受率分别是 0.78（K = 5）、0.85（K = 6）、0.50（K = 4）。核心代码：

```python
        for i, token in enumerate(draft_tokens):
            draft_p = draft_model.get_probs(context + list(draft_tokens[:i]), token)
            target_p = target_probs[i]
            r = np.random.random()
            if r < draft_model.acceptance_rate:
                accepted += 1
                ...
            else:
                new_token = np.random.choice(draft_model.vocab_size, p=target_p)
                ...
                break
        ...
    "acceptance_rate": np.mean(accepted_counts) / num_speculative,
```

成本参数：`draft_cost = 1.0`（每个草稿 token）、`verify_cost = 12.0`（每轮验证）、`target_cost = 10.0`（顺序解码每 token）。

1. 为什么输出的 "Accept Rate" 远低于配置值？推导"每轮期望接受数"的公式，并用 α = 0.78、K = 5 验证 2.54 这个数。
2. 推导每轮期望产出 token 数与期望加速比，验证 2.08x。
3. 这个模拟器为什么**不能**体现讲义所说的 "mathematically exact"？指出两处与真实算法不符的地方。
4. N-gram 查表几乎没有草稿开销，但代码仍按每 token 1.0 计费。若把它的 `draft_cost` 设为 0，理论加速比是多少？

**Q10.** 阅读 `KVCache` 与 `MultiHeadAttention.forward`：

```python
    def update(self, layer_idx, new_keys, new_values):
        num_new = new_keys.shape[1]
        end = self.seq_len + num_new
        self.k_cache[layer_idx, :, self.seq_len:end, :] = new_keys
        ...
        if kv_cache is not None:
            K_full, V_full = kv_cache.update(layer_idx, K[0], V[0])
            K = K_full[np.newaxis, :, :, :]
            V = V_full[np.newaxis, :, :, :]
            if seq_len == 1:
                kv_cache.advance(1)
```

演示中只有 1 层、batch = 1，一切正常（实测缓存解码与全量重算的最大差异约 1e−3，改用 float32 缓存后为 1e−7）。

1. 若模型有 2 层、共用一个 `KVCache`（`layer_idx` 分别为 0、1），prefill 8 个 token 后 decode 1 个 token，`cache.seq_len` 会变成多少？为什么？会造成什么错误？
2. 若输入 batch = 2，会发生什么？
3. 为什么缓存版与全量重算之间有约 1e−3 的差异？
4. 给出修正方案。

**Q11.** 批处理模拟的输出（30 个请求，batch_size = 8，输出长度 5–45、总计 449 个 token，到达时刻 0–17）：

```text
  Metric                          Static   Continuous  Improvement
  avg_latency                       86.7         25.8   70.2% less
  p99_latency                      132.0         57.1   56.7% less
  total_time                       146.0         77.0   47.3% less
  throughput                         3.1          5.8        1.90x
```

1. 验证两个 throughput 数值。
2. 在"8 个槽位、每步每槽 1 个 token"的模型下，处理完 449 个 token 至少需要多少步？continuous 的 77 步离下限还有多远，差距来自哪里？
3. 这个模拟器做了哪些简化（至少 3 条），它们分别会让结果偏向哪一方？

**Q12.** STEP 6 把 "Decode, batch = B" 的 ops:byte 直接写成 B。

1. 对 FP16 权重，为什么"每读 1 字节的 FLOPs ≈ batch 大小"？如果权重换成 INT4（W4A16），ops:byte 与拐点 batch 如何变化？
2. 代码只考虑了权重读取。decode 中注意力还要读 KV cache，这部分的 ops:byte 会随 batch 增大吗？这对"batch ≥ 156 就是算力受限"的结论有什么影响？
3. 讲义说 "Prefill for a 4,096-token prompt on a 70B model takes ~400ms on a single A100"。用 `FLOPs ≈ 2 × 参数量 × token 数` 检验这个说法。

---

## 四、面试高频题

**Q13.**（基础必考）一个请求到达 vLLM 之后，从 prompt 到最后一个 token，经历了哪些阶段？TTFT 和 TPOT 分别由什么决定？

**Q14.**（原理深挖）为什么说 decode 是 memory-bound？请用 roofline 模型解释，并说明量化、batching、投机解码分别从哪个角度缓解它。

**Q15.**（原理深挖）为什么投机解码是"无损"的？什么情况下它反而不划算？

**Q16.**（工程实践）你要在 4×A100-80GB 上用 BF16 部署 Llama 3 70B，目标是 100 个并发用户、平均上下文 4K。请做容量估算，并给出优化方案。

**Q17.**（场景设计）一个 RAG 客服机器人：每个请求有 2,000 token 的固定系统提示 + 检索到的文档 + 多轮对话历史。你会如何设计推理侧的缓存与调度？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Prefill processes your prompt in parallel -- compute-bound. Decode generates tokens one at a time -- memory-bound." decode 时权重矩阵与 prefill 一样大，却只乘以一个向量，算力很快算完，然后等待下一批权重从 HBM 读出。A 把两者说反了；C 错，decode 受带宽限制，更快的核心无济于事；D 错，每个 decode 步都要读全部权重（加上 KV cache）。

### Q2 — 答案：D

`2（K、V）× 80 × 8 × 128 × 2 字节 = 327,680 字节 = 320 KB`，与讲义和代码 STEP 1 的输出 `320.0KB` 一致。4K 上下文 1.25 GiB，128K 上下文 40 GiB。

- A 是用 64 个**查询头**计算（不考虑 GQA）的结果：2,560 KB；
- B 是 `80 × 8 × 128 × 2 / 4` 之类的误算；
- C 漏了 K、V 的因子 2。

### Q3 — 答案：A

`140 GB / 2 TB/s = 70 ms`，所以 batch = 1 时最多约 14 token/s。讲义："Reading the full model once takes 70ms -- that is your floor for a single decode step." B 是用 312 TFLOPS 算 `2 × 70e9` FLOPs 的时间（0.45 ms），说明 decode 的计算时间远小于读取时间——这正是 memory-bound 的含义；D 是 4,096 token prefill 在 312 TFLOPS 下的理论时间（见 Q12）。另外注意 140 GB 放不进一张 80 GB 的 A100，实际要多卡切分，带宽相应叠加。

### Q4 — 答案：C

讲义："Continuous batching (also called iteration-level batching) inserts new requests into the batch as soon as any request completes. The batch is reevaluated at every decode step." 以及 "With uniform lengths, continuous batching matches static batching." A 描述的是 packing；B 正好相反；D 是 PagedAttention / KV 量化等的作用。

### Q5 — 答案：D

讲义："Instead of allocating one contiguous block per request, it allocates fixed-size 'pages' (typically 16 tokens each). Pages can be anywhere in physical GPU memory. A page table maps..." 并且 "PagedAttention also enables copy-on-write for shared prefixes." A 是 FlashAttention / 稀疏注意力关注的问题；C 是量化与并行的问题。注意：本节代码**没有实现** PagedAttention，SUMMARY 中 "PagedAttention eliminates memory fragmentation (simulated via trie)" 的说法有误，trie 模拟的是 prefix caching。

### Q6 — 答案：A

这是 Leviathan et al. 2023 的 speculative sampling 规则。对任意 token y，最终被输出的概率为 `q(y)·min(1, p(y)/q(y)) + P(拒绝)·残差(y) = min(q, p)(y) + max(0, p − q)(y) = p(y)`，因此输出分布严格等于 p。

- B 会严重偏向草稿模型；
- C 是本节模拟器的做法（见 Q9），与 p、q 无关，不是无损的；
- D 只适用于贪心解码的特例（温度 0 时接受"草稿 = 目标的 argmax"），而且也不需要重生成全部草稿。

### Q7 — 答案：C

FP16 权重每个参数 2 字节，每个 token 对它做 1 次乘加（2 FLOPs），batch = B 时每字节 FLOPs ≈ `2B / 2 = B`，所以 ops:byte ≈ 32 < 156，带宽受限。代码 STEP 6 输出 "Decode, batch=32 ... Memory 20.5%"（`32/156`）。应对方式是增大 batch（continuous batching）或减少每步读取的字节数（权重量化、KV 压缩）。讲义："Below 156, you are memory-bound."

### Q8 — 答案：B

KV cache 与 KV 头数成正比，`8 / 64 = 1/8`。讲义练习 3："Llama 3 70B uses 64 query heads but only 8 KV heads ... (8x reduction in KV cache size)." GQA 并不减少 Q 的计算，主要节省 KV cache 显存与 decode 时的 KV 读取带宽。

### Q9 — 参考答案

1. 输出的 "Accept Rate" 是 `平均每轮接受数 / K`，而配置值 α 是**单个 token** 的接受概率。每轮从第一个草稿开始，遇到第一次拒绝就停止，所以第 i 个草稿被接受的概率是 `α^i`：

   `E[每轮接受数] = Σ_{i=1..K} α^i = α(1 − α^K)/(1 − α)`

   α = 0.78、K = 5：`0.78 × (1 − 0.78^5)/0.22 ≈ 2.52`，除以 5 得 50.4%，与实测 2.54、50.8% 吻合。同理 EAGLE 理论 3.53（58.8%），N-gram 0.94（23.4%）。讲义里 "acceptance rates of 70-85%" 指的是单 token 接受率，两个概念不能混用。

2. 每轮必然额外产出 1 个 token（拒绝时的重采样，或全部接受时的 bonus token），所以

   `E[每轮 token] = 1 + Σ_{i=1..K} α^i = (1 − α^{K+1})/(1 − α)`

   每轮成本 `K × draft_cost + verify_cost`，顺序解码每 token 成本 `target_cost`：

   `加速比 = target_cost × E[每轮 token] / (K × draft_cost + verify_cost)`

   α = 0.78、K = 5：`E = (1 − 0.78^6)/0.22 ≈ 3.52`，`10 × 3.52 / 17 ≈ 2.07`，与实测 2.08x 吻合；EAGLE `10 × 4.53 / 18 ≈ 2.52`；N-gram `10 × 1.94 / 16 ≈ 1.21`（实测 1.19）。

3. 两处（以及一处附带问题）：
   - **接受判定与分布无关**：用 `r < acceptance_rate` 的固定伯努利代替 `r < min(1, p(x)/q(x))`；`draft_p` 被计算后完全没用（讲义版代码算了 `acceptance_prob` 也没用）。
   - **拒绝后从 p 重采样**，而正确做法是从归一化的 `max(0, p − q)` 采样。直接从 p 采样会让已经"有机会被草稿接受"的 token 被重复计入，输出分布不再等于 p。
   - 附带：草稿 token 是 `randint` 均匀抽的，并不来自 q。所以这个模拟器只能用来演示"接受率 → 加速比"的成本模型，不能演示正确性。
4. `draft_cost = 0` 时 `加速比 = 10 × 1.94 / 12 ≈ 1.61x`（我们用模拟器实跑 20 次平均约 1.54x）。这说明对 n-gram 这类几乎免费的草稿，即使接受率只有 50%，仍有可观收益；而代码的成本设定低估了它。

### Q10 — 参考答案

1. `seq_len` 会变成 **10**（已实测）。`advance(1)` 写在 `MultiHeadAttention.forward` 里，**每一层**的前向都会调用一次。第 0 层把新 token 写在位置 8 后把 `seq_len` 改成 9；第 1 层再用 `seq_len = 9` 作为写入位置，把它的 K、V 写到位置 9，并返回 `[:10]`——其中位置 8 是全零的"空洞"，第 1 层的注意力会看到一个不存在的 token。之后每生成一个 token，`seq_len` 增加 2，各层越错越远。
2. `kv_cache.update(layer_idx, K[0], V[0])` 只取了 batch 中的**第 0 个样本**，缓存本身也没有 batch 维；随后 `K_full[np.newaxis]` 形状为 `(1, heads, seq, dim)`，在 `np.matmul` 中被广播给所有样本。于是 batch 中其他样本都使用第 0 个样本的 K、V，程序不报错但结果错误（实测第 2 个样本的输出与不带缓存的结果不一致）。
3. 缓存的 `dtype` 默认是 `np.float16`，而 K、V 是 float32 计算的，存入时被舍入到半精度（约 3 位有效数字），所以有约 1e−3 的差异。这本身也说明 KV cache 精度会影响输出（上一节 KV cache 量化的话题）。
4. 修正方案：
   - 缓存加 batch 维：`(num_layers, batch, num_heads, max_seq_len, head_dim)`，`update` 写入整个 batch；
   - `update` 只负责写入并返回 `[:seq_len + num_new]`，**不在注意力层里推进**；由模型在所有层前向结束后统一调用一次 `advance(num_new)`（prefill 时推进 prompt 长度、decode 时推进 1）；
   - 写入前检查 `end <= max_seq_len`；
   - 用"缓存解码 vs 全量重算"的数值一致性作为单元测试。

### Q11 — 参考答案

1. 吞吐 = 总 token / 总时间：`449 / 146 ≈ 3.08`，`449 / 77 ≈ 5.83`，比值 1.90x。
2. 下限：`449 / 8 ≈ 56.1`，至少 57 步。continuous 用了 77 步，差距来自：开始阶段请求还没到齐（到达时刻 0–17），槽位没有填满；尾部只剩最长的请求（45 token）在跑，其他槽位空闲。static 的 146 步则是每批都要等"最长的那个"跑完。
3. 简化与偏向：
   - **忽略 prefill**：`prompt_tokens = 100` 没有被使用。真实系统中新请求加入需要做 prefill，会拖慢正在 decode 的请求（chunked prefill 等技术就是为此设计的）。这偏向 continuous。
   - **每步耗时与 batch 大小无关**：符合 decode memory-bound 的假设，但 batch 变大后会逐渐接近算力上限。
   - **static 中短请求要等整批结束才算完成**：`r.end_step = step + max_output` 对所有请求一样。若 static 也允许完成的请求先返回，延迟差距会缩小，但 GPU 槽位浪费依旧。这偏向 continuous 的延迟数据。
   - **static 先凑满 batch 再开始**：它按到达顺序取 8 个请求，等到最后一个到达才开跑，等待时间也计入延迟。
   - **没有显存约束**：continuous batching 实际受 KV cache 容量限制（这正是 PagedAttention 要解决的问题）。

### Q12 — 参考答案

1. decode 时，每个权重参与每个 token 的一次乘加（2 FLOPs）。batch = B 时，读取 2 字节（FP16）完成 2B FLOPs，所以 `ops:byte = B`。代码把 ops:byte 直接写成 batch 大小，正是利用了"2 FLOPs / 2 字节"刚好抵消。若权重为 INT4（0.5 字节/参数，激活仍 FP16）：`ops:byte = 2B / 0.5 = 4B`，拐点 batch 从约 156 降到约 39；同一 batch 下 decode 更快（读取量变为 1/4），但更早撞上算力上限。
2. 不会。每个请求的 KV cache 是**它自己的**，不能被 batch 中的其他请求复用。注意力部分每读一个 K/V 元素只做约一次乘加，ops:byte 约为常数（~1），与 batch 无关。所以即使 batch ≥ 156，decode 中的注意力部分依然是带宽受限；上下文越长、KV cache 占比越大，"增大 batch 就进入算力受限"的结论越不成立。这也是 GQA/MQA、KV 量化、FlashDecoding 等技术存在的原因。
3. `2 × 70e9 × 4,096 ≈ 5.7e14 FLOPs`，A100 峰值 312 TFLOPS，100% 利用率下约 **1.84 s**；何况 70B FP16 的 140 GB 权重根本放不进单张 80 GB 的 A100。所以 "~400ms on a single A100" 不成立。若是 4×A100 张量并行，理想情况约 0.46 s，再考虑 50–70% 的实际利用率，更接近 0.7–0.9 s。估算时应以 FLOPs 和带宽为依据自己算一遍。

### Q13 — 参考回答要点

- **排队与调度**：请求进入等待队列；调度器（continuous batching）在某个迭代把它加入运行中的 batch，前提是有足够的 KV cache 页。
- **Prefill**：对整个 prompt 做一次前向，生成所有层的 K、V 写入分配到的页（PagedAttention），同时得到第一个输出 token 的分布。若开启 prefix caching，命中的前缀部分直接复用已有页，只算剩余部分。
- **Decode**：每个迭代与其他请求一起前向一次，生成 1 个 token（或开启投机解码时一次接受多个），新 K、V 追加到页中，页满则再分配一页。
- **结束**：遇到 EOS、停止词或达到 `max_tokens`，释放（或保留供前缀复用的）页。
- **指标**：
  - TTFT（Time To First Token）：排队时间 + prefill 时间，主要由 prompt 长度与算力决定（讲义："dominated by prefill time for long prompts"）；
  - TPOT / ITL（每个输出 token 的间隔）：由 decode 单步时间决定，主要受显存带宽与 batch 大小影响；
  - 吞吐（total tokens/s）与 TPOT 之间存在权衡：batch 越大吞吐越高，单个用户的 TPOT 越慢。
- 加分点：长 prompt 的 prefill 会阻塞同一批中的 decode，chunked prefill 或 prefill/decode 分离部署可以缓解。

### Q14 — 参考回答要点

- **roofline**：可达性能 = `min(峰值算力, 带宽 × 算术强度)`。A100 拐点约 156 FLOPs/byte。
- **decode 的算术强度**：batch = 1 时每个权重只用一次，ops:byte ≈ 1，远低于拐点；GPU 大部分时间在等数据，算力利用率不到 1%（代码 STEP 6：0.6%）。讲义："decode is memory-bound because you read the entire model to produce a single token."
- **三种缓解思路**（讲义："Every optimization below either reduces what you read, increases the batch of tokens processed per read, or avoids reads entirely"）：
  - **减少读取量**：权重量化（INT8/INT4/FP8）、KV cache 量化、GQA/MQA；
  - **每次读取服务更多 token**：continuous batching（多个请求共享一次权重读取）、投机解码（一次读取验证 K 个 token）；
  - **避免读取/计算**：KV cache（不重算历史）、prefix caching（不重算共享前缀）。
- 注意：KV cache 的读取不能跨请求摊薄（见 Q12），长上下文时它会成为新的瓶颈。

### Q15 — 参考回答要点

- **无损性**：按 `min(1, p/q)` 接受，拒绝时从 `norm(max(0, p − q))` 采样，可以证明每个位置输出的边缘分布严格等于 p（见 Q6 的推导）。被接受的前缀之后，后续位置以新的上下文继续，整体序列分布与目标模型逐 token 采样相同。讲义："It is not an approximation."
- **为什么快**：目标模型一次前向验证 K 个位置，和 decode 一个 token 的成本相近（都主要是读一遍权重），期望每轮产出 `(1 − α^{K+1})/(1 − α)` 个 token。
- **不划算的情况**：
  - 接受率低（领域不匹配、高温度采样）：每轮只产出 1 个多 token，草稿开销白付；
  - 草稿模型太贵（草稿/目标成本比过高）；
  - **大 batch 高吞吐场景**：系统已接近算力受限，验证 K 个位置不再"几乎免费"，投机解码会挤占用于其他请求的算力，总吞吐可能下降；
  - K 设得过大：后面位置的接受概率 `α^i` 迅速下降，额外草稿与验证成本得不偿失。
- **选择**：延迟敏感、低并发时收益最大；EAGLE 系列接受率更高且额外显存约 1%；n-gram 适合代码、结构化、重复性输出。

### Q16 — 参考回答要点

- **权重**：140 GB（BF16），4 卡张量并行每卡约 35 GB。
- **KV cache**：320 KB/token × 4,096 ≈ 1.25 GiB/用户，100 用户 ≈ 125 GiB（讲义："100 concurrent users at 4K tokens each, KV cache alone requires 128 GB"）。
- **总量**：320 GB 总显存 − 140 GB 权重 − 约 10% 预留 ≈ 150 GiB 可用（代码 `memory_budget` 给出 157.6 GB、可容纳 126 个 4K 用户），**刚好够**，但没有余量应对长上下文用户。
- **吞吐估算**：decode 单步下限 ≈ 140 GB / (4 × 2 TB/s) ≈ 17.5 ms（不计 KV 读取与通信），100 个用户每步共享一次权重读取，但每个用户的 KV（1.25 GiB）也要读，100 用户共约 125 GiB，与权重相当，单步时间大约翻倍。
- **优化方案**：
  - vLLM / SGLang：PagedAttention + continuous batching，`gpu_memory_utilization` 约 0.9；
  - FP8 KV cache（若硬件支持）或 INT8 KV，容量翻倍；
  - 开启 prefix caching，复用系统提示；
  - 若质量允许，FP8/INT4 权重进一步腾出 KV 空间（参考上一节）；
  - 投机解码改善低并发时的延迟；
  - 设置 `max_model_len` 防止个别长请求独占显存。
- 加分点：同时给出 TTFT / TPOT 的 SLO，并用压测（而不是只靠公式）验证。

### Q17 — 参考回答要点

- **前缀缓存**：2,000 token 系统提示对所有请求相同，用 prefix caching 只计算一次（讲义：约省掉每请求 400 ms 的 prefill，按讲义的估算口径）；多轮对话中历史轮次也是下一轮的前缀，用 RadixAttention 式基数树可以自动复用"系统提示 + 历史对话"。
- **组织 prompt 的顺序**：把稳定的部分放前面（系统提示 → 工具说明 → 检索文档 → 对话历史 → 当前问题），让可复用前缀尽可能长；检索文档的顺序保持确定（例如按文档 ID 排序），否则同样的文档换个顺序就无法命中。
- **淘汰策略**：显存有限时按 LRU 淘汰（讲义练习 4），并优先保留系统提示等高复用前缀；可将冷前缀卸载到 CPU 内存。
- **调度**：continuous batching；cache-aware 路由让同一会话的请求落到持有其 KV 的副本上；长文档 prefill 用 chunked prefill 避免阻塞其他会话的 decode。
- **引擎选择**：多轮、前缀复用多、需要结构化输出 → SGLang；通用兼容 → vLLM 并开启 `enable_prefix_caching`。
- **监控**：前缀命中率、TTFT 分布、KV 显存占用、淘汰次数。
- 常见误区：在系统提示里放时间戳、随机 ID 等每次都变的内容，导致前缀永远无法命中。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：KV cache 的公式、prefill 与 decode 的初步介绍。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 与 FlashAttention 的实现细节。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：多头拆分与 GQA 的基础。
- [阶段 10 · 11 Quantization：让模型装得下](../../11-quantization/docs/zh.md)：通过量化减少每步读取的字节数。

### 本节被哪些后续内容用到
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../15-speculative-decoding-eagle3/docs/zh.md)、[阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：投机解码的完整推导与新变体。
- [阶段 17 · 04 服务引擎内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：PagedAttention、continuous batching 与 chunked prefill 的工程实现。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../../17-infrastructure-and-production/06-sglang-radixattention/docs/zh.md)：基数树前缀缓存。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：推理服务的指标体系。
- [阶段 17 · 17 Prefill 与 Decode 分离](../../../17-infrastructure-and-production/17-disaggregated-prefill-decode/docs/zh.md)：把两个阶段放到不同硬件上。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../../11-llm-engineering/15-prompt-caching/docs/zh.md)：API 层面的前缀缓存与计费。
- [阶段 19 · 14 综合项目：推测解码 Inference 服务端](../../../19-capstone-projects/14-speculative-decoding-server/docs/zh.md)：动手实现一个投机解码服务。

### 延伸关键词
`prefill / decode` · `TTFT / TPOT / ITL` · `KV cache` · `GQA / MQA` · `continuous batching` · `chunked prefill` · `PagedAttention` · `copy-on-write` · `prefix caching / RadixAttention` · `speculative sampling` · `EAGLE` · `roofline / arithmetic intensity` · `vLLM / SGLang / TensorRT-LLM`
