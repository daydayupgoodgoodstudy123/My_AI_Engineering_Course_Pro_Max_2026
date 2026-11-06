# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 12 节 Inference Optimization ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：第三方 `numpy`；标准库 `heapq` 被导入但未使用（无需 GPU、无需模型、无需网络）。同目录的 `main.rs` 是结构对应的 Rust 版本，本文不展开。

---

## 1. 这份代码在考察什么

这份代码用纯 NumPy 和小型模拟器，把讲义里的推理优化技术逐一"跑一遍"：

1. **KV cache 显存估算**：不同模型在 4K / 32K / 128K 上下文下的 KV cache 大小，以及给定 GPU 显存能容纳多少并发用户。
2. **带 KV cache 的多头注意力**：prefill 一次写入 prompt 的 K/V，decode 每步只算新 token 的 Q/K/V 并拼接缓存。
3. **调度**：static batching 与 continuous batching 的离散时间模拟，比较延迟与吞吐。
4. **前缀缓存**：用 trie（前缀树）按 token 存 KV，统计命中率与节省的 token 数。
5. **投机解码**：一个"成本模型"式的模拟器，展示接受率与加速比的关系。
6. **ops:byte / roofline**：A100 的拐点与不同 batch 下 decode 的受限类型。

> 一句话：**decode 慢是因为"为了一个 token 读一遍整个模型"——这份代码的每个部分都在演示如何少读（KV cache、前缀缓存）、一次读服务更多 token（batching、投机解码），以及如何判断瓶颈（ops:byte）。** 其中 STEP 2 的 KV cache 数值正确，STEP 5 的投机解码只是成本模型，不实现真正的接受—拒绝采样；PagedAttention 没有实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `KVCache` | 类 | 预分配 `(层, 头, max_seq, head_dim)` 的 K/V 数组；`update` 写入、`advance` 推进、`used_bytes` 统计 | KV cache |
| `scaled_dot_product_attention` | 函数 | 带"右下对齐"因果 mask 的注意力 | 注意力 |
| `MultiHeadAttention` | 类 | Q/K/V 投影、拆头、可选使用 KV cache、合头、输出投影 | 多头注意力 + 缓存 |
| `Request` | 类 | 请求的到达时刻、输出长度、开始/结束步 | 调度对象 |
| `simulate_static_batching` | 函数 | 凑满一批，整批跑到最长请求结束 | static batching |
| `simulate_continuous_batching` | 函数 | 每步补位，完成即退出 | continuous batching |
| `batching_stats` | 函数 | 平均 / P50 / P99 延迟、总时间、吞吐 | 服务指标 |
| `TrieNode` / `PrefixCache` | 类 | 按 token 建 trie，查最长公共前缀 | prefix caching |
| `DraftModel` / `TargetModel` | 类 | 返回随机 token / 随机 Dirichlet 分布 | 草稿与目标模型（模拟） |
| `speculative_decode` | 函数 | 草稿 K 个 → 验证 → 接受/拒绝 → 统计成本 | 投机解码（成本模型） |
| `MODEL_CONFIGS` | 字典 | Llama 3 8B/70B/405B、Mistral 7B、GPT-4 估计配置 | 模型规格 |
| `kv_cache_memory` / `memory_budget` | 函数 | KV 大小；扣除权重与 10% 预留后的并发容量 | 容量规划 |
| `__main__` 中的 STEP 1–6 | 脚本 | 依次打印六个演示 | 演示入口 |

数据流：`np.random.seed(42)` → STEP 1 显存表与容量表 → STEP 2 prefill 8 token + decode 4 步 → STEP 3 用 `RandomState(42)` 生成 30 个请求分别跑两种调度 → STEP 4 插入 3 个系统提示，100 个请求查前缀 → STEP 5 三种策略各 10 次模拟 → STEP 6 ops:byte 表 → SUMMARY。

---

## 3. 逐段精讲

### 3.1 KVCache：预分配 + 写指针

