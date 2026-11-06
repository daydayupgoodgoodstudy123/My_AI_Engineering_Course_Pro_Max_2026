# 测验 · 为什么需要多 Agent？（Why Multi-Agent?）

> **阶段 16 · 多智能体与集群 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/single_vs_multi.ts](../code/single_vs_multi.ts)（TypeScript，本节不单独提供代码讲解，代码要点见第三部分） ｜ 原有英文小测：[quiz.json](../quiz.json)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **运行方式**：`cd code && npx tsx single_vs_multi.ts`（Node 22 + tsx；无需 API key，LLM 调用是 `fakeLLMCall` 模拟的）。本测验中的数字均来自实际运行。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 单 agent 天花板 | 一个 loop、一个 context window、一个 system prompt；三种失效：context saturation（上下文饱和）、role confusion（角色混淆）、sequential bottleneck（串行瓶颈） |
| 2 | 多 agent 的基本思路 | 每个 agent 一个职责、一个独立 context window、一个专门调过的 system prompt、一个明确的输入/输出契约 |
| 3 | 复杂度光谱 | Single agent → Subagents → Pipeline → Team → Swarm，从简单到复杂，不是非此即彼 |
| 4 | Pipeline | 顺序执行，前一阶段输出是后一阶段输入；好推理，但任一阶段失败会阻塞后续 |
| 5 | Fan-out / Fan-in | 把独立子任务并行分发再合并，"agent 版的 map-reduce" |
| 6 | Orchestrator-Worker | 一个"会派活的 agent"负责规划、委派、综合；它的工具包括生成和管理其他 agent |
| 7 | Peer Swarm | 无中心编排者，点对点通信 + 共享状态/队列，行为涌现；难调试但可扩展到很多 agent |
| 8 | Orchestrator vs Coordinator | orchestrator 是 agent（LLM）；coordinator 往往只是按规则路由消息的普通代码 |
| 9 | 复杂度成本 | 每个 agent 边界都是一次有损压缩；协调逻辑本身是 bug 来源；延迟上升；成本按 agent 数相乘 |
| 10 | 经验法则 | 讲义："if a task takes fewer than 20 tool calls and fits in 100k tokens, keep it single-agent" |

### 核心技能（能动手做到）

- [ ] 给定一个任务，用上下文量、角色多样性、可并行度、协调复杂度、出错面五个维度判断该用单 agent 还是哪种多 agent 模式（`outputs/prompt-multi-agent-decision.md`）
- [ ] 读懂 `single_vs_multi.ts` 中的三种实现（单 agent、pipeline、fan-out），并说出各自的 LLM 调用次数和关键路径长度
- [ ] 用"按收件人过滤消息"的方式实现 agent 之间的消息传递，理解它为什么能隔离上下文
- [ ] 用 `Promise.all` / `Promise.allSettled` 把独立的 agent 并行起来，并处理其中一个失败的情况
- [ ] 为 pipeline 增加 tester 角色和"reviewer → coder"的最多 2 轮修订回路（讲义练习 1、2）
- [ ] 识别"总 token 数"与"单个 context window 大小"这两个不同的指标，不被演示代码的对比口径误导

---

## 二、基础自测（选择题）

**Q1.** 讲义所说的"单 agent 天花板"由哪三个问题组成？

- A. 模型参数不够、GPU 显存不够、API 速率限制
- B. 工具太少、提示词太短、温度太高
- C. 幻觉、越狱、提示注入
- D. 上下文饱和、角色混淆、串行瓶颈

**Q2.** 按讲义的经验法则，下列哪种情况应当**保持单 agent**？

- A. 任务预计 15 次工具调用、工作数据约 60k tokens，且各阶段不需要不同的 system prompt
- B. 需要读 50 个文件、累计超过 200k tokens
- C. 需要同时调研三个互不相关的外部 API
- D. 需要研究、编码、审查、测试四种明显不同的角色

**Q3.** "许多相同或近似相同的 agent，共享状态，没有固定的编排者，从队列中领取工作"描述的是光谱上的哪一种？

- A. Subagents
- B. Pipeline
- C. Swarm
- D. Team

**Q4.** 讲义 Key Terms 中 Orchestrator 与 Coordinator 的区别是：

