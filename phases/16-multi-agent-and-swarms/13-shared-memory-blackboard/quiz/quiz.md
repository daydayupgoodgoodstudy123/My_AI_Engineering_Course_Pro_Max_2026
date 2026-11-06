# 测验 · 共享记忆与黑板模式（Shared Memory and Blackboard Patterns）

> **阶段 16 · 多智能体与集群 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（如把 message pool 译成"信件库"、append-only 译成"附件"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 共享状态是多 Agent 系统里唯一"有状态"的部分 | 讲义："Both are the only stateful part of a multi-agent system — which means both are where the interesting bugs live." |
| 2 | 两种主流拓扑 | **完整消息池（message pool）**：所有 agent 读全部消息（AutoGen GroupChat、MetaGPT）；**带订阅的黑板（blackboard）**：agent 只订阅相关 topic，由底层路由（CA-MCP、Matrix） |
| 3 | 各自的适用场景 | 消息池：agent 少（< 10）、异构、短程对话；黑板：agent 多、同角色多实例（swarm）、长程运行；生产常混用（上层规划用小池，下层 worker 用黑板） |
| 4 | Memory poisoning（记忆投毒） | 一个 agent 的幻觉写进共享状态，下游 agent 当作已验证事实继续推理；不崩溃、不报错，准确率"慢慢变差"，比崩溃难调试得多 |
| 5 | 投毒是结构性问题 | 问题不在"共享"本身，而在"没有 provenance、没有独立 verifier"的共享；讲义称其为 MAST 分类中记录第二多的失效家族 |
| 6 | 三条缓解措施 | ①每次写入记录 provenance（writer、时间、prompt hash、source_uri）；②append-only + 版本化，更正是新条目 `supersedes` 旧条目；③至少一个**不能写共享状态**的只读 verifier |
| 7 | 不可写 verifier 的四条规则 | 能读共享状态；没有写句柄（只写独立的核查通道）；独立重新获取引用来源；输出送人或独立决策 agent，**绝不回灌到池里** |
| 8 | 写冲突的三种处理 | 单写者串行化（sequential writer）、带版本号的乐观并发、按 topic 分区归属；2026 年框架多默认单写者，因为 LLM 调用慢、冲突罕见 |
| 9 | Projection（投影视图） | 每个 agent 拿到按角色定制的状态切片；LangGraph 的 state reducer 是典型实现；需要 schema，否则每个 prompt 里都在临时手写投影 |
| 10 | 历史渊源 | Hayes-Roth（1985）黑板架构：Knowledge Source 观察全局黑板、贡献部分解、触发其他 Knowledge Source；今天只是把 KS 换成 LLM agent |

### 核心技能（能动手做到）

- [ ] 用标准库写出线程安全的 append-only `MessagePool` 与 topic 订阅式 `Blackboard`，说清锁的范围与回调为什么放在锁外执行
- [ ] 给每次写入挂上 provenance 字段，并能说出"只存内容哈希"为什么不够
- [ ] 复现"幻觉沿 retriever → summarizer → analyst 传播"的投毒链，并定位根因条目
- [ ] 实现一个只读 verifier：独立取源、比对、把发现交给调用方而不是写回池子
- [ ] 指出本节代码中 verifier 的局限（只能查带 `source_uri` 的条目、字符串全等比较、标记后下游仍然照用）并给出改进
- [ ] 针对给定场景（agent 数量、角色异构程度、对话时长）在消息池、黑板、per-agent projection 之间做选型

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 memory poisoning 难以排查的根本原因是：

- A. 系统不会崩溃、测试也能通过，错误以"看似合理的输出"在共享状态里扩散，根因往往在推理链很早的一条写入
- B. LLM 输出不可复现，每次运行结果都不一样
- C. 共享状态通常存在 GPU 显存里，无法导出检查
- D. 多线程竞争导致日志顺序随机

**Q2.** 下列场景中，最适合"完整消息池"的是：

- A. 200 个同质的网页抓取 worker，持续运行一周
- B. 一个交易系统，价格、订单、告警三类事件分别有不同消费方
- C. 上千个 agent 组成的 swarm，每个 agent 只关心自己负责的分片
- D. 4 个角色各不相同的 agent（规划、检索、写作、审校）协作完成一篇 20 分钟内结束的报告

