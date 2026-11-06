# 测验 · 多模态 Agents 与计算机操作（综合项目）（Multimodal Agents and Computer-Use (Capstone)）

> **阶段 12 · 多模态 AI · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 多模态 agent 循环 | perceive → reason → act → observe → repeat：截图 → 结合 URL 与目标做计划 → 输出结构化动作 → 浏览器执行 → 观察新截图；每一步都是一次 VLM 调用，错误会逐步累积 |
| 2 | GUI grounding | 给定截图和自然语言指令，输出要点击的 `(x, y)`（或其它动作）；SeeClick 首个大规模开源结果，CogAgent 用 1120×1120 高分辨率处理密集 UI，Ferret-UI 面向移动端 |
| 3 | 动作输出用 JSON | 如 `{"action": "click", "x": 384, "y": 220, "element_desc": "Search button"}`；`element_desc` 是语义提示，截图间坐标漂移时可据此重新 grounding |
| 4 | Action schema | 6–10 种动作：click、type、scroll、drag、select、hover、navigate、wait、done，加上可选的视觉工具（如 `screenshot_region`）；每步只输出一个动作 |
| 5 | 三种输入模式 | 纯截图（最通用）、可访问性树 / DOM（grounding 更可靠，但需要树）、混合（树负责原子动作定位，截图负责语义上下文）；生产中能用混合就用混合 |
| 6 | 长程记忆压缩 | summary-chain（每 5 步总结并丢弃旧截图）、skip-frame（保留首、尾和每第 3 张）、工具日志（只保留文本动作日志）；讲义称 Claude computer-use 采用日志模式 |
| 7 | 视觉工具调用 | ChartAgent：输出"裁剪区域 → 调 OCR"一类工具调用，拿到结构化结果后继续推理；set-of-mark、区域标注、外部检测器都符合这个模式 |
| 8 | 基准 | ScreenSpot-Pro（grounding）、VisualWebArena（端到端网页任务）、AgentVista（2026 最难，12 个领域，讲义：前沿模型 27–40%，开源 10–20%）、WebArena/WebShop（已被前沿饱和） |
| 9 | 为什么仍然难 | 细粒度 grounding（"点那个小 X"）、长程规划漂移（10 步后偏离目标）、错误恢复（训练数据里很少有）、跨页面/标签页上下文丢失 |
| 10 | 评估要看真实状态 | 成功与否必须由环境状态（页面、已填字段、副作用）判定，而不是 agent 自己报的 `done(success=True)` |

### 核心技能（能动手做到）

- [ ] 写出一个 action schema，并实现校验器：未知动作、缺参数、多余参数、坐标越界都能拦截
- [ ] 把"只看按钮名字"的页面跳转改写成 `(当前页面, 元素) → 下一页面` 的状态机，并让评估同时检查已填字段
- [ ] 实现闭环执行：点击前做命中测试，失败时用 `element_desc` 重新 grounding，最多重试 2 次，再失败就上报/重新规划
- [ ] 设计"最多 4 张截图在上下文中"的 summary-chain 记忆，并估算 20 步任务压缩前后的 token 数
- [ ] 比较纯截图、可访问性树、混合三种输入模式在不同应用上的取舍
- [ ] 为一个订票类 computer-use 产品设计评估方案与安全措施（付款前人工确认、网页内容中的 prompt injection）

---

## 二、基础自测（选择题）

**Q1.** 讲义描述的多模态 agent 循环是：

- A. perceive → reason → act → observe → repeat
- B. plan 一次 → 一次性输出全部动作 → 执行完毕
- C. act → reason → perceive，只在任务开始时截一次图
- D. reason → act，不需要观察环境，由模型记住每一步的结果

**Q2.** GUI grounding 的 JSON 输出里为什么要带 `element_desc`（如 `"Search button"`）？

