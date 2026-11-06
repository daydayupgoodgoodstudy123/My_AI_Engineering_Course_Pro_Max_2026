# 测验 · 技能库与终身学习（Voyager）（Skill Libraries and Lifelong Learning (Voyager)）

> **阶段 14 · Agent 工程 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，读不通时请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 每次从零开始的三个问题 | 浪费 token（重复推理）、丢失进度（会话 A 学到的纠正带不到会话 B）、长程组合失败（复杂任务需要能力层级） |
| 2 | Voyager 三组件 | Automatic curriculum（好奇心驱动地提出下一个任务）、Skill library（成功即入库的可执行代码，按"查询-描述"相似度检索）、Iterative prompting（失败时把执行错误、环境反馈、自我验证结果喂回去改写技能） |
| 3 | 动作空间 = 代码 | Voyager 输出 JavaScript 函数而不是原子命令；技能由子技能组合，按描述和 embedding 存储，作为**程序**而不是 prompt 被检索 |
| 4 | 技能检索流程 | 嵌入任务描述 → 查 top-k 相似技能 → 取回相关子技能 → 用"已有原语 + 新逻辑"组合新技能 |
| 5 | 三种执行信号 | `success`、`error`（带栈）、`self-verification failure`；循环到成功或达到最大轮数 |
| 6 | 与前面课程的关系 | 迭代改写是 Self-Refine 用于代码生成并以环境做验证；CRITIC 是同一模式、用外部工具做验证者 |
| 7 | 课程（curriculum） | 依据环境状态与技能清单，选"略高于当前能力"的任务——探索的甜区；生产中对应"还缺哪些技能"的定期审查 |
| 8 | 三种故障 | Skill library rot（同一技能换个描述加了 10 次 → 写入去重）、Composed-skill drift（父技能依赖的子技能被改写 → 版本固定）、Retrieval quality（技能数过几百后向量检索变差 → 加 tag 过滤与硬约束） |
| 9 | 2026 的落地形态 | 讲义：Claude Agent SDK skills（描述 + 代码 + 指令，按需加载）、skillkit、领域技能库、OpenAI Agents SDK `tools` |
| 10 | 本节代码的落差 | 无环检测（A↔B 循环静默执行）；v2"修复"靠把异常改成返回字符串，缺依赖时也报告成功；去重只按名字；没有版本固定；`dedup=False` 会静默覆盖并丢历史 |

### 核心技能（能动手做到）

- [ ] 说清 Voyager 三组件各自的输入、输出和在循环中的位置
- [ ] 读懂 `topo_order` 的迭代式后序 DFS，手推任意依赖图的执行顺序
- [ ] 为技能组合加上环检测（三色 DFS），并决定"报错还是警告"
- [ ] 实现 `name@version` 形式的版本固定，避免父技能静默升级子技能
- [ ] 区分"不抛异常"与"任务成功"，为技能加上自我验证（self-verification）
- [ ] 实现基于描述相似度的写入去重，并改善小技能库的检索（停用词、tag、名字）

---

## 二、基础自测（选择题）

**Q1.** Voyager 的三个核心组件是：

- A. Planner、Executor、Critic
- B. Tokenizer、Retriever、Generator
- C. 记忆块、休眠时计算、archival 存储
- D. Automatic curriculum、Skill library、Iterative prompting mechanism

**Q2.** Voyager 把动作空间设为"代码（函数）"而不是原子命令，最主要的好处是：

- A. 代码比自然语言更省 token
- B. 函数可以表达时间上延展的行为，能被命名、存储、检索、组合成能力层级，并由执行反馈逐步修正
- C. 代码不需要验证
- D. 模型无法输出原子命令

**Q3.** 运行 `code/main.py`，phase 4 执行 v1 的 `craft_iron_pickaxe`，日志依次是：

- A. `ran place_crafting_table v1` → `ran mine_ore v1` → `error in craft_iron_pickaxe v1: RuntimeError: need 2 stick, have 0`
- B. `ran mine_ore v1` → `ran place_crafting_table v1` → `ran craft_iron_pickaxe v1: crafted iron_pickaxe`
- C. `error in craft_iron_pickaxe v1: RuntimeError: no crafting table in context`
- D. `missing skill: gather_sticks`

