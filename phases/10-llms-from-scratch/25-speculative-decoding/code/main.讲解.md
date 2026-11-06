# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 25 节 Speculative Decoding 与 EAGLE ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`，或 `python main.py --vocab 64 --alpha 0.75 --k 4 --samples 50000 --seed 0` ｜ **依赖**：`numpy`（第三方）+ 标准库 `argparse`；无需 GPU、无需模型权重、无需网络

---

## 1. 这份代码在考察什么

这份代码不加载任何语言模型，而是在**与上下文无关的玩具分布**上，把 speculative decoding 的三件核心数学事实"跑出来"：

1. **精确拒绝规则是无损的**：按 `min(1, p/q)` 接受、拒绝时从 `(p − q)+` 采样，得到的 token 分布与直接从 target 采样一致。
2. **期望产出公式成立**：单 token 接受率为 α、draft 长度为 K 时，每次验证平均产出 `(1 − α^{K+1})/(1 − α)` 个 token，实测与公式吻合。
3. **树形验证的 mask 怎么构造**：给定分支因子建一棵候选树，生成"每个节点只看祖先"的 tree attention mask。

对应讲义的 The Exactness Rule、Expected Speedup、Tree Attention Verification 三节。

> 一句话：**用几十行 NumPy 证明"小模型猜、大模型验"可以既快又不改变分布，并给出加速有多少的定量公式**。同时要注意：讲义 "Build It" 描述的 GPT-2 蒸馏、top-p 树形 drafter、temperature 参数在代码里都没有实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_target` | 函数 | 随机 logits → softmax，得到 target 分布 p | target 模型 `M_p` |
| `make_draft` | 函数 | `a·p + (1−a)·uniform` 再乘随机噪声，得到 draft 分布 q | draft 模型 `M_q` |
| `sample` | 函数 | 按概率向量采样一个下标 | 采样 |
| `speculative_step` | 函数 | 一轮：draft K 个 → 逐个接受/拒绝 → 残差补位或 bonus token | 精确拒绝规则 |
| `total_variation` / `empirical_dist` | 函数 | TV 距离；样本 → 经验分布 | 分布比较 |
| `verify_distribution` | 函数 | 比较 plain 采样与 speculative 首 token 的经验分布 | 无损性验证 |
| `measure_alpha` | 函数 | 抽样估计单 token 接受率 | α |
| `expected_tokens` | 函数 | `(1 − α^{K+1})/(1 − α)` | 期望产出 |
| `measure_throughput` | 函数 | 跑 2000 轮，统计平均每轮产出 | 实测 tokens/verify |
| `build_tree` / `tree_attention_mask` / `validate_tree_mask` | 函数 | 建候选树、构造并检查祖先 mask | 树形验证 |
| `_positive_int` / `_unit_float` / `parse_args` | 函数 | 命令行参数解析与校验 | 工程细节 |
| `main` | 函数 | 串起以上步骤并打印 | 入口 |

数据流：`parse_args` → `make_target` → `make_draft` → `verify_distribution`（TV 检查）→ `measure_alpha` → `measure_throughput` vs `expected_tokens` → α 扫描表 → `build_tree` → `tree_attention_mask` → `validate_tree_mask`。

---

## 3. 逐段精讲

### 3.1 构造 target 与 draft

```python
def make_target(vocab: int, rng: np.random.Generator) -> np.ndarray:
    logits = rng.standard_normal(vocab) * 1.4
    e = np.exp(logits - logits.max())
    return e / e.sum()
```

- 标准正态 logits 乘 1.4 让分布有一定"尖度"，再做数值稳定的 softmax（先减最大值）。
- 形状 `(vocab,)`。注意它是一个**固定**分布，不依赖前文——真实 LLM 中 p 是 `p(· | x_{1:t})`，每个位置都不同。

```python
def make_draft(target, alpha_hint, rng):
    uniform = np.full(vocab, 1.0 / vocab)
    draft = alpha_hint * target + (1.0 - alpha_hint) * uniform
    noise = rng.uniform(0.95, 1.05, size=vocab)
    draft = draft * noise
    return draft / draft.sum()