- A. 为了让 JSON 更容易通过语法校验
- B. 浏览器执行点击时只认 `element_desc`，坐标仅供参考
- C. 截图之间坐标可能漂移；带上语义提示，执行失败时系统可以据此重新 grounding（skill 文件也规定不能依赖跨截图的坐标记忆）
- D. 用来计算 VisualWebArena 的得分

**Q3.** 关于纯截图、可访问性树和混合三种输入模式，讲义的说法是：

- A. 纯截图模式在所有场景下都最可靠
- B. 混合模式用可访问性树做原子动作的可靠定位，用截图提供语义上下文；浏览器自动化总有树，桌面应用不一定有
- C. 可访问性树在任何桌面应用中都可用，因此无需截图
- D. 混合模式会让 grounding 变差，生产中应避免

**Q4.** 按讲义，Claude 的 computer-use API 采用哪种长程记忆策略？

- A. summary-chain：每 5 步总结一次
- B. skip-frame：保留首、尾和每第 3 张截图
- C. 保留全部截图，不做压缩
- D. 工具记录日志：执行动作后保留文本日志，不再回看旧截图

**Q5.** 运行本节代码，"Reset password" 任务被判为 FAIL，最终页面是 `confirmation`。原因是：

- A. 任务计划少了一步 `navigate`
- B. `apply_action` 只看按钮名字、不看当前页面：第 2 步点 "Forgot password" 就已经把页面设成 `reset_sent`，第 4 步点 "Submit" 又按"含 Submit 就进入 confirmation"的规则把它覆盖掉了
- C. `done` 动作把页面改成了 `confirmation`
- D. `type` 动作没有填入邮箱地址

**Q6.** 讲义 "Use It" 说代码包含"10 个任务的迷你基准"和"动作失败时的错误恢复钩子"，代码 docstring 还说有"按固定策略表输出动作的玩具 VLM"。实际代码是：

- A. 与描述完全一致
- B. 有 10 个任务，但没有错误恢复
- C. 只有 2 个任务；动作计划写死在 `Task.plan` 里按顺序重放（开环），既不读取状态也没有任何 VLM/策略；没有错误恢复钩子
- D. 有错误恢复，但只有 5 个任务

**Q7.** 在本节代码中构造一个新任务：目标仍是"Book flight NYC to Tokyo April 15"，`plan` 只有一步 `{"action": "click", "x": 0, "y": 0, "element_desc": "Book"}`，`expected_page="confirmation"`。`run_task` 的结果是：

- A. FAIL，因为没有输入 "Tokyo"
- B. FAIL，因为坐标 (0, 0) 不在按钮上
- C. 抛出 `KeyError`，因为缺少 `done` 动作
- D. PASS：成功判定只比较最终页面名；既不做坐标命中测试，也不检查是否输入了目的地、选了日期

**Q8.** 讲义 "Why it's still hard" 列出的瓶颈是：

- A. 细粒度视觉 grounding、长程规划漂移、错误恢复、跨页面上下文
- B. 模型参数太少、训练数据太多、GPU 太贵、推理太快
- C. JSON 解析太慢、浏览器不支持点击、截图分辨率过高、网络延迟
- D. 只有 grounding 一个问题，规划已经解决

---

## 三、动手 / 代码题

**Q9.** 阅读 `apply_action` 中的点击逻辑：

```python
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
```

1. 逐步写出 "Reset password" 任务每一步之后的 `page`。
2. 指出这段逻辑至少三个问题（跳转条件、`type` 的存储方式、未知动作的处理）。
3. 改写为 `TRANSITIONS = {(当前页面, element_desc): 下一页面}` 的状态机版本，未知动作抛异常；运行两个任务并写出结果；再用 Q7 的"只点 Book"计划测试。

**Q10.** 代码定义了 `ACTION_SCHEMA`，但从未用它校验动作。写 `validate_action(a, screen=(1280, 800))`，检查：未知动作、缺少参数、多余参数、坐标必须是整数且在屏幕内。写出以下输入的校验结果，并讨论讲义中 `type: (text, x?, y?)` 的"可选参数"在这个 schema 里如何表达：

