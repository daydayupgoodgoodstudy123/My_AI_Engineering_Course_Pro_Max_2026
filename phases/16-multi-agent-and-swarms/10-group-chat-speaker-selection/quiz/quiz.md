# 测验 · 群聊与发言者选择（Group Chat and Speaker Selection）

> **阶段 16 · 多智能体与集群 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 提示：中文讲义为机器翻译，"round-robin"被译成"圆形"、"projections"被译成"预测"、"GroupChat"有时被译成"集团"。另外讲义说 projection 见 "Lesson 15"，但本阶段第 15 节讲的是投票与辩论拓扑，projection 实际在第 13 节（共享记忆与黑板模式）中讲解。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | GroupChat 的形状 | N 个 agent 共享一个消息池，每个 agent 都读全部消息；每一轮由 selector 函数决定下一个发言者 |
| 2 | 为什么需要 GroupChat | 静态图适合流程已知的任务；真实对话中"谁问谁"不固定，把所有可能的 handoff 都硬编码会造成边爆炸（edge explosion） |
| 3 | 三种 selector | round-robin（固定循环、确定、忽略上下文）；LLM-selected（读最近消息选人，懂上下文但每轮多一次 LLM 调用，是 AutoGen 默认）；custom（LLM + 规则兜底） |
| 4 | AutoGen API | `ConversableAgent(name, system_message, llm_config)`、`GroupChat(agents, messages)`、`GroupChatManager` 持有 selector 并循环 |
| 5 | 终止条件 | max rounds 硬上限、`TERMINATE` 哨兵、goal-reached 检查（轻量 verifier）；生产中要组合使用 |
| 6 | 谱系 | 讲义：AG2 分叉保留了 AutoGen v0.2 的 GroupChat 语义；v0.4 重写为事件驱动 actor 模型；2026 年 2 月 AutoGen 进入维护模式并与 Semantic Kernel 合并为 Microsoft Agent Framework |
| 7 | 适用场景 | 涌现式对话、角色交叉提问（流程不是 DAG）、探索式问题求解（"头脑风暴会"而非"流水线"） |
| 8 | 失效模式 | LLM selector 不确定、谄媚级联、上下文膨胀（每个人读全部消息）、hot speaker（某 agent 霸占发言） |
| 9 | GroupChat vs supervisor | 原语相同、默认值不同：supervisor 是"问 planner 下一步"；GroupChat 是所有 agent 平等、selector 作用于共享池 |
| 10 | 生产清单 | max rounds（10–20）、speaker-balance 指标、终止 token 或 verifier、约 10 条消息后用 projection 限定视图、记录 selector 的输入和选择 |

### 核心技能（能动手做到）

- [ ] 用标准库写出一个 GroupChat 循环：共享池、selector、agent policy、`TERMINATE` 与 `max_rounds` 双重终止
- [ ] 实现 round-robin 与"按上下文路由"的 selector，并能根据代码预测完整的发言轨迹
- [ ] 读懂本节 `coder_policy` 的上下文窗口逻辑，找出它在 round-robin 下"丢失审稿意见"的 bug 并修复
- [ ] 给 selector 加上每 agent 发言次数上限、speaker-balance 统计和 selector 日志
- [ ] 实现 goal-reached 终止，并比较它与 `TERMINATE` 哨兵的优缺点
- [ ] 根据任务结构（DAG 与否、是否需要审计、agent 数量）判断该用 GroupChat、supervisor 还是静态图

---

## 二、基础自测（选择题）

**Q1.** 关于 GroupChat 的结构，正确的描述是：

- A. 每个 agent 只能看到发给自己的消息，由 supervisor 转发
- B. 所有 agent 共享一个消息池、都能读到全部消息；每一轮由一个 selector 函数选出下一个发言者
- C. agent 之间按预先定义的有向无环图依次执行
- D. 每个 agent 并行回答，最后投票选出答案

**Q2.** 关于三种 selector 的取舍，下列说法正确的是：

- A. round-robin 能根据话题自动选择最合适的 agent
- B. LLM-selected 完全确定，同样的输入一定选出同一个人
- C. custom selector 不能调用 LLM，只能写规则
- D. LLM-selected 懂上下文，但每一轮都要多一次 LLM 调用，更慢更贵，且结果可能不稳定；round-robin 确定但忽略上下文

**Q3.** 运行 `code/main.py`，round-robin 场景的实际结果是：

