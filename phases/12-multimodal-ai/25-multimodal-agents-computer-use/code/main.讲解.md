# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 25 节 多模态 Agents 与计算机操作（综合项目） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`dataclasses`），无需网络、浏览器、GPU 或模型权重

---

## 1. 这份代码在考察什么

这是阶段 12 综合项目的"脚手架"，约 180 行，用一个模拟浏览器演示 computer-use agent 的骨架：

1. **Action schema**：10 种动作（click、type、scroll、drag、select、hover、navigate、wait、screenshot_region、done）及其参数名。
2. **浏览器状态与状态转移**：`BrowserState` 记录 URL、页面名、已填字段；`apply_action` 根据动作更新状态。
3. **任务与评估**：`Task` 包含目标、动作计划、期望的最终页面；`run_task` 执行计划并比较最终页面，`run_benchmark` 统计通过率。
4. **基准与记忆策略的速览**：打印 2026 年基准分数表和三种长程记忆压缩策略。

> 一句话：**把"动作要结构化、状态要可观测、成功要可判定"这三条 computer-use 的工程底线摆出来**。但要清楚：代码里没有 VLM、没有观察驱动的决策、没有错误恢复，计划是写死后按顺序重放的；而且它的状态转移和成功判定都有漏洞——其中一个任务因此失败、一个"只点一下 Book"的作弊计划却能通过。修补这些漏洞正是本综合项目要你完成的部分。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ACTION_SCHEMA` | 模块级字典 | 动作名 → 参数名列表 | Action schema / 工具定义 |
| `BrowserState` | dataclass | `url`、`page`、`filled` | 环境状态（模拟浏览器） |
| `Task` | dataclass | `goal`、`plan`（动作列表）、`expected_page` | 基准任务 |
| `mock_tasks` | 函数 | 返回 2 个任务（订机票、重置密码） | 迷你基准 |
| `apply_action` | 函数 | 根据动作返回新状态（不修改旧状态） | 浏览器执行器 / 环境转移 |
| `run_task` | 函数 | 依次执行计划、记录轨迹、比较最终页面 | 开环执行 + 评估 |
| `print_schema` | 函数 | 打印动作表 | — |
| `run_benchmark` | 函数 | 跑全部任务，打印 PASS/FAIL 和得分 | 基准评估 |
| `benchmark_leaderboard` | 函数 | 打印 5 行基准分数 | 2026 基准速览 |
| `main` | 函数 | 依次调用以上函数，打印记忆策略与阶段总结 | 入口 |

数据流：`main` → `print_schema` → `run_benchmark`（`mock_tasks` → 每个任务 `run_task` → 逐个动作 `apply_action` → 比较 `state.page` 与 `expected_page`）→ `benchmark_leaderboard` → 打印记忆策略。

讲义中的理想循环是 `截图 → VLM 决策 → 动作 → 执行 → 新截图 → VLM 决策 …`；本代码实际是 `写死的动作列表 → 逐个执行 → 最后比较页面名`，中间没有"观察 → 决策"的闭环。

---

## 3. 逐段精讲

### 3.1 `ACTION_SCHEMA`：动作空间

```python
ACTION_SCHEMA = {
    "click": ["x", "y", "element_desc"],
    "type":  ["text", "x", "y"],
    "scroll": ["direction", "amount"],
    "drag": ["x0", "y0", "x1", "y1"],
    "select": ["option_index"],
    "hover": ["x", "y"],
    "navigate": ["url"],
    "wait": ["ms"],
    "screenshot_region": ["x0", "y0", "x1", "y1"],
    "done": ["success", "explanation"],
}
```

- 对应讲义 "Action schemas" 一节的 9 种动作，再加上视觉工具 `screenshot_region`（裁剪 + 放大，讲义练习 1 要求"扩展"的正是它——代码里已经有了）。
- `click` 带 `element_desc`：讲义强调它是坐标漂移时重新 grounding 的语义提示。
- `done` 带 `success` 和 `explanation`：agent 自己宣布任务结束及结果。注意：**自报的 success 不能当作评估结果**（见 3.5）。
- ⚠️ 这只是"参数名列表"：没有类型、取值范围、必选/可选之分。讲义写 `type: (text, x?, y?)`（坐标可选），这里却无法表达。整个文件**从未用它校验动作**——`apply_action` 遇到未知动作直接忽略。测验 Q10 给出了校验器，生产中应写成 JSON Schema 并作为 tool calling 的工具定义交给模型。

### 3.2 `BrowserState` 与 `Task`：状态与任务

```python
@dataclass
class BrowserState:
    url: str = "https://mock-booking/"
    page: str = "home"
    filled: dict = field(default_factory=dict)