**Q3.** 关于"不可写 verifier"，下列说法**错误**的是：

- A. verifier 可以读取团队的黑板或消息池
- B. 为了让团队尽快看到问题，verifier 应把核查结论作为新条目写回共享池
- C. verifier 应独立重新获取写入条目所引用的来源
- D. verifier 的输出应交给人或独立的决策 agent

**Q4.** 运行本节 `main.py` 的 RUN 2（带 verifier），最终 analyst 的输出是：

- A. `Recommend further review`，因为 verifier 已经标记了问题
- B. 没有 analyst 条目，因为被 verifier 拦截了
- C. 仍然是 `Recommend adoption`，42% 这个错误数字照样进入了结论
- D. 一条撤回声明（retraction）

**Q5.** 在 RUN 2 中，verifier 一共标记了几个条目，为什么？

- A. 3 个，三条记录都含有 42%
- B. 2 个，retriever 和 summarizer 两条都与来源不一致
- C. 0 个，verifier 只在 RUN 1 中运行
- D. 1 个，只有 retriever 条目带 `source_uri`，summarizer 与 analyst 条目没有来源可比对

**Q6.** 讲义推荐"append-only，更正作为新条目 supersede 旧条目"，其核心收益是：

- A. 保留完整审计轨迹，能追溯"谁在什么时候基于什么写了错误内容、又是哪条更正了它"
- B. 节省存储空间
- C. 让读操作不再需要加锁
- D. 让 LLM 生成更准确

**Q7.** 讲义提到 2026 年多数框架默认采用"单写者串行化（sequential writer）"处理写冲突，理由是：

- A. 它是唯一能保证一致性的方案
- B. 乐观并发需要分布式事务，LLM 框架无法实现
- C. LLM 调用本身很慢，写冲突很少发生，单点瓶颈几乎不造成损失
- D. topic 分区在 Python 中无法实现

**Q8.** 在本节 `Blackboard` 中，某 agent 在 `publish` 了 3 条 `prices` 消息**之后**才 `subscribe("prices", cb)`，结果是：

- A. `cb` 会立即被回放调用 3 次
- B. `cb` 不会收到这 3 条历史消息，只能通过 `read_topic("prices")` 主动拉取
- C. `subscribe` 抛出异常，因为 topic 已存在
- D. 这 3 条消息会被删除

---

## 三、动手 / 代码题

**Q9.** 把 `run_without_verifier` 中 retriever 的 `hallucinate=True` 改为 `False`，运行后 summarizer 写出的内容是：

```text
Summary: study reports a significant result -- The study reports a 4.
```

相关源码：

```python
def summarizer_agent(pool: MessagePool) -> int:
    retrieved = [e for e in pool.read_all() if e.writer == "retriever"]
    ...
    latest = retrieved[-1].content
    summary = f"Summary: study reports a significant result -- {latest.split('.')[0]}."
```

1. 解释为什么正确的 4.2% 被截成了 "4."。
2. 这个 bug 与"记忆投毒"有什么共同点？verifier 能发现它吗？
3. 给出修复方法。

**Q10.** 讲义练习 2：让 summarizer 再编造一个数据集规模（来源里是 12,500，summarizer 写成 125,000）。在现有代码下运行：

```python
p = MessagePool()
retrieval_agent(p, "https://arxiv.org/paper-2", hallucinate=False)
p.write("summarizer", "Dataset size was 125,000 examples.", "s")
print(verifier_agent(p))
```

输出是 `[]`。

1. 为什么 verifier 没发现？
2. 讲义要求 verifier "should catch both without being hand-tuned for either"。请设计一个改造方案（数据结构 + verifier 逻辑），让派生条目也能被核查。

**Q11.** RUN 2 的流程是：

```python
    findings = verifier_agent(pool)
    for eid, reason in findings:
        pool.flag(eid, reason)
    analyst_agent(pool)
```

`pool.flag` 的实现是找到对应条目，然后 `e.flags.append(flag)`。