```python
class KVCache:
    def __init__(self, num_layers, num_heads, head_dim, max_seq_len, dtype=np.float16):
        self.k_cache = np.zeros((num_layers, num_heads, max_seq_len, head_dim), dtype=dtype)
        self.v_cache = np.zeros((num_layers, num_heads, max_seq_len, head_dim), dtype=dtype)
        self.seq_len = 0

    def update(self, layer_idx, new_keys, new_values):
        num_new = new_keys.shape[1]
        end = self.seq_len + num_new
        self.k_cache[layer_idx, :, self.seq_len:end, :] = new_keys
        self.v_cache[layer_idx, :, self.seq_len:end, :] = new_values
        return (self.k_cache[layer_idx, :, :end, :], self.v_cache[layer_idx, :, :end, :])

    def used_bytes(self):
        per_token = 2 * self.num_layers * self.num_heads * self.head_dim * np.dtype(self.dtype).itemsize
        return per_token * self.seq_len
```

- **预分配到 `max_seq_len`**：这正是讲义所说"每个请求一块连续显存"的做法。`memory_bytes()` 返回的是预分配总量，`used_bytes()` 返回实际用到的部分，二者之差就是"预留但未使用"的浪费——PagedAttention 要消除的就是它（以及由此产生的碎片）。
- `seq_len` 是写指针：`update` 写到 `[seq_len, seq_len + num_new)`，返回 `[:end]`（历史 + 新写入）。切片返回的是**视图**，不复制数据。
- `used_bytes` 的公式与讲义一致：`2 × 层 × 头 × head_dim × 字节 × token 数`。演示配置为 1 层、4 头、head_dim 16、FP16，每 token `2 × 1 × 4 × 16 × 2 = 256` 字节，8 个 token 正好 2048 字节。
- ⚠️ **没有 batch 维**：缓存形状里没有 batch，调用方只能写入一个样本（见 3.3）。
- ⚠️ 默认 `dtype=np.float16`，而 K/V 是 float32 算出来的，写入时被舍入到半精度。实测缓存解码与全量重算的最大差异约 1e−3；把缓存改为 float32 后约 1e−7。这顺便说明 KV cache 精度会影响输出。
- ⚠️ 写入前没有检查 `end <= max_seq_len`；越界时 NumPy 切片会静默截断，赋值报形状不匹配的错误。

### 3.2 带"右下对齐"mask 的注意力

```python
def scaled_dot_product_attention(query, keys, values):
    head_dim = query.shape[-1]
    scores = np.matmul(query, keys.transpose(0, 1, 3, 2)) / np.sqrt(head_dim)
    seq_len_q = scores.shape[-2]
    seq_len_k = scores.shape[-1]
    if seq_len_q > 1:
        mask = np.triu(np.ones((seq_len_q, seq_len_k), dtype=np.float32), k=seq_len_k - seq_len_q + 1)
        scores = scores + mask * (-1e9)
    ...
```

- 形状：`query (B, H, Sq, D)`、`keys (B, H, Sk, D)` → `scores (B, H, Sq, Sk)`。
- **mask 的偏移量 `k = Sk − Sq + 1`**：当 query 是序列的最后 `Sq` 个位置、key 是全部 `Sk` 个位置时，第 i 个 query 的绝对位置是 `Sk − Sq + i`，它只能看到列号 ≤ 该位置的 key。`np.triu(..., k=Sk−Sq+1)` 正好屏蔽这些"未来列"。无缓存的普通 prefill 时 `Sk = Sq`，退化为常见的 `k=1`。
- decode 时 `Sq = 1`，新 token 可以看到全部历史，不需要 mask，所以直接跳过。
- 屏蔽值用 `-1e9` 而不是 `-inf`，避免整行都被屏蔽时出现 NaN；softmax 先减行最大值保证数值稳定。

### 3.3 MultiHeadAttention.forward：缓存的读写时机

```python
    def forward(self, x, kv_cache=None, layer_idx=0):
        batch, seq_len, d_model = x.shape
        Q = np.matmul(x, self.W_q).reshape(batch, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = ...
        V = ...
        if kv_cache is not None:
            K_full, V_full = kv_cache.update(layer_idx, K[0], V[0])
            K = K_full[np.newaxis, :, :, :]
            V = V_full[np.newaxis, :, :, :]
            if seq_len == 1:
                kv_cache.advance(1)
        attn_out = scaled_dot_product_attention(Q, K, V)
        attn_out = attn_out.transpose(0, 2, 1, 3).reshape(batch, -1, d_model)
        return np.matmul(attn_out, self.W_o)
```

