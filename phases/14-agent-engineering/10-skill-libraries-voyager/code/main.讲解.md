# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 10 节 技能库与终身学习（Voyager） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；不调用 LLM，"改写"由脚本直接提供 v2

---

## 1. 这份代码在考察什么

这份代码用一个 Minecraft 风格的小例子，跑通 Voyager 技能库的完整循环：

1. **技能 = 可执行代码**：`Skill` 带名字、描述、代码字符串、真正执行的 Python 函数 `fn`、版本、tags、依赖、历史。
2. **注册与改写**：`SkillLibrary.register` 对新名字直接入库，对已有名字视为"改写"——版本 +1、旧代码进 `history`。
3. **检索**：按"查询—描述"的词重叠（Jaccard）取 top-k，可选 tag 过滤。
4. **组合**：`topo_order` 对依赖图做后序 DFS 得到执行顺序；`execute` 依次运行，任何一步出错就停止并记录。
5. **失败驱动的改写**：v1 因缺少木棍而失败 → 注册 v2（加上 `gather_sticks` 依赖）→ 再次执行成功。

> 一句话：**把"会做的事"存成可检索、可组合、可版本化的代码，失败时用执行反馈改出下一个版本——这就是 Voyager 的终身学习循环。**

需要提前知道的简化与问题：没有 curriculum 模块；"改写"是写死的而不是模型根据错误生成的；`topo_order` 没有环检测；v2 把异常改成了返回字符串，会把失败伪装成成功；去重只看名字；没有版本固定；`dedup=False` 会静默覆盖历史。下文逐一实测。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Skill` | dataclass | `name`、`description`、`code`、`fn`、`version`、`tags`、`depends_on`、`history` | 技能（代码 + 描述） |
| `SkillLibrary.register` | 方法 | 新技能入库；同名则原地改写、版本 +1、旧代码入历史 | 写入 / 改写 |
| `SkillLibrary.search` | 方法 | Jaccard 词重叠打分，可选 `tag_filter` | 技能检索 |
| `SkillLibrary.topo_order` | 方法 | 迭代式后序 DFS，返回依赖优先的执行顺序 | 组合（技能 DAG） |
| `SkillLibrary.execute` | 方法 | 按拓扑序运行每个技能的 `fn`，捕获异常写入日志 | 执行与反馈 |
| `_mine` / `_place_table` / `_gather_sticks` | 函数 | 三个原语技能，修改共享的 `context` | 原语技能 |
| `_craft_iron_pick_v1` / `_v2` | 函数 | 高阶技能的两个版本：v1 条件不满足时抛异常，v2 返回"skipped"字符串 | 失败与改写 |
| `main` | 函数 | 六个阶段：注册原语 → 注册 v1 → 检索 → 执行失败 → 改写 v2 → 执行成功 | Voyager 循环演示 |

数据流：`register` × 4 → `search("I need a pickaxe")` → `execute("craft_iron_pickaxe")`（`topo_order` → 依次调用 `fn(context)` → v1 抛异常 → `failed=True`）→ `register` v2（同名改写）→ 再次 `execute`（多了 `gather_sticks` → 成功，库存中出现 `iron_pickaxe`）。

---

## 3. 逐段精讲

### 3.1 `Skill`：代码字符串与真正执行的函数

```python
@dataclass
class Skill:
    name: str
    description: str
    code: str
    fn: Callable[..., Any]
    version: int = 1
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    history: list[str] = field(default_factory=list)
```

- `code` 是给人看（或给模型看）的代码字符串，例如 `"mine_ore(); place_table(); craft('iron_pickaxe')"`；**真正执行的是 `fn`**，`code` 从未被运行。真实的 Voyager 存储并执行的是模型生成的 JavaScript 代码本身，这里用"字符串 + 预写的 Python 函数"来模拟。
- `description` 是检索的唯一依据——讲义"Skills are retrieved by query-to-description similarity"。
- `depends_on` 只存子技能的**名字**，不含版本——这为 composed-skill drift 埋下伏笔（3.5）。
- `history` 只保存旧的 `code` 字符串，不保存旧的 `fn`、描述和依赖，因此无法真正回滚行为。

### 3.2 `register`：同名即改写

```python
    def register(self, skill: Skill, dedup: bool = True) -> str:
        if dedup and skill.name in self._skills:
            existing = self._skills[skill.name]
            existing.history.append(existing.code)
            existing.code = skill.code
            existing.fn = skill.fn
            existing.description = skill.description
            existing.tags = skill.tags
            existing.depends_on = skill.depends_on
            existing.version += 1
            return f"refined {skill.name} -> v{existing.version}"
        self._skills[skill.name] = skill
        return f"registered {skill.name} v{skill.version}"