- A. 4 轮后由 coder 发出 `TERMINATE` 结束，reviewer 要求的修复从未发生，`a - b` 的 bug 留在了最终结果里
- B. 6 轮后 reviewer 批准、manager 发出 `TERMINATE`
- C. 达到 `max_rounds=8` 才停止
- D. reviewer 在第 1 轮就批准了代码

**Q4.** round-robin 场景第 4 轮轮到 coder 时，它为什么没有修复代码而是发出 `TERMINATE`？相关代码：

```python
def coder_policy(pool: list[Msg]) -> str:
    recent = [m for m in pool[-3:] if m.speaker != "coder"]
    last = recent[-1].content if recent else ""
    if "review" in last.lower() or "fix" in last.lower():
        return "revised code: return a + b"
    if not any(m.speaker == "coder" for m in pool):
        return "initial code: return a - b  (buggy)"
    return "TERMINATE"
```

- A. 因为 reviewer 的消息不包含 "fix"
- B. 因为 `pool[-3:]` 只取了前 3 条消息
- C. 因为 coder 只看"最近 3 条中最后一条非 coder 消息"，此时那条是 manager 的 "manager: continue working"，既无 "review" 也无 "fix"；而 coder 已经发过言，于是落到最后的 `return "TERMINATE"`
- D. 因为 round-robin selector 返回了 `None`

**Q5.** 在本节的 `llm_style_selector` 中，reviewer 发出 "review: approved" 之后，下一个发言者是谁？

- A. coder
- B. manager
- C. reviewer 自己
- D. `None`，对话立即结束

**Q6.** 本节的终止判断是 `content.strip().endswith("TERMINATE")`。下列哪条消息会被**错误地**当成终止信号？

- A. `"Please do not TERMINATE"`
- B. `"TERMINATE."`
- C. `"terminate"`
- D. `"TERMINATE now"`

**Q7.** 讲义指出 GroupChat 的"上下文膨胀（context bloat）"问题，推荐的缓解办法是：

- A. 把 max rounds 调到 100
- B. 改用 round-robin selector
- C. 去掉 `TERMINATE` 终止
- D. 大约 10 条消息之后，用 projection（按角色限定的视图）或作用域记忆，只给每个 agent 看与其角色相关的部分

**Q8.** 关于 AutoGen 的谱系，讲义的描述是：

- A. AG2 是 AutoGen v0.4 的官方新名字，采用 actor 模型
- B. AutoGen 已被完全废弃，GroupChat 概念不再存在
- C. 社区分叉 AG2 保留了 AutoGen v0.2 的 GroupChat 语义；AutoGen v0.4 重写为事件驱动 actor 模型；2026 年 2 月 AutoGen 进入维护模式，与 Semantic Kernel 合并为 Microsoft Agent Framework，GroupChat 概念在两条线中都保留了
- D. Microsoft Agent Framework 只支持静态图，不支持 GroupChat

---

## 三、动手 / 代码题

**Q9.** Q3/Q4 暴露了 `coder_policy` 的问题。请：

1. 指出它的**两个**缺陷（提示：除了"只看最近 3 条"之外，再看看 reviewer 的批准消息 "review: approved" 会触发什么）。
2. 写一个修复版 `coder_policy`：只在"最近一条 reviewer 消息晚于最近一条 coder 消息、且要求修复"时才修改代码，否则等待；coder 不应自行发出 `TERMINATE`。
3. 用修复版重新跑 round-robin（`max_rounds=8`），写出发言轨迹。

**Q10.** 讲义练习 2：给 selector 加一条"每个 agent 最多发言 k 次"的规则。请写一个包装函数 `capped(selector, cap)`：若原 selector 选中的人已达上限，就改选第一个未达上限的 agent；所有人都达上限时返回 `None`。分别用 `cap=1` 和 `cap=2` 包装 `llm_style_selector` 运行，结果有何不同？这说明了什么？

**Q11.** 把 `AGENTS` 字典的顺序改成 `reviewer → coder → manager`，用原始的 `coder_policy` 和 round-robin、`max_rounds=8` 运行。请预测（或运行得到）完整的发言轨迹，并解释：为什么 reviewer 已经批准了，对话却没有终止，而是一直跑到上限？

**Q12.** 讲义练习 3 + Ship It "selector logging"：