@dataclass
class Task:
    goal: str
    plan: list[dict]
    expected_page: str
```

- `field(default_factory=dict)`：每个实例都得到一个**新的**空字典。如果写成 `filled: dict = {}`，dataclass 会直接报错（可变默认值会被所有实例共享）。
- `BrowserState` 用一个字符串 `page` 代表"当前在哪个页面"，`filled` 记录表单里填了什么——这是对真实浏览器（DOM + 截图）的极度简化。
- `Task.plan` 是**预先写好的动作序列**。在真实 agent 中，动作应该由模型根据每一步的观察实时产生；这里把"模型"省略了，相当于一个完美但盲目的脚本。

### 3.3 `mock_tasks`：两个任务

```python
        Task(goal="Book flight NYC to Tokyo April 15",
             plan=[
                 {"action": "click", "x": 120, "y": 200, "element_desc": "Search"},
                 {"action": "type",  "text": "Tokyo",  "x": 300, "y": 240},
                 {"action": "click", "x": 400, "y": 240, "element_desc": "date"},
                 {"action": "select", "option_index": 15},
                 {"action": "click", "x": 500, "y": 400, "element_desc": "Book"},
                 {"action": "done", "success": True, "explanation": "booked"},
             ],
             expected_page="confirmation"),
```

- 每个动作都是讲义要求的 JSON 形态（Python 字典），可以直接 `json.dumps`。
- ⚠️ 讲义 "Use It" 说有 "10-task mini-benchmark"，代码只有 2 个任务（`run_benchmark` 打印的标题也是 "2 sample tasks"）。
- 讲义问题描述里的"靠过道、800 美元以内"等约束在任务中完全没有体现。
- 第二个任务（重置密码）的计划是 Login → Forgot password → 输入邮箱 → Submit → done。

### 3.4 `apply_action`：状态转移（问题集中处）

```python
def apply_action(state: BrowserState, action: dict) -> BrowserState:
    new = BrowserState(url=state.url, page=state.page, filled=dict(state.filled))
    act = action["action"]
    if act == "click":
        desc = action.get("element_desc", "")
        if "Book" in desc or "Submit" in desc:
            new.page = "confirmation"
        elif "Login" in desc or "Forgot" in desc:
            new.page = "reset_sent" if "Forgot" in desc else "login"
        elif "Search" in desc:
            new.page = "search"
    elif act == "type":
        new.filled[action.get("x", 0)] = action.get("text", "")
    elif act == "select":
        new.filled["select_idx"] = action.get("option_index", 0)
    elif act == "done":
        # terminal signal only; do not overwrite workflow page state
        pass
    return new
```

好的设计：

- **不修改旧状态**：先复制出 `new`（`dict(state.filled)` 是浅拷贝），再修改并返回。这样轨迹中每一步的状态都可以保留下来做回放和调试，是函数式风格的状态更新。
- `done` 明确不改页面（注释说明了意图）。

问题：

- ⚠️ **跳转与当前页面无关**：任何页面点 "Submit" 都进 `confirmation`，点 "Forgot" 立即 `reset_sent`。重置密码任务因此失败：第 2 步就变成 `reset_sent`（还没输入邮箱），第 4 步 "Submit" 又把它覆盖成 `confirmation`（测验 Q5）。
- ⚠️ **坐标完全没用**：没有命中测试，`element_desc` 写什么就点中什么。GUI grounding——讲义说的最核心难点——在模拟中消失了。
- ⚠️ **子串匹配**：`"Book" in desc` 对 "Bookmarks" 同样成立。
- ⚠️ **`type` 用 x 坐标当键**：`filled` 里出现 `{200: 'alice@x.com'}`，整数键与 `"select_idx"` 字符串键混用；缺参数时默认 x = 0 而不是报错。
- ⚠️ **其它动作静默忽略**：`navigate`、`scroll`、`hover`、`wait`、`drag`、`screenshot_region` 都没有分支，非法动作（如 `"fly"`）也不报错。
- 状态机版本见测验 Q9：用 `{(当前页面, 元素): 下一页面}` 表示转移，修复后两个任务都通过。

### 3.5 `run_task` 与 `run_benchmark`：开环执行与评估

```python
def run_task(task: Task) -> dict:
    state = BrowserState()
    trace = []
    for step, action in enumerate(task.plan, 1):
        trace.append((step, action["action"], action.get("element_desc", "")))
        state = apply_action(state, action)
    success = (state.page == task.expected_page)
    return {"goal": task.goal, "trace": trace, "final_page": state.page,
            "success": success}