```

- `dedup=True` 时，同名注册被解释为"改写"：在**原对象**上逐字段覆盖，版本 +1，旧代码入历史。这符合 skill 文件"Every refinement MUST bump `version` and push the old code to `history`"。
- ⚠️ 去重**只看名字**。讲义说的 skill library rot 是"Same skill added 10 times with slightly different descriptions"——名字不同、描述近似的重复技能（如 `dig_iron` 与 `mine_ore`）照样入库（测验 Q12 实现了按描述相似度去重）。
- ⚠️ `dedup=False` 时走第二个分支，直接 `self._skills[skill.name] = skill`。实测：对已有 v2 的 `x` 再 `register(..., dedup=False)`，返回 `registered x v1`，`version` 回到 1、`history` 变成空列表——**静默覆盖**，正是 skill 文件的 hard reject。
- 原地修改意味着所有持有该 `Skill` 引用的地方都会立即看到新版本。

### 3.3 `search`：描述上的 Jaccard

```python
    def search(self, query: str, top_k: int = 3,
               tag_filter: str | None = None) -> list[tuple[float, Skill]]:
        q_tokens = set(query.lower().split())
        ...
            if tag_filter and tag_filter not in skill.tags:
                continue
            d_tokens = set(skill.description.lower().split())
            ...
            score = overlap / len(q_tokens | d_tokens)
```

- 与第 07、09 节相同的 Jaccard 词重叠，作为 embedding 的替身。
- `tag_filter` 是讲义建议的"硬约束"——只在给定时用于过滤，不参与打分。
- 实测 `"I need a pickaxe"`：

| 技能 | 描述 token 数 | 交集 | 并集 | 分数 |
|------|-------------|------|------|------|
| `craft_iron_pickaxe` | 10 | `{a, pickaxe}` | 12 | 0.167 |
| `place_crafting_table` | 7 | `{a}` | 10 | 0.100 |

  第二条完全是因为停用词 `a` 被召回；第一条的分数也有一半来自 `a`。只搜 `"pickaxe"` 时，结果只剩 `craft_iron_pickaxe`（0.1）。这说明小库上停用词会主导分数（讲义练习 3 建议换成 BM25 或 embedding）。
- 检索结果在 `main` 中只被打印，**没有被用于组合**——组合靠的是手写的 `depends_on`。真实 Voyager 会把检索到的技能代码放进 prompt，让模型据此写新技能。

### 3.4 `topo_order`：迭代式后序 DFS

```python
    def topo_order(self, name: str) -> list[str]:
        visited: set[str] = set()
        order: list[str] = []
        stack = [(name, False)]
        while stack:
            node, processed = stack.pop()
            if processed:
                order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            skill = self._skills.get(node)
            if skill is None:
                continue
            for dep in skill.depends_on:
                if dep not in visited:
                    stack.append((dep, False))
        return order