1. 实现 goal-reached 终止：reviewer 的消息包含 "approved" 时立即停止。分别对原始 round-robin、原始 LLM-style、修复版 coder + round-robin 运行，各在第几轮、以什么原因停止？
2. 讲义说"For LLM-selected variants, log both the selector's input and its choice. Otherwise debugging is impossible." 本节 `run_groupchat` 只记录了 `trace`（选择结果）。请说明一条合格的 selector 日志应包含哪些字段。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 GroupChat 式多 agent 编排？speaker selection 有哪几种方式，各自的优缺点是什么？如何终止？

**Q14.**（原理深挖）GroupChat、supervisor、静态图（如 LangGraph）三者在"谁决定下一步"上有什么本质区别？什么时候该选哪一个？

**Q15.**（工程实践）一个 4 个 agent 的 LLM-selected GroupChat 跑 20 轮，每条消息约 200 token。请估算上下文开销与 LLM 调用次数，并给出上线前必须做的工程措施。

**Q16.**（场景设计）设计一个线上故障排查（incident response）的 GroupChat：值班 SRE agent、日志分析 agent、数据库专家 agent、变更记录 agent、总结 agent。你会怎么设计 selector 和终止条件？

**Q17.**（追问型）上线后发现某个 agent 几乎每轮都被选中（hot speaker），而且其他 agent 常常附和它（谄媚级联）。你怎么定位和解决？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Every agent sees every message. A selector function is invoked at each turn to pick who speaks next." A 描述的是 supervisor 转发式；C 是静态图（LangGraph）；D 是并行投票（第 15 节）。

### Q2 — 答案：D

讲义：round-robin "Deterministic ... but ignores context"；LLM-selected "Context-aware but slow: every turn adds an LLM call. AutoGen's default."；失效模式中又指出 "The LLM selector can be inconsistent. Same prompt, different runs, different next speakers." A 把 round-robin 和 LLM-selected 弄反了；B 错在 LLM 的不确定性；C 错，讲义说 custom 的典型做法就是"LLM-selected with fallback rules"。

### Q3 — 答案：A

实际运行输出：

```text
=== Round-robin ===
  [coder   ]: initial code: return a - b  (buggy)
  [reviewer]: review: bug detected -- sum must be a+b, please fix
  [manager ]: manager: continue working
  [coder   ]: TERMINATE
  Selector trace: ['coder', 'reviewer', 'manager', 'coder']
  Rounds used: 4
  Speaker counts: {'coder': 2, 'reviewer': 1, 'manager': 1}
```

对话以"有 bug 的代码 + coder 自己宣布结束"收场。B 是 LLM-style 场景的结果；C、D 与输出不符。脚本的总结只说 "Round-robin gives every agent an equal turn regardless of context"，没有指出这次 round-robin 实际产出了错误结果——这是本节演示最值得注意的地方：**忽略上下文的轮转，会让关键反馈被插话"冲掉"**。

### Q4 — 答案：C

第 4 轮时 `pool[-3:]` = `[coder 初稿, reviewer 修复要求, manager 继续]`，去掉 coder 后 `recent = [reviewer, manager]`，`last` 取的是 manager 的 "manager: continue working"。它不含 "review"/"fix"（注意是 "manager: continue working"，没有 "review" 字样），而 coder 已经发过言，第二个分支也不成立，于是 `return "TERMINATE"`。A 错，reviewer 的消息含 "please fix"；B 错，`pool[-3:]` 是**最后** 3 条；D 错，round-robin 从不返回 `None`。

### Q5 — 答案：B

```python
    if last.speaker == "reviewer":
        if "approved" in last.content:
            return "manager"
        return "coder"
```

reviewer 批准 → 交给 manager；manager 的 policy 看到池中有 "approved" 就返回 `TERMINATE`。所以 LLM-style 轨迹是 `manager → coder → reviewer → coder → reviewer → manager`，共 6 轮。

### Q6 — 答案：A

`"Please do not TERMINATE".strip().endswith("TERMINATE")` 为 `True`（已验证）——否定句也会触发终止，属于误判。B `"TERMINATE."` 以句号结尾，`endswith` 为 `False`，属于**漏判**而不是误判；C 大小写不同，不匹配；D 不以 TERMINATE 结尾。生产中更稳妥的做法是：让 agent 通过**结构化字段**（如 `{"action": "terminate"}` 或专门的 tool call）表达终止意图，而不是在自然语言里找关键字；AutoGen 中也常通过 `is_termination_msg` 自定义判断函数。

### Q7 — 答案：D