1. 这段实现在哪两点上违背了讲义自己提出的原则？
2. 为什么 analyst 仍然给出 `Recommend adoption`？讲义"预期输出"说 RUN 2 的最终报告会"include a retraction"，代码是否做到了？
3. 写出一个让下游真正"压制"错误结论的最小改动。

**Q12.** `MessagePool.read_all` 的实现是 `return list(self.entries)`。执行：

```python
p = MessagePool(); p.write("a", "x", "y")
l = p.read_all(); l[0].content = "hacked"
print(p.entries[0].content)
```

打印什么？这对"verifier 只读"的保证意味着什么？如何修复？

---

## 四、面试高频题

**Q13.**（基础必考）多 Agent 系统里的"消息池"和"黑板"有什么区别？各自适合什么场景？

**Q14.**（原理深挖）什么是 memory poisoning？为什么说它是"结构性"的？三条缓解措施中哪条最关键，为什么？

**Q15.**（工程实践）你负责一个 30 个 agent 的研究系统，共享状态放在 Postgres 里。请设计 schema 与写入规范，使系统能抵御记忆投毒，并能在事后定位根因。

**Q16.**（场景设计）多个 agent 需要同时更新同一份"项目计划"文档。请比较单写者、乐观并发、topic 分区三种方案，并给出你的选择。

**Q17.**（追问型）既然 verifier 不能写回池子，那它发现问题以后，系统怎么"修复"？如果 verifier 自己也是 LLM、也会出错，怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："No agent crashed. No test failed. The system 'worked.'"，以及"By the time the human notices, the reasoning chain is five steps deep and the root cause is the third message ever written."。B 是 LLM 的普遍性质，但不是投毒难查的原因（本节代码完全确定性，问题照样存在）；C 无依据；D 本节写入都加锁、按顺序编号，与投毒无关。

### Q2 — 答案：D

讲义："Full pool wins when agents are few (< 10), heterogeneous, and the conversation is short-horizon."。D 是 4 个异构、短时任务。A、C 是"多、同质、长时间运行"，属于黑板的主场；B 天然按事件类型分 topic，正是本节 `demo_blackboard` 演示的 prices/alerts 场景。

### Q3 — 答案：B

讲义明确："Verifier's own outputs are routed to a human or a separate decision agent, never fed back into the pool." 原因是：如果 verifier 的结论回写池子，被投毒的池子会反过来污染 verifier 读到的内容，进而污染它的核查结论。A、C、D 都是讲义列出的实现规则。

### Q4 — 答案：C

实际运行 RUN 2 的第 [2] 条：

```text
[2] analyst     (eb19da3531) :: Analyst verdict: Recommend adoption (based on: Summary: ... 42% accuracy improvement ...)
```

`analyst_agent` 只读 summarizer 的内容、只判断字符串里有没有 `"42%"`，**完全不看 `flags` 字段**。代码最后打印的 "downstream agents can suppress the verdict" 只是说"可以"，代码本身没做。D 是讲义"预期输出"的说法，但代码没有实现撤回（见 Q11）。A、B 都是想当然。

### Q5 — 答案：D

`verifier_agent` 只检查 `e.source_uri and e.source_uri in FAKE_SOURCES` 的条目。summarizer 和 analyst 写入时 `source_uri=None`，直接被跳过。所以只有 [0] 被标记，打印 "verifier surfaced 1 inconsistency"。这暴露了一个设计缺口：派生条目没有记录"我是从哪条条目推出来的"，污染的传播路径无法被追踪（见 Q10）。

### Q6 — 答案：A

讲义："A correction is a new entry that supersedes the old, not an in-place update. The audit trail is preserved." B 恰恰相反，append-only 更费空间；C 错，写入仍需加锁分配 id，读也需要一致快照；D 与存储模型无关。

### Q7 — 答案：C

讲义："Most 2026 frameworks default to sequential writer because LLM calls are slow enough that contention is rare and the bottleneck does not hurt." A 错，乐观并发和 topic 分区也能保证一致性；B 错，乐观并发只需要版本号比较，不需要分布式事务；D 显然错误。

### Q8 — 答案：B