- 拆头：`(B, S, d) → (B, S, H, D) → (B, H, S, D)`；演示 `d_model = 64, H = 4, D = 16`。
- **prefill**：`seq_len = 8`，写入 8 个位置，`advance` 由 `__main__` 在外部手动调用 `cache.advance(seq_len)`。
- **decode**：`seq_len = 1`，只为新 token 算 Q/K/V，写入后与历史拼接；`advance(1)` 在函数**内部**调用。
- 这种"prefill 外部推进、decode 内部推进"的不对称设计埋下了 bug：
  - ⚠️ **多层时重复推进**：每一层的 `forward` 都会 `advance(1)`。实测 2 层模型 prefill 8 个 token 后 decode 1 个 token，`seq_len` 变成 10 而不是 9；第 1 层把 K/V 写到错误位置，并在注意力里看到一个全零的"空洞"。
  - ⚠️ **只缓存第 0 个样本**：`K[0]` 丢掉了 batch 中的其他样本，`K_full[np.newaxis]` 再被广播给整个 batch。batch = 2 时第 2 个样本用的是第 1 个样本的 K/V，程序不报错但结果错误（实测与无缓存结果不一致）。
- 正确性验证（我们额外做的）：对同一序列，"prefill 8 + 逐个 decode 4" 的输出与"一次性无缓存前向"的最后 4 行相比，最大差异约 1e−3（来自 FP16 缓存）。这类"缓存 vs 全量"的一致性测试是实现 KV cache 时最重要的单元测试。
- `np.sqrt(2.0 / d_model)` 的缩放是 He 初始化；与推理优化无关，只是让数值不至于过大或过小。

### 3.4 Static 与 continuous batching 模拟

```python
def simulate_static_batching(requests, batch_size):
    queue = sorted(requests, key=lambda r: r.arrival_step)
    while queue:
        batch = []
        while queue and len(batch) < batch_size:
            r = queue.pop(0)
            r.start_step = max(step, r.arrival_step)
            batch.append(r)
        if batch:
            step = max(step, max(r.start_step for r in batch))
            max_output = max(r.output_tokens for r in batch)
            for r in batch:
                r.tokens_generated = r.output_tokens
                r.end_step = step + max_output
            step += max_output
```

- 按到达顺序每次取 8 个请求，等**最后一个到达**才开始；整批跑 `max_output` 步；**所有请求的结束时间都是整批结束时间**。
- `queue.pop(0)` 对列表是 O(n) 操作，大规模模拟应改用 `collections.deque`。

```python
def simulate_continuous_batching(requests, batch_size):
    while queue_idx < len(queue) or active or waiting:
        while queue_idx < len(queue) and queue[queue_idx].arrival_step <= step:
            waiting.append(queue[queue_idx]); queue_idx += 1
        while waiting and len(active) < batch_size:
            r = waiting.pop(0); r.start_step = step; active.append(r)
        if not active:
            ...  # 没有活跃请求时跳到下一个到达时刻
        for r in active:
            r.tokens_generated += 1
        done = [r for r in active if r.is_done()]
        for r in done:
            r.end_step = step + 1
            completed.append(r)
        active = [r for r in active if not r.is_done()]
        step += 1
```

- 每一步：① 把已到达的请求放入 `waiting`；② 用 `waiting` 补满空槽；③ 所有活跃请求各生成 1 个 token；④ 完成的请求立刻移出。这就是讲义的 "iteration-level batching"。
- 时间模型：**每步耗时相同，与 batch 大小无关**——对应 decode memory-bound 的假设（一次读取权重，服务整批）。
- 简化：`prompt_tokens = 100` 从未被使用，即**完全忽略 prefill**；也没有 KV cache 显存约束。真实系统中新请求的 prefill 会占用该迭代的算力，这正是 chunked prefill 要解决的问题。
- `make_requests` 用 `np.random.RandomState(42)`：到达时刻 `randint(0, 20)`，输出长度 `int(pareto(1.5) × 15) + 5`、上限 200（重尾分布，少数请求很长）。打印长度统计时又调用了三次 `make_requests()`，因为种子固定所以结果一致，只是多余的计算。