```

- draft 是 target 与均匀分布的线性混合，再乘 ±5% 的噪声并重新归一化。混合系数越大，q 越接近 p。
- ⚠️ docstring 说"expected token-level acceptance is near alpha_hint"，但真实接受率 `Σ min(p, q)` 系统性**高于** hint：hint = 0.75 时精确值为 0.8955，hint = 0.1 时也有 0.621；hint = 1.0 时因为噪声反而到不了 1（0.988）。所以 `--alpha` 应理解为"混合系数"，不是"目标接受率"（见测验 Q8）。

### 3.2 一轮 speculative decoding

```python
def speculative_step(target, draft, K, rng):
    proposed: list[int] = []
    q_at: list[float] = []
    for _ in range(K):
        t = sample(draft, rng)
        proposed.append(t)
        q_at.append(float(draft[t]))
```

- 第 1 步：从 q 连续采 K 个 token，并记录每个 token 在 q 下的概率。真实系统里这是 draft 模型的 K 次自回归前向；这里 q 不随上下文变化，所以 K 次采样相互独立。

```python
    accepted: list[int] = []
    for k, tok in enumerate(proposed):
        ratio = float(target[tok]) / max(q_at[k], 1e-12)
        if rng.random() < min(1.0, ratio):
            accepted.append(tok)
        else:
            residual = np.maximum(target - draft, 0.0)
            s = residual.sum()
            if s == 0.0:
                accepted.append(sample(target, rng))
            else:
                accepted.append(sample(residual / s, rng))
            return accepted
    accepted.append(sample(target, rng))
    return accepted
```

- 第 2 步（在真实系统中是 target 的**一次** forward，这里 p 是现成的）：从左到右判定。
- `ratio = p(x)/q(x)`，`max(..., 1e-12)` 防止除零。以 `min(1, ratio)` 的概率接受。
- 拒绝时：残差 `(p − q)+` 用的是**整个向量**的逐点差，归一化后采 1 个替换 token，然后**立刻返回**——后面的 draft token 都作废，因为它们是以被拒绝的 token 为前缀生成的。
- `s == 0.0` 只在 p 与 q 逐点完全相同时出现，此时 ratio 恒为 1、根本不会走到拒绝分支，属于防御性代码。
- 全部接受：再从 p 采一个 bonus token（target 在第 K+1 个位置的预测"白送"）。所以每轮返回 1 到 K+1 个 token。
- 与讲义片段对比：讲义的 `residual = np.maximum(p_probs_all[k] - q_probs[k], 0)` 减的是**标量** `q_probs[k]`，是个 bug；本文件写对了。解析计算显示讲义写法会让输出分布偏离 p 约 0.019（TV），正确写法为 0（测验 Q9）。

### 3.3 无损性验证

```python
def verify_distribution(target, draft, K, n_samples, rng):
    vocab = target.size
    plain = [sample(target, rng) for _ in range(n_samples)]
    spec_first: list[int] = []
    while len(spec_first) < n_samples:
        toks = speculative_step(target, draft, K, rng)
        spec_first.append(toks[0])
    p_plain = empirical_dist(plain, vocab)
    p_spec = empirical_dist(spec_first, vocab)
    return total_variation(p_plain, target), total_variation(p_spec, target)
