# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 05 节 自主研究 Agent——AI-Scientist 级系统 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`heapq`、`random`、`dataclasses`、`typing`），不调用 LLM、不启动 Docker、不跑 PyTorch

---

## 1. 这份代码在考察什么

讲义的系统包含文献检索、实验树搜索、沙箱执行、视觉反馈 writer、reviewer ensemble、red team 和可复现包。`main.py` 的 docstring 写明只实现其中的"hard architectural primitive"：**带预算的 best-first 实验树搜索**，LLM 规划器和真实实验都用桩（stub）代替：

1. **实验节点**：`Node` 记录假设、配置、结果、成本、novelty、quality、失败原因。
2. **expand**：每个子节点只改一个配置维度（讲义第 3 步 "one config change per child"）。
3. **execute**：`run_experiment` 用公式 + 噪声"伪造"一个 loss，并模拟 10% 的 OOM 失败。
4. **verify**：失败或 loss 发散的节点不再展开。
5. **调度**：用 `heapq` 维护优先队列，按 `0.4·novelty + 0.5·quality + 0.1·budget` 排序；预算或节点数用完即停。
6. **选分支**：在成功节点里选 quality 最高的，沿父指针回溯到根。

> 一句话：**这是"plan → execute → verify → 打分 → 再展开"循环的骨架**。但仔细跑一遍会发现：它实际是广度优先、只跑了 4 个实验、子节点里有重复配置、最佳结果来自噪声——这些"假象"恰好是真实研究 agent 最需要防范的问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Node` | dataclass | 实验节点；`score(remaining)` 计算优先级 | 实验规格 + 打分函数 |
| `expand` | 函数 | 3 种 sparsity × 原 lr、2 种 lr × 原 sparsity，共 5 个子节点 | plan（小步修改） |
| `run_experiment` | 函数 | 伪造 loss、成本、quality、novelty，10% 概率 OOM | execute（沙箱执行的替身） |
| `verify` | 函数 | 失败或 loss > 4.0 返回 False | verify |
| `Tree` | dataclass | 节点表、堆 frontier、预算、`push`/`pop` | 搜索状态 |
| `tree_search` | 函数 | 主循环：pop → 运行 → verify → expand → push | best-first 树搜索 |
| `best_branch` | 函数 | 取 quality 最高的成功节点，回溯到根 | 选最佳分支交给 writer |
| `main` | 函数 | 种子 7，跑一次搜索并打印摘要 | 演示 |

数据流：种子想法 → 根节点（`sparsity_top=8, lr=3e-4`）入堆 → 循环 { 出堆 → `run_experiment` → 记账 → `verify` → `expand` → 子节点入堆 } → 停止 → `best_branch` → 打印（writer/reviewer/red team 未实现）。

---

## 3. 逐段精讲

### 3.1 `Node` 与打分函数

```python
@dataclass
class Node:
    node_id: int
    parent: int | None
    hypothesis: str
    config: dict[str, object]
    result: dict[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0
    novelty: float = 0.5
    quality: float = 0.0
    failure: str | None = None

    def score(self, remaining_budget: float) -> float:
        budget_weight = min(1.0, remaining_budget / 10.0)
        return self.novelty * 0.4 + self.quality * 0.5 + budget_weight * 0.1
```

- `parent: int | None` 用 ID 而不是对象引用指向父节点，所有节点存在 `Tree.nodes` 字典里——这种"扁平存储 + ID 引用"便于序列化成讲义要求的 trace JSON。
- 打分是**加权和**：novelty 0.4、quality 0.5、预算 0.1（与 skill 文件一致）；讲义 Concept 与 Key Terms 写的是 "novelty × quality × budget" 的乘积形式，两者不一致。
- `budget_weight = min(1, 剩余/10)`：剩余预算 ≥ $10 时恒为 1，只有最后 $10 才开始下降。
- ⚠️ 新节点默认 `novelty=0.5, quality=0.0`，入队分数 = `0.2 + 0 + 0.1 = 0.3`，**所有未运行的子节点同分**。这是后面"退化为广度优先"的根源。
- 根节点：`novelty=1.0, quality=0.5` → `0.75`。

### 3.2 `expand`：一次只改一个维度

```python
def expand(node: Node, next_id: int) -> list[Node]:
    children: list[Node] = []
    base_cfg = node.config
    for sp in (4, 8, 16):
        cfg = dict(base_cfg, sparsity_top=sp)
        children.append(Node(node_id=next_id, parent=node.node_id,
                             hypothesis=f"sparsity top-{sp}", config=cfg))
        next_id += 1
    for lr in (3e-4, 1e-3):
        cfg = dict(base_cfg, lr=lr)
        ...
    return children
```

- `dict(base_cfg, sparsity_top=sp)`：复制父配置并覆盖一个键，父节点的 `config` 不受影响——"one config change per child"。
- `next_id` 是局部变量，函数内部的 `+= 1` 不会影响调用方；调用方用 `next_id += len(children)` 同步。
- ⚠️ **重复配置**：子节点不检查"新值是否等于旧值"。根节点 `sparsity_top=8, lr=3e-4`，于是 "sparsity top-8" 和 "lr=0.0003" 这两个子节点与根**完全相同**。5 个子节点里只有 3 个是新实验。
- ⚠️ 整个搜索空间只有 `3 × 2 = 6` 种配置，无论树多深都在这 6 个点上打转；真实系统由 LLM 提出开放式修改（换优化器、消融组件），空间大得多。
- 讲义练习 1 让你"找出重复浪费的算力"——这份代码本身就是现成的例子。

### 3.3 `run_experiment`：伪造的实验结果

```python
def run_experiment(node: Node, rng: random.Random) -> None:
    sp = node.config.get("sparsity_top", 8)
    lr = node.config.get("lr", 3e-4)
    ideal_sp = 8
    loss = 3.0 - 0.3 * (1 - abs(sp - ideal_sp) / 16) + rng.gauss(0, 0.05)
    loss += 0.0001 * abs(lr - 3e-4) * 1000
    node.result = {"loss": round(loss, 3), "sparsity_top": sp, "lr": lr}
    node.cost_usd = 1.2 + rng.uniform(0, 0.4)
    node.quality = max(0.0, 1.0 - (loss - 2.5) / 1.5)
    node.novelty = 0.5 + rng.uniform(-0.1, 0.2)
    if rng.random() < 0.1:
        node.failure = "oom_killed_by_cgroup"
        node.quality = 0.0
```

- docstring 说明真实实现会执行 `docker run --network=none --memory=8g --cpus=2 --read-only ...` 并从挂载卷读取指标；这里完全在进程内模拟。
- loss 的"真值"：sp=8 → 2.70，sp=4 → 2.775，sp=16 → 2.85，再加标准差 0.05 的噪声。
- ⚠️ **学习率几乎没有作用**：`0.0001 × |1e-3 − 3e-4| × 1000 = 7×10⁻⁵`，比噪声小约 700 倍。注释与假设名 "lr=0.001" 让人以为在测学习率，实际测的是噪声。
- `quality = 1 − (loss − 2.5)/1.5`：loss 2.5 → 1.0，loss 4.0 → 0；loss 2.70 → 0.867。
- `novelty` 是随机数，与讲义"penalizes proximity to the 50-paper literature cache"（依据文献缓存的距离）无关。
- 失败节点仍然被收取成本（`cost_usd` 已赋值），这一点符合现实——OOM 的实验也花了钱。
- 所有随机性来自传入的 `rng = random.Random(7)`，所以整个程序**完全确定**（两次运行输出的 MD5 相同），满足讲义"deterministic seeds"的要求。

### 3.4 `verify`

```python
def verify(node: Node) -> bool:
    if node.failure:
        return False
    if node.result.get("loss", 99) > 4.0:
        node.failure = "loss_diverged"
        return False
    return True
```

- 失败的节点会把原因写在 `node.failure` 上（讲义第 5 步 "Failed nodes get a failure reason stored on the tree"），且不再展开。
- ⚠️ 按 3.3 的公式，loss 最大约 2.85 + 几倍噪声，永远到不了 4.0，`loss_diverged` 分支不会触发。讲义说 verify 还应检查"消融是否隔离了效应"、基线是否运行，这里都没有。

### 3.5 `Tree`：堆与预算

```python
@dataclass
class Tree:
    root: Node
    nodes: dict[int, Node] = field(default_factory=dict)
    frontier: list = field(default_factory=list)  # (neg_score, counter, node_id)
    counter: int = 0
    budget: float = 30.0
    spent: float = 0.0
    max_nodes: int = 24

    def push(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        self.counter += 1
        remaining = self.budget - self.spent
        heapq.heappush(self.frontier, (-node.score(remaining), self.counter, node.node_id))

    def pop(self) -> Node | None:
        while self.frontier:
            _, _, nid = heapq.heappop(self.frontier)
            return self.nodes[nid]
        return None
```

- `heapq` 是**最小堆**，存 `-score` 就能让分数最高的先出。
- 三元组的第二项 `counter` 用于打破平局：分数相同时比较 counter，先入队的先出；同时避免了比较到第三项以后的对象。
- ⚠️ 分数在 `push` 时就固定在堆里，节点运行后 quality 变化不会更新优先级；子节点又都是 0.3，所以出队顺序 = 入队顺序 = **广度优先**。
- `pop` 里的 `while ... return` 第一轮就返回，等价于 `if`。
- `max_nodes = 24` 统计 `self.nodes` 的长度，也就是**入队过的节点数**，而不是执行过的实验数（见 3.6）。

### 3.6 `tree_search`：主循环

```python
    while tree.frontier and len(tree.nodes) < tree.max_nodes:
        cur = tree.pop()
        if cur is None:
            break
        if tree.spent >= tree.budget:
            print(f"    BUDGET EXHAUSTED at ${tree.spent:.2f}")
            break
        if cur.node_id != 0:
            run_experiment(cur, rng)
            tree.spent += cur.cost_usd
            ok = verify(cur)
            ...
            if not ok:
                continue
        children = expand(cur, next_id)
        next_id += len(children)
        for ch in children:
            tree.push(ch)
```

- 根节点（`node_id == 0`）不运行，直接展开——根配置作为"基线"从来没有被单独测量过（只是被重复的子节点"碰巧"测到了）。
- 失败节点 `continue`，不展开。
- ⚠️ **节点数口径**：根 1 + 每次展开 5 个；运行完第 4 个实验后入队数为 26 ≥ 24，循环结束。所以默认只跑了 4 个实验、花费 $5.57，剩下 $24 预算没用——讲义的意图是 "The tree grows until budget is exhausted"。
- ⚠️ **预算是事后检查**：只有已花费 ≥ $30 才停，因此最后一个实验可能超支。把 `max_nodes` 设得很大后，搜索执行 22 个实验、在 `$30.96` 时才停止，超支 $0.96。skill 文件把"只做事后警告的预算"列为 hard reject；应在运行前比较 `spent + 预估成本` 与预算。
- 打印中的 `{cur.node_id:02d}` 把编号补成两位；`{cur.result.get('loss','?'):>5}` 右对齐 5 个字符宽。

### 3.7 `best_branch` 与 `main`

```python
def best_branch(tree: Tree) -> list[Node]:
    done = [n for n in tree.nodes.values() if n.result and not n.failure]
    if not done:
        return []
    best = max(done, key=lambda n: n.quality)
    chain = [best]
    while chain[-1].parent is not None:
        chain.append(tree.nodes[chain[-1].parent])
    return list(reversed(chain))
```

- 只在"有结果且没失败"的节点中选 quality 最大者，再沿 `parent` 回溯到根，反转得到"根 → 最佳"的路径。根节点没有 `result`，所以不会被选为最佳，但会出现在路径开头。
- ⚠️ **winner's curse**：每个配置只测一次、噪声 σ = 0.05，在多个噪声测量中取最大值，必然高估。默认运行中最佳是 `#04 lr=0.0003`——它的配置与根节点完全相同，只是这次噪声偏小。不限制节点数时，22 个实验中只有 6 种配置，最佳选中 `#05 lr=0.001, q=0.923`（loss ≈ 2.615），而该配置的真值是 2.70。
- `main()` 用 `random.Random(7)` 创建独立随机源，保证可复现；最后打印 writer/reviewer/red team 未实现的提示。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用公式 + 噪声伪造实验 | 不需要 GPU 也能跑通树搜索 | 结论毫无科学意义；真实实验在 E2B/Docker 沙箱里跑 PyTorch，W&B 记录 |
| 加权和打分 | 简单、可调 | 与讲义的乘积形式不一致；未运行节点同分 → BFS；应给子节点继承父节点实测分数作先验，或用 UCB |
| 分数在入队时固定 | `heapq` 不支持修改优先级 | 运行后需要重新入队或用"惰性删除"更新优先级 |
| `expand` 枚举固定的 5 个修改 | 不依赖 LLM | 有重复配置、空间只有 6 个点；生产由 LLM 提出修改并做语义去重 |
| `max_nodes` 按入队数计 | 防止树无限增长 | 只跑 4 个实验，浪费预算；应按执行数或预算控制 |
| 预算事后检查 | 实现最简单 | 会超支；应运行前估算 + 为写作和评审预留额度 |
| 每个配置单次运行、取最大 quality | 省钱 | winner's curse；应多种子、带基线、用均值和置信区间 |
| 固定种子 `Random(7)` | 可复现 | 好的做法，应同时把种子写进 trace |
| 不实现 writer / reviewer / red team | 聚焦搜索骨架 | 讲义第 6–9 步才是完整交付物 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，`Node \| None` 等写法在旧版本也可用 |
| `@dataclass` + 默认值 | `class Node`、`class Tree` | 自动生成构造函数 |
| `field(default_factory=dict)` | `result: dict[str, float] = field(default_factory=dict)` | 可变默认值必须用工厂 |
| 联合类型 | `parent: int \| None`、`failure: str \| None = None` | 可以为 None 的字段 |
| `from typing import Iterable` | 导入但未使用 | 多余的导入，可以删除 |
| `heapq.heappush` / `heappop` | `heapq.heappush(self.frontier, (-score, counter, id))` | 最小堆；存负数实现最大堆；元组按字典序比较 |
| `dict(base, key=value)` | `dict(base_cfg, sparsity_top=sp)` | 复制字典并覆盖/新增键 |
| `dict.get(key, default)` | `node.config.get("sparsity_top", 8)` | 键不存在时返回默认值 |
| `random.Random(seed)` | `rng = random.Random(7)` | 独立随机源，函数之间显式传递 |
| `rng.gauss` / `rng.uniform` / `rng.random` | 伪造 loss、成本、失败 | 正态、均匀、[0,1) 随机数 |
| `round(x, 3)` | `round(loss, 3)` | 保留 3 位小数 |
| `max(..., key=...)` | `max(done, key=lambda n: n.quality)` | 按某个属性取最大元素 |
| 列表推导式带条件 | `[n for n in tree.nodes.values() if n.result and not n.failure]` | 过滤；空字典 `{}` 为假值 |
| 生成器 + `sum` 计数 | `sum(1 for n in tree.nodes.values() if n.failure)` | 统计满足条件的个数 |
| `reversed` | `list(reversed(chain))` | 反转序列 |
| `while` + 负索引 | `while chain[-1].parent is not None:` | 沿父指针回溯 |
| 条件表达式 | `flag = "ok " if ok else "FAIL"` | 三元表达式 |
| f-string 格式符 | `{cur.node_id:02d}`、`{x:>5}`、`${tree.spent:.2f}` | 补零、右对齐、两位小数 |
| `continue` / `break` | 主循环中 | 跳过本次 / 结束循环 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13；两次运行输出完全相同）：

```text
=== autonomous research agent: tree search (budget $30) ===
    [ok ] node #01  hypo='sparsity top-4'  loss=2.762  $=1.46  cum=$1.46
    [ok ] node #02  hypo='sparsity top-8'  loss=2.726  $=1.35  cum=$2.81
    [ok ] node #03  hypo='sparsity top-16'  loss=2.902  $=1.23  cum=$4.03
    [ok ] node #04  hypo='lr=0.0003'  loss=2.712  $=1.53  cum=$5.57

nodes explored : 26
budget spent   : $5.57 of $30.00
failed nodes   : 0

best branch (length 2):
  #00 investigate sparsity patterns in attention maps of sub-1B transformers   q=0.50  loss=?
  #04 lr=0.0003   q=0.86  loss=2.712

(writer + reviewer + red-team steps would run here; stubbed for the scaffold)
```

逐项解读：

- **只执行了 4 个实验，且是根的前 4 个子节点**：出队顺序严格是 #01→#04，说明是 FIFO（3.1、3.5）。第 5 个子节点 `lr=0.001` 还没轮到，循环就因为入队数达到 26 而结束。
- **`nodes explored : 26` 有误导性**：26 是入队数，实际执行 4 个。
- **loss 与真值对照**：#01（sp=4）真值 2.775，测得 2.762；#02（sp=8）真值 2.70，测得 2.726；#03（sp=16）真值 2.85，测得 2.902；#04（sp=8）真值 2.70，测得 2.712。
- **#02 与 #04 都是根配置的重复**：两次测同一个配置，结果相差 0.014，正好让你直观看到噪声的大小。
- **"最佳分支"是根的重复**：`#04 lr=0.0003` 赢下来只因为噪声更小；它没有验证任何新假设。如果把这个结果写成论文，就是一个典型的"由噪声支撑的论断"。
- **预算只用了 $5.57**：`max_nodes` 口径导致的提前终止；不限节点数时会一直跑到 $30.96 并超支。
- **与讲义 Use It 的对比**：讲义示例展示 "expanded 8 nodes, budget 12/30"、节点 #3 sparsity=top-8 最佳、之后写作与评审均分 4.2/5、共花 $28.40——是完整系统的示意，本代码只覆盖树搜索部分。

---

## 7. 动手改一改

1. **去重**：在 `push` 前用 `tuple(sorted(config.items()))` 做键检查，跳过已见过的配置；观察默认运行中被跳过的子节点。
2. **真正的 best-first**：让子节点的入队分数继承父节点的实测 `0.4·novelty + 0.5·quality`，再加一个小随机项打破平局；比较修改前后最先被探索的节点（测验 Q9）。
3. **修正终止条件与预算**：用"已执行实验数"代替 `len(tree.nodes)`；运行前判断 `spent + 预估成本 > budget` 则停止；为 writer/reviewer 预留 $5（测验 Q11、Q16）。
4. **多种子与基线**：每个配置用 3 个不同种子运行取均值和标准差，并强制先跑一次根配置作为基线；`best_branch` 改为"相对基线的提升超过 2 个标准误才算发现"。
5. **随机基线对比**（讲义练习 5）：实现一个同预算、随机采样配置的搜索，比较两者找到的最佳真值 loss（不是测得的 loss）。
6. **进阶：沙箱化执行**：把 `run_experiment` 改成真的通过 `subprocess.run(["docker", "run", "--network=none", "--memory=8g", "--cpus=2", "--pids-limit=256", "--read-only", ...])` 执行一个小脚本，并写 4 个 red-team 脚本（fork bomb、curl、读 `/etc/shadow`、写根目录）验证全部被拦截（测验 Q12）。

---

## 8. 常见坑

- **未评估节点同分**：best-first 的优先级如果在评估前计算且全部相同，就退化为 BFS；要么给先验，要么评估后重新入队。
- **把"入队数"当"探索数"**：日志口径错误会让人误以为搜索很充分。
- **重复配置**：`dict(base, key=same_value)` 生成的"新实验"与父节点完全相同，白白花钱，还会因噪声制造"假发现"。
- **在噪声上取最大值**：单次测量 + 选最大 = winner's curse；研究 agent 必须有多种子、基线和显著性判断。
- **预算事后检查**：花完了才发现超支；硬上限需要事前估算和预留。
- **novelty 用随机数**：真实 novelty 依赖文献检索；漏检会把已有工作当作新发现。
- **假设名与实际效应不符**：假设叫 "lr=0.001"，但模拟中 lr 几乎不影响 loss——生成论文时会出现"论断—证据不对齐"，这正是 vision critique 和 reviewer 要抓的问题。
- **把沙箱当可选项**：本代码的 `run_experiment` 是进程内函数；一旦换成执行 LLM 生成的代码，就必须放进 `--network=none` 等限制的容器里（skill 文件 hard reject："Experiments that run outside a sandbox"）。
