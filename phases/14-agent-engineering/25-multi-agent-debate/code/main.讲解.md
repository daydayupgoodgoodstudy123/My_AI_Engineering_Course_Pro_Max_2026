# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 25 节 多 Agent 辩论与协作 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`collections.Counter`、`dataclasses`、`typing`）；辩手是脚本化函数，不调用任何模型

---

## 1. 这份代码在考察什么

这份代码把 Du et al. 的多 agent 辩论协议压缩成几十行：

1. **辩手**（`Debater`）：一个名字 + 一个 `drift(question, peer_answers)` 函数，输入同伴上一轮的答案，输出自己这一轮的答案。
2. **轮次**：第 0 轮每人独立作答（`peer_answers` 为空），之后 R 轮互读互改。
3. **两种拓扑**：全连接（每人读所有同伴）与星形（hub 读所有 spoke，spoke 只读 hub）。
4. **度量**：最终答案（最后一轮多数票）、第几轮收敛、"批评读取次数"（`ops`，作为 token 成本的代理）。

> 一句话：**辩论 = 独立作答 + 按拓扑交换答案 + 按规则更新 + 收敛判定**；拓扑决定成本。但这份演示有一个根本问题：三个辩手在第 0 轮就全部答对了，辩论没有任何分歧可以消解；而一旦人为制造分歧，它的更新规则会让答案来回振荡、甚至把正确的多数带偏。读懂这些，比读懂演示本身更有价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Debater` | dataclass | 名字 + `drift` 回调 | 一个模型实例 |
| `_make_debater` | 工厂函数 | 用闭包生成带 `bias`（默认观点）与 `corrections`（按题修正）的 `drift` | 有"观点漂移"的脚本化 LLM |
| `full_mesh_round` | 函数 | 每人读其余所有人上一轮答案并更新，返回新答案与读取次数 | 全连接拓扑 |
| `sparse_star_round` | 函数 | hub 读所有 spoke，每个 spoke 只读 hub | 星形（hub-and-spoke）稀疏拓扑 |
| `run_debate` | 函数 | 第 0 轮独立作答 → R 轮 → 收敛检测 → 多数票 | 辩论主循环 |
| `main` | 函数 | 3 道题 × 2 种拓扑，打印答案、收敛轮次、ops、对错 | 演示 |

数据流：`main` 构造 3 个辩手 → 对每道题、每种拓扑调用 `run_debate` → 第 0 轮 `drift(q, [])` 得到 `prior` → 每轮按拓扑调用 `*_round` 得到 `new` 与 `ops` → 检查是否全员一致 → `prior = new` → R 轮后对 `prior` 做多数票 → 返回 `(答案, 收敛轮次, 总 ops)`。

---

## 3. 逐段精讲

### 3.1 `Debater` 与闭包工厂

```python
@dataclass
class Debater:
    name: str
    drift: Callable[[str, list[str]], str]


def _make_debater(name: str, bias: str,
                  corrections: dict[str, str]) -> Debater:
    def drift(question: str, peer_answers: list[str]) -> str:
        current = corrections.get(question, bias)
        if peer_answers:
            common = Counter(peer_answers).most_common(1)[0][0]
            if common != current and common != bias:
                return common
        return current
    return Debater(name=name, drift=drift)
```

- `drift` 是一个**闭包**：它"记住"了外层函数的 `bias` 和 `corrections`。三个辩手共用同一段代码，但各自持有不同的观点。
- `bias`：没有修正时的默认答案（alpha=Lisbon、beta=Madrid、gamma=Porto，对应讲义"per-debater opinion drift"）。`corrections`：按题目给出的"自己的真实看法"。
- 更新规则：看同伴答案中出现最多的那个 `common`；如果它既不是自己当前的答案，也不是自己的 bias，就**改成它**；否则保持。
- ⚠️ **没有记忆**：`current` 每轮都从 `corrections.get(question, bias)` 重新算，不考虑自己上一轮说了什么，也不把自己算进投票。每个辩手实质上是"复制同伴多数"。
- ⚠️ **平票随顺序**：`Counter(...).most_common(1)` 在平票时返回最先出现的元素（实测 `Counter(["Porto","Lisbon"])` 得 Porto，反过来得 Lisbon）。结果取决于辩手在列表中的顺序。
- ⚠️ **没有说服门槛**：只要同伴多数不等于自己的 bias 就跟随，2 人中 1 人反对（平票）也会跟随。
- 测验 Q9 展示了这三点合在一起的后果：两个正确的辩手在第 1 轮被一个错误的辩手"带偏"，之后每轮来回翻转，最终答案取决于 R 的奇偶。

### 3.2 全连接一轮

```python
def full_mesh_round(debaters: list[Debater], question: str,
                    prior: dict[str, str]) -> tuple[dict[str, str], int]:
    new_answers: dict[str, str] = {}
    ops = 0
    for debater in debaters:
        peers = [prior[d.name] for d in debaters if d.name != debater.name]
        new_answers[debater.name] = debater.drift(question, peers)
        ops += len(peers)
    return new_answers, ops