```python
{"action": "click", "x": 384, "y": 220, "element_desc": "Search button"}
{"action": "click", "x": 384, "y": 220}
{"action": "type", "text": "Tokyo"}
{"action": "click", "x": 1500, "y": 220, "element_desc": "X"}
{"action": "tap", "x": 1, "y": 2}
{"action": "scroll", "direction": "down", "amount": 3, "speed": 2}
```

**Q11.** 讲义练习 4 与 skill 文件要求错误恢复："On action failure, re-ground via element_desc semantic hint; retry up to 2 times; fall back to replanning." 给页面加上元素表 `{页面: {元素名: (x0, y0, x1, y1, 下一页面)}}`，实现 `execute_click(page, action, max_retries=2)`：先做命中测试；未命中或命中了别的元素时，用 `element_desc` 在元素表（相当于可访问性树）里重新定位到元素中心再试；重试用尽返回失败。用"Book 按钮坐标漂移 30 像素"和"点击不存在的 Pay now"两个例子演示。

**Q12.** 讲义练习 3：设计一个 summary-chain，任意时刻最多 4 张截图在上下文中，日志不限条数。假设一张 1280×800 截图按 Qwen2.5-VL"每 28×28 像素一个 token"计、一行动作日志 20 token、一段 5 步摘要 60 token。写 `build_context(history, keep_shots=4, summary_every=5)`，计算 5、20、50 步时压缩后与"保留全部截图 + 日志"的 token 数。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 GUI grounding？SeeClick、CogAgent、Ferret-UI 各自的贡献是什么？为什么动作输出要用带 schema 的 JSON 而不是自由文本？

**Q14.**（原理深挖）比较纯截图、可访问性树、混合三种输入模式。讲义练习 5 要比较"纯截图的 Claude 4.7"和"截图 + 可访问性树的 Qwen2.5-VL"在 10 个网页任务上的表现：你预期谁在哪类任务上赢？为什么？

**Q15.**（工程实践）一个 20 步的网页工作流会产生 20 张截图。请设计记忆/上下文管理方案，并估算压缩前后的 token 开销；超过 50 步的工作流又该怎么办？

**Q16.**（场景设计）设计一个"帮我订 4 月 15 日去东京、靠过道、800 美元以内的机票并完成预订"的 computer-use agent：动作集、输入模式、错误恢复、评估方式，以及上线前必须有的安全措施。

**Q17.**（追问型）为什么前沿模型在 VisualWebArena、AgentVista 上的成功率仍只有 30% 左右，而 ScreenSpot 类 grounding 基准却很高？如果你的 agent 在内部评估中成功率 90%，你会怀疑什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义学习目标："Design a multimodal agent loop: perceive → reason → act → observe → repeat." 并在 "The Problem" 中列出：截图 → 解析截图 + URL + 目标得到计划 → 输出结构化动作 → 执行 → 观察新状态 → 重复。B 是开环一次性计划（恰好是本节代码的实际行为，见 Q6），无法应对页面变化；C、D 缺少"观察"，错误会无声累积。

### Q2 — 答案：C

讲义："The `element_desc` helps recovery: if coordinates drift between screenshots, the semantic hint lets the system re-ground." skill 文件硬性拒绝 "Relying on coordinate memory across screenshots. Coordinates drift between captures." A 与语义无关；B 错，点击执行依赖坐标，描述用于恢复；D 无关。

### Q3 — 答案：B

讲义："Hybrid: both, with the tree as a reliable grounder for atomic actions and the screenshot for semantic context ... Browser automation (Selenium + accessibility) always has the tree; desktop apps sometimes do." A 错，纯截图最通用但 grounding 最不可靠；C 错，桌面应用"sometimes"才有；D 与"Production agents use hybrid when possible"相反。