讲义："Context bloat. Every agent reads every message; after 10 turns the context is huge. Use projections ... to scope views." 以及 Ship It："After ~10 messages, consider giving each agent only a scoped view." A 让问题更糟；B 只改变谁发言，不改变每人读多少；C 与上下文大小无关，还会失去终止手段。（讲义写的是 "Lesson 15"，但 projection 的详细讨论在本阶段第 13 节。）

### Q8 — 答案：C

这是讲义 "Lineage: forks and mergers" 一节的内容（相关日期以讲义为准）。A 把 AG2 与 v0.4 搞反了：AG2 保留的是 v0.2 的 API；讲义："AG2 is the preferred upstream for v0.2-compatible code." B、D 与讲义"The GroupChat primitive survives in both AG2 and Microsoft Agent Framework"相矛盾。

### Q9 — 参考答案

1. 两个缺陷：
   - **窗口太窄**：只看"最近 3 条里最后一条非 coder 消息"。只要 reviewer 和 coder 之间插入了别人（如 manager）的发言，修复请求就被"冲掉"（Q4）。
   - **关键字太宽**：`"review" in last.lower()` 会匹配 reviewer 的**每一条**消息，因为它们都以 "review:" 开头，包括 "review: approved"。于是 coder 会在代码已被批准后再次提交 "revised code"（Q11 中实际出现）。另外，coder 的兜底分支是 `TERMINATE`——由执行者自己宣布结束，绕过了 reviewer 和 manager。
2. 修复版（已运行验证）：

   ```python
   def fixed_coder(pool: list[Msg]) -> str:
       last_rev = next((m for m in reversed(pool) if m.speaker == "reviewer"), None)
       last_code = next((m for m in reversed(pool) if m.speaker == "coder"), None)
       if last_code is None:
           return "initial code: return a - b  (buggy)"
       if (last_rev and "fix" in last_rev.content
               and pool.index(last_rev) > pool.index(last_code)):
           return "revised code: return a + b"
       return "waiting for review"            # 不自行 TERMINATE，把结束权留给 manager
   ```

   要点：按**角色**找最近的审稿意见，而不是按位置；用"修复请求是否晚于我最近一次提交"判断是否需要修改。
3. 修复版 + round-robin 的轨迹：`coder → reviewer → manager → coder → reviewer → manager`，6 轮：初稿 → 发现 bug → 继续 → 修订版 `a + b` → 批准 → manager `TERMINATE`。与 LLM-style 一样得到正确结果，只是顺序固定。

### Q10 — 参考答案

```python
def capped(selector, cap):
    def sel(pool, team):
        nxt = selector(pool, team)
        if nxt is None:
            return None
        counts = speaker_counts(pool)
        if counts.get(nxt, 0) < cap:
            return nxt
        others = [n for n in team if counts.get(n, 0) < cap]
        return others[0] if others else None
    return sel
```

运行结果：

- `cap=1`：轨迹 `manager → coder → reviewer`，3 轮后所有人都用完配额，selector 返回 `None`，对话结束——**bug 尚未修复**（最后一条是 "please fix"）。
- `cap=2`：轨迹与原来完全相同（6 轮，正确结束），因为原本每人恰好说 2 次。

说明：发言上限是防 hot speaker 的有效手段，但设得太紧会在任务完成前把对话"饿死"。上限应与任务所需的"修订轮数"匹配，并且触达上限时应**升级或总结**而不是静默结束。更好的做法是把 speaker-balance 作为 selector 的一个输入特征（讲义："Introduce speaker balance as a selector feature"），而不是一刀切的硬限制。

### Q11 — 参考答案

实际运行轨迹（8 轮，触顶）：

```text
[reviewer]: waiting for code
[coder   ]: initial code: return a - b  (buggy)
[manager ]: manager: continue working
[reviewer]: review: bug detected -- sum must be a+b, please fix
[coder   ]: revised code: return a + b
[manager ]: manager: continue working
[reviewer]: review: approved
[coder   ]: revised code: return a + b
```

解释：

- 第 5 轮 coder 的窗口 `pool[-3:]` = `[coder 初稿, manager, reviewer 修复要求]`，最后一条非 coder 消息是 reviewer 的要求，所以这次正确修复了——同一个 policy 在不同的发言顺序下行为不同，说明它对顺序极其敏感。
- 第 6 轮 manager 发言时，池中还没有 "approved"，所以只说 "continue working"。
- 第 7 轮 reviewer 批准；但下一个是 coder 而不是 manager。coder 看到的最后一条是 "review: approved"，其中含 "review"，于是**再次提交** "revised code"（Q9 的关键字缺陷）。
- 第 8 轮达到 `max_rounds`，manager 再也没有机会发出 `TERMINATE`。结果代码其实是对的，但对话以"触顶"结束，浪费了轮次。