```

- 每个辩手读 `N − 1` 个同伴的**上一轮**答案（`prior`），所有人基于同一份快照同时更新——这是"同步"辩论，与原论文一致。
- `ops += len(peers)`：每读一个同伴记一次"批评操作"，每轮 `N(N − 1)`。N=3 时每轮 6，R=3 共 18。
- 列表推导式 `[prior[d.name] for d in debaters if d.name != debater.name]` 按辩手列表顺序收集同伴答案——这个顺序会影响平票结果。
- 真实系统里，"读一个同伴"意味着把对方的完整推理放进 prompt，token 成本远不止一次"操作"，而且随答案长度增长。

### 3.3 星形一轮

```python
def sparse_star_round(hub: Debater, spokes: list[Debater], question: str,
                      prior: dict[str, str]) -> tuple[dict[str, str], int]:
    new_answers: dict[str, str] = {}
    ops = 0
    spoke_names = [s.name for s in spokes]
    new_answers[hub.name] = hub.drift(
        question, [prior[n] for n in spoke_names]
    )
    ops += len(spoke_names)
    for spoke in spokes:
        new_answers[spoke.name] = spoke.drift(
            question, [prior[hub.name]]
        )
        ops += 1
    return new_answers, ops
```

- hub 读全部 `N − 1` 个 spoke，每个 spoke 只读 hub：每轮 `2(N − 1)` 次读取。N=3 时每轮 4，R=3 共 12。
- spoke 只看到 hub 一个答案，`Counter` 的多数就是 hub 的答案——spoke 是否跟随完全取决于 hub。这就是讲义"Hub failure. In a star topology, a bad hub corrupts everyone"。
- ⚠️ **与讲义计数口径不同**：讲义说"Star N=5, R=3 ... spokes read only the hub = 12 critique ops"，只计 spoke 读 hub；本代码还计了 hub 读 spoke，N=5、R=3 实测为 **24**。全连接 N=5、R=3 为 60，两边一致。

| 拓扑 | 每轮读取（本代码） | N=3, R=3 | N=5, R=3 | 复杂度 |
|------|-------------------|---------|---------|-------|
| 全连接 | `N(N − 1)` | 18 | 60 | O(N²R) |
| 星形 | `2(N − 1)` | 12 | 24（讲义口径 12） | O(NR) |

- skill 文件说"Debate ops scale O(N*R)"——对全连接并不成立，全连接的读取次数是 O(N²R)。

### 3.4 `run_debate`：主循环与收敛判定

```python
def run_debate(debaters: list[Debater], question: str, rounds: int,
               topology: str) -> tuple[str, int, int]:
    prior: dict[str, str] = {}
    for debater in debaters:
        prior[debater.name] = debater.drift(question, [])

    total_ops = 0
    converged_round = -1
    hub = debaters[0]
    spokes = debaters[1:]
    for r in range(rounds):
        if topology == "full_mesh":
            new, ops = full_mesh_round(debaters, question, prior)
        else:
            new, ops = sparse_star_round(hub, spokes, question, prior)
        total_ops += ops
        if all(v == list(new.values())[0] for v in new.values()) and converged_round == -1:
            converged_round = r + 1
        prior = new

    votes = Counter(prior.values()).most_common(1)[0][0]
    return votes, converged_round, total_ops
```

- **第 0 轮**：`drift(question, [])`，没有同伴信息，返回各自的独立观点。
- **hub 固定为列表第一个**辩手（alpha），没有轮换。
- **收敛检测**：`all(v == 第一个值 for v in ...)` 判断是否全员一致，只记录**第一次**一致的轮次（`converged_round == -1` 保证只赋值一次）。`-1` 表示从未一致。
- **最终答案**：最后一轮答案的多数票。
- ⚠️ **第 0 轮的一致不被检测**：即使独立作答时已经全员一致，也要跑满 R 轮、付出全部读取成本，并记为"第 1 轮收敛"。
- ⚠️ **收敛后不停止**：一致之后仍继续跑剩余轮次。真实系统应提前停止以节省成本（测验 Q12 给出了 `run_debate_early`）。
- ⚠️ **没有"无共识"**：多数票平票时 `most_common` 随便取第一个；三人三个答案时也会"选出"一个答案。skill 文件："No convergence rule"是硬性拒绝项；应设过半数/超级多数门槛，否则返回无共识或转人工。
- ⚠️ **拓扑名不校验**：任何不是 `"full_mesh"` 的字符串都会静默按星形运行，包括 `"ring"` 和拼写错误。
- `list(new.values())[0]` 在生成器里每次都重建列表，写成 `len(set(new.values())) == 1` 更简洁。

### 3.5 `main`：演示数据

```python
    questions_and_truth = {
        "capital_of_portugal": "Lisbon",
        "is_2_plus_2_equal_4": "yes",
        "chess_legal_e4": "legal",
    }

    debaters = [
        _make_debater("alpha", bias="Lisbon",
            corrections={"is_2_plus_2_equal_4": "yes", "chess_legal_e4": "legal"}),
        _make_debater("beta", bias="Madrid",
            corrections={"capital_of_portugal": "Lisbon",
                         "is_2_plus_2_equal_4": "yes", "chess_legal_e4": "legal"}),
        _make_debater("gamma", bias="Porto",
            corrections={"capital_of_portugal": "Lisbon",
                         "is_2_plus_2_equal_4": "yes", "chess_legal_e4": "legal"}),
    ]