### Q4 — 答案：D

讲义："Tool-recorded log: execute actions, keep a text log of what was done; don't re-look at old screenshots. Claude's computer-use API uses the log pattern. Simpler, more reliable." A、B 是另外两种策略；C 会让上下文迅速被截图塞满（20 张 1280×800 截图按 Qwen2.5-VL 规则约 2.7 万 token，见 Q12）。

### Q5 — 答案：B

逐步实测：`click Login → login`；`click Forgot password → reset_sent`（还没输入邮箱就已"发送"）；`type → reset_sent`；`click Submit → confirmation`（"Submit" 命中第一条分支，覆盖了正确状态）；`done → confirmation`。期望 `reset_sent`，所以 FAIL。根源是跳转规则只看按钮文字，不看当前页面，也没有"页面上是否真的有这个按钮"的概念。A 错，计划不需要 navigate；C 错，代码注释写明 `done` 不改页面；D 错，`filled` 里确实有 `{200: 'alice@x.com'}`。

### Q6 — 答案：C

代码 `mock_tasks()` 只返回 2 个任务（`run_benchmark` 自己也打印 "2 sample tasks"）；`run_task` 只是 `for action in task.plan: state = apply_action(state, action)`，动作完全不依赖观察到的状态，是开环重放；没有任何 VLM、策略表或错误恢复代码。讲义的描述与代码不符，这也是本节最值得补完的部分（Q9–Q12）。

### Q7 — 答案：D

已实际运行：`cheat: True`。`run_task` 的成功判定只有 `state.page == task.expected_page`；`apply_action` 不做坐标命中测试（(0, 0) 处没有任何按钮也照样"点中"），也不要求当前页面上有 Book 按钮。评估既没检查目的地 "Tokyo" 是否填写、日期是否选择，更没检查讲义原始需求里的"靠过道、800 美元以内"。同理，一个包含未知动作 `{"action": "fly"}`、期望页面为 `home` 的任务也会被判 PASS。这说明：**评估必须检查环境的真实状态和副作用，而不是一个容易被"走捷径"满足的代理指标**。A、B 是合理的期望但代码没实现；C 错，`done` 不是必需的。

### Q8 — 答案：A

讲义："1. Visual grounding at fine scale ... 2. Long-horizon planning ... 3. Error recovery ... 4. Cross-page context." 对应的研究方向是记忆架构、显式重规划、多模态验证（用截图比对确认动作是否成功）。B、C 是无关或错误的说法；D 与讲义相反。

### Q9 — 参考答案

1. 见 Q5：`login → reset_sent → reset_sent → confirmation → confirmation`。

2. 问题：
   - **跳转与当前页面无关**：任何页面上点"Submit"都会进入 `confirmation`，"Forgot" 一点就是 `reset_sent`；真实网站是"在哪个页面点了什么"决定下一页。
   - **没有命中测试**：坐标完全没用到，`element_desc` 写什么就点中什么——这让 grounding 这一核心难点在模拟中消失了。
   - **子串匹配**：`"Book" in desc` 会让 "Bookmarks"、"Facebook" 也触发预订。
   - **`type` 的存储**：`new.filled[action.get("x", 0)]` 用 x 坐标（整数）做键，和 `"select_idx"`（字符串）混在一个字典里；两个 x 相同的输入框会互相覆盖；缺参数时默认 x = 0 而不是报错。
   - **未知动作静默忽略**：`navigate`、`scroll` 等没有分支，`"fly"` 这样的非法动作也不报错。

3. 参考实现（已运行验证）：