### 3.5 batching_stats

```python
    latencies = [r.end_step - r.arrival_step for r in completed]
    total_time = max(r.end_step for r in completed) - min(r.arrival_step for r in completed)
    total_tokens = sum(r.output_tokens for r in completed)
```

- 延迟 = 完成时刻 − 到达时刻，包含排队时间。`np.percentile(latencies, 99)` 在只有 30 个样本时基本等于最大值附近的插值，P99 在小样本上很不稳定。
- 吞吐 = 总输出 token / 总时间（单位：token/步）。

### 3.6 前缀缓存（trie）

```python
    def lookup(self, token_ids):
        node, depth = self._walk(token_ids)
        if depth > 0:
            self.hits += 1
            ...  # 再走两遍路径：一遍累加 hit_count，一遍收集 kv_data
            return depth, kv_entries
        self.misses += 1
        return 0, []

    def insert(self, token_ids, kv_per_token):
        node = self.root
        for i, tid in enumerate(token_ids):
            if tid not in node.children:
                if self.total_entries >= self.max_entries:
                    return i
                node.children[tid] = TrieNode()
                self.total_entries += 1
            node = node.children[tid]
            if i < len(kv_per_token):
                node.kv_data = kv_per_token[i]
        return len(token_ids)
```

- trie 的每条从根出发的路径就是一个 token 前缀，节点上存该位置的 KV。查找时沿着请求的 token 走，能走多深就复用多少——这就是 RadixAttention "部分前缀匹配"的思想。KV 能复用的前提是"前面所有 token 完全相同"，trie 路径恰好保证了这一点。
- `dict` 作为子节点表，查找为 O(1)；整个 lookup 是 O(匹配长度)，但代码把路径走了三遍。
- ⚠️ 只要匹配到 **1 个** token 就记为一次命中；更合理的统计是"命中的 token 比例"。
- ⚠️ 未命中的请求不会被插入；容量满时 `insert` 直接停止（只插入一部分），没有淘汰策略（讲义练习 4 要求实现 LRU）；`hit_count` 被累加但从未使用。
- 真实实现：RadixAttention 使用**压缩的**基数树（一条边可以对应一段 token），KV 存放在分页的 block 中，节点记录 block 引用与引用计数，配合 LRU 淘汰。
- 演示设计让结果"必然"完美：3 个系统提示的 token 范围是 100–479，用户 token 是 500–999，两者不重叠，所以每次匹配都正好停在系统提示末尾，命中率 100%。
- ⚠️ SUMMARY 的第 3 条 "PagedAttention eliminates memory fragmentation (simulated via trie)" 是错误的：trie 模拟的是 prefix caching；本文件**没有实现** PagedAttention（讲义学习目标里提到的 "Implement ... PagedAttention concepts" 也没有对应代码）。

### 3.7 投机解码模拟器

```python
class DraftModel:
    def generate(self, context, num_tokens):
        return np.random.randint(0, self.vocab_size, size=num_tokens)
    def get_probs(self, context, token):
        return np.random.dirichlet(np.ones(self.vocab_size))

def speculative_decode(draft_model, target_model, context, num_speculative=5,
                       draft_cost=1.0, target_cost=10.0, verify_cost=12.0):
    while total_tokens < max_tokens:
        draft_tokens = draft_model.generate(context, num_speculative)
        total_cost += draft_cost * num_speculative
        target_probs = target_model.get_probs(context, draft_tokens)
        total_cost += verify_cost
        accepted = 0
        for i, token in enumerate(draft_tokens):
            draft_p = draft_model.get_probs(...)
            target_p = target_probs[i]
            r = np.random.random()
            if r < draft_model.acceptance_rate:
                accepted += 1; context.append(token); total_tokens += 1
            else:
                new_token = np.random.choice(draft_model.vocab_size, p=target_p)
                context.append(new_token); total_tokens += 1
                break
        accepted_counts.append(accepted)
        if accepted == num_speculative:
            bonus_token = ...; total_tokens += 1
```