```

- 用显式栈模拟递归：每个节点第一次出栈（`processed=False`）时标记已访问，压回一个 `(node, True)` 的"完成标记"，再压入未访问的依赖。依赖都处理完后，`(node, True)` 才出栈，节点被加入 `order`——这就是**后序遍历**，保证依赖先于父技能。
- 菱形依赖（`D → B, C`；`B → A`；`C → A`）实测返回 `['A', 'C', 'B', 'D']`，A 只出现一次，合法。
- 兄弟依赖顺序被**反转**：`depends_on=("mine_ore", "place_crafting_table")` 依次压栈，后压入的先出栈，于是先执行 `place_crafting_table`。本例中两者独立所以无害，但不能依赖书写顺序表达先后关系。
- 依赖不存在时（`skill is None`），名字仍会进入 `order`，由 `execute` 报 `missing skill: ...`。
- ⚠️ **没有环检测**：`visited` 只有"访问过/没访问过"两种状态，分不清"在当前路径上"和"已处理完"。实测 `A → B → A` 返回 `['B', 'A']`，`execute` 两步都"成功"；自依赖 `C → C` 返回 `['C']`。讲义练习 1 要求补上（测验 Q10 用三色 DFS 实现，遇环抛 `CycleError: A -> B -> A`）。

### 3.5 `execute`：按序运行、遇错即停

```python
    def execute(self, name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if context is None:
            context = {}
        context.setdefault("log", [])
        for skill_name in self.topo_order(name):
            skill = self._skills.get(skill_name)
            if skill is None:
                context["log"].append(f"missing skill: {skill_name}")
                context["failed"] = True
                return context
            try:
                result = skill.fn(context)
                context["log"].append(f"ran {skill.name} v{skill.version}: {result}")
            except Exception as e:
                context["log"].append(
                    f"error in {skill.name} v{skill.version}: "
                    f"{type(e).__name__}: {e}"
                )
                context["failed"] = True
                return context
        context["failed"] = False
        return context
```

- `context` 是所有技能共享的"环境状态"字典（资源、是否有工作台、库存）以及日志。
- `context: ... = None` 再在函数内新建字典：避免"可变默认参数"陷阱（若写成 `context={}`，所有调用会共享同一个字典）。
- `setdefault("log", [])`：键不存在才设置。如果调用方传入同一个 `context` 反复执行，日志和资源会累积（实测两次执行 `mine_ore` 后 `ore` 为 6）。
- 每个技能单独 `try/except`，错误信息带技能名和版本写入日志——这就是 Voyager 改写循环需要的 error 信号（skill 文件："Execution MUST catch exceptions per-skill and surface them into the trace"）。
- 成功的判定标准只有一个：**没有抛异常**。没有讲义所说的第三种信号 self-verification。
- 依赖按名字取**最新版本**，没有版本固定（讲义练习 2，测验 Q11 实现了 `name@version`）。

### 3.6 原语与两版高阶技能

```python
def _craft_iron_pick_v1(context: dict[str, Any]) -> str:
    if not context.get("has_table"):
        raise RuntimeError("no crafting table in context — cannot craft")
    ...
    if stick < 2:
        raise RuntimeError(f"need 2 stick, have {stick}")
    ...

def _craft_iron_pick_v2(context: dict[str, Any]) -> str:
    if not context.get("has_table"):
        return "skipped craft: no table yet"
    ...
    if ore < 3 or stick < 2:
        return f"skipped craft: ore={ore}, stick={stick}"
    ...
```

- 原语技能通过 `context.get("resources", {})` 与 `+=` 修改共享状态，`_mine` 每次 +3 矿石，`_gather_sticks` 每次 +2 木棍。
- v1 在前置条件不满足时**抛异常**——这会被 `execute` 捕获为失败。
- v2 在同样情况下**返回字符串**——`execute` 认为成功。
- phase 5 同时改了两件事：依赖加上 `gather_sticks`（真正的修复）和 `fn` 换成 v2（引入隐患）。实测如果 v2 漏写 `gather_sticks` 依赖，日志为 `skipped craft: ore=3, stick=0`，`failed: False`，`inventory: None`——**失败被伪装成成功**。这正是让模型自动改写时最需要警惕的"伪修复"，也是 self-verification（检查库存里是否真的有镐）不可缺少的原因（测验 Q9）。

### 3.7 `main`：六个阶段

| 阶段 | 做了什么 | 对应 Voyager 概念 |
|------|---------|------------------|
| phase 1 | 注册 3 个原语技能 | 技能库初始化 |
| phase 2 | 注册 `craft_iron_pickaxe` v1，依赖采矿与工作台 | 组合高阶技能 |
| phase 3 | 检索 `"I need a pickaxe"` | 技能检索 |
| phase 4 | 执行 v1，因缺木棍失败 | error 信号 |
| phase 5 | 同名注册 v2，补上 `gather_sticks` 依赖 | iterative refinement |
| phase 6 | 再次执行，成功造出镐 | success 信号 |

- 没有 curriculum：任务"造铁镐"是写死的。
- 改写不依赖 phase 4 的错误信息——真实系统中，`need 2 stick, have 0` 这条日志会被交给模型，模型据此生成 v2。
- 末尾 `assert skill is not None`：`get` 的返回类型是 `Skill | None`，`assert` 既是运行时检查，也帮助类型检查器收窄类型。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `code` 字符串 + 预写 `fn` | 不需要执行任意代码，安全、离线 | 不是真正的"代码即技能"；生产中执行模型生成的代码，必须放进沙箱 |
| 同名即改写（原地修改） | 版本号与历史自动维护 | 只存旧 `code`，无法回滚 `fn`/依赖；所有引用立刻看到新版；应存不可变的版本记录 |
| 按名字去重 | 实现简单 | 挡不住换名字的近重复；应按描述/embedding 相似度检测并人工复核 |
| `dedup=False` 直接覆盖 | 提供"强制写入"的开关 | 静默丢弃版本与历史；应禁止或要求显式版本号 |
| Jaccard 检索 | 零依赖、可手算 | 停用词主导小库分数；生产用 BM25/embedding + tag 过滤 + top-k rerank |
| 迭代后序 DFS 无环检测 | 代码短、不会死循环 | 环被静默忽略；应三色 DFS 检测并在注册时拒绝 |
| 依赖只存名字 | 自动用上改进后的子技能 | composed-skill drift；应支持 `name@version` 固定，升级需回归测试 |
| "无异常即成功" | 判定简单 | 伪修复（返回 "skipped"）被当作成功；应为每个技能定义后置条件做 self-verification |
| 共享 `context` 字典 | 模拟环境状态 | 多次执行会累积状态；生产中每次执行应有独立、可重置的环境 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `Callable[..., Any]` | `fn: Callable[..., Any]` | 字段可以存放函数；`...` 表示任意参数 |
| 函数作为值 | `fn=_mine`、`skill.fn(context)` | 函数是一等对象，可以存进 dataclass 再调用 |
| `field(default_factory=list)` | `history: list[str] = field(default_factory=list)` | 每个技能有独立的历史列表 |
| 元组默认值 | `depends_on: tuple[str, ...] = ()` | 不可变默认值可以直接写 |
| `None` 作为可变参数的默认值 | `context: dict \| None = None` 再 `if context is None: context = {}` | 避免可变默认参数在多次调用间共享 |
| `dict.setdefault` | `context.setdefault("log", [])` | 键不存在时设置默认值并返回 |
| `dict.get` 链式默认 | `context.get("resources", {}).get("ore", 0)` | 逐层取值，缺失时给默认值 |
| `while stack:` + `stack.pop()` | `topo_order` | 用列表当栈，空列表为假 |
| 元组入栈与解包 | `stack.append((node, True))`、`node, processed = stack.pop()` | 栈元素携带"是否已处理"标记 |
| `set` 成员判断 | `if node in visited:` | O(1) 查找 |
| `raise RuntimeError(...)` | `_craft_iron_pick_v1` | 主动抛出异常表示失败 |
| `except Exception as e` + `type(e).__name__` | `execute` | 捕获异常并记录类名与信息 |
| 早返回 | `return context`（失败时） | 出错立即结束，不再执行后续技能 |
| `assert` | `assert skill is not None` | 运行时断言；也帮助类型检查器收窄类型 |
| `sorted(dict)` | `sorted(self._skills)` | 返回排好序的键列表 |
| f-string 格式符 | `f"{score:.3f}"` | 保留三位小数 |
| 前导下划线函数 | `_mine`、`_craft_iron_pick_v1` | 模块内部使用的约定 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成）：

```text
phase 1: register primitive skills
  registered mine_ore v1
  registered place_crafting_table v1
  registered gather_sticks v1

phase 2: compose a higher-order skill (v1)
  registered craft_iron_pickaxe v1

phase 3: retrieval on 'I need a pickaxe'
  0.167  craft_iron_pickaxe v1: craft an iron pickaxe using ore and a crafting table
  0.100  place_crafting_table v1: place a crafting table at current position

phase 4: execute craft_iron_pickaxe (expect failure — missing sticks)
  ran place_crafting_table v1: placed crafting table
  ran mine_ore v1: +3 ore
  error in craft_iron_pickaxe v1: RuntimeError: need 2 stick, have 0
  failed: True

phase 5: iterative refinement — rewrite as v2 with stick deps
  refined craft_iron_pickaxe -> v2

phase 6: re-execute (expect success)
  ran place_crafting_table v1: placed crafting table
  ran gather_sticks v1: +2 stick
  ran mine_ore v1: +3 ore
  ran craft_iron_pickaxe v2: crafted iron_pickaxe
  inventory: ['iron_pickaxe']
  failed: False

library state
  craft_iron_pickaxe v2  deps=('mine_ore', 'gather_sticks', 'place_crafting_table')  tags=('craft', 'tool')
  gather_sticks v1  deps=()  tags=('gather', 'stick')
  mine_ore v1  deps=()  tags=('gather', 'ore')
  place_crafting_table v1  deps=()  tags=('setup', 'crafting')
```

逐项解读：

- **phase 3**：第一名正确；第二名 `place_crafting_table` 只因共享停用词 `a` 被召回（`1/10 = 0.1`）。
- **phase 4**：执行顺序是 `place_crafting_table` → `mine_ore` → 父技能，与 `depends_on` 的书写顺序相反（栈的后进先出）。工作台和矿石都有了，唯独缺木棍，v1 抛出带具体数字的错误——这条信息正是改写循环需要的反馈。
- **phase 5**：同名注册被识别为改写，版本升到 v2，v1 的代码字符串进入 `history`。
- **phase 6**：依赖变成三个，执行顺序为 工作台 → 木棍 → 矿石 → 制作（再次反转），资源满足，库存出现 `iron_pickaxe`。
- **library state**：只有被改写的技能是 v2，三个原语仍是 v1。
- 这次"成功"确实是真的成功（库存里有镐）；但判定依据仍然只是"没有抛异常"——若 v2 漏写依赖，同样会输出 `failed: False`（3.6）。

---

## 7. 动手改一改

1. **讲义练习 1**：用三色 DFS 重写 `topo_order`，对 `A ↔ B` 和 `C → C` 抛出 `CycleError` 并给出环路径；再把检测前移到 `register`，拒绝写入成环的技能（测验 Q10）。
2. **讲义练习 2**：支持 `depends_on=("crafting@1",)`，为每个版本保存不可变副本，验证改写 `crafting` 到 v2 后父技能仍运行 v1（测验 Q11）。
3. **自我验证**：给 `Skill` 增加 `verify: Callable[[dict], bool]` 字段（例如检查库存中是否有 `iron_pickaxe`），`execute` 在"无异常"之外还要求 `verify` 通过；用"漏写 `gather_sticks` 依赖的 v2"验证它会被判为失败（测验 Q9）。
4. **写入去重**：按描述的内容词 Jaccard（去停用词）检测近重复，命中时拒绝并提示"改为 refine 已有技能"；检索时把 tags 与名字拆词纳入匹配（测验 Q12）。
5. **讲义练习 3**：实现标准库 BM25，构造 50 个技能和若干查询，比较 Jaccard 与 BM25 的 retrieval@5。
6. **讲义练习 4（curriculum）**：写一个函数，输入技能库与一组目标物品（如 `stone_pickaxe`、`furnace`），输出"还缺哪些技能"——先用规则（目标所需的原语中哪些不在库里），再思考如何交给模型提出"略高于当前能力"的任务。

---

## 8. 常见坑

- **"没抛异常"当作"成功"**：返回 `"skipped ..."` 的技能会被判为成功；必须有对环境状态的自我验证。
- **同时改依赖和行为**：phase 5 一次改了两处，难以判断是哪一处修好了问题、哪一处引入了风险；改写应尽量单一变更并逐项验证。
- **按名字去重**：挡不住换名字的重复技能，也会把同名的不同技能当成改写覆盖掉。
- **`dedup=False` 静默覆盖**：版本号回到 1、历史清空。
- **依赖书写顺序 ≠ 执行顺序**：栈的后进先出会反转兄弟依赖；有先后要求就写成显式依赖。
- **环被静默忽略**：`visited` 防住了死循环，却让不可满足的依赖"成功"执行。
- **依赖不带版本**：子技能一改写，所有父技能立刻用上未测试过的新版本。
- **共享 `context` 被重复使用**：多次执行会累积资源与日志，测试之间相互污染。
- **停用词主导检索**：小技能库中 `a`、`the` 这类词足以决定排序。