**Q4.** phase 3 检索 `"I need a pickaxe"` 返回两条结果，第二条是 `0.100 place_crafting_table`。它为什么会被检索到？

- A. 它的 tags 包含 `crafting`，与 pickaxe 相关
- B. 检索使用了 embedding，语义上"工作台"与"镐"相关
- C. 唯一的重叠词是停用词 `a`：`{i, need, a, pickaxe}` 与 `{place, a, crafting, table, at, current, position}` 交集为 1，`1 / 10 = 0.1`
- D. `craft_iron_pickaxe` 依赖它，检索时会连带返回依赖

**Q5.** 按讲义，一次技能执行尝试可能返回的三种信号是：

- A. 编译成功、编译失败、超时
- B. `success`、`error`（带堆栈）、`self-verification failure`
- C. 通过、拒绝、待审
- D. 高分、中分、低分

**Q6.** 讲义中 composed-skill drift 的含义与推荐修复是：

- A. 技能描述随时间变得冗长；定期摘要
- B. 检索结果随技能库增大而漂移；改用 BM25
- C. 课程模块提出的任务越来越难；降低难度
- D. 父技能依赖的子技能被改写，父技能在未经测试的情况下用上了新版本；给技能做版本固定（pin 到 v1 的父技能不会自动用上 v3）

**Q7.** 在本节 `SkillLibrary` 中注册 `A depends_on ("B",)` 和 `B depends_on ("A",)`，然后调用 `lib.execute("A")`，结果是：

- A. `topo_order("A")` 返回 `['B', 'A']`，两个技能都"成功"执行，没有任何循环依赖的报错
- B. 抛出 `RecursionError`
- C. 进入死循环
- D. 返回 `failed: True` 并在日志中写入 "cycle detected"

**Q8.** 已有 `x` 的 v2（`history` 中有 v1 代码）。调用 `lib.register(Skill("x", ...), dedup=False)` 后：

- A. 抛出异常，拒绝同名注册
- B. 版本升为 v3，旧代码进入 `history`
- C. 新对象直接覆盖字典中的 `x`：版本回到 v1、`history` 为空，旧版本被静默丢弃
- D. 两个 `x` 并存，检索时都返回

---

## 三、动手 / 代码题

**Q9.** phase 5 的"迭代改写"把 `craft_iron_pickaxe` 从 v1 改成了 v2：

```python
def _craft_iron_pick_v2(context: dict[str, Any]) -> str:
    if not context.get("has_table"):
        return "skipped craft: no table yet"
    ore = context.get("resources", {}).get("ore", 0)
    stick = context.get("resources", {}).get("stick", 0)
    if ore < 3 or stick < 2:
        return f"skipped craft: ore={ore}, stick={stick}"
    ...
```

同时依赖从 `("mine_ore", "place_crafting_table")` 改为 `("mine_ore", "gather_sticks", "place_crafting_table")`。

1. 真正修好问题的是哪一处改动？另一处改动带来了什么隐患？
2. 如果 v2 的 `depends_on` 漏写了 `gather_sticks`，`execute` 会报告什么？`inventory` 是什么？
3. 写一个带自我验证的执行函数，让"没有真正造出镐"被判为失败。

**Q10.** 讲义练习 1：给 `compose`（`topo_order`）加环检测。

1. 读懂原 `topo_order`：对依赖图 `D → (B, C)`、`B → A`、`C → A`，它返回什么顺序？为什么 `place_crafting_table` 会在 `mine_ore` 之前执行（尽管 `depends_on` 中 `mine_ore` 写在前面）？
2. 用三色 DFS 实现 `topo_order_checked`，遇到环抛出带路径的 `CycleError`。
3. 讲义问：环应该报错还是警告？给出你的理由。

**Q11.** 讲义练习 2：实现版本固定。父技能声明 `depends_on=("crafting@1",)`，之后 `crafting` 被改写为 v2（v2 会抛异常）。要求：