- **成本模型**：每轮草稿 K 个 token 花 `K × 1.0`，目标模型一次验证花 12.0（比顺序解码一步的 10.0 略贵，因为要多处理 K 个位置，但仍主要是读一遍权重）。顺序解码每 token 花 10.0。
- **每轮至少产出 1 个 token**：拒绝时从目标分布重采样 1 个；全部接受时目标模型在同一次验证中顺带给出第 K+1 个位置的分布，额外得到 1 个 "bonus token"（不额外计费，这是对的）。
- **期望值**（单 token 接受率 α，第一次拒绝即停止）：
  - 每轮接受数 `Σ α^i = α(1 − α^K)/(1 − α)`；
  - 每轮产出 `(1 − α^{K+1})/(1 − α)`；
  - 加速比 `10 × 产出 / (K + 12)`。
  α = 0.78、K = 5 时分别为 2.52、3.52、2.07x，与实测 2.54、2.08x 吻合（推导见测验 Q9）。
- ⚠️ 打印的 "Accept Rate" 是 `平均接受数 / K`，不是单 token 接受率，所以 0.78 的配置显示为 50.8%。
- ⚠️ **不是无损的投机采样**：接受判定 `r < acceptance_rate` 与 p、q 无关；`draft_p` 算了不用；拒绝后从 p 而不是 `norm(max(0, p − q))` 重采样；草稿 token 是均匀随机而不是来自 q。讲义说投机解码 "mathematically exact"，对真实算法成立，对这个模拟器不成立。
- ⚠️ N-gram 的草稿几乎免费，但代码仍按每 token 1.0 计费，低估了它的加速比（`draft_cost = 0` 时理论约 1.61x）。
- `max_tokens = 100` 是软上限，最后一轮可能超出（`total_tokens` 可达 100 + K）。
- `np.random.dirichlet(np.ones(V))`：从"对称 Dirichlet(1)"中采一个随机的概率分布，相当于在概率单纯形上均匀取点。

### 3.8 KV 显存与容量规划

```python
def kv_cache_memory(config, seq_len, dtype_bytes=2):
    per_token = 2 * config["num_layers"] * config["num_kv_heads"] * config["head_dim"] * dtype_bytes
    ...
        "total_gb": total / (1024 ** 3),

def memory_budget(config, gpu_memory_gb, model_dtype_bytes=2, kv_dtype_bytes=2):
    model_memory_gb = config["model_params_b"] * 1e9 * model_dtype_bytes / (1024 ** 3)
    overhead_gb = gpu_memory_gb * 0.1
    available_for_kv = gpu_memory_gb - model_memory_gb - overhead_gb
    ...
    max_tokens = int(available_for_kv * (1024 ** 3) / per_token)
```

- 用的是 `num_kv_heads`，正确考虑了 GQA（对比第 04 节代码用查询头数导致高估）。Llama 3 70B：320 KB/token，4K → 1.25 GiB、128K → 40 GiB。
- 单位都是 GiB（KB 也是 KiB）。`gpu_memory_gb = 80` 直接当 GiB 用；A100 80GB 的实际容量约为 80 GiB，所以这里口径基本一致。
- 预留 10% 给激活、CUDA context、框架开销；多卡时直接把显存相加，隐含了"张量并行完美切分"的假设，没有计入通信缓冲。
- `"gqa"` 字段没有被使用；`GPT-4-est` 是非官方的估计配置（讲义也只写作 "est"），不应当作事实引用。
- 讲义练习 1 要求比较 FP16 / FP8 / INT4 的 KV cache，只需改 `kv_dtype_bytes`。

### 3.9 ops:byte 表

```python
    a100_tflops = 312
    a100_bandwidth_tbs = 2.0
    crossover = a100_tflops / a100_bandwidth_tbs          # 156
    for name, ops_per_byte in scenarios:
        bound = "Compute" if ops_per_byte >= crossover else "Memory"
        util = ops_per_byte / crossover * 100 if bound == "Memory" else 100.0
```