- A. 两者是同义词
- B. Orchestrator 是一个 agent，它的工具包括生成和管理其他 agent；Coordinator 往往只是按规则在 agent 之间路由消息的普通代码，不是 LLM
- C. Coordinator 负责规划，Orchestrator 只负责转发消息
- D. Orchestrator 只存在于 Swarm 中

**Q5.** 实际运行 `single_vs_multi.ts`，单 agent 用了 1745 tokens，pipeline 用了 1652 tokens（多次运行都一样）。而讲义 Step 4 说"The multi-agent version uses more total tokens"。对这一矛盾最准确的解释是：

- A. 模拟函数每次调用固定加 500 tokens，且模拟输出被截断到 80 个字符，单 agent 的上下文累积几乎体现不出来；三次调用的差别主要来自 system prompt 和输入长度，结果不能代表真实系统
- B. 讲义说错了，多 agent 在真实系统中总是更省 token
- C. 代码有并发 bug，导致 pipeline 少算了一次调用
- D. pipeline 用了更便宜的模型

**Q6.** `multiAgentFanOut` 的结尾部分如下。它有什么问题？

```typescript
  const reviewResult = await reviewer.run(codeResult.content);
  totalTokens += reviewResult.tokensUsed;
  totalToolCalls += reviewResult.toolCalls;

  return {
    content: messages
      .map((m) => `[${m.from} -> ${m.to}]: ${m.content}`)
      .join("\n\n"),
    ...
  };
```

- A. `reviewer.run` 没有 `await`
- B. token 被重复计算了两次
- C. reviewer 的 system prompt 被替换成了 coder 的
- D. reviewer 的结果没有 push 进 `messages`，返回的 `content` 里根本没有审查意见；而且 reviewer 直接读 `codeResult.content`，绕过了"按收件人过滤消息"的约定

**Q7.** `fakeLLMCall` 每次固定 `setTimeout` 50 ms。不计其它开销，三种实现的墙钟时间大约是：

- A. 单 agent 150 ms，pipeline 50 ms，fan-out 50 ms
- B. 单 agent 150 ms，pipeline 150 ms，fan-out 200 ms
- C. 单 agent 150 ms，pipeline 150 ms，fan-out 150 ms（fan-out 有 4 次调用，但其中 2 次并行）
- D. 三者都是 50 ms

**Q8.** 讲义说"Every agent boundary is a lossy compression step"，意思是：

- A. agent 之间传消息时会用 gzip 压缩，可能丢字节
- B. agent A 的完整上下文只能被总结成一条消息交给 agent B，B 看不到 A 读过的全部细节
- C. 多 agent 系统会自动对 prompt 做量化
- D. 每增加一个 agent，模型精度就下降一个固定比例

---

## 三、动手 / 代码题

**Q9.** `fakeLLMCall` 的 token 计算方式是：

```typescript
  const inputLength = systemPrompt.length + userMessage.length;
  const simulatedTokens = Math.floor(inputLength / 4) + 500;
  ...
  return {
    output: `[Response to: ${userMessage.slice(0, 80)}...]`,
    ...
  };
```

已知单 agent 的 system prompt 长 173 个字符，task 长 53 个字符；三次调用的 user message 长度分别为 63、177、226 个字符。

1. 算出单 agent 三次调用各自的 tokens，验证总数 1745。
2. 程序最后打印 "Single agent context pollution: all 1745 tokens in one window"。这个说法哪里不对？应该用什么指标来比较"上下文污染"？
3. 为什么这份模拟几乎体现不出单 agent 的上下文累积？如果研究阶段真的产出 50k tokens，三次调用的输入会怎样变化？

**Q10.** 修复 Q6 的 bug，并完成讲义练习 1：加一个 tester 专家，它接收 coder 的代码和 reviewer 的反馈，然后写测试。要求 tester 的输入必须通过"按收件人过滤消息"得到。

**Q11.** 讲义练习 2：让 reviewer 可以把反馈发回 coder 修订，最多 2 轮。写出循环骨架，并回答：在最坏情况下（2 轮都触发）加上 tester，一共会调用 LLM 多少次？墙钟时间约多少（每次 50 ms）？

**Q12.** 关于 `Promise.all` 与可复现性：

```typescript
  const [researchResult, requirementsResult] = await Promise.all([
    researcher.run(`Research technical approach for: ${task}`),
    createSpecialist("requirements", "...").run(`Analyze requirements for: ${task}`),
  ]);
```