- `execute("make_tool")` 仍然运行 `crafting` v1；
- 直接 `execute("crafting")` 运行最新的 v2；
- 写出实现，并说明当前 `register` 的数据结构为什么做不到这一点。

**Q12.** 讲义说"Skill library rot. Same skill added 10 times with slightly different descriptions. Add deduplication on write"。

1. 本节 `register(dedup=True)` 的"去重"依据是什么？它能挡住 `dig_iron: "mine the iron ore from rock formations nearby"` 这样一个与 `mine_ore` 几乎相同的技能吗？
2. 实现基于描述相似度的写入去重（命中时拒绝并提示"改为 refine 已有技能"），并顺带改进检索，使 `"I need a pickaxe"` 不再因为停用词 `a` 召回 `place_crafting_table`。

---

## 四、面试高频题

**Q13.**（基础必考）介绍 Voyager 的架构。它和普通的 ReAct agent 有什么根本区别？

**Q14.**（原理深挖）为什么说"技能 = 代码"比"技能 = prompt / 自然语言经验"更适合终身学习？代价是什么？

**Q15.**（工程实践）你的 agent 技能库已经有 400 个技能，检索经常拿错。你会如何改进？

**Q16.**（场景设计）为一个数据分析 agent 设计 SQL 技能库：技能如何入库、检索、组合、改写、上线？哪些环节需要人把关？

**Q17.**（追问型）技能失败后让模型改写再重试，有什么风险？什么情况下"重试"会让问题更糟？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Voyager (arXiv:2305.16291) structures an agent around: Automatic curriculum, Skill library, Iterative prompting mechanism." A 是 Plan-and-Execute + Critic 的组合；C 是 Letta（第 08 节）；B 是 RAG 管道。

### Q2 — 答案：B

讲义："Most agents emit primitive commands. Voyager emits JavaScript functions ... Composed from sub-skills. Stored keyed on description and embedding. Retrieved as a program, not a prompt." Key Terms 中 Action-space-as-code 的解释是"Emit functions, not primitive commands, for temporally extended behavior"。A 不一定成立；C 恰好相反，代码需要执行反馈和自我验证；D 错。

### Q3 — 答案：A

实际输出：

```text
  ran place_crafting_table v1: placed crafting table
  ran mine_ore v1: +3 ore
  error in craft_iron_pickaxe v1: RuntimeError: need 2 stick, have 0
  failed: True
```

`topo_order` 先运行依赖，再运行父技能。有工作台、有 3 个矿石，但 v1 的依赖里没有 `gather_sticks`，木棍为 0，于是抛出 `need 2 stick, have 0`。B 的顺序与成功结果都不对；C 不会发生，因为工作台依赖先运行了；D 错在 v1 根本没有声明 `gather_sticks` 依赖。注意依赖的执行顺序是 `place_crafting_table` 在前、`mine_ore` 在后，与 `depends_on` 的书写顺序相反（Q10 解释原因）。

### Q4 — 答案：C

`search` 用 `lower().split()` 切词后算 Jaccard。查询 `{i, need, a, pickaxe}`（4 个），`place_crafting_table` 的描述有 7 个 token，交集只有 `a`，并集 `4 + 7 − 1 = 10`，分数 0.1。它被召回纯粹是因为停用词。A 错：`search` 只在 `tag_filter` 参数给定时才用 tags 过滤，不参与打分；B 错：没有 embedding；D 错：检索不展开依赖。第一条 `craft_iron_pickaxe` 的 0.167 同理：交集 `{a, pickaxe}`，并集 12，`2/12`——其中一半的"相关性"也来自 `a`。

### Q5 — 答案：B

讲义 Iterative refinement："One of three signals returns: `success`, `error` (with stack trace), `self-verification failure`." 第三种最容易被忽视：代码没报错不代表任务完成（见 Q9）。

### Q6 — 答案：D

讲义："Composed-skill drift. Parent skill depends on a child that was refined. Version skills; a parent pinned to v1 doesn't magically pick up v3." 本节代码的 `depends_on` 只存名字，`execute` 总是使用最新版本——正是这种漂移的温床（Q11）。A、B、C 都不是讲义的定义；B 描述的是第三种故障 Retrieval quality。