- 拐点 `312e12 / 2e12 = 156 FLOPs/byte`。
- 把 "decode, batch = B" 的 ops:byte 设为 B：FP16 权重每个参数 2 字节，每个 token 一次乘加 2 FLOPs，所以每字节 FLOPs = B。这个"巧合"只对 FP16/BF16 权重成立；INT4 权重时变为 4B。
- "Utilization" 是 roofline 给出的**算力利用率上限**，实际还要打折。
- ⚠️ 只考虑了权重读取。decode 中每个请求的 KV cache 读取不能跨请求摊薄，其 ops:byte 约为常数，所以长上下文下即使 batch 很大，注意力部分仍是带宽受限（见测验 Q12）。
- 讲义表格写 batch = 256 是 "Transitioning"，代码判为 Compute；roofline 是理想模型，拐点附近两者都受影响。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| KV cache 预分配到 `max_seq_len` | 实现最简单，写入 O(1) | 预留浪费 + 碎片；生产用 PagedAttention 按页分配 |
| 缓存无 batch 维、只写 `K[0]` | 单请求演示 | batch > 1 时静默出错；应加 batch 维或每请求一个页表 |
| decode 在层内 `advance`、prefill 在外部 `advance` | 演示方便 | 多层时重复推进；应在所有层之后统一推进 |
| FP16 缓存 | 模拟真实显存占用 | 引入约 1e−3 误差；这是 KV 精度与显存的权衡 |
| 右下对齐因果 mask | 同时支持无缓存 prefill 与带缓存的多 token 追加 | 无 |
| 调度模拟：每步等时、忽略 prefill | 聚焦"槽位利用率" | 高估 continuous 的收益；真实系统要处理 prefill 抢占、显存上限 |
| trie 按 token 存 KV | 直观展示最长前缀匹配 | 节点过多、无淘汰；生产用压缩基数树 + 分页 block + LRU |
| 投机解码用固定接受概率 | 直接控制接受率，便于展示成本模型 | 不是无损采样；不能用来验证正确性 |
| 统一 `draft_cost = 1.0` | 简化 | 低估 n-gram 的收益 |
| ops:byte = batch | FP16 下恰好成立 | 忽略 KV 读取与权重精度变化 |
| 容量规划按 GiB、10% 预留 | 常见经验值 | 未计通信缓冲、激活峰值；需以压测为准 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 预分配数组 | `np.zeros((L, H, S, D), dtype=np.float16)` | 一次性分配，后续切片写入 |
| 切片赋值 | `self.k_cache[layer_idx, :, self.seq_len:end, :] = new_keys` | 多维切片原地写入；返回切片是视图 |
| `np.dtype(...).itemsize` | `np.dtype(self.dtype).itemsize` | 每个元素的字节数（float16 为 2） |
| `.nbytes` | `self.k_cache.nbytes` | 数组占用的总字节数 |
| `np.newaxis` | `K_full[np.newaxis, :, :, :]` | 增加一个长度为 1 的维度（等价于 `None`） |
| `np.matmul` 与批量矩阵乘 | `np.matmul(query, keys.transpose(0, 1, 3, 2))` | 前面的维度作为 batch，最后两维做矩阵乘 |
| `np.triu(..., k=...)` | `np.triu(np.ones((Sq, Sk)), k=Sk - Sq + 1)` | 取上三角，`k` 控制对角线偏移 |
| `.astype` | `np.random.randn(...).astype(np.float32)` | 类型转换 |
| `sorted` + `lambda` | `sorted(requests, key=lambda r: r.arrival_step)` | 按属性排序，返回新列表 |
| `list.pop(0)` | `queue.pop(0)`、`waiting.pop(0)` | 取出队首（O(n)，大规模用 `deque.popleft()`） |
| 生成器表达式 | `max(r.start_step for r in batch)`、`sum(r.output_tokens for r in completed)` | 不建中间列表的聚合 |
| 列表推导式过滤 | `[r for r in active if not r.is_done()]` | 过滤出未完成的请求 |
| 嵌套函数 + 默认参数 | `def make_requests(n=30, seed=42):` | 在 `__main__` 块内定义的局部函数 |
| `np.random.RandomState` | `rng = np.random.RandomState(seed)` | 独立的随机数生成器，结果可复现 |
| `rng.pareto(a)` | `int(rng.pareto(1.5) * 15) + 5` | 重尾分布，模拟长短不一的输出 |
| `np.percentile` / `np.median` | `np.percentile(latencies, 99)` | 分位数 |
| 字典作为子节点表 | `node.children[tid] = TrieNode()` | trie 的标准实现 |
| `enumerate` | `for i, tid in enumerate(token_ids)` | 同时取下标和值 |
| `np.random.dirichlet` | `np.random.dirichlet(np.ones(V))` | 随机生成一个概率分布 |
| `np.random.choice(n, p=...)` | `np.random.choice(vocab_size, p=target_p)` | 按给定概率采样 |
| 条件表达式 | `c / s if s > 0 else 0` | 防止除零 |
| f-string 格式符 | `{name:<20s}`、`{x:>10.1f}KB`、`{rate:>11.1%}`、`{n:>10d}`、`{30}` | 字符串左对齐、浮点、百分数、整数；`{30}` 直接插入字面量 |
| 嵌套字典 | `MODEL_CONFIGS["Llama-3-70B"]["num_layers"]` | 用字典描述配置 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行全部演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy 2.5，耗时约 1 秒），节选：