```python
TRANSITIONS = {
    ("home", "Search"): "search",
    ("search", "Book"): "confirmation",
    ("home", "Login"): "login",
    ("login", "Forgot password"): "forgot",
    ("forgot", "Submit"): "reset_sent",
}

class ActionError(Exception):
    pass

def apply_action_v2(state, action):
    new = BrowserState(url=state.url, page=state.page, filled=dict(state.filled))
    act = action["action"]
    if act not in ACTION_SCHEMA:
        raise ActionError(f"unknown action {act!r}")
    if act == "click":
        key = (state.page, action.get("element_desc", ""))
        if key in TRANSITIONS:
            new.page = TRANSITIONS[key]
        # 其它点击（如日期输入框）不改变页面
    elif act == "type":
        new.filled[f"field@{action['x']},{action['y']}"] = action["text"]
    elif act == "select":
        new.filled["select_idx"] = action["option_index"]
    return new
```

   结果：订票任务最终 `confirmation`，`filled = {'field@300,240': 'Tokyo', 'select_idx': 15}`；重置密码任务最终 `reset_sent`，两个任务都通过（2/2）。Q7 的"只点 Book"在 `home` 页上找不到 `("home", "Book")` 这条转移，停留在 `home`，判为失败——作弊路径被堵住。进一步还应让评估检查 `filled` 中是否有 "Tokyo"、日期是否为 15。

### Q10 — 参考答案

```python
def validate_action(a, screen=(1280, 800)):
    errs = []
    act = a.get("action")
    if act not in ACTION_SCHEMA:
        return [f"unknown action: {act!r}"]
    need = ACTION_SCHEMA[act]
    missing = [p for p in need if p not in a]
    extra = [k for k in a if k != "action" and k not in need]
    if missing:
        errs.append(f"missing: {missing}")
    if extra:
        errs.append(f"unexpected: {extra}")
    W, H = screen
    for kx, ky in (("x", "y"), ("x0", "y0"), ("x1", "y1")):
        if kx in a and ky in a:
            x, y = a[kx], a[ky]
            if not (isinstance(x, int) and isinstance(y, int)):
                errs.append(f"{kx},{ky} must be int")
            elif not (0 <= x < W and 0 <= y < H):
                errs.append(f"({x},{y}) outside screen {W}x{H}")
    return errs
```

实测输出：

| 输入 | 结果 |
|------|------|
| 合法 click | `[]` |
| click 缺 `element_desc` | `["missing: ['element_desc']"]` |
| `type` 只有 text | `["missing: ['x', 'y']"]` |
| click x = 1500 | `['(1500,220) outside screen 1280x800']` |
| `tap` | `["unknown action: 'tap'"]` |
| scroll 多了 `speed` | `["unexpected: ['speed']"]` |

两个原始任务的全部 11 个动作都通过校验。讨论：讲义写 `type: (text, x?, y?)`，即坐标可选（可以向当前焦点元素输入），但代码的 `ACTION_SCHEMA` 只是"参数名列表"，无法区分必选与可选，于是合法的"只给 text"被判为缺参数。生产中应改用 JSON Schema（`required` 字段 + 每个参数的类型、范围、枚举值，例如 `direction ∈ {up, down, left, right}`），并直接作为 tool calling 的工具定义交给模型，配合约束解码；skill 文件也要求"Always JSON-structured with explicit schema"。校验失败时不要执行，而是把错误信息作为观察反馈给模型重新生成。

### Q11 — 参考答案

参考实现（已运行验证）：