### Q7 — 答案：A

已实际运行验证：`topo_order("A")` 返回 `['B', 'A']`，`execute` 日志为 `ran B v1: ok`、`ran A v1: ok`。`visited` 集合阻止了死循环（所以不是 B、C），但也让环被**静默忽略**——依赖关系"A 需要 B 先完成、B 需要 A 先完成"在逻辑上无法满足，代码却报告成功。自依赖 `C → C` 同样返回 `['C']`。skill 文件把"Depth-first without cycle detection"列为 hard reject，讲义练习 1 要求补上。

### Q8 — 答案：C

已实际运行验证：`register(..., dedup=False)` 返回 `registered x v1`，之后 `version == 1`、`history == []`。`dedup=False` 跳过了"同名即改写"的分支，直接执行 `self._skills[skill.name] = skill`，把原来带历史的对象整个替换掉。这违反了 skill 文件的 hard reject "Silent version overwrites. Every refinement MUST bump `version` and push the old code to `history`"。B 是 `dedup=True` 时的行为。

### Q9 — 参考答案

1. **真正的修复是依赖改动**：加入 `gather_sticks` 后，执行顺序中会先收集 2 根木棍，v2 的 `fn` 走到"crafted iron_pickaxe"分支。
   **隐患来自 `fn` 的改动**：v1 在条件不满足时 `raise RuntimeError`，v2 改成 `return "skipped craft: ..."`。异常变成了普通返回值，`execute` 的 `except` 捕获不到，`failed` 会被设为 `False`——**失败被伪装成成功**。这是"让测试通过"而不是"让任务完成"的典型改写，在 LLM 自动改写技能时尤其常见。
2. 实测（v2 的 `fn` + 依赖只有 `mine_ore`、`place_crafting_table`）：日志最后一行 `ran craft_iron_pickaxe v1: skipped craft: ore=3, stick=0`（测试时把 `_craft_iron_pick_v2` 直接注册到一个新库，所以版本号显示 v1），`failed: False`，`inventory: None`。系统认为技能成功，却什么都没造出来；后续依赖这把镐的技能会在更远的地方失败，难以追溯。
3. 自我验证（已运行验证）：

```python
def execute_verified(lib, name, verify):
    ctx = lib.execute(name)
    ok, why = verify(ctx)
    if not ctx["failed"] and not ok:
        ctx["failed"] = True
        ctx["log"].append(f"self-verification failed: {why}")
    return ctx

verify_pickaxe = lambda c: ("iron_pickaxe" in c.get("inventory", []),
                            f"inventory={c.get('inventory', [])}")
```

   对上面那个"漏依赖的 v2"，结果为 `self-verification failed: inventory=[]`、`failed: True`。这就是 Voyager 的第三种信号：**用对环境状态的检查（库存里有没有镐）而不是"有没有抛异常"来判定成功**。验证条件最好与技能一起存储（每个技能声明自己的后置条件）。

### Q10 — 参考答案

1. 原 `topo_order` 是用显式栈实现的**后序 DFS**：节点第一次出栈时标记 visited、压回一个 `(node, True)` 标记，再压入未访问的依赖；`(node, True)` 再次出栈时才加入结果。
   - 菱形依赖实测返回 `['A', 'C', 'B', 'D']`：A 在 B、C 之前，D 最后，是合法的拓扑序。
   - 兄弟依赖的顺序被**反转**：`depends_on=("mine_ore", "place_crafting_table")` 依次压栈，后压入的 `place_crafting_table` 先出栈、先执行。对互相独立的兄弟依赖无所谓，但如果作者隐含地依赖"按书写顺序执行"（例如先采矿再放工作台），就会出错——应把这种隐含顺序写成显式依赖。
2. 三色 DFS（已运行验证）：