```

- 分别采 n 个 plain 样本和 n 个 speculative 首 token，转成经验分布，各自与真实 p 求 TV。
- `total_variation = 0.5 * Σ|p − q|`；`empirical_dist` 用 `np.bincount(..., minlength=vocab)` 计数后归一化。
- ⚠️ 三个局限（测验 Q11 详述）：
  1. 有限样本有噪声底：vocab = 32、n = 20,000 时即使完美采样 TV 也在 0.012–0.016，docstring 里的 "< 0.01" 阈值不成立；
  2. `main` 打印的 "delta TV" 是两个 TV 之差，不是两个分布之间的距离，方向相反的偏差会互相抵消；
  3. 只检验了每轮第一个 token。
- 更强的验证：直接解析计算 `min(p,q) + (1 − α)·residual` 与 p 对比（误差 1e-17 量级），或做卡方检验。

### 3.4 α 与吞吐

```python
def measure_alpha(target, draft, n_samples, rng):
    accepted = 0
    for _ in range(n_samples):
        t = sample(draft, rng)
        ratio = float(target[t]) / max(float(draft[t]), 1e-12)
        if rng.random() < min(1.0, ratio):
            accepted += 1
    return accepted / n_samples
```

- 蒙特卡洛估计 `α = E_{x~q}[min(1, p/q)] = Σ min(p, q) = 1 − TV(p, q)`。可以直接用 `np.minimum(target, draft).sum()` 精确算出（0.8955），抽样版本 0.897。

```python
def expected_tokens(alpha: float, K: int) -> float:
    if alpha >= 1.0:
        return float(K + 1)
    return (1.0 - alpha ** (K + 1)) / (1.0 - alpha)
```

- 推导：第 i 个 draft token 被"走到并接受"的概率为 α^i，期望产出 = 1（拒绝补位或 bonus 必有 1 个）+ Σ_{i=1..K} α^i = Σ_{i=0..K} α^i，即等比数列求和。
- `alpha >= 1.0` 单独处理，避免分母为 0。
- 这个公式假设各位置接受**独立同分布**。本文件中 q、p 与上下文无关，假设严格成立，所以实测与公式吻合；真实 LLM 中越靠后的位置通常越难被接受。

```python
def measure_throughput(target, draft, K, n_rounds, rng):
    total = 0
    for _ in range(n_rounds):
        total += len(speculative_step(target, draft, K, rng))
    return total / n_rounds
```

- 跑 2000 轮取平均产出，每轮对应真实系统中的 1 次 target forward。
- ⚠️ 这是"每次验证的 token 数"，不是墙钟加速比。真实加速要扣除 K 次 draft 前向：约 `E / (1 + K·c)`，c 为成本比（测验 Q12）。讲义里"cost_q·K + cost_p"那句话描述的就是这一点，但随后 3.36× 的结论默认 c ≈ 0。

### 3.5 候选树与 tree attention mask

```python
def build_tree(branch_factor):
    tree = [(-1, [])]
    frontier = [0]
    for depth, b in enumerate(branch_factor):
        next_frontier = []
        for parent in frontier:
            for _ in range(b):
                tree.append((parent, tree[parent][1] + [len(tree)]))
                next_frontier.append(len(tree) - 1)
        frontier = next_frontier
    return tree
```

- 每个节点存 `(父节点下标, 从根到自己的路径)`，根是 `(-1, [])`。按层（BFS）展开：第 d 层每个节点有 `branch_factor[d]` 个孩子。
- 细节：`tree[parent][1] + [len(tree)]` 在 `append` **之前**求值，此时 `len(tree)` 恰好是新节点的下标。`depth` 变量未被使用。
- `(3, 2, 2)` → 1 + 3 + 6 + 12 = 22 个节点；`(2, 2)` 的结构是 `[(-1, []), (0, [1]), (0, [2]), (1, [1, 3]), (1, [1, 4]), (2, [2, 5]), (2, [2, 6])]`。
- ⚠️ 这只是**树的形状**，节点上没有 token。讲义说的"带 top-p 分支的 EAGLE 式 drafter"并未实现。

```python
def tree_attention_mask(tree):
    n = len(tree)
    mask = np.zeros((n, n), dtype=np.int8)
    for i in range(n):
        cur = i
        while cur != -1:
            mask[i, cur] = 1
            cur = tree[cur][0]
    return mask