教训：round-robin 下"谁在批准之后发言"由顺序决定，而不是由需要决定；`max_rounds` 是必要的兜底，但不应该是正常的结束方式。

### Q12 — 参考答案

1. 运行结果（goal-reached = reviewer 消息含 "approved" 立即停止，`max_rounds=8`）：

   | 配置 | 停止轮次 | 原因 |
   |------|---------|------|
   | 原始 coder + LLM-style | 第 5 轮 | goal reached（比原来少一轮，省掉了 manager 的 TERMINATE） |
   | 原始 coder + round-robin | 第 4 轮 | coder 发出 TERMINATE（目标从未达成） |
   | 修复版 coder + round-robin | 第 5 轮 | goal reached |

   goal-reached 比 `TERMINATE` 哨兵更可靠：它由一个确定性条件（或轻量 verifier）判定，不依赖某个 agent "记得说"结束语；但要防止"假批准"——批准本身应该由 verifier 支撑（参见第 08 节）。
2. 合格的 selector 日志至少包含：轮次编号、trace/会话 ID、selector 的**输入**（送给 selector 的最近 N 条消息或其摘要、候选 agent 列表、各 agent 已发言次数）、selector 的**输出**（选中的 agent）以及 LLM selector 的原始回复和理由、所用模型与参数、耗时与 token 数、是否触发了兜底规则（如发言上限、回退到 round-robin）。有了输入和输出，才能复现"为什么这一轮选了它"。

### Q13 — 参考回答要点

- **定义**：多个 agent 共享一个对话池，每个人读全部消息；GroupChatManager 在每一轮调用 selector 选出下一个发言者，循环直到终止。AutoGen/AG2 的 `GroupChat` + `GroupChatManager` 是参考实现。
- **三种 selector**：
  - round-robin：确定、便宜、公平，但忽略上下文（法律话题也会轮到 coder）；
  - LLM-selected：读最近消息选择最合适的人，懂上下文，但每轮多一次 LLM 调用、不确定、需要日志；
  - custom：Python 函数，常见形式是 LLM 选择 + 规则兜底（如"coder 之后总是 verifier"）。
- **终止**：max rounds 硬上限 + `TERMINATE` 哨兵 + goal-reached 检查，三者组合。
- 加分点：结合本节代码说明 round-robin 下 reviewer 的修复请求被 manager 插话"冲掉"的现象，以及 `endswith("TERMINATE")` 的误判问题。

### Q14 — 参考回答要点

- **静态图**：下一步由**开发者预先写好的边**决定，确定、可审计、易调试；适合已知 DAG 的流程。缺点：对话式、角色交叉提问的场景会出现边爆炸。
- **supervisor**：下一步由**一个中心 planner agent** 决定（"问 planner 该做什么"），其他 agent 执行；适合有全局计划、需要汇总的任务。
- **GroupChat**：下一步由**作用于共享池的 selector 函数**决定，所有 agent 平等；适合涌现式、探索式对话。
- 讲义："Same primitives, different defaults"——三者都可以用第 04 节的原语表达，区别在于默认的编排方式与共享状态范围（GroupChat 默认 LLM-selected + 全池共享）。
- **选择原则**（`skill-groupchat-selector` 的拒绝规则）：有已知 DAG → 静态图；需要严格审计 → 带 checkpointer 的静态图；agent 超过 5–6 个 → 嵌套群组或层级模式；对称的同质 agent 做推理任务 → 用辩论（第 07 节）。

### Q15 — 参考回答要点

- **上下文估算**：第 t 轮发言的 agent 要读前 `t−1` 条消息。20 轮共读 `200 × (0 + 1 + … + 19) = 200 × 190 = 38,000` token；LLM selector 每轮也读全池，再加约 38,000 token，合计约 76,000 输入 token（还没算 system prompt）。对话越长，增长是平方级的。
- **调用次数**：20 次 agent 调用 + 20 次 selector 调用 = 40 次 LLM 调用，selector 让调用次数翻倍、延迟也翻倍。
- **必做措施**（讲义 Ship It）：
  - `max_rounds` 硬上限（10–20）；
  - 终止 token 或专门的 verifier agent；
  - speaker-balance 指标与告警；
  - 约 10 条消息后对每个 agent 使用 projection / 摘要检查点，限定视图；
  - 记录 selector 的输入与选择；
  - 成本估算：讲义配套 skill 要求在配置说明末尾给出"每轮一次 selector 调用"的成本。