```python
PAGES = {   # page -> {element_desc: (x0, y0, x1, y1, next_page)}
    "home":   {"Search": (100, 180, 160, 220, "search"), "Login": (30, 30, 80, 70, "login")},
    "search": {"Book": (460, 380, 560, 420, "confirmation")},
}

def hit_test(page, x, y):
    for desc, (x0, y0, x1, y1, nxt) in PAGES[page].items():
        if x0 <= x < x1 and y0 <= y < y1:
            return desc, nxt
    return None, None

def reground(page, desc):
    """用 element_desc 在可访问性树/元素表中重新定位，返回元素中心。"""
    for d, (x0, y0, x1, y1, _) in PAGES[page].items():
        if desc.lower() in d.lower():
            return (x0 + x1) // 2, (y0 + y1) // 2
    return None

def execute_click(page, action, max_retries=2, log=None):
    x, y, desc = action["x"], action["y"], action["element_desc"]
    for attempt in range(max_retries + 1):
        hit, nxt = hit_test(page, x, y)
        if hit is not None and desc.lower() in hit.lower():   # 点中了且点中的是"想点的那个"
            log.append(f"click {desc!r} at ({x},{y}) ok -> {nxt}")
            return nxt, True
        log.append(f"click {desc!r} at ({x},{y}) missed (hit={hit})")
        pos = reground(page, desc)
        if pos is None:
            break                                              # 页面上根本没有这个元素
        x, y = pos
        log.append(f"  re-grounded via element_desc -> ({x},{y})")
    log.append(f"  give up on {desc!r}: replan / report failure")
    return page, False
```

运行输出：

```text
click 'Search' at (120,200) ok -> search
click 'Book' at (500,450) missed (hit=None)
  re-grounded via element_desc -> (510,400)
click 'Book' at (510,400) ok -> confirmation
...
click 'Pay now' at (10,10) missed (hit=None)
  give up on 'Pay now': replan / report failure
```

要点：
- **"点中"要验证"点中的是想点的元素"**，否则点到相邻按钮也会被当作成功（讲义的瓶颈 3）。
- 重新 grounding 的来源：混合模式下用可访问性树；纯截图模式下把 `element_desc` 和新截图再交给 VLM 定位，或用 `screenshot_region` 裁剪放大后再定位。
- 元素根本不存在时不要盲目重试，应进入重规划（可能是页面没加载完——可先 `wait` 再截图；也可能前一步走错了页面——需要回退）。
- 真实系统中"动作是否生效"要靠**动作后的观察**验证（讲义的"multimodal verification"：比对截图或检查 DOM 变化）。

### Q12 — 参考答案

1280×800 截图：`round(1280/28) × round(800/28) = 46 × 29 = 1,334` token。参考实现（已运行验证）：

```python
SHOT_TOKENS, LOG_TOKENS, SUMMARY_TOKENS = 1334, 20, 60

def build_context(history, keep_shots=4, summary_every=5):
    n = len(history)
    live_from = max(0, n - keep_shots)                       # 最近 keep_shots 步保留截图
    n_old = (live_from // summary_every) * summary_every     # 只对完整的 5 步块做摘要
    summaries = [f"summary of steps {i+1}-{i+summary_every}"
                 for i in range(0, n_old, summary_every)]
    logs = [f"step {i+1}: {h['action']} -> {h['result']}" for i, h in enumerate(history)]
    shots = [h["shot"] for h in history[live_from:]]
    tokens = (len(summaries) * SUMMARY_TOKENS + len(logs) * LOG_TOKENS
              + len(shots) * SHOT_TOKENS)
    return {"summaries": summaries, "logs": logs, "shots": shots, "tokens": tokens}
```

| 步数 | 摘要段数 | 在上下文中的截图 | 压缩后 token | 全保留 token |
|------|---------|----------------|-------------|-------------|
| 5 | 0 | s2–s5 | 5,436 | 6,770 |
| 20 | 3（覆盖 1–15 步） | s17–s20 | 5,916 | 27,080 |
| 50 | 9 | s47–s50 | 6,876 | 67,700 |

结论：压缩后 token 几乎只随日志线性缓慢增长（每步 20 token），而全保留随截图线性快速增长（每步约 1,354 token）。设计细节：摘要由 LLM 生成，应包含"已完成的子目标、当前所在页面、已填写的关键字段、尚未满足的约束"；第 1 步截图（任务起点）有时也值得保留；日志过长时日志本身也可以再摘要。

### Q13 — 参考回答要点