```

- 从每个节点沿父指针走到根，把路径上的节点（含自己）标 1。`(2, 2)` 树的 mask：

```text
[[1 0 0 0 0 0 0]
 [1 1 0 0 0 0 0]
 [1 0 1 0 0 0 0]
 [1 1 0 1 0 0 0]
 [1 1 0 0 1 0 0]
 [1 0 1 0 0 1 0]
 [1 0 1 0 0 0 1]]
```

  节点 3 只看 {0, 1, 3}，看不到兄弟分支 2、5、6——这就是"多条候选路径在一次 forward 里互不干扰"的原因。
- 因为节点按 BFS 顺序编号，父节点下标永远小于子节点，mask 是下三角的，可以看作"稀疏化的因果 mask"。
- ⚠️ 与真实实现的差距：真实验证时每个树节点还要看**全部前缀（prompt + 已生成 token）的 KV**，mask 应为 `[前缀全 1 | 树内祖先 mask]`；同一深度的节点要共享 position id。
- ⚠️ `validate_tree_mask` 用和构造时**完全相同的方法**（沿父指针收集祖先）再算一遍并比较，属于同义反复，几乎不可能失败。更有意义的检查是：mask 下三角、每行 1 的个数 = 深度 + 1、兄弟节点之间为 0。

### 3.6 参数解析与主函数

```python
def _unit_float(value: str) -> float:
    f = float(value)
    if not (0.0 < f <= 1.0):
        raise argparse.ArgumentTypeError(f"value must be in (0, 1], got {f}")
    return f