```

- 三道题对应讲义"one factual, one rule-based, one reasoning"：首都（事实）、2+2（讲义称推理，其实很难算推理）、国际象棋 e4 是否合法（规则）。
- ⚠️ **演示没有分歧**：alpha 的 bias 恰好是 Lisbon，其他两题有修正；beta、gamma 三题都有修正。于是每道题第 0 轮三人答案就完全相同且正确。beta 的 Madrid、gamma 的 Porto 这两个"错误观点"从未出场。
- 讲义 Build It 说"sparse matches full mesh on 2/3 questions at lower cost"，实际两种拓扑都是 3/3 正确——与讲义不符，而且"都对"不是辩论的功劳。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 辩手是脚本化函数 | 可复现、零成本 | 没有推理文本、没有"被论证说服"；真实辩手看到的是同伴的完整论证 |
| 闭包携带 bias / corrections | 一段代码生成多种观点 | 观点固定、无记忆；应记住上一轮答案（测验 Q11） |
| 只交换答案标签 | 简单 | 无法区分"有理有据"与"随口一说"；应附理由与置信度 |
| 同步更新（都读上一轮快照） | 与原论文一致、结果确定 | —— |
| `Counter` 多数、平票取首个 | 代码短 | 结果依赖排列顺序；应平票保持原答案或用置信度 |
| hub 固定为第一个辩手 | 简单 | hub 失效无缓解；应轮换或多 hub |
| 读取次数作为成本代理 | 易于比较拓扑 | 忽略答案长度；生产中统计真实 token |
| 不检测第 0 轮一致、不提前停止 | 演示完整轮次 | 白花成本；生产应提前停止 |
| 末轮多数票作为答案、无门槛 | 总能给出答案 | 没有"无共识"；应设过半/超级多数并兜底 |
| 演示数据第 0 轮即一致 | 让输出"全对" | 展示不了辩论的纠错与失败；应设计有分歧的场景（测验 Q12） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `@dataclass` 存放函数 | `drift: Callable[[str, list[str]], str]` | dataclass 字段可以是函数；调用时写 `debater.drift(q, peers)` |
| `Callable` 类型注解 | `Callable[[str, list[str]], str]` | "接收 str 和 list[str]、返回 str 的函数" |
| 闭包 | `_make_debater` 内部定义并返回 `drift` | 内层函数捕获外层变量 `bias`、`corrections` |
| `collections.Counter` | `Counter(peer_answers).most_common(1)[0][0]` | 计数；`most_common(1)` 返回 `[(元素, 次数)]`，平票时按首次出现顺序 |
| 链式索引 | `.most_common(1)[0][0]` | 取列表第 0 项（元组），再取元组第 0 项（元素） |
| `dict.get(k, default)` | `corrections.get(question, bias)` | 没有修正时用 bias |
| 返回元组 + 解包 | `return new_answers, ops`、`new, ops = full_mesh_round(...)` | 一次返回多个值 |
| 带条件的列表推导式 | `[prior[d.name] for d in debaters if d.name != debater.name]` | 过滤掉自己 |
| 切片 | `hub = debaters[0]`、`spokes = debaters[1:]` | 取第一个与其余 |
| `all()` + 生成器 | `all(v == list(new.values())[0] for v in new.values())` | 是否全部相等 |
| 哨兵值 | `converged_round = -1` | 用 -1 表示"尚未收敛" |
| 关键字参数 | `_make_debater("alpha", bias="Lisbon", corrections={...})` | 按名字传参更清晰 |
| 字典遍历 | `for q, truth in questions_and_truth.items():` | 同时取键和值 |
| f-string 对齐 | `f"{topology:12}"`、`f"answer={answer:10}"` | 字符串左对齐、固定宽度 |
| 条件表达式 | `"CORRECT" if answer == truth else "WRONG"` | 一行 if/else |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成）：

```text
--- capital_of_portugal  (truth: Lisbon) ---
  full_mesh     answer=Lisbon      converged_round=1  ops=18  CORRECT
  sparse_star   answer=Lisbon      converged_round=1  ops=12  CORRECT