```text
STEP 1:
  Model                   Per Token     @ 4K ctx    @ 32K ctx   @ 128K ctx
  Llama-3-8B                128.0KB       0.50GB       4.00GB      16.00GB
  Llama-3-70B               320.0KB       1.25GB      10.00GB      40.00GB
  Llama-3-405B              504.0KB       1.97GB      15.75GB      63.00GB
  GPT-4-est                5760.0KB      22.50GB     180.00GB     720.00GB   ← 非官方估计配置，无 GQA

  GPU Config                   Model   KV Avail  @2K users  @4K users
  1xA100-80GB                 130.4GB   DOES NOT FIT
  2xA100-80GB                 130.4GB      13.6GB         21         10
  4xA100-80GB                 130.4GB     157.6GB        252        126
  8xH100-80GB                 130.4GB     445.6GB        712        356

STEP 2:
  KV cache after prefill: 8 tokens, 2048 bytes
  Decode step 1: cache=9 tokens, output shape=(1, 1, 64), used=2304 bytes
  ...
  Decode step 4: cache=12 tokens, output shape=(1, 1, 64), used=3072 bytes

STEP 3:  30 requests, batch_size=8   Output lengths: min=5, max=45, mean=15.0
  avg_latency    86.7 → 25.8   | p99_latency 132.0 → 57.1
  total_time    146.0 → 77.0   | throughput    3.1 → 5.8 (1.90x)

STEP 4:  Cache hit rate: 100.0%   Tokens saved: 11450   Avg per hit: 114.5   Trie entries: 330

STEP 5:
  Draft-target (8B->70B)          50.8%         2.54      2.08x
  EAGLE                           59.0%         3.54      2.52x
  N-gram lookup                   22.5%         0.90      1.19x

STEP 6:  Crossover 156
  Decode, batch=1     Memory    0.6%  |  batch=32   Memory 20.5%
  Decode, batch=128   Memory   82.1%  |  batch=256  Compute 100.0%
```

逐项解读：

- **STEP 1**：8B 与 Mistral 7B 都是 32 层、8 个 KV 头、head_dim 128，所以每 token 都是 128 KB。70B 的 128K 上下文 40 GiB 与讲义一致（注意：上一节讲义把"40GB"写成了 70B 在 **32K** 时的值，按本节公式 32K 只有 10 GiB）。容量表中 2×A100 只剩 13.6 GiB 给 KV，4K 上下文只能服务 10 个用户；4×A100 能服务 126 个，这与讲义"100 个 4K 用户需要约 128 GB KV"相吻合。
- **STEP 2**：每 token 256 字节（1 层 × 4 头 × 16 维 × 2(K,V) × 2 字节），8 → 12 个 token 线性增长。输出形状 prefill 为 `(1, 8, 64)`、decode 为 `(1, 1, 64)`：decode 每步只处理一个位置，这正是 KV cache 省下的计算。
- **STEP 3**：总输出 449 token。continuous 的 77 步接近下限 `⌈449/8⌉ = 57` 步，多出来的部分来自开头请求未到齐和结尾只剩长请求；static 的 146 步是每批都等最长请求。平均延迟降低 70%，主要来自"短请求不再陪跑"（以及 static 中短请求被记到整批结束）。
- **STEP 4**：100 次查找全部命中，平均每次复用 114.5 个 token（3 个提示长度 100/150/80，被随机选中）。trie 共 330 个节点 = 100 + 150 + 80，3 个提示之间没有共享前缀。
- **STEP 5**：三行数字与"截断几何分布"的理论值吻合（2.52 / 3.53 / 0.94 接受数，2.07x / 2.52x / 1.21x 加速比）。"Accept Rate" 列不是单 token 接受率。SUMMARY 中 "2-3x speedup" 对应的是前两种策略。
- **STEP 6**：batch = 1 时算力利用率上限仅 0.6%；batch = 128 达到 82%；≥ 156 后进入算力受限。这只是权重读取的视角，长上下文下 KV 读取会让拐点后移。