1. 如果 requirements agent 抛出异常，会发生什么？怎样改成"一个失败、另一个结果仍可用"？
2. 多次运行时 "Tool calls" 一栏每次都不一样（实测单 agent 9/8/7、pipeline 14/6/9），而 tokens 恒定。原因是什么？这对"单 agent vs 多 agent"的对比实验意味着什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么时候应该从单 agent 走向多 agent？请说出单 agent 的三个瓶颈以及"不要用多 agent"的条件。

**Q14.**（原理深挖）多 agent 系统的"上下文隔离"到底带来了什么好处？它的代价是什么？为什么说每个 agent 边界都是一次有损压缩？

**Q15.**（工程实践）比较 pipeline、fan-out/fan-in、orchestrator-worker、peer swarm 四种模式：各自适合什么任务结构、失败模式是什么、怎么调试？

**Q16.**（场景设计）你要做一个"读 200 个文件、涉及三种语言、需要先调研外部 API 再写代码"的自动化改造系统。请给出 agent 架构、通信方式和风险控制。

**Q17.**（追问型）有人说"多 agent 就是多花钱多调几次 LLM，没什么本质区别，换个更大的模型就行"。你怎么回应？在什么情况下他是对的？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义 "Three things break"：Context saturation（工具结果堆积，第 30 轮时已消耗 150k tokens，第 5 轮的关键细节丢失）、Role confusion（"你既是研究员又是程序员又是审查员"的 prompt 会让 agent 每样都做一半）、Sequential bottleneck（依次读文件 A、B、C，没有并行）。A 是基础设施问题；B、C 是其它话题。

### Q2 — 答案：A

经验法则："fewer than 20 tool calls and fits in 100k tokens, keep it single-agent"，并且 "Stay single-agent when ... You do not need different system prompts for different stages"。A 同时满足。B 超出上下文（讲义原例 "reading 50 files blows past 200k tokens"）；C 是可并行的独立子任务；D 需要多种角色——这三者都是走向多 agent 的信号。

### Q3 — 答案：C

讲义："Swarm - many identical or near-identical agents with shared state. No fixed orchestrator. Agents pick up work from a queue." Subagents 是父 agent 派子任务；Pipeline 是顺序阶段；Team 是有角色、有编排者、通过消息总线并行协作。

### Q4 — 答案：B

讲义 Key Terms：Orchestrator — "An agent whose tools include spawning and managing other agents. It plans and delegates but may not do the actual work."；Coordinator — "A non-agent component (often just code, not an LLM) that routes messages between agents based on rules." 本节代码里 `multiAgentPipeline` 函数本身就是一个 coordinator：它用固定的代码顺序调用三个 specialist，没有任何 LLM 在做调度决策。

### Q5 — 答案：A

逐次计算（见 Q9）：单 agent 559 + 587 + 599 = 1745；pipeline 548 + 551 + 553 = 1652。每次调用的 500 是固定开销，占了总数的约 86%–91%；模拟输出被截断成 `[Response to: <前 80 个字符>...]`，所以单 agent 把前面的输出拼进上下文时只多了几十个字符。pipeline 更少，只是因为 specialist 的 system prompt（139/117/102 字符）比单 agent 的（173 字符）短，且 researcher 的输入只是 task 本身。真实系统中多 agent 通常确实更费总 token（每个 agent 都要重复读背景、system prompt，还要额外写交接消息），讲义的判断本身没错，是演示数据不支持它。B 过度推论；C、D 代码中都不存在。

### Q6 — 答案：D

实际运行打印 fan-out 的 `content`，只有三条消息：`researcher -> coder`、`requirements -> coder`、`coder -> reviewer`，**没有 reviewer 的输出**。审查结果只被计入了 token，然后被丢弃了——对调用方而言，花钱做了审查却拿不到审查意见。另外 pipeline 版本 reviewer 通过 `messages.filter((m) => m.to === "reviewer")` 取输入，fan-out 版本直接传 `codeResult.content`，两处约定不一致。A 错，有 `await`；B 错，每个结果只加一次；C 错，用的是 `reviewer`。

### Q7 — 答案：C

单 agent 3 次串行调用 ≈ 150 ms；pipeline 3 次串行 ≈ 150 ms；fan-out 共 4 次调用，但 researcher 与 requirements 并行（≈ 50 ms），再串行 coder、reviewer（≈ 100 ms），合计约 150 ms。实测三者分别约 152 / 152 / 153 ms。也就是说 fan-out **多做了一个 agent 的工作却没有增加延迟**——关键路径长度没变。这就是讲义说的 "why read three files sequentially when you can read them simultaneously?"。