```

- 循环里**没有任何决策**：下一个动作不取决于当前 `state`，这就是"开环重放"。真实 agent 循环应是 `action = policy(goal, observation, memory)`，执行后再观察。
- 轨迹只记录了动作名和 `element_desc`，所以 `type`、`select`、`done` 在输出中描述为空（见第 6 节）——调试时看不到输入了什么、选了什么。
- 成功判定只有一条：最终页面名等于期望页面名。
  - 好的一面：它**不相信** agent 自报的 `done(success=True)`。重置密码任务自报 "reset sent"，实际被判失败——这恰好演示了"评估要看环境状态"的原则。
  - 坏的一面：页面名是个很弱的代理指标。实测一个只有 `click Book` 一步的计划也能 PASS（测验 Q7）；一个只含非法动作 `fly`、期望页面 `home` 的任务同样 PASS。评估应同时检查已填字段（目的地是否为 Tokyo、日期是否为 15 日）和副作用（订单是否生成）。
- ⚠️ 讲义提到的 "Error-recovery hook for when an action fails" 不存在：`apply_action` 永远不会"失败"，自然也没有可恢复的错误。测验 Q11 实现了命中测试 + `element_desc` 重新 grounding + 最多 2 次重试。

```python
        status = "PASS" if r["success"] else "FAIL"
        ...
    print(f"\n  score: {passed}/{total}")
```

- 得分 1/2。修复状态机后为 2/2。

### 3.6 `benchmark_leaderboard`：基准速览

```python
    rows = [
        ("ScreenSpot-Pro",  "Qwen2.5-VL-72B 85",  "Claude Opus 4.7 ~90"),
        ("VisualWebArena",  "open ~20",           "Gemini 3 Pro ~27"),
        ("WebArena",        "open ~35",           "saturated ~60"),
        ("AgentVista",      "open ~10-20",        "frontier 27-40"),
        ("Ferret-UI mobile","Qwen2.5-VL ~70",     "GPT-5 ~82"),
    ]
    print(f"  {'benchmark':<20}{'open model':<26}{'frontier'}")
    for r in rows:
        print(f"  {r[0]:<20}{r[1]:<26}{r[2]}")
```

- 前两行与第四行与讲义 "The 2026 benchmarks" 一节一致（ScreenSpot-Pro 开源 SOTA 约 85、前沿约 90；VisualWebArena 开源约 20、Gemini 3 Pro 约 27；AgentVista 前沿 27–40、开源 10–20）。
- ⚠️ **WebArena 一行**：讲义只说它 "saturated by frontier"，没有给数字；"~35 / ~60" 不在讲义中，且"约 60%"称作"饱和"也说不通。
- ⚠️ **Ferret-UI 一行**：讲义把 Ferret-UI（arXiv:2404.05719）介绍为面向移动 UI 的**模型**，代码却把它当成**基准**并给出 Qwen2.5-VL ~70、GPT-5 ~82 的分数，这些数字讲义中也没有。
- 讲义内部的口径也略有出入：开头说 Gemini 3 Pro 与 Claude Opus 4.7 在 AgentVista 难题上"约 30%"，基准一节写"前沿 27–40%"，Key Terms 写"Gemini 3 Pro 约 30%"。引用这些数字时应以原论文为准。
- 用 `r[0]`、`r[1]` 下标访问元组，不如 `for name, open_, frontier in rows:` 解包清晰。

### 3.7 `main`：记忆策略与阶段总结

```python
    print("  summary-chain : periodic text summary, drop old screenshots")
    print("  skip-frame    : keep first + last + every 3rd")
    print("  log only      : only action log in context (Claude computer-use)")
    print("  best: hybrid of log + last-2 screenshots + summary")
