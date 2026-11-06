# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 06 节 层级架构及其失效模式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需 LLM、无需网络

---

## 1. 这份代码在考察什么

层级架构（hierarchical）就是"嵌套的 supervisor"：顶层 manager 管子 manager，子 manager 管 worker，只有叶子节点干活。讲义的重点不是"怎么搭"，而是"怎么坏"——最典型的失效是**分解漂移（decomposition drift）**：顶层 manager 把任务分错了分支，下层忠实地执行错误的任务，错误要到顶层汇总时才显现。

代码用三层结构演示这一点：

1. **顶层 `TopManager`（vp-eng）**：按 `branch_labels` 把任务交给对应的子 manager。
2. **子 manager**：`eng-manager`（前端、后端两个 worker）、`legal-manager`（一个 lawyer）、`finance-manager`（一个 finance worker）。
3. **worker**：用关键字匹配返回预设答案（canned answer）。
4. **两条路径**：happy path 用 `["engineering", "legal"]`；perturbed path 用 `["engineering", "finance"]`，模拟顶层 manager 把 "legal" 误标成 "finance"。

> 一句话：**一次顶层的错误标签，会被下层"尽职地"放大成一份看起来完整、实际答非所问的汇总。**

需要注意：这里的"误标"是由 `main` 直接传入的，而不是 manager 自己"幻觉"出来的；讲义列出的三种失效模式中，代码只演示了第一种（任务分配错误）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `LeafOutput` | dataclass | worker 名、收到的问题、答案 | 叶子输出 |
| `SubSummary` | dataclass | 子 manager 名、所有叶子输出、汇总文本 | 局部汇总（local summarization） |
| `TopSynthesis` | dataclass | 顶层 manager 名、所有分支、最终汇总 | 顶层汇总；保留了到叶子的引用链 |
| `Worker` | 类 | 关键字匹配预设答案 | 叶子 worker |
| `SubManager` | 类 | 按 `split` 给每个 worker 分配子问题，拼接结果 | 中间节点：规划 + 汇总 |
| `TopManager` | 类 | 按 `branch_labels` 分派到子 manager，找不到就生成 `MISSING` 分支 | 顶层 manager |
| `build_hierarchy` | 函数 | 搭出 vp-eng → {eng, legal, finance} → workers 的树 | 组织结构 |
| `render` | 函数 | 打印每个分支、每个叶子的问与答、汇总 | 可观测性 / provenance |
| `main` | 函数 | 跑 happy 与 perturbed 两条路径并打印结论 | 演示入口 |

数据流：`main` → `build_hierarchy()` → `TopManager.run(task, branch_labels)` → 对每个 label 调 `SubManager.run(f"{task} -- branch: {label}")` → 对每个 worker 调 `Worker.run(sub_q)` → `LeafOutput` 上浮成 `SubSummary` → 上浮成 `TopSynthesis` → `render` 打印。

---

## 3. 逐段精讲

### 3.1 三层数据结构：天然的 provenance 链

```python
@dataclass
class LeafOutput:
    worker: str
    question: str
    answer: str

@dataclass
class SubSummary:
    sub_manager: str
    leaves: list[LeafOutput]
    summary: str

@dataclass
class TopSynthesis:
    top_manager: str
    branches: list[SubSummary]
    synthesis: str
```

- 每一层都**同时保存**自己的汇总文本和下一层的原始输出（`leaves`、`branches`）。这正是讲义 Ship It 的 "Provenance on every synthesis. Each node's summary must cite which leaf outputs produced it"——从 `TopSynthesis` 可以一路追到每个 worker 被问了什么、答了什么。
- 生产中，LLM manager 往往只把汇总文本往上传，原始叶子输出被丢掉，于是一旦汇总出错就无从追查。这里的数据结构设计值得模仿。

### 3.2 Worker：关键字匹配的"假 LLM"

```python
class Worker:
    def run(self, question: str) -> LeafOutput:
        key = self._match_key(question)
        ans = self.canned.get(key, f"[no canned answer for '{question}']")
        return LeafOutput(worker=self.name, question=question, answer=ans)

    def _match_key(self, q: str) -> str:
        ql = q.lower()
        for k in self.canned:
            if k in ql:
                return k
        return "default"
```