`publish` 只对**当时**已登记的回调 `subs = list(self.subscribers.get(topic, []))` 逐个调用；`subscribe` 只是把回调追加进列表，没有回放逻辑。实际验证：先发布 1 条再订阅，回调收到 `[]`，`read_topic` 返回 `[0]`。生产中的消息系统（如 Kafka 的 consumer offset）会支持"从某个位置开始消费"，本节简化掉了。

### Q9 — 参考答案

1. `latest.split('.')[0]` 的本意是"取第一句"，但它按**所有**句点切分。`"The study reports a 4.2% accuracy..."` 中 `4.2` 的小数点也是 `.`，于是切成 `['The study reports a 4', '2% accuracy ...']`，取第 0 段得到 `"The study reports a 4"`，再补一个句号成了 "4."。有趣的是：幻觉版本 "42%" 没有小数点，反而被完整保留了——**正确数据被截断，错误数据完整传播**。
2. 共同点：summarizer 把一个与来源不一致的内容写进了共享状态，下游 analyst 读到 "4." 后因为找不到 "42%" 给出 `Recommend further review`，同样是"基于残缺事实的结论"。verifier **发现不了**，因为 summarizer 条目没有 `source_uri`（与 Q5、Q10 同因）。这说明投毒不一定来自 LLM 幻觉，确定性代码的解析 bug 同样会污染共享记忆。
3. 修复：用更稳妥的分句，例如 `re.split(r'(?<=[.!?])\s+', latest)[0].rstrip('.')`（只在"句末标点 + 空白"处切，再去掉句尾句号以免与 f-string 里补的 `.` 重复），或者干脆不截断，直接引用原句并在条目里记录 `derived_from=[retriever_entry_id]`。已验证：修复后得到 `The study reports a 4.2% accuracy improvement over the baseline`，"4.2%" 被完整保留。

### Q10 — 参考答案

1. verifier 的循环只处理 `e.source_uri` 非空的条目；`p.write("summarizer", ..., "s")` 没传 `source_uri`，条目被跳过，所以返回空列表。summarizer 的输出是"派生事实"，代码没有记录它派生自哪条条目。
2. 改造方案（不为某一种幻觉手工调参）：
   - **数据结构**：给 `ProvenanceEntry` 增加 `derived_from: list[int]`，summarizer/analyst 写入时填上所读条目的 id；同时把来源 URI 沿派生链继承（`cited_sources`）。
   - **verifier 逻辑**：对每个条目，收集它自己或其祖先引用的全部来源原文；抽取条目中的"可核查断言"（数字、实体、日期，用正则或 LLM 抽取），逐一检查是否能在来源原文中找到支撑；找不到就标记。
   - **传播标记**：某条目被判定不一致时，沿 `derived_from` 的反向边把所有下游条目标为 `tainted`。
   - 简化版实现：用 `re.findall(r'\d[\d,.]*%?', content)` 抽取数字（再 `rstrip('.,')` 去掉句尾标点），检查每个数字是否作为子串出现在来源原文中。已验证：对 "125,000" vs 来源 "12,500"，数字不在原文中 → 标记；对 "42%" vs "4.2%" → 同样标记；而正确转述的 "4.2%" 能在原文中找到 → 不标记。两种幻觉都能抓到，且没有针对其中任何一个写特例；同时它不再要求"整句全等"，正确的改写（paraphrase）不会被误报。

### Q11 — 参考答案

1. 违背两点：
   - **append-only**：`flag` 直接修改已有条目的 `flags` 列表，是"原地修改"，而讲义要求更正以新条目 supersede 旧条目。
   - **verifier 输出不回灌池子**：虽然 `verifier_agent` 本身没写池子，但调用方随即把它的结论写进了池中条目的 `flags`，下游 agent 读池子时就会读到 verifier 的结论——这正是讲义说的"never fed back into the pool"要避免的通道。更合理的是写入一个独立的 `verification_channel`，由人或决策 agent 消费。
2. analyst 仍然只看 summarizer 文本里有没有 "42%"，不检查 `flags`，也不检查上游条目的 flags（`flags` 挂在 [0] 上，analyst 读的是 [1]）。代码没有生成任何撤回条目，讲义"the pool is labeled 'flagged', the final report includes a retraction"与代码实际行为不符。
3. 最小改动示例：