```python
class CycleError(ValueError):
    pass

def topo_order_checked(lib, name):
    WHITE, GRAY, BLACK = 0, 1, 2          # 未访问 / 在当前递归路径上 / 已完成
    color, order = {}, []

    def visit(n, path):
        c = color.get(n, WHITE)
        if c == GRAY:                      # 回到当前路径上的节点 = 有环
            raise CycleError(" -> ".join(path + [n]))
        if c == BLACK:
            return
        color[n] = GRAY
        sk = lib.get(n)
        for dep in (sk.depends_on if sk else ()):
            visit(dep, path + [n])
        color[n] = BLACK
        order.append(n)

    visit(name, [])
    return order
```

   实测：A↔B 抛出 `CycleError: A -> B -> A`；自依赖抛出 `CycleError: C -> C`；菱形返回 `['A', 'B', 'C', 'D']`（兄弟按书写顺序）。原实现只有一个 `visited` 集合，无法区分"在当前路径上"（GRAY，说明有环）与"已经处理完"（BLACK，菱形中的共享依赖），所以检测不到环。递归版本在依赖链极深时可能触发 Python 递归上限，技能库规模下一般不是问题。
3. **应该报错**：循环依赖意味着依赖声明本身是错的，没有任何执行顺序能满足它；警告后继续执行（像原代码那样）会让技能在缺少前置条件的情况下运行，产生难以排查的副作用。最好在 `register` 时就检测并拒绝写入，把错误作为 observation 交给改写循环。

### Q11 — 参考答案

当前 `register` 在同名改写时**原地修改**已有对象（`existing.code = ...`、`existing.fn = ...`），`history` 只保存旧的 `code` 字符串，旧的 `fn`、`depends_on`、`description` 全部丢失。字典中每个名字只对应一个"最新对象"，所以不存在"取 v1"的可能。

实现（已运行验证）：

```python
import copy

class PinnedLibrary(SkillLibrary):
    def __init__(self):
        super().__init__()
        self._versions = {}                       # (name, version) -> 冻结的副本

    def register(self, skill, dedup=True):
        msg = super().register(skill, dedup)
        cur = self._skills[skill.name]
        self._versions[(cur.name, cur.version)] = copy.copy(cur)
        return msg

    def resolve(self, ref):                       # "crafting@1" 或 "crafting"
        name, _, ver = ref.partition("@")
        return self._skills.get(name) if not ver else self._versions.get((name, int(ver)))

    def execute_pinned(self, ref, context=None):
        context = {} if context is None else context
        context.setdefault("log", [])
        def run(ref, seen):
            sk = self.resolve(ref)
            if sk is None:
                context["log"].append(f"missing skill: {ref}")
                return False
            if ref in seen:
                return True
            seen.add(ref)
            for dep in sk.depends_on:
                if not run(dep, seen):
                    return False
            try:
                context["log"].append(f"ran {sk.name} v{sk.version}: {sk.fn(context)}")
                return True
            except Exception as e:
                context["log"].append(f"error in {sk.name} v{sk.version}: {e}")
                return False
        context["failed"] = not run(ref, set())
        return context
```

实测：`crafting` 先注册 v1，`make_tool` 依赖 `crafting@1`，随后 `crafting` 改写为会抛异常的 v2。`execute_pinned("make_tool")` 的日志为 `ran crafting v1: crafted (v1 behaviour)`、`ran make_tool v1: ok`；`execute_pinned("crafting")` 为 `error in crafting v2: v2 needs a furnace`。

要点：`copy.copy` 是浅拷贝，但由于 `register` 是给属性**重新赋值**而非原地修改，副本保留了旧的 `fn` 和 `code`。生产中每个版本应该是不可变的记录（内容哈希或数据库行），父技能升级子技能版本需要重新跑测试——类比软件包的 lock 文件。（简化起见，上面的 `run` 未做环检测，可与 Q10 结合。）

### Q12 — 参考答案

1. 去重依据只是 **`name` 是否已存在**。`dig_iron` 名字不同，会作为新技能注册，库里就有了两个几乎一样的采矿技能——讲义描述的 skill library rot 正是这种情况（模型每次给技能起的名字都略有不同）。反过来，两个不同功能的技能如果碰巧同名，后者会被当成前者的"改写"覆盖掉。
2. 实现（已运行验证）：