- `_match_key` 遍历预设字典的键，只要键是问题的**子串**就命中。没命中返回 `"default"`，但所有 worker 的字典里都没有 `"default"` 键，于是 `canned.get` 走默认值，输出 `[no canned answer for '...']`。
- 关键点：worker **只看收到的问题**，不知道"整体任务是什么"——它对上游的错误毫无察觉，"obediently works on what it was given"。
- ⚠️ 子串匹配很粗糙：`"legal"` 会命中 `"illegal finance question"`，字典里有多个键同时命中时取先插入的那个（实测 `{"legal": ..., "finance": ...}` 对 `"illegal finance question"` 返回 legal 的答案）。

### 3.3 SubManager：按预设 split 分配，忽略上游任务

```python
class SubManager:
    def run(self, task: str) -> SubSummary:
        leaves = []
        for w in self.workers:
            sub_q = self.split.get(w.name, task)
            leaves.append(w.run(sub_q))
        summary = f"[{self.name}] aggregated: " + " | ".join(l.answer for l in leaves)
        return SubSummary(sub_manager=self.name, leaves=leaves, summary=summary)
```

- `self.split.get(w.name, task)`：如果 split 里为这个 worker 预设了子问题，就**用预设的、完全丢掉上游传来的 `task`**；只有没预设时才把原任务原样下传。
- 在 `build_hierarchy` 中所有 worker 都有预设子问题，所以顶层传下来的 `"Ship the premium tier feature to production. -- branch: legal"` 从未到达任何 worker。实测：即使顶层任务是 `"Review GDPR compliance"`，lawyer 收到的仍是 `"legal review of the feature"`。
- 这有两层含义：
  - 模拟了真实系统中"子 manager 按自己的理解改写任务"的现象——上游意图在每一层都可能被替换；
  - 也意味着子 manager **没有能力**检测漂移：它根本不看上游任务，自然无法发现"我被分到的工作和用户问题对不上"。讲义练习 3 的 canary worker 正是为了补上这个缺口。
- 汇总是简单拼接；真实 LLM 子 manager 在这一步会"改写"叶子输出，讲义的第二种失效（output misinterpretation，例如把 "unable to verify claim X" 总结成 "claim X not confirmed"）就发生在这里，代码没有模拟。

### 3.4 TopManager：按标签分派，错误标签有两种结局

```python
class TopManager:
    def run(self, task: str, branch_labels: list[str]) -> TopSynthesis:
        summaries: list[SubSummary] = []
        for label in branch_labels:
            if label not in self.subs:
                summaries.append(
                    SubSummary(
                        sub_manager=f"MISSING[{label}]",
                        leaves=[],
                        summary=f"[top] tried to delegate to '{label}' -- no such sub-manager",
                    )
                )
                continue
            summaries.append(self.subs[label].run(f"{task} -- branch: {label}"))
        synth = "top synthesis: " + " || ".join(s.summary for s in summaries)
        return TopSynthesis(top_manager=self.name, branches=summaries, synthesis=synth)
```

- **分解不是 manager 自己做的**：`branch_labels` 由调用方传入。真实系统中这一步是 LLM 读任务后生成的分解，讲义说的 "hallucinates a decomposition" 发生在这里。
- 错误标签的两种结局：
  - **拼错成不存在的名字**（如 `"legl"`）：生成 `MISSING[legl]` 分支，汇总里出现 "no such sub-manager"——错误**响亮**，容易发现（实测见第 6 节）。
  - **错成另一个存在的分支**（如 `"finance"`）：finance 子 manager 正常工作、返回看起来专业的结论——错误**静默**，汇总在格式上完全正常。perturbed path 演示的正是后者，这才是层级架构真正危险的地方。
- 顶层汇总同样是拼接。它不检查"分支集合是否覆盖了用户的问题"——讲义 Ship It 的 "Alert on decomposition drift ... diff against the user query" 在这里缺失。

### 3.5 build_hierarchy 与 main

```python
def build_hierarchy() -> TopManager:
    fe = Worker("fe", {"frontend": "React component audited; 2 issues."})
    be = Worker("be", {"backend": "API endpoints audited; 1 issue."})
    eng = SubManager("eng-manager", [fe, be],
                     {"fe": "frontend review of the feature", "be": "backend review of the feature"})
    ...
    return TopManager("vp-eng", {"engineering": eng, "legal": legal, "finance": finance})
```

```python
task = "Ship the premium tier feature to production."
happy = top.run(task, branch_labels=["engineering", "legal"])
perturbed = top.run(task, branch_labels=["engineering", "finance"])
...
print("User asked about legal/engineering review.")
```