```python
def analyst_agent(pool, blocked_ids=frozenset()):
    tainted = any(e.id in blocked_ids for e in pool.read_all() if e.writer == "retriever")
    ...
    if tainted:
        verdict = "Withheld: upstream source failed verification"
```

调用方用 `blocked_ids = {eid for eid, _ in findings}` 传入，而不是写回池子；更完整的版本应配合 Q10 的 `derived_from` 判断"我读的条目是否派生自被标记条目"。若要满足讲义的"retraction"，可以由决策 agent 写一条 `supersedes=0` 的更正条目，内容为来源原文。

### Q12 — 参考答案

打印 `hacked`（已实际运行验证）。`list(self.entries)` 是**浅拷贝**：新列表里装的仍是同一批 `ProvenanceEntry` 对象。任何拿到 `read_all()` 结果的 agent（包括所谓"只读"的 verifier）都能直接修改池中条目，锁也保护不了。

意义：本节的"只读"只是**约定**，不是**能力限制**。讲义要求"Verifier has no write handle to shared state"，而在 Python 里传进 `pool` 对象就等于给了 `write`、`flag` 和对象引用。

修复：
- 把 `ProvenanceEntry` 设为 `@dataclass(frozen=True)`，`flags` 改为元组，或者 `read_all` 返回 `copy.deepcopy`；
- 给 verifier 传一个只暴露 `read_all` 的只读视图对象（如 `ReadOnlyPool`），而不是完整的 `MessagePool`；
- 生产中靠权限隔离：verifier 使用只读数据库账号。

### Q13 — 参考回答要点

- **消息池**：全局 append-only 日志，每个 agent 读全部消息。优点：简单、透明、好审计，"谁说了什么"一目了然。缺点：每个 agent 的上下文被别人的工作填满，讲义认为超过约 10 个 agent 就扩展不动。代表：AutoGen GroupChat、MetaGPT。
- **黑板**：按 topic 发布/订阅，底层只路由相关消息。优点：节省 token、减少上下文污染，适合大量同质 agent、长期运行。缺点：需要预先设计 topic schema。代表：CA-MCP 的 Shared Context Store、Matrix。
- **per-agent projection**：更进一步，每个 agent 拿到按角色计算的视图，LangGraph reducer 是代表，需要明确 schema。
- **混合**：上层规划层用小消息池，下层 worker 层用黑板。
- 加分点：提到黑板起源于 Hayes-Roth 1985，写冲突、机会式控制等老问题已有成熟解法。

### Q14 — 参考回答要点

- **定义**：一个 agent 的错误（幻觉、解析 bug）写入共享状态，其他 agent 把它当作已验证事实，错误沿推理链扩散；系统不崩溃，准确率逐步下降。
- **为什么是结构性的**：没有共享状态时，A 的幻觉只在 A 的上下文里，下游可能重新获取、重新推导而发现错误；有了"天真的"共享状态，A 的上下文变成了所有人的上下文，幻觉被"洗白"成事实。任何缺少 provenance 和独立 verifier 的设计最终都会出现。
- **三条缓解**：provenance、append-only + 版本化、不可写 verifier。
- **最关键**：不可写 verifier。讲义称其 "most load-bearing"；本节 skill 文件也写道 "every other mitigation is decorative without it"。provenance 和版本化只让你"事后能查"，verifier 才是"有人主动去查"，而且因为它不能写池子，它自己不会被池子污染。
- 常见误区：认为"加测试"能防投毒——投毒产生的是看似合理的输出，能通过测试（skill 文件把"add more tests"列为硬拒绝项）。

### Q15 — 参考回答要点