parser.add_argument("--vocab", type=lambda v: _positive_int(v, minimum=2), default=32, ...)
```

- `type=` 可以是任意"字符串 → 值"的函数；抛 `ArgumentTypeError` 时 argparse 会打印友好的错误信息并退出。
- `lambda v: _positive_int(v, minimum=2)` 把带关键字参数的校验函数包装成单参数函数。`minimum` 是**仅限关键字参数**（签名中的 `*`）。
- `main` 中所有随机性都来自同一个 `np.random.default_rng(args.seed)`，因此结果可复现；但各步骤共享同一个生成器，改动前面的样本数会改变后面所有数字。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用固定的玩具分布代替 LM | 数学一目了然，1 秒跑完 | 位置间独立，公式"必然"吻合；真实系统需用 p(·\|前缀)、q(·\|前缀) |
| draft = p 与均匀分布的混合 | 用一个参数控制 q 与 p 的接近程度 | 参数名 `--alpha` 与真实接受率不等，易误解 |
| 残差用整个向量 `target - draft` | 精确规则的正确实现 | 真实系统需为每个位置保存 draft 的完整分布（显存/带宽开销） |
| 用经验 TV 检验无损 | 直观 | 受抽样噪声限制，阈值 0.01 不成立；应改用解析分布或假设检验 |
| `expected_tokens` 不计 draft 成本 | 先讲清楚核心公式 | 选 K 时必须用 `E/(1+Kc)`，否则 K 越大越好的错误结论 |
| 树只建形状 + 祖先 mask | 展示 tree attention 的拓扑本质 | 无前缀列、无 position id、无 token、无"最长被接受分支"选择；生产由 vLLM/SGLang/TensorRT-LLM 实现 |
| 全局一个 RNG + 种子 | 可复现 | 步骤之间互相影响随机流 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可在旧版本 Python 中使用 `list[int]` 等写法 |
| 类型注解 | `def sample(probs: np.ndarray, rng: np.random.Generator) -> int:` | 标注参数和返回值类型，不影响运行，便于阅读和静态检查 |
| 内置泛型注解 | `list[int]`、`tuple[float, float]`、`list[tuple[int, list[int]]]` | Python 3.9+ 可直接用内置类型做泛型 |
| 新式随机数生成器 | `rng = np.random.default_rng(args.seed)`、`rng.choice(n, p=probs)`、`rng.random()` | 推荐替代 `np.random.seed`；生成器对象可以传来传去 |
| `np.full` / `np.maximum` | `np.full(vocab, 1.0 / vocab)`、`np.maximum(target - draft, 0.0)` | 填充常数数组；逐元素取最大值，实现"取正部" |
| `np.bincount` | `np.bincount(samples, minlength=vocab)` | 统计每个非负整数出现的次数，`minlength` 保证长度为 vocab |
| `.astype` | `.astype(np.float64)`、`dtype=np.int8` | 转换/指定数组元素类型 |
| `enumerate` | `for k, tok in enumerate(proposed):` | 同时拿到下标和元素 |
| 提前 `return` | 拒绝分支里 `return accepted` | 在循环中直接结束函数 |
| 集合推导式 | `{j for j in range(n) if mask[i, j] == 1}` | 生成 set，用于和祖先集合比较 |
| 列表推导式 | `[sample(target, rng) for _ in range(n_samples)]` | `_` 表示不用的循环变量 |
| `while` 循环 + 哨兵 | `while cur != -1: ... cur = tree[cur][0]` | 沿父指针走到根（根的父为 -1） |
| 仅限关键字参数 | `def _positive_int(value: str, *, minimum: int = 1)` | `*` 之后的参数必须写成 `minimum=2` |
| `lambda` | `type=lambda v: _positive_int(v, minimum=2)` | 匿名函数，常用于把多参数函数包成单参数 |
| `argparse` | `parser.add_argument("--k", type=..., default=4, help=...)`、`args.k` | 命令行参数解析，`--k` 对应属性 `args.k` |
| 异常 | `raise argparse.ArgumentTypeError(...)` | argparse 捕获后打印错误并退出 |
| f-string 格式符 | `{tv_plain:.4f}`、`{a:.2f}`、`{mask.shape}`、`{mask.sum(axis=1).tolist()}` | 小数位、表达式直接嵌入 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行（本讲解的验证脚本就是 import 后调用各函数） |

---

## 6. 运行结果解读

实际运行（Python 3.13.16 + NumPy，`python3 main.py`，约 1.3 秒）：

```text
distribution check (n=20000):
  TV(plain_target_sampling, target)       = 0.0169   ← 完美采样器的噪声底，已 > 0.01
  TV(speculative_sampling, target)         = 0.0141   ← 同一量级，看不出偏差
  delta TV (spec vs plain)                 = 0.0028   ← 两个 TV 之差，不是分布距离

alpha measurement (vocab=32, alpha hint=0.75):
  measured alpha = 0.897                     ← 精确值 Σmin(p,q) = 0.8955，远高于 hint

throughput at K=4:
  measured E[tokens/verify]  = 4.045
  predicted E[tokens/verify] = 4.075  (1 - a^(K+1)) / (1 - a)   ← 公式吻合（i.i.d. 设定下必然）

alpha sweep, K=4:
  alpha=0.30  expected_tokens=1.43
  alpha=0.50  expected_tokens=1.94
  alpha=0.70  expected_tokens=2.77
  alpha=0.85  expected_tokens=3.71
  alpha=0.95  expected_tokens=4.52          ← 上限是 K+1 = 5