- **定义**：给定截图与自然语言指令，输出目标元素的坐标或动作（讲义 Key Terms："Model outputs (x,y) for the target of an instruction on a screenshot"）。它是一切 GUI agent 的原语——计划再好，点不中就失败。
- **SeeClick**（arXiv:2401.10935）：首个大规模开源结果，在合成 + 真实 GUI 数据上微调 VLM，把坐标当作普通文本 token 输出。
- **CogAgent**（arXiv:2312.08914）：加入 1120×1120 高分辨率编码，处理密集 UI；讲义称网页导航约 84%。
- **Ferret-UI**（arXiv:2404.05719）：面向移动端 UI，结合 iOS 可访问性数据。
- **为什么用 JSON + schema**：可解析、可校验（Q10）、可直接作为 tool calling 的工具定义并配合约束解码；自由文本需要脆弱的正则解析，一步出错就会让多步任务整体失败（讲义："The VLM output must be parseable JSON. Errors compound across steps"）。skill 文件把自由文本动作输出列为硬性拒绝。
- 加分点：说明坐标的参考系（原始截图像素 vs 模型缩放后的分辨率）必须统一，否则会出现系统性偏移。

### Q14 — 参考回答要点

| 模式 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| 纯截图 | 任何应用都能用；能看到渲染后的真实样子（图标、颜色、canvas 内容） | 细粒度 grounding 难，小按钮、密集 UI 易点错；token 多 | 无可访问性接口的桌面应用、游戏、远程桌面 |
| 可访问性树 / DOM | 元素有明确的 id、角色、文本和边界框，定位可靠 | 依赖接口；看不到 canvas/图片内容；树可能很大、可能与视觉不一致 | 浏览器、提供 a11y 的原生应用 |
| 混合 | 树负责原子动作定位，截图负责语义理解 | 实现复杂、两者需要对齐 | 生产中能用就用（讲义） |

- **练习 5 的预期**：在标准表单、按钮、链接密集的网页任务上，混合模式的 Qwen2.5-VL 更可能胜出——树让定位几乎不会错；在需要理解视觉内容的任务（图表、图片中的信息、canvas 绘制的控件、视觉布局判断）上，纯截图但更强的 Claude 4.7 可能胜出；长流程任务主要取决于规划和恢复能力，强底座模型占优。必须用实验验证，并按任务类型分别统计。
- 加分点：set-of-mark——在截图上给可交互元素叠加编号，让模型输出编号而不是坐标，是介于两者之间的折中。

### Q15 — 参考回答要点

- **开销估算**：1280×800 截图按 Qwen2.5-VL 规则约 1,334 token，20 步全保留约 2.7 万 token；按 Q12 的 summary-chain（≤4 张截图 + 全量日志 + 每 5 步摘要）约 5,900 token。
- **方案**（skill 文件："Summary-chain every 5 steps + last-2 screenshots live; log-only for very long workflows"）：
  - 上下文 = 任务目标 + 约束清单 + 历史摘要 + 动作日志 + 最近 2–4 张截图；
  - 摘要记录已完成子目标、当前页面、关键字段值、未满足的约束；
  - 需要回看旧页面时，用工具重新导航/截图，而不是保留旧截图。
- **超过 50 步**：skill 文件要求拒绝单 agent 循环，改为分层"规划者 + 执行者"——规划者维护高层计划和进度，执行者只负责一个子任务的短循环；每个子任务结束时做检查点（checkpoint），失败可从检查点重试。
- 常见误区：只看 token 不看质量——过度压缩会丢失后续步骤需要的细节（例如前面看到的价格），所以关键事实要写进结构化的"工作记忆"而不只是自由文本摘要。

### Q16 — 参考回答要点