### Q8 — 答案：B

讲义："Every agent boundary is a lossy compression step: agent A's full context gets summarized into a message for agent B." 这是上下文隔离的另一面：reviewer 不会被 researcher 读的 50k tokens 文档污染，但也看不到那些文档里可能与审查相关的细节。A、C、D 都是字面误解。

### Q9 — 参考答案

1. 公式 `floor((sys + user) / 4) + 500`：
   - 第 1 次：`floor((173 + 63)/4) + 500 = 59 + 500 = 559`
   - 第 2 次：`floor((173 + 177)/4) + 500 = 87 + 500 = 587`
   - 第 3 次：`floor((173 + 226)/4) + 500 = 99 + 500 = 599`
   - 合计 1745，与程序输出一致。
2. `tokensUsed` 是**三次调用的 token 之和**，不是某一个 context window 的大小。每次调用都是独立请求，单 agent 最大的一次 context 只有约 599 tokens（第 3 次）。"上下文污染"应该比较**单次调用的输入大小（或峰值 context）**以及**其中有多少与当前子任务无关**：单 agent 第 3 次调用（review）的输入里包含了研究笔记和代码；pipeline 的 reviewer 只收到 coder 发给它的消息。同样，"Multi-agent isolation: 1652 total tokens across 3 isolated windows" 把总和当成了隔离的证据，也不准确。
3. 因为模拟输出只有 `[Response to: ...]` 加前 80 个字符，单 agent 每一步拼进上下文的增量只有约 80–100 个字符。若研究阶段真实产出 50k tokens：单 agent 第 2 次调用输入 ≈ 50k，第 3 次 ≈ 50k + 代码长度，总量约 100k+ 且全部挤在同一个对话里；pipeline 的 coder 只收到研究结论（若 researcher 按 system prompt "Output only the facts needed" 压缩成几千 tokens），reviewer 只收到代码。这时 pipeline 的峰值 context 小得多——这才是讲义想说明的效果。

### Q10 — 参考答案

```typescript
const tester = createSpecialist(
  "tester",
  "You are a test engineer. Given code and review feedback, write focused unit tests."
);

const inbox = (messages: AgentMessage[], to: string) =>
  messages
    .filter((m) => m.to === to)
    .map((m) => `[From ${m.from}]: ${m.content}`)
    .join("\n");

  // ... coder 之后：
  messages.push({ from: "coder", to: "reviewer", content: codeResult.content, timestamp: Date.now() });
  const reviewResult = await reviewer.run(inbox(messages, "reviewer"));   // 统一走收件箱
  totalTokens += reviewResult.tokensUsed;
  totalToolCalls += reviewResult.toolCalls;

  // 修复：把审查结果放进消息流；同时把代码和审查发给 tester
  messages.push({ from: "coder", to: "tester", content: codeResult.content, timestamp: Date.now() });
  messages.push({ from: "reviewer", to: "tester", content: reviewResult.content, timestamp: Date.now() });

  const testResult = await tester.run(inbox(messages, "tester"));
  messages.push({ from: "tester", to: "orchestrator", content: testResult.content, timestamp: Date.now() });
  totalTokens += testResult.tokensUsed;
  totalToolCalls += testResult.toolCalls;
```

要点：把"取收件箱"抽成函数，避免像原 fan-out 那样有的地方走消息、有的地方直接传值；返回的 `content` 现在包含 reviewer 和 tester 的输出。可以先保留 `to: "orchestrator"` 的 reviewer 消息，再额外发一份给 tester；一条消息只有一个收件人，是这个最小实现的限制（真实系统常用 `to: string[]` 或发布/订阅）。

### Q11 — 参考答案

```typescript
let code = await coder.run(inbox(messages, "coder"));
let review = await reviewer.run(code.content);
let rounds = 0;
const MAX_ROUNDS = 2;
while (rounds < MAX_ROUNDS && hasBlockingIssues(review.content)) {
  rounds++;
  code = await coder.run(`${inbox(messages, "coder")}\n[From reviewer]: ${review.content}`);
  review = await reviewer.run(code.content);
}
```