```

- 三种策略对应讲义 "Long-horizon memory"；最后一行"日志 + 最近 2 张截图 + 摘要"与 skill 文件的推荐一致（"Summary-chain every 5 steps + last-2 screenshots live"）。
- 代码没有实现任何记忆机制——因为它根本不处理截图。测验 Q12 实现了"≤4 张截图 + 全量日志 + 每 5 步摘要"，20 步任务的上下文从约 27,080 token 降到约 5,916 token（按 1280×800 截图约 1,334 token 估算）。
- 最后打印的"YOU NOW COMPLETE PHASE 12"是阶段收尾语。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字符串 `page` 模拟浏览器 | 无需 Selenium/Playwright，确定性强、秒级运行 | 没有 DOM、没有截图、没有坐标；生产用真实浏览器 + 截图 + 可访问性树 |
| 动作计划写死在任务里 | 不需要模型即可演示流程 | 开环，无法应对页面变化；生产由 VLM 每步根据观察产生动作 |
| `ACTION_SCHEMA` 只列参数名 | 一目了然 | 不能表达类型、范围、可选参数，也没被用来校验；生产用 JSON Schema + 约束解码 + 执行前校验 |
| 点击按 `element_desc` 子串决定跳转 | 两行规则即可模拟 | 与当前页面无关、无命中测试，导致任务失败和作弊通过；应改为 `(页面, 元素)` 状态机 + 坐标命中测试 |
| 不可变式状态更新（复制后修改） | 轨迹可回放、易调试 | 复制有开销（这里可忽略）；生产中通常保存每步截图/DOM 快照 |
| 只比较最终页面名判成功 | 简单 | 代理指标太弱；应检查字段、订单等真实状态与副作用 |
| 不相信 agent 自报的 `done` | 避免"自我宣布成功" | 这是对的，应保留 |
| 基准分数写死 | 便于概览 | 部分数字不在讲义中、Ferret-UI 被误当作基准；应注明来源 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，旧版本也能写 `list[dict]` |
| 嵌套字典字面量 | `ACTION_SCHEMA = {"click": ["x", "y", "element_desc"], ...}` | 动作名映射到参数名列表 |
| `@dataclass` 带默认值 | `url: str = "https://mock-booking/"` | 字段默认值；有默认值的字段必须排在无默认值字段之后 |
| `field(default_factory=dict)` | `filled: dict = field(default_factory=dict)` | 可变默认值必须用工厂函数，保证每个实例独立 |
| 关键字参数构造 | `BrowserState(url=state.url, page=state.page, filled=dict(state.filled))` | 按名字传参，清晰且不怕顺序错 |
| `dict(d)` 浅拷贝 | `dict(state.filled)` | 复制一层，修改新字典不影响旧字典 |
| `dict.get(key, default)` | `action.get("element_desc", "")` | 缺失时返回默认值 |
| `in` 子串判断 | `"Book" in desc` | 判断子串；注意会误匹配 "Bookmarks" |
| 条件表达式 | `"reset_sent" if "Forgot" in desc else "login"` | 一行的 if-else |
| `pass` | `elif act == "done": pass` | 占位语句，什么都不做 |
| `enumerate(seq, 1)` | `for step, action in enumerate(task.plan, 1)` | 从 1 开始计数 |
| 元组追加 | `trace.append((step, action["action"], ...))` | 用元组记录一条轨迹 |
| 比较表达式赋值 | `success = (state.page == task.expected_page)` | 布尔值直接作为结果 |
| 返回字典 | `return {"goal": ..., "success": success}` | 轻量的结构化返回值（也可用 dataclass） |
| 元组解包循环 | `for step, act, desc in r["trace"]:` | 每条轨迹拆成三个变量 |
| `dict.items()` | `for act, params in ACTION_SCHEMA.items()` | 同时遍历键和值 |
| f-string 打印列表 | `f"  {act:<18}{params}"` | 列表自动转为 `['x', 'y', ...]` 形式 |
| 下标访问元组 | `r[0]`、`r[1]`、`r[2]` | 可读性不如解包 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |
| `json` 模块 | `import json` | 本文件导入了但**没有使用**；真实 agent 用 `json.loads` 解析模型输出 |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬时完成）：

```text
ACTION SCHEMA
------------------------------------------------------------
  click             ['x', 'y', 'element_desc']
  type              ['text', 'x', 'y']
  ...
  screenshot_region ['x0', 'y0', 'x1', 'y1']
  done              ['success', 'explanation']