- **动作集**：click、type、scroll、select、navigate、wait、done，加 `screenshot_region` 用于读取座位图/价格的小字（练习 1）；每个动作都有 JSON schema 和校验（Q10）。
- **输入模式**：浏览器场景用混合（DOM/可访问性树 + 截图）。
- **流程**：搜索航班 → 按约束过滤（日期 4/15、价格 ≤ 800 美元）→ 选座（靠过道）→ 填写乘客信息 → **在付款前停下来请用户确认**。
- **错误恢复**：命中测试 + `element_desc` 重新 grounding + 最多 2 次重试 + 重规划（Q11）；每步动作后验证页面是否按预期变化。
- **评估**：用沙箱/模拟站点构造固定任务集，成功判定检查最终状态（订单是否存在、日期、价格、座位类型），而不是 agent 自报的 `done`；统计成功率、平均步数、恢复次数、约束违反率。
- **安全措施**：
  - 付款、提交个人信息等不可逆操作必须人工确认（propose-then-commit）；
  - 防 prompt injection：网页内容（广告、评论、隐藏文字）只能作为数据，不能当作指令；
  - 权限最小化：在隔离的浏览器配置/沙箱中运行，不接触无关账号和文件；
  - 预算与步数上限、完整审计日志（每步截图与动作）。
- 常见误区：让 agent 自己判断"已完成"并直接付款。

### Q17 — 参考回答要点

- **grounding 高、端到端低**：ScreenSpot 类基准只测单步定位；端到端任务的成功率近似是每一步成功率的乘积——即使单步 95%，20 步全对的概率也只有 `0.95²⁰ ≈ 36%`。再叠加讲义的四个瓶颈：长程规划漂移、错误恢复缺乏训练数据、跨页面状态丢失、细粒度目标（小 X 按钮）。
- **AgentVista 更难**：讲义描述为 12 个领域的真实工作流，前沿 27–40%，开源 10–20%；skill 文件指出开源 7B 与前沿在 AgentVista 上仍差 10–20 分。
- **内部评估 90% 时要怀疑**：
  - 成功判定是否只看代理指标（如最终页面名）而非真实状态——本节代码就是例子（Q7：只点 Book 也能 PASS）；
  - 是否用 agent 自报的 `done(success=True)` 计分（本节 "Reset password" 任务自报成功，实际失败）；
  - 任务是否过于简单、与训练数据重叠、环境是否确定性过强（没有弹窗、加载延迟、布局变化）；
  - 是否只跑了少量任务（本节只有 2 个）。
- 加分点：把评估环境做成可复位的沙箱，加入扰动（布局变化、弹窗、慢加载），并分别报告 grounding 准确率、单步成功率和端到端成功率。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：本节先修；VLM 如何读截图。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率视频](../../09-qwen-vl-family-dynamic-fps/docs/zh.md)：本节先修；原生动态分辨率与 JSON/坐标输出。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：perceive → reason → act → observe 循环的基础。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：action schema 的规范表达与约束解码。
- [阶段 12 · 22 文档与图解理解](../../22-document-diagram-understanding/docs/zh.md)：读懂高分辨率页面是读懂屏幕的前提。

### 本节被哪些后续内容用到
- [阶段 14 · 21 计算机操作：Claude、OpenAI CUA、Gemini](../../../14-agent-engineering/21-computer-use-agents/docs/zh.md)：主流 computer-use 产品的接口与实践。
- [阶段 14 · 20 基准评测：WebArena 与 OSWorld](../../../14-agent-engineering/20-benchmarks-webarena-osworld/docs/zh.md)：端到端 agent 基准的细节。
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../../15-autonomous-systems/11-browser-agents/docs/zh.md)：长程网页任务中的记忆与恢复。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：付款等不可逆操作前的人工确认。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：网页内容作为攻击面。

### 延伸关键词
`GUI grounding` · `SeeClick` · `CogAgent` · `Ferret-UI` · `action schema` · `accessibility tree` · `set-of-mark` · `summary-chain` · `visual tool use` · `ScreenSpot-Pro` · `VisualWebArena` · `AgentVista` · `error recovery` · `propose-then-commit`