- `hasBlockingIssues` 需要 reviewer 输出结构化结果（例如 JSON `{ "blocking": true, "issues": [...] }`），不能靠自由文本猜。
- 最坏情况调用次数：researcher 1 + coder 1 + reviewer 1 + 2 轮 ×（coder 1 + reviewer 1）+ tester 1 = **8 次**，全部串行，约 8 × 50 = **400 ms**。我们实际运行了带修订回路和 tester 的版本（修订条件恒为真），耗时约 404 ms、2 轮、8 次调用。
- `MAX_ROUNDS` 的硬上限是必须的：没有上限时，两个 agent 可能无限互相"挑刺—修改"，这是多 agent 系统最常见的成本失控方式之一。

### Q12 — 参考答案

1. `Promise.all` 只要有一个 Promise 被拒绝，整体立即以该错误拒绝，另一个已完成的结果也拿不到（我们用一个人为失败的 Promise 实测：`Promise.all rejected: boom`）。改成：

```typescript
const [r1, r2] = await Promise.allSettled([researcher.run(a), requirements.run(b)]);
const research = r1.status === "fulfilled" ? r1.value : null;
const reqs     = r2.status === "fulfilled" ? r2.value : null;
// 至少要有一个可用，否则整体失败；缺的那一路在给 coder 的消息里注明
```

   `allSettled` 返回每一项的 `status`（`fulfilled` / `rejected`），实测为 `['fulfilled', 'rejected']`。生产中还要给每一路加超时与重试。
2. `calls: Math.floor(Math.random() * 5) + 1` 每次调用随机返回 1–5，三次调用合计 3–15 且不可复现；tokens 只依赖字符串长度，所以恒定。这意味着"tool calls"一栏的差异是纯噪声，不能据此得出"单 agent 更省工具调用"之类的结论。做对比实验时应固定随机种子（或注入确定性的伪随机函数）、多次运行取分布，并比较同一指标的**分布**而不是单次数字。

### Q13 — 参考回答要点

- **三个瓶颈**：上下文饱和（工具输出堆积，早期细节丢失）、角色混淆（一个 prompt 兼任多种角色，每样都做不好）、串行瓶颈（本可并行的读取/调研被串行化）。
- **走向多 agent 的信号**：工作数据远超 100k tokens；需要 3 种以上不同技能；存在明显可并行的独立子任务。
- **保持单 agent 的条件**（讲义）：任务装得进一个 context window（工作数据 < ~100k tokens）；各阶段不需要不同 system prompt；串行速度够用；拆分带来的开销大于收益。经验法则 "< 20 tool calls 且 < 100k tokens"。
- 加分点：先考虑 subagents（父 agent 保持计划、子 agent 做聚焦任务并返回摘要，即 Claude Code 的 Task 子 agent 方式），它是复杂度最低的多 agent 形态。

### Q14 — 参考回答要点

- **好处**：
  - 每个 agent 的上下文只包含与它的子任务相关的信息，注意力不被稀释，早期细节不被挤掉；
  - system prompt 可以针对单一职责调优（"Your only job is finding bugs."）；
  - 可以并行；
  - 每个 agent 的输入/输出契约清晰，便于单独测试和替换。
- **代价**：
  - 有损压缩：A 的完整上下文只能以一条消息的形式交给 B，B 可能缺少关键背景；
  - 协调逻辑本身是 bug 来源（顺序、路由、重试、终止条件）；
  - 延迟：串行链路越长越慢；
  - 成本：每个 agent 独立消耗 token，背景信息常被重复读取；
  - 调试从"读一段对话"变成"跨五个 agent 追踪消息"。
- 加分点：对策是让交接消息结构化（明确字段，而非自由文本摘要）、保留可追溯的消息日志（本节的 `AgentMessage` 带 `from/to/timestamp`）、必要时允许下游 agent 回查原始材料。

### Q15 — 参考回答要点

| 模式 | 适合 | 失败模式 | 调试 |
|------|------|---------|------|
| Pipeline | 阶段之间有严格依赖：研究 → 编码 → 审查 → 测试 | 任一阶段失败阻塞后续；错误沿链条放大 | 逐阶段检查输入输出，最容易 |
| Fan-out / Fan-in | 可分解为独立子任务（多个文件、多个调研角度） | 合并阶段冲突；某一路失败或超时；结果不一致 | 每一路单独记录，重点看 merge 逻辑 |
| Orchestrator-Worker | 子任务事先不确定、需要动态规划与委派 | 编排者规划错误、重复派活、无限循环 | 记录编排者每一步决策及其依据 |
| Peer Swarm | 大量同质任务、高吞吐（从队列领活） | 行为涌现不可预测、重复或遗漏处理、共享状态竞争 | 最难；需要共享状态的版本记录与全链路追踪 |