```python
import re
STOP = {"a", "an", "the", "and", "or", "of", "to", "from", "at", "i", "need",
        "using", "with", "for", "on", "in"}

def content_tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP}

def jac(a, b):
    A, B = content_tokens(a), content_tokens(b)
    return len(A & B) / len(A | B) if A | B else 0.0

class DedupLibrary(SkillLibrary):
    def register(self, skill, dedup=True, threshold=0.6):
        if dedup and skill.name not in self._skills:
            for other in self._skills.values():
                s = jac(skill.description, other.description)
                if s >= threshold:
                    return (f"rejected {skill.name}: near-duplicate of {other.name} "
                            f"(sim={s:.2f}); refine {other.name} instead")
        return super().register(skill, dedup)

    def search(self, query, top_k=3, tag_filter=None):
        q, out = content_tokens(query), []
        for sk in self._skills.values():
            if tag_filter and tag_filter not in sk.tags:
                continue
            d = content_tokens(sk.description) | set(sk.tags) | set(sk.name.split("_"))
            o = len(q & d)
            if o:
                out.append((o / len(q | d), sk))
        out.sort(key=lambda x: -x[0])
        return out[:top_k]
```

   实测：`dig_iron` 被拒绝，返回 `rejected dig_iron: near-duplicate of mine_ore (sim=1.00); refine mine_ore instead`；`"I need a pickaxe"` 只返回 `craft_iron_pickaxe`（0.143），不再召回工作台；把 tags 和名字拆词纳入匹配后，`"I need a tool"` 也能通过 tag `tool` 找到 `craft_iron_pickaxe`。
   注意：停用词表是手写的，阈值 0.6 也需要在真实技能库上调；生产中用 embedding 相似度 + 人工复核疑似重复。

### Q13 — 参考回答要点

- **三组件**：automatic curriculum 提出"略高于当前能力"的任务；skill library 存放成功的可执行技能，按描述相似度检索；iterative prompting 把执行错误、环境反馈、自我验证结果喂回模型改写技能。
- **与 ReAct 的根本区别**：
  - ReAct 每一步输出一个原子动作，经验只存在于当前上下文，会话结束即丢失；Voyager 把成功的行为**固化成可复用的代码**，跨任务、跨会话积累（终身学习）。
  - ReAct 由外部给定任务；Voyager 有自己的课程模块，自下而上地探索。
  - ReAct 的"反思"停留在文本；Voyager 用环境执行结果做验证。
- **评估结果**（讲义）：Minecraft 中独特物品 3.3 倍、石质工具快 8.5 倍、铁质工具快 6.4 倍、地图移动距离 2.3 倍；"The numbers are Minecraft-specific, but the pattern transfers."
- 加分点：讲义把 Claude Agent SDK skills 视为该模式的 2026 产品化——"a named, retrievable chunk of code plus instructions the agent loads on demand"。

### Q14 — 参考回答要点

- **代码的优势**：
  - **可执行、可验证**：能在环境中运行并得到确定的成败信号；自然语言经验只能"参考"。
  - **可组合**：函数调用函数，自然形成能力层级（`craftIronPickaxe` 调用 `mineIron`、`placeCraftingTable`），解决长程组合问题。
  - **时间上延展**：一个技能封装多步行为，减少每一步都要模型决策的 token 与出错机会。
  - **可版本化、可审计**：有 diff、有历史、可回滚、可测试。
- **代价**：
  - 需要**沙箱**执行环境（skill 文件："If the target runtime has no sandbox for skill execution, refuse for domains where skills touch production systems"）；
  - 需要稳定的底层 API（Voyager 依赖 Mineflayer 这类控制接口），环境变了技能就失效；
  - 代码技能的泛化有限，遇到新情况需要改写；错误的技能会被反复复用，放大错误；
  - 检索与依赖管理随规模增长变复杂（环、版本、重复）。

### Q15 — 参考回答要点