- 加分点：selector 用小而便宜的模型、只给最近 N 条 + 各 agent 简介；对确定的转移（coder → reviewer）用规则跳过 selector 调用；利用 prompt caching 降低重复读池的成本。

### Q16 — 参考回答要点

- **selector**：custom = 规则 + LLM。
  - 规则：告警进来先给值班 SRE；任何 agent 提出修复操作后，必须先轮到变更记录 agent 核对最近变更、再由人确认；总结 agent 只在终止前发言；
  - LLM 部分：在"日志 / 数据库 / 变更"三个专家之间根据最近消息选择；输入包括最近 N 条消息、每个 agent 的专长描述、已发言次数。
- **防 hot speaker**：同一 agent 连续发言不超过 2 次；speaker-balance 作为 selector 输入。
- **上下文**：每个专家只看与自己相关的 projection（日志 agent 看日志片段和问题描述，数据库 agent 看慢查询和指标），总结 agent 看全量摘要。
- **终止**：goal-reached（根因已确认且有证据 + 缓解措施已执行/已提交给人）或 max rounds（如 15）后升级给人；`TERMINATE` 只作为辅助。
- **审计**：故障处理需要事后复盘，必须记录 selector 输入/输出与每轮消息；若组织要求严格审计，讲义的 skill 会建议改用带 checkpointer 的静态图，可以把"定位"阶段做成 GroupChat、"执行修复"阶段做成静态图。
- 规模：5 个 agent 正好在"5–6 个以内用扁平 GroupChat"的边界上，再多就应分组嵌套。

### Q17 — 参考回答要点

- **定位**：
  - 统计每个 agent 的发言次数与连续发言长度（speaker-balance 指标），找出 hot speaker；
  - 查 selector 日志：它为什么总选这个 agent——是 agent 描述写得过宽（"我什么都能做"），还是最近消息的关键词总是落在它的专长上；
  - 检查其他 agent 的回复是否大量是"同意 / 补充"而无独立证据，即谄媚级联。
- **解决 hot speaker**：
  - 把发言次数作为 selector 输入特征，或硬性规则：连续 K 轮后强制轮换、每人上限；
  - 收紧 agent 描述，让专长不重叠；
  - 对确定性的转移用规则而不是 LLM。
- **解决谄媚级联**：
  - 讲义："Agents defer to whoever spoke most confidently. Counter-prompt explicitly."——在 system prompt 中明确要求独立判断、给出证据、允许反对；
  - 让某个角色担任"唱反调"的 critic；
  - 让 agent 先独立作答再看他人观点（类似辩论中的独立初稿）；
  - 用 verifier 而不是"大家都同意"来决定结束。
- 加分点：说明 LLM selector 的不确定性会让问题时有时无，必须靠日志与统计而不是个案排查。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：GroupChat 由第 04 节的四个原语组成。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：与 GroupChat 对照的中心化编排。
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../07-society-of-mind-debate/docs/zh.md)：对称 agent 做推理时应改用辩论；谄媚级联。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../08-role-specialization/docs/zh.md)：群聊中的 coder/reviewer 角色分工。

### 本节被哪些后续内容用到
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../11-handoffs-and-routines/docs/zh.md)：另一种"谁说下一句"的机制：由当前 agent 主动移交。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：projection / 按角色视图，缓解上下文膨胀。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../15-voting-debate-topology/docs/zh.md)：多 agent 讨论的拓扑设计。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：谄媚级联、群体思维。
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../../14-agent-engineering/14-autogen-actor-model/docs/zh.md)：AutoGen v0.4 的事件驱动 actor 模型。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)、[阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：静态图与 GroupChat 的框架选型。

### 延伸关键词
`AutoGen GroupChat` · `GroupChatManager` · `ConversableAgent` · `speaker_selection_method` · `AG2` · `Microsoft Agent Framework` · `TERMINATE / is_termination_msg` · `goal-reached termination` · `hot speaker` · `speaker balance` · `context bloat` · `projection` · `sycophancy cascade` · `selector logging`