- 讲义实例：Claude Code subagents（父子），Devin（planner + coder + browser），SWE-bench 上的多 agent 编码系统（researcher + planner + coder），ChatGPT Deep Research（并行搜索再综合）。
- 加分点：真实系统往往是混合体，例如 orchestrator 内部对独立子任务做 fan-out。

### Q16 — 参考回答要点

- **架构**：orchestrator-worker 为主，内部混合 fan-out。
  - Orchestrator：读需求，生成改造计划，按模块/语言拆分任务；
  - Researcher（可 fan-out 多个）：各自调研一个外部 API，只输出实现所需的事实；
  - Codebase explorer（按语言或目录 fan-out）：读文件、产出模块摘要与依赖关系，避免任何单个 agent 读完 200 个文件；
  - Coder（按模块并行）：只接收自己模块的摘要 + 相关 API 事实；
  - Reviewer + Tester：审查与测试，reviewer 可把结构化反馈发回 coder，最多 2 轮。
- **通信**：结构化消息（`from/to/type/payload`）+ 共享的计划/产物存储；交接内容用 schema 约束；全部消息落日志可回放。
- **风险控制**：
  - 修订轮数上限、每个 agent 的 token/时间预算；
  - 并行用 `allSettled` + 超时 + 重试，单路失败不拖垮整体；
  - 合并阶段检测冲突（多个 coder 改同一文件）；
  - 测试环境依赖基础设施时，由 tester 统一管理，其他 agent 不直接执行有副作用的命令；
  - 关键操作（合并到主干）人工确认。
- 加分点：先评估是否真的需要——如果 200 个文件里只有十几个与改动相关，subagents 做检索 + 单 agent 修改可能更简单。

### Q17 — 参考回答要点

- **回应**：更大的模型（更长的上下文、更强的能力）能推高天花板，但解决不了三件事：
  1. 上下文再长，注意力也会被无关内容稀释，早期细节照样丢失；
  2. 一个 system prompt 无法同时针对多种角色最优；
  3. 单个 loop 天然串行，模型再大也不能同时读三个文件。
  讲义的开场就是："The smart move is not a bigger agent - it is more agents."
- **他对的情况**：任务小（< 20 次工具调用、< 100k tokens）、单一角色、串行足够快时，多 agent 只增加延迟、成本和调试难度，换更强的模型或优化单 agent 的上下文管理更划算。本节演示里 pipeline 的 token 数和单 agent 几乎一样、延迟相同，也说明"多 agent 本身"不带来收益，收益来自隔离、专门化和并行。
- 加分点：给出决策依据而不是立场——用 `prompt-multi-agent-decision.md` 的五个维度（上下文量、角色多样性、可并行度、协调复杂度、出错面）逐项评估。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：单 agent 的循环结构，本节的"天花板"就是相对它而言。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md)：pipeline、并行化、orchestrator-workers 等工作流模式，以及"先用简单方案"的原则。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)：单 agent 应对上下文饱和的另一条路。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：在单 agent 内部做并行的方式。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../../15-autonomous-systems/01-long-horizon-agents/docs/zh.md)：长程任务让上下文与成本问题更突出。

### 本节被哪些后续内容用到
- [阶段 16 · 02 FIPA-ACL 与言语行为理论的历史基础](../../02-fipa-acl-heritage/docs/zh.md)：agent 之间的消息应该长什么样。
- [阶段 16 · 03 通信协议](../../03-communication-protocols/docs/zh.md)、[阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：把本节的 `AgentMessage` 发展成正式协议与原语。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)、[阶段 16 · 06 层级架构及其失效模式](../../06-hierarchical-architecture/docs/zh.md)：orchestrator-worker 的深入展开。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：fan-out 与 peer swarm。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：swarm 的共享状态。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：本节"复杂度成本"的系统化分析。

### 延伸关键词
`single-agent ceiling` · `context saturation` · `subagents` · `pipeline` · `fan-out / fan-in` · `orchestrator-worker` · `peer swarm` · `message passing` · `Promise.allSettled` · `revision loop` · `lossy handoff` · `AutoGen` · `CrewAI`