BENCHMARK — 2 sample tasks                       ← 讲义说 10 个任务
------------------------------------------------------------
  [PASS] Book flight NYC to Tokyo April 15
    step 1: click      Search
    step 2: type                                 ← type/select/done 没有 element_desc，描述为空
    step 3: click      date
    step 4: select     
    step 5: click      Book
    step 6: done       
  [FAIL] Reset password for user alice@x.com
    step 1: click      Login                     ← page = login
    step 2: click      Forgot password           ← page = reset_sent（过早）
    step 3: type                                 ← filled = {200: 'alice@x.com'}
    step 4: click      Submit                    ← page = confirmation（被覆盖）
    step 5: done                                 ← 自报 success=True，但评估判失败

  score: 1/2

2026 MULTIMODAL AGENT BENCHMARK SNAPSHOT
------------------------------------------------------------
  benchmark           open model                frontier
  ScreenSpot-Pro      Qwen2.5-VL-72B 85         Claude Opus 4.7 ~90
  VisualWebArena      open ~20                  Gemini 3 Pro ~27
  WebArena            open ~35                  saturated ~60      ← 讲义无此数字
  AgentVista          open ~10-20               frontier 27-40
  Ferret-UI mobile    Qwen2.5-VL ~70            GPT-5 ~82          ← Ferret-UI 是模型不是基准
```

逐项解读：

- **订机票 PASS**：Search → search 页，Book → confirmation 页，等于期望。但这个 PASS 并不能说明"订票正确"：输入的 "Tokyo" 和选择的日期都不参与判定，只点 Book 一步也会 PASS。
- **重置密码 FAIL**：逐步状态已在上面标出。这是状态转移规则的 bug，不是计划的问题——修成状态机后通过。它同时说明了一件好事：评估没有采信 agent 的 `done(success=True)`。
- **score 1/2**：在只有 2 个任务时，一个 bug 就让成功率从 100% 变成 50%——小样本基准的结论非常不稳定。
- **记忆策略与阶段总结**：只是打印文字，无计算。

---

## 7. 动手改一改

1. **状态机**：按测验 Q9 把点击逻辑改为 `TRANSITIONS[(page, element_desc)]`，未知动作抛 `ActionError`；确认 2/2 通过，且"只点 Book"的作弊计划失败。再让 `run_task` 的成功判定同时检查 `filled` 中的目的地与日期。
2. **动作校验**：实现测验 Q10 的 `validate_action`，在 `run_task` 执行每个动作前调用，校验失败时把错误写进轨迹并终止；再把 `ACTION_SCHEMA` 改写成带 `required` 和类型的 JSON Schema，让 `type` 的坐标变为可选。
3. **命中测试与错误恢复**：给每个页面加元素表（名称、边界框、下一页面），实现测验 Q11 的 `execute_click`：未命中时用 `element_desc` 重新 grounding，最多重试 2 次，仍失败则记录并触发"重规划"（讲义练习 4）。
4. **闭环策略**：写一个 `policy(goal, state) -> action` 的规则策略代替写死的计划（例如：在 home 页且目标含 "flight" → 点 Search；在 search 页且未填目的地 → type），让动作取决于观察；再把规则策略替换成调用 VLM 的接口桩。
5. **记忆压缩**：实现测验 Q12 的 `build_context`（≤4 张截图 + 全量日志 + 每 5 步摘要），对 5、20、50 步任务打印压缩前后的 token 估算（讲义练习 3）。
6. **扩充基准到 10 个任务**：补足讲义承诺的 10 个任务，覆盖搜索、筛选、填表、多页跳转、需要 `screenshot_region` 读取小字的场景，并加入扰动（按钮坐标偏移、多余的弹窗页）测试错误恢复。

---

## 8. 常见坑

- **相信 agent 自报的成功**：`done(success=True)` 只是模型的说法；评估必须看环境状态。本节重置密码任务就是"自报成功、实际失败"。
- **代理指标过弱**：只比较页面名，会让"跳过所有中间步骤"的计划也通过；要检查字段值和副作用。
- **状态转移不看当前状态**：同一个按钮名在不同页面含义不同，必须用 `(页面, 元素)` 做键。
- **跨截图复用坐标**：页面滚动、重新渲染后坐标会变；每次执行前都应基于最新观察定位，失败时用 `element_desc` 重新 grounding。
- **"点中了"不等于"点对了"**：命中测试要确认命中的元素就是想点的那个。
- **未知动作静默忽略**：模型输出了 schema 之外的动作时应报错并把错误反馈给模型，而不是假装执行了。
- **可变默认值**：dataclass 中写 `filled: dict = {}` 会直接报错，要用 `field(default_factory=dict)`。
- **不可逆操作没有确认**：真实订票、付款前必须人工确认，网页内容中的指令不能被当作用户指令执行。