- **诊断**：建立检索评测集（查询 → 期望技能），统计 recall@k，分析错误类型——是同义技能太多（rot）、描述写得差、还是检索算法本身弱。
- **清理技能库**：近重复检测与合并（Q12）；为每个技能补充"何时使用 / 何时不用"的描述；淘汰长期未被使用或失败率高的技能。
- **分层与过滤**：讲义："Supplement with tag filters and hard constraints ('only skills with `category=tooling`')"；按领域建立层级命名空间，先路由到类别再检索；skill 文件："If the library exceeds ~200 skills with flat retrieval, refuse to call it 'production-ready.'"
- **检索算法**：embedding 或 BM25 召回 + 对 top-k 用 LLM rerank（skill 文件：LLM 打分只允许用于 top-k 短名单，不能扫全库）。
- **渐进披露**：只把技能名和一句描述放进上下文，需要时再加载完整内容（参见 [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../../13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/docs/zh.md)）。

### Q16 — 参考回答要点

- **入库**：只有通过自我验证的技能才能入库——SQL 在只读副本上执行成功、结果满足断言（行数、列名、与已知答案一致）。入库时做近重复检测，记录描述、tags（表名、业务域）、依赖（视图/子查询技能）、测试用例。
- **检索**：按查询中的表名/指标名做 tag 过滤，再做语义检索；返回技能名 + 描述 + 签名，而不是整段 SQL。
- **组合**：父查询引用子技能的固定版本（`revenue_by_month@3`），依赖图做环检测。
- **改写**：失败时把错误信息（SQL 报错、断言失败、空结果）连同 schema 信息喂回模型；限制最大改写轮数；版本递增并保留历史。
- **上线**：新版本先在影子模式下与旧版本对比结果，再切换；依赖它的父技能需要重新跑测试才能升级 pin。
- **人工把关**：涉及写操作（`UPDATE`/`DELETE`）的技能必须人工审核或直接禁止；涉及敏感表的技能需要权限审查；周期性的 curriculum review（讲义："Teams typically implement this manually as curriculum review"）决定还缺哪些技能。

### Q17 — 参考回答要点

- **风险一：伪修复**。模型为了"让它不报错"可能吞掉异常、放宽检查、硬编码返回值——本节 v2 把 `raise` 改成 `return "skipped craft"` 就是例子（Q9）。必须用独立的自我验证判定成功，而不是"没有异常"。
- **风险二：无改写的重试**。skill 文件："If the user asks for 'auto-retry on every failure without refinement,' refuse. Retries without refinement amplify the bug; they do not fix it." 有副作用的技能重试可能重复执行写操作。
- **风险三：漂移扩散**。改写后的子技能被所有父技能静默使用（composed-skill drift），一个修复可能破坏其他地方——需要版本固定和回归测试。
- **风险四：错误反馈不足**。只给"失败了"而不给错误信息和环境状态，模型只能瞎猜；skill 文件要求收集 `(task, skill_name, error, env_state)`。
- **控制手段**：最大轮数、每轮必须有可验证的进展、失败过多时升级给人或换策略、改写结果须通过同一套验证与测试才能入库。
- 加分点：这与 [阶段 14 · 05 Self-Refine 与 CRITIC](../../05-self-refine-and-critic/docs/zh.md) 的结论一致——外部（环境/工具）验证比模型自评更可靠。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：Voyager 的迭代改写就是用环境做验证的 Self-Refine。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)、[阶段 14 · 08 记忆块与休眠时计算](../../08-memory-blocks-sleep-time-compute/docs/zh.md)：技能库是 procedural memory，与前两节的事实记忆互补。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：技能执行同样需要校验、错误 observation 与沙箱。

### 本节被哪些后续内容用到
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../11-planning-htn-and-evolutionary/docs/zh.md)：分层任务分解与技能组合同构。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：Claude Agent SDK 中 skills 的实际用法。
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../../13-tools-and-protocols/22-skills-and-agent-sdks/docs/zh.md)、[阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../../13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/docs/zh.md)、[阶段 13 · 27 Skill 评估、打包与可移植性](../../../13-tools-and-protocols/27-skill-evals-packaging-and-portability/docs/zh.md)：技能的协议、发现与评估。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：评估技能库质量。

### 延伸关键词
`Voyager` · `automatic curriculum` · `skill library` · `iterative prompting` · `action space as code` · `self-verification` · `topological sort` · `cycle detection` · `version pinning` · `dedup on write` · `Claude Agent SDK skills` · `progressive disclosure` · `procedural memory`