- **表结构**（append-only）：`entries(id, writer_agent_id, writer_role, created_at, topic, content, prompt_hash, model_version, tool_calls_cited jsonb, source_uris text[], derived_from bigint[], supersedes bigint null, version)`；只授予 agent `INSERT` 和 `SELECT` 权限，禁止 `UPDATE/DELETE`。
- **更正**：写新行，`supersedes` 指向旧行；读取"当前视图"时用视图或物化视图过滤掉已被 supersede 的条目。
- **verifier**：独立服务、只读账号，独立抓取 `source_uris`；结果写入单独的 `verifications` 表（不在 agent 可读的 topic 里），由人或决策 agent 消费后再写更正条目。
- **根因定位**：通过 `derived_from` 做反向图遍历，从最终报告回溯到第一个未通过核查的条目。
- **监控**：讲义建议记录"supersession 占全部写入的比例"，比例上升是幻觉模式的早期信号；另外监控未通过核查的比例、按 writer 统计的被标记次数。
- 加分点：prompt 原文可以单独存储，条目只存 hash；内容哈希只能说明"写了什么"，不能说明"谁写的、从哪来"（skill 文件的硬拒绝项）。

### Q16 — 参考回答要点

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| 单写者 | 所有修改提交给一个协调 agent 串行合并 | 实现最简单，天然一致 | 单点瓶颈；协调者成为投毒的集中入口 |
| 乐观并发 | 每个条目带 version，写时比对，不一致则失败重试 | 并发度高，经典数据库技术 | LLM 重试代价高（要重新读、重新生成）；冲突频繁时活锁 |
| topic 分区 | 计划按章节分区，每个 agent 只拥有自己的章节 | 无跨分区冲突 | 需要提前设计分区边界；跨章节的修改仍需协调 |

- 选择：章节边界清晰时用 topic 分区；跨章节的少量修改走单写者协调者；冲突罕见时乐观并发也可以。讲义观察：LLM 调用慢，冲突本就少，多数框架默认单写者。
- 加分点：无论哪种方案都要保留 provenance 与 append-only 历史，否则合并后无法追责。

### Q17 — 参考回答要点

- **修复流程**：verifier 只"发现"，不"修复"。它的结论进入独立通道 → 人或独立决策 agent 审阅 → 由有写权限的角色写入更正条目（`supersedes` 旧条目）→ 下游 agent 读到更正后重新推理，或把受影响的派生条目标为 tainted 后重跑。
- **verifier 出错**：
  - verifier 的输入应尽量来自**独立**来源（重新抓取原文），而不是池子，降低与被检对象"同错"的概率；
  - 用不同模型或不同提示做 verifier，避免与写入者同质化（关联阶段 16 · 23 群体思维/同质化）；
  - verifier 输出本身也带 provenance，并抽样交人审；
  - 对高风险结论使用多个 verifier 投票或要求一致（关联阶段 16 · 14 共识）。
- 常见误区：让 verifier 直接改池中内容——这会让一个出错的 verifier 变成新的投毒源。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：讲义列出的先修课，理解 agent、消息与状态的基本抽象。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：讲义列出的先修课，黑板模式主要服务于大规模 swarm。
- [阶段 16 · 10 群聊与发言者选择](../../10-group-chat-speaker-selection/docs/zh.md)：GroupChat 就是典型的完整消息池。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)、[阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：单 agent 记忆，是本节"多 agent 共享记忆"的基础。
- [阶段 14 · 13 有状态图 Orchestration](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 的 state 与 reducer，即本节的 projection 模式。

### 本节被哪些后续内容用到
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../14-consensus-and-bft/docs/zh.md)：当共享状态里的写入者可能出错甚至恶意时，如何达成一致。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：把共享状态落到持久化存储与队列上。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：memory poisoning 所属的 MAST 失效分类与级联错误。
- [阶段 18 · 15 Indirect Prompt Injection](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：恶意内容通过外部数据进入共享记忆，是"有意投毒"的版本。
- [阶段 14 · 39 Reviewer Agent](../../../14-agent-engineering/39-reviewer-agent/docs/zh.md)：把实现者与评分者分开，与"不可写 verifier"思路一致。

### 延伸关键词
`message pool` · `blackboard architecture` · `pub/sub` · `provenance` · `append-only log` · `event sourcing` · `memory poisoning` · `MAST` · `read-only verifier` · `LangGraph reducer` · `optimistic concurrency control` · `Hayes-Roth Knowledge Source`