--- is_2_plus_2_equal_4  (truth: yes) ---
  full_mesh     answer=yes         converged_round=1  ops=18  CORRECT
  sparse_star   answer=yes         converged_round=1  ops=12  CORRECT

--- chess_legal_e4  (truth: legal) ---
  full_mesh     answer=legal       converged_round=1  ops=18  CORRECT
  sparse_star   answer=legal       converged_round=1  ops=12  CORRECT

sparse star matches full mesh on accuracy with fewer critique ops.
debate helps factual and rule-based tasks; adds latency and cost.
```

逐项解读：

- **ops**：全连接 `3 × 2 × 3 = 18`，星形 `(2 + 2) × 3 = 12`，星形省 1/3。
- **converged_round=1**：并不是"辩论一轮就纠正了错误"，而是第 0 轮已经一致，代码只是从第 1 轮开始检查。
- **全部 CORRECT**：与讲义"2/3"的描述不符；而且由于没有分歧，这个结果对"辩论是否有用""稀疏是否和全连接一样好"都**没有证明力**。
- 为了看到辩论真正的行为，我们额外运行了几组有分歧的配置（详见测验 Q9、Q12）：

| 配置（`capital_of_portugal`，R=3） | 全连接 | 星形 | 说明 |
|-----------------------------------|-------|------|------|
| alpha=Lisbon、beta 修正为 Lisbon、gamma=Porto | Lisbon，第 1 轮收敛 | Lisbon，第 1 轮收敛 | 多数正确，少数被纠正 |
| alpha=Lisbon、beta=Madrid、gamma=Porto | Lisbon，不收敛 | Lisbon，不收敛 | 每轮来回翻转，末轮多数恰好正确 |
| gamma=Porto 排第一、alpha=Lisbon、beta 修正为 Lisbon | **Porto**，不收敛 | **Porto**，不收敛 | 两个正确的辩手被平票规则带偏；R=2、4 时又变回 Lisbon |

  第三行最值得注意：**最初多数正确，辩论后反而错了**，并且结果随 R 的奇偶翻转——这是讲义"Convergence collapse"在玩具里的样子。
- 最后两行是讲义的结论口号；第一句在本演示中并未被真正验证。

---

## 7. 动手改一改

1. 制造分歧：删掉 beta、gamma 对 `capital_of_portugal` 的修正，观察第 0～3 轮每人答案的变化（在 `run_debate` 里加打印），并对比 R=2 与 R=3。
2. 修正更新规则：让辩手记住自己的答案、把自己算进投票、只在被严格多数超过时改变主意（测验 Q11），重新运行第 1 题的各种配置。
3. （讲义练习 1）强制分歧：第 1 轮要求每个辩手给出与他人不同的提案（如果可能），比较收敛速度。
4. （讲义练习 2）置信度加权：`drift` 返回 `(answer, confidence)`，最终答案按置信度加权；设计一个"一个高置信正确 vs 两个低置信错误"的场景，看结果是否改变。
5. 实现 `run_debate_early`：第 0 轮一致直接返回、收敛即停止、未过半返回 `NO_CONSENSUS`、未知拓扑报错（测验 Q12）；统计三道题节省的读取次数。
6. （讲义练习 4、5）增加环形拓扑（每人读左右邻居），把 N 扩到 5、R 扩到 3，画出三种拓扑的"读取次数 vs 正确率"；同时轮换 hub，观察 hub 失效场景是否改善。

---

## 8. 常见坑

- **演示没有分歧就宣布"辩论有效"**：第 0 轮已一致时，任何拓扑都"全对"，不能说明任何问题。先统计第 0 轮的分歧率。
- **更新规则不考虑自己的观点**：纯粹复制同伴多数会导致振荡和从众。
- **平票规则依赖排列顺序**：`Counter.most_common` 平票时取先出现者，结果由列表顺序决定。
- **只在第 1 轮之后检查收敛、收敛后不停止**：白白付出成本。
- **没有"无共识"出口**：强行给出答案会掩盖系统的不确定性。
- **成本口径不统一**：星形是否计"hub 读 spoke"会让成本相差一倍；全连接的读取次数是 O(N²R)，不是 O(NR)。
- **拓扑参数不校验**：`"ring"` 被静默当成星形。
- **hub 固定不变**：坏 hub 会带偏所有 spoke，应轮换或使用多个 hub。
- **同一个模型 + 同一个 prompt**：辩手高度相关，辩论只会放大共同的错误。