- 树的形状：1 个顶层 + 3 个子 manager（每次只用其中 2 个）+ 4 个 worker。按"节点层数"是 3 层，按"manager 之间的委托边"是 2 级。讲义 Ship It 说 "Cap tree depth at 2. Three levels already hides most errors"，与 Build It 的 "3-level hierarchy" 用的是不同口径，阅读时要分清。
- ⚠️ 任务字符串 `"Ship the premium tier feature to production."` 里**并没有**提到 legal 或 engineering 审查，"User asked about legal/engineering review" 只是 `print` 出来的旁白。也就是说，"用户到底问了什么"在代码里并没有被形式化，所以也无法自动检测漂移。
- 末尾四行结论都是写死的文字，不是程序计算出来的对比；讲义说的 "a clear side-by-side of 'what was asked' vs 'what was delivered'" 在输出中实际上是两段先后打印的树。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用预设答案代替 LLM | 结果确定，便于对比两条路径 | 无法展示 LLM manager"每轮重新理解组织"带来的随机漂移 |
| 分解由调用方传入 `branch_labels` | 能精确地注入一次错误 | 不是真正的"manager 幻觉"；生产中需记录 manager 每一步的分解并与用户问题做 diff |
| 每层保存下层原始输出 | 提供 provenance 链 | 数据量随树规模增长；生产中可只保存引用（ID）+ 摘要 |
| 子 manager 用预设 split 覆盖上游任务 | 代码简单 | 上游意图丢失，下层无法检测漂移；应把原始用户问题一路下传（canary） |
| 汇总只是字符串拼接 | 结构清晰 | 不演示 output misinterpretation；真实 LLM 汇总会改写语义 |
| 未知分支生成 `MISSING` 而非抛异常 | 让错误出现在汇总里 | 错误仍可能被上层忽略；应计入告警指标 |
| 不演示 reconciliation loop | 控制篇幅 | 讲义第三种失效（共识循环）与"协调预算"没有代码支撑 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `LeafOutput`、`SubSummary`、`TopSynthesis` | 自动生成 `__init__`、`__repr__`；适合做"只装数据"的结构 |
| 嵌套类型注解 | `leaves: list[LeafOutput]`、`subs: dict[str, SubManager]` | 容器里装的元素类型 |
| 关键字参数构造 | `LeafOutput(worker=self.name, question=question, answer=ans)` | 显式写出字段名，可读性好、不怕顺序写错 |
| 私有约定 | `def _match_key(self, q)` | 单下划线表示"内部使用"，Python 不强制 |
| `str.lower()` + `in` | `if k in ql` | 大小写无关的子串判断 |
| `dict.get(key, default)` | `self.split.get(w.name, task)`、`self.canned.get(key, ...)` | 键不存在时返回默认值 |
| 遍历字典 | `for k in self.canned:` | 遍历的是键，按插入顺序 |
| `continue` | `if label not in self.subs: ... continue` | 跳过本次循环剩余部分 |
| 生成器表达式 + `join` | `" \| ".join(l.answer for l in leaves)` | 不建中间列表直接拼接 |
| f-string 嵌入表达式 | `f"MISSING[{label}]"`、`f"{task} -- branch: {label}"` | 字符串插值 |
| f-string 宽度 | `f"{leaf.worker:8s}"` | 左对齐、宽度 8 |
| `"-" * 60` | `print("-" * 60)` | 字符串重复 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
=== Happy path (correct branches) ===
  [sub] eng-manager
    [leaf] fe       asked: frontend review of the feature
           answered: React component audited; 2 issues.
    [leaf] be       asked: backend review of the feature
           answered: API endpoints audited; 1 issue.
    [summary] [eng-manager] aggregated: React component audited; 2 issues. | API endpoints audited; 1 issue.
  [sub] legal-manager
    [leaf] lawyer   asked: legal review of the feature
           answered: Contract clauses A and B are non-compliant.
    [summary] [legal-manager] aggregated: Contract clauses A and B are non-compliant.
  [top] top synthesis: ... || [legal-manager] aggregated: Contract clauses A and B are non-compliant.

=== Perturbed path (top manager mislabels 'legal' as 'finance') ===
  [sub] eng-manager
    （与 happy path 完全相同）
  [sub] finance-manager
    [leaf] finance  asked: finance review of the feature
           answered: Projected cost $42k/month; exceeds budget by 12%.
    [summary] [finance-manager] aggregated: Projected cost $42k/month; exceeds budget by 12%.
  [top] top synthesis: ... || [finance-manager] aggregated: Projected cost $42k/month; exceeds budget by 12%.