---

## 7. 动手改一改

1. **修 KVCache**：加 batch 维；把 `advance` 从注意力层移到模型层面（所有层前向之后统一推进）；写一个 2 层模型，断言"prefill + 逐步 decode"与"全量前向"的输出在 float32 缓存下误差小于 1e−5。
2. **讲义练习 1**：在 `memory_budget` 中比较 `kv_dtype_bytes = 2 / 1 / 0.5`（FP16 / FP8 / INT4），算出 Llama 3 70B 在 4×A100 上 4K 上下文的最大并发，验证"INT4 KV 约 4 倍容量"。
3. **讲义练习 2**：在两种调度器中记录每步的槽位占用率，用 50 个 Pareto 长度的请求画出利用率随时间变化的曲线；再给 continuous 加入 prefill 成本（例如新请求加入的那一步耗时按 `prompt_tokens / 512` 增加），观察收益变化。
4. **实现真正的投机采样**：草稿 token 从 q 采样；按 `min(1, p(x)/q(x))` 接受；拒绝时从 `norm(max(0, p − q))` 采样。用很多次实验统计输出 token 的经验分布，验证它与 p 一致（例如对小词表做卡方检验）。
5. **讲义练习 4（LRU 前缀缓存）**：给 trie 节点加"最后访问时间"，容量满时淘汰最久未用的叶子；生成 1,000 个请求，其中 60% 共享 5 个常见前缀，比较 `max_entries = 500` 与不限容量时的命中率。
6. **讲义练习 5（树形投机）**：每层 2 个分支、3 层共 8 个候选路径，统计每次验证的平均接受长度，与线性 K = 3 比较；再把 EAGLE 的接受率设为随深度递减，观察最优树形。

---

## 8. 常见坑

- **KV cache 推进时机错误**：在每一层里推进写指针，多层模型会错位。缓存的"写入位置"必须对所有层一致。
- **忘了 batch 维**：缓存只存一个样本，再靠广播给整个 batch，不报错但结果错。
- **不做"缓存 vs 全量重算"的一致性测试**：这是发现 KV cache bug 最直接的办法。
- **用查询头数估 KV cache**：GQA 模型应使用 KV 头数（Llama 3 70B 是 8，不是 64）。
- **混淆单 token 接受率与"平均接受数 / K"**：后者因为"首次拒绝即停止"会明显更低。
- **把固定概率接受当成投机解码**：真正的规则依赖 p 与 q，拒绝后要从残差分布采样，否则不再无损。
- **以为增大 batch 总能进入算力受限**：KV cache 读取不能摊薄，长上下文时 decode 始终受带宽影响。
- **把 trie 前缀缓存当作 PagedAttention**：前者省计算（复用前缀 KV），后者省显存（按页分配、消除碎片），二者可以组合，但不是一回事。
- **系统提示里放每次都变的内容**：时间戳、随机 ID 会让前缀缓存永远无法命中。
- **轻信讲义中的数字**：例如 "4,096-token prefill on a 70B model ~400ms on a single A100" 按 FLOPs 估算至少需要约 1.8 s，而且 70B FP16 放不进单卡；要养成自己估算的习惯。
- **中文讲义的机翻错误**：`docs/zh.md` 中 "The Ops:Byte Framework" 被译成"行动中心:网络框架"、"KV Cache from Scratch" 被译成"KV Cache 从剪辑"，阅读时以英文版为准。