tree drafting demo: depth-3 tree, branch=(3, 2, 2)
  total candidate nodes: 22 (one verify pass covers all)
  mask shape: (22, 22)
  mask correctness vs ancestor sets: True
  attends-per-node (rows): [1, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
```

用讲义建议参数 `--vocab 64 --alpha 0.75 --k 4 --samples 50000` 运行：两个 TV 分别为 0.0143、0.0127（仍 > 0.01），α = 0.879，实测/预测产出 3.937 / 3.926。

逐项解读：

- **分布检查**：两个 TV 都在 0.014–0.017，说明 speculative 与 plain 在噪声范围内不可区分；但"< 0.01"并没有达到，原因是抽样噪声，不是算法错误。我们另外做了解析计算，正确规则下输出分布与 p 的 TV 为 1.4e-17，这才是"无损"的严格证据。
- **α = 0.897**：比 hint 高，原因见 3.1。若想得到接受率约 0.75 的 draft，hint 需要设得更低（hint = 0.3 时 α ≈ 0.70）。
- **吞吐**：α ≈ 0.8955、K = 4 时公式给出 4.075，实测 4.045，误差在 2000 轮的抽样噪声内。这一行对应"每次 target forward 产出 4 个 token"——若 draft 成本可忽略，就是约 4 倍的 decode 加速。
- **α 扫描**：α 从 0.5 提到 0.95，产出从 1.94 增到 4.52，体现讲义"a good draft is everything"。
- **树**：22 个节点（21 个候选 token）在一次 forward 里被验证；每行 1 的个数 = 深度 + 1。

---

## 7. 动手改一改

1. **解析验证无损**：写 `exact_output_dist(p, q) = np.minimum(p, q) + (1 − α)·residual`，打印与 p 的最大绝对误差；再把残差换成讲义片段里的"减标量"写法，或换成"拒绝后从 p 重采"，观察 TV 分别变成约 0.019 和 0.040。
2. **修正 alpha 参数**：给 `make_draft` 加一个二分搜索，找到混合系数使 `Σ min(p, q)` 恰好等于用户输入的 α（讲义练习 2 的前置工作）。
3. **最优 K**：实现测验 Q12 的 `best_k(alpha, c)`，对 α ∈ {0.5, 0.7, 0.9}、c ∈ {0, 0.05, 0.1} 打印最优 K 与加速比，并用 matplotlib 画出 `E/(1+Kc)` 随 K 的曲线。
4. **温度实验**：给 `make_target` / `make_draft` 增加 temperature（对 log 概率除以 T 再 softmax），扫描 T ∈ {0.3, 0.5, 1.0, 1.5, 2.0} 下的 α。在玩具分布上你会看到 α 约为 0.919、0.909、0.895、0.914、0.929——并不"崩溃"，思考讲义练习 5 的结论在什么条件下才成立（测验 Q16）。
5. **带前缀的树 mask**：给 `tree_attention_mask` 增加 `prefix_len` 参数，返回 `(n, prefix_len + n)` 的 mask（前缀列全 1），并为每个节点输出 position id = `prefix_len + depth`。
6. **进阶（讲义练习 3/4）**：用 Hugging Face 的 GPT-2 small 作 draft、GPT-2 medium 作 target（二者 tokenizer 相同），实现真正依赖上下文的 `speculative_decode`，统计真实 α 随位置的衰减，并与公式预测比较。

---

## 8. 常见坑

- **残差减成了标量**：保存的是 `probs[t]` 而不是整个 `probs`，残差形状错误，分布悄悄偏移（讲义片段即为此例）。
- **拒绝后从 p 重新采样**：看起来"更接近 target"，实际会让 q 高估的 token 被重复计数，TV ≈ 0.04（本例）。
- **拒绝后没有 `return`**：继续判定后面的 draft token 是错的——它们的前缀已经变了。
- **忘了 bonus token**：全部接受时只产出 K 个而不是 K+1 个，期望产出少了 α^K（α = 0.8、K = 4 时从 3.36 降到 2.95），白白浪费 target 已经算好的第 K+1 个位置。
- **把 tokens/verify 当成墙钟加速比**：没扣 draft 成本，也没考虑高并发下 verifier 变成 compute-bound。
- **用经验 TV 设硬阈值**：阈值低于抽样噪声底时，正确实现也会"失败"；反过来，噪声大时小偏差也测不出来。
- **draft 与 target tokenizer 不一致**：token id 对不上，接受规则完全失效；生产中必须逐字节核对词表。
- **树验证只用树内 mask**：漏了前缀列或 position id 设成展平下标，target 的打分就不是真实条件分布。