```

逐项解读：

- **engineering 分支两次完全相同**：错误只影响被误标的那一个分支，其余分支照常工作。这让错误更难被发现——汇总的大部分内容是对的。
- **perturbed 的汇总格式完美**：finance 的答案具体、专业（"$42k/month; exceeds budget by 12%"），没有任何报错。真正关键的合规问题"Contract clauses A and B are non-compliant"彻底消失了。对一个只看顶层汇总的人来说，这份报告看起来比 happy path 更"丰富"。
- **错误在哪一层被引入、在哪一层显现**：引入于顶层的分解，显现于顶层的汇总——中间的子 manager 和 worker 都"做对了"自己的事。讲义："the error only surfaces at the top synthesis — one level removed from where a human could have caught it"。
- **讲义练习 1 的答案（在本代码中）**：只需要**一次**顶层误标，对应分支就**完全**偏离，没有"逐层渐变"——因为每个子 manager 都用预设 split，并不会把错误部分纠正回来。
- **补充实测**：
  - 把标签拼错成 `"legl"`：汇总出现 `[top] tried to delegate to 'legl' -- no such sub-manager`，错误响亮可见。
  - 顶层任务改成 `"Review GDPR compliance"`：lawyer 收到的仍是 `"legal review of the feature"`，证明上游任务没有传到叶子。
  - 一个简单的覆盖检查（要求的分支集合 − 实际执行的分支集合）对 perturbed path 输出 `missing: ['legal']`——用几行代码就能把静默错误变成告警。

---

## 7. 动手改一改

1. **覆盖检查**：给 `TopManager.run` 增加参数 `required: set[str]`（从用户问题中提取的必须覆盖的领域），汇总前计算 `required - 实际分支`，不为空就在汇总里加 `DRIFT ALERT`。
2. **canary worker**（讲义练习 3）：给每个子 manager 增加一个 canary，总是收到**原始用户问题**（而不是改写后的子问题）；当 canary 的答案涉及的领域与该分支不符时发出告警。思考：manager 应该如何反应——重新分解、上报人工，还是追加一个分支？
3. **模拟输出误读**：在 `SubManager.run` 的汇总里加一个"改写规则"（例如把 "unable to verify" 改成 "not confirmed"），观察语义在每一层的漂移，并让 `render` 同时打印原始叶子输出与汇总，体会 provenance 的价值。
4. **加深一层**（讲义练习 2）：在 engineering 下再加一个 "platform-manager"，管 fe 和 be；在中间层也注入一次误标，统计在不同深度注入错误时，最终汇总有多少比例的内容与问题相关。
5. **协调预算**：让两个分支返回矛盾的结论，顶层要求它们"重新协调"，每轮重新运行 worker（加入随机扰动），设置最多 2 轮，超过就强制提交并在汇总中标注"未达成一致"——实现讲义的 reconciliation budget。
6. **让 manager 自己分解**：写一个 `decompose(task)`，用关键字把任务映射到分支（如含 "contract"、"GDPR" → legal），再故意加入一个错误映射，体会"分解由 manager 生成"时的漂移来源。

---

## 8. 常见坑

- **只看顶层汇总**：汇总格式正确、内容具体，不代表回答了用户的问题；必须能追溯到叶子。
- **把"拼错的标签"当成主要风险**：拼错会产生 `MISSING` 分支，响亮可见；真正危险的是"错成另一个存在的分支"，它完全静默。
- **子 manager 丢弃上游任务**：`self.split.get(w.name, task)` 让上游意图在中间层被替换，下层无法发现漂移。
- **深度口径混淆**：节点层数（3 层）与委托边数（2 级）不同；讨论"最多 2 层"时先统一口径。
- **用子串匹配做路由**：`"legal" in "illegal ..."` 为真，关键字路由需要分词或更严格的匹配。
- **把 print 的旁白当成程序判断**：末尾的 "User asked about legal/engineering review" 等结论是写死的，代码本身并不知道用户问了什么。
- **以为层级越深越"像公司"越好**：讲义指出 LLM manager 每轮都从上下文重新推理组织结构，深度越大，漂移越多、可观测性越差；能用 sequential 就别用 hierarchical。
