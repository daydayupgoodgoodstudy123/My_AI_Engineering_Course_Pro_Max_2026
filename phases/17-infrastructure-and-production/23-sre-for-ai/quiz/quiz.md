# 测验 · AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测（SRE for AI — Multi-Agent Incident Response, Runbooks, Predictive Detection）

> **阶段 17 · 基础设施与生产 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AI SRE 是什么 | 用基于基础设施数据（日志、runbook、服务拓扑）做 RAG 的 LLM，自动化事故处理中的**调查、文档、协调**阶段；判断仍由人做 |
| 2 | 多 Agent 架构 | Supervisor 把事故拆成子查询 → 专用 agent（日志、指标、runbook）各自调用工具 → Supervisor 汇总成"假设 + 证据" → 人工审批 → 执行窄范围动作 |
| 3 | 可自动化的部分 | 讲义：一次凌晨 3 点事故中，前 20 分钟的调查（按服务归类日志、关联最近部署、匹配 runbook）都可以用 RAG + tool use 自动完成 |
| 4 | Auto-remediation 的窄边界 | 安全：重启 Pod、回滚特定部署、在预批准范围内扩容、开启预批准的 feature flag；不安全：改拓扑、改资源限制、部署新代码、改 IAM、改数据库 |
| 5 | Adversarial evaluation（对抗式评估） | NeuBird Hawkeye：两个模型**独立**分析同一事故，一致 = 置信度高，不一致 = 把两个假设都交给人；用来过滤幻觉出的根因 |
| 6 | Operational memory（运维记忆） | 把 runbook 与事后复盘（post-mortem）存进向量库，每次新事故都检索；对抗团队流动导致的"部落知识"流失 |
| 7 | Runbooks as code | 从 Confluence 页面变成版本化的结构化 markdown（symptom / hypothesis / verify / act），结构化才能检索得好 |
| 8 | 预测性检测 | 讲义引用 MIT 2025 研究：基于历史日志、GPU 温度、API 错误模式，在测试集上提前 10–15 分钟预测了 89% 的故障；但"没有执行策略的预测只是仪表盘" |
| 9 | 2026 产品 | Datadog Bits AI、Azure SRE Agent、NeuBird Hawkeye、PagerDuty AIOps、Incident.io Autopilot |
| 10 | 本节代码的关键缺陷 | Supervisor 用字符串前缀分组，三个 agent 语义上指向同一根因却被分成三组，"一致性"从未被识别；动作是硬编码的 |

### 核心技能（能动手做到）

- [ ] 画出 supervisor + 专用 agent + 人工审批门 + 窄动作集合的架构，并说明每个 agent 接哪个数据源
- [ ] 为一个具体服务列出 3 个"安全"的自动修复动作和一个明确的 deny list，并写出理由
- [ ] 写出结构化 runbook 模板（症状、假设、验证命令、动作、回滚、负责人）
- [ ] 读懂 `supervisor()` 的分组与排序逻辑，指出它为什么识别不出一致，并改成基于根因标签的分组
- [ ] 区分"多个专用 agent 一致"和"两个独立模型一致"，说明后者为何需要独立性
- [ ] 为预测性告警设计执行策略（pager / 预先摘流 / 自动扩容），并考虑误报率

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 AI SRE 在 2026 年最适合自动化事故处理中的哪一部分？

- A. 全部环节，包括重构服务架构
- B. 只做告警去重，不碰调查
- C. 调查、文档与协调：按服务归类日志、关联最近部署、匹配 runbook，给出假设与证据，由人做判断
- D. 只负责事后复盘，不参与实时事故

**Q2.** 以下哪一项**不属于**讲义所说的"安全（窄）自动修复"集合？

- A. 修改 Pod 的资源限制（resource limits）
- B. 重启 Pod
- C. 回滚某一次特定部署
- D. 在预先批准的范围内扩容 GPU 池

**Q3.** NeuBird Hawkeye 的 adversarial evaluation 模式是：

- A. 让一个模型生成根因，另一个模型专门攻击它的 prompt
- B. 对同一事故重复询问同一模型 10 次，取多数票
- C. 用红队攻击 runbook 库
- D. 两个模型独立分析同一事故；结论一致则置信度高，不一致则把两个假设都交给人

**Q4.** 讲义对"预测性检测（MIT：提前 10–15 分钟预测 89% 的故障）"的核心提醒是：

- A. 89% 已经足够高，可以直接接自动修复
- B. 没有执行策略的预测只是仪表盘，关键问题是"预测到了之后做什么"
- C. 预测只适用于 GPU 温度类故障
- D. 提前量 10–15 分钟太短，没有实际价值

**Q5.** 运行本节代码，Supervisor 最终输出 `supporting_agents: ['RunbookAgent']`、`adversarial_agreement: False`。根本原因是：

- A. 三个 agent 的根因确实互相矛盾
- B. 分组键是根因字符串的前 30 个字符（先按 " on " / " hit " 截断），三个语义相同的根因得到三个不同的键，各自成组
- C. RunbookAgent 的置信度最高，其余 agent 被丢弃
- D. 事故描述里不含 "checkout"，LogAgent 返回了 unclear

**Q6.** 代码中 `aggregated_confidence` 的计算方式是：

- A. 组内置信度之和，一致越多越高
- B. 组内最大置信度
- C. 1 − 组内各 agent "都错"的概率之积
- D. 组内置信度的算术平均——所以"一致"并不会提升它，与注释"agreement = confidence boost"不符

**Q7.** 讲义说"运维记忆（operational memory）"主要用来解决什么问题？

- A. 团队人员流动导致的部落知识流失：把 runbook 与复盘存入向量库，新事故时检索
- B. GPU 显存不足
- C. 日志存储成本过高
- D. 告警风暴

**Q8.** 关于 runbooks as code，讲义推荐的做法是：

- A. 保留 Confluence 自由文本，让 LLM 自己理解
- B. 把 runbook 写进 Python 脚本里直接执行
- C. 改成版本化的结构化 markdown，包含 symptom / hypothesis / verify / act 等段落，作为任何 AI SRE 落地的第一步
- D. 只保留最近 30 天用过的 runbook

---

## 三、动手 / 代码题

**Q9.** 阅读 `supervisor()`：

```python
    root_causes = {}
    for h in hypotheses:
        key = h.root_cause.split(" on ")[0].split(" hit ")[0][:30]
        root_causes.setdefault(key, []).append(h)

    ranked = sorted(root_causes.items(), key=lambda kv: -sum(h.confidence for h in kv[1]))
    top_key, top_agents = ranked[0]
    adversarial_agreement = len(top_agents) >= 2
```

1. 写出三个 agent 的根因分别得到的 `key`。
2. 为什么最终 top 是 RunbookAgent？
3. 如果 LogAgent 返回 `"unclear"`（置信度 0.35），结果会怎样变化？（讲义练习 1）

**Q10.** 把分组改为基于**根因标签**：给出一个 `tag(h)` 函数（关键词匹配到 `kv_cache_oom` 等标签）和新的 supervisor，使三个 agent 被识别为一致。说明改造后的输出，并指出：当事故描述换成 "Latency spike in /search" 时，新 supervisor 仍然判定 MetricAgent 与 RunbookAgent 一致——这暴露了什么问题？

**Q11.** 代码中的动作与安全门：

```python
    action = "restart pod + lower --gpu-memory-utilization"  # safe action
    ...
        "safety_gate": "human approval required" if not adversarial_agreement else "safe action auto-approved",
```

请指出至少三个问题，并改写成"动作来自 runbook、按 allowlist 判断、按置信度和一致性决定是否需要人工"的版本。

**Q12.**（讲义练习 3）写一个结构化 runbook 模板（YAML 或 markdown 均可），以 RB-017 "KV cache OOM under burst concurrency" 为例填写，要求包含：症状、假设、验证命令、动作（区分可自动/需审批）、回滚、负责人、最后验证日期。

---

## 四、面试高频题

**Q13.**（基础必考）描述一个多 Agent AI SRE 系统的架构。Supervisor 和专用 agent 各自负责什么？人在哪个环节？

**Q14.**（原理深挖）为什么"两个模型一致 = 置信度高"能过滤幻觉根因？它在什么情况下会失效？

**Q15.**（工程实践）你要给团队定义自动修复的边界。哪些动作可以自动执行，哪些必须人工审批？如何把这个边界做成 policy as code？

**Q16.**（场景设计）（讲义练习 4）预测模型在故障前 12 分钟告警，你的策略是 pager、预先摘流（pre-drain）还是两者都做？请结合误报率给出决策框架。

**Q17.**（追问型）（讲义练习 5）一个 3 人小团队在 2026 年应该上 AI SRE 吗？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："In 2026 the first 20 minutes of that investigation are automatable. Grouping logs by service, correlating to recent deploys, matching against runbooks — all are RAG + tool-use." 同时"AI proposes hypotheses and queries, humans approve judgment calls"。

- A：讲义明确"Re-architect the service: absolutely not"。
- B：告警去重只是 PagerDuty AIOps 等产品的一部分功能，讲义的重点是调查。
- D：AI SRE 的核心价值在实时 triage，复盘只是运维记忆的输入。

### Q2 — 答案：A

讲义的"Not safe (broad)"列表："change service topology, modify resource limits, deploy new code, change IAM, alter databases"。B、C、D 都在"Safe (narrow)"列表中（扩容要求"within pre-approved bounds"）。

延伸：本节代码的动作 `lower --gpu-memory-utilization` 修改的是引擎的显存配额参数，与"修改资源限制"性质接近，严格按讲义应走人工审批（见 Q11）。

### Q3 — 答案：D

讲义："Two models independently analyze the same incident. If they agree on root cause, confidence is high. If they disagree, escalate to human with both hypotheses visible." 关键词是**两个模型、独立、同一事故**。A 是红队思路；B 是 self-consistency（同一模型多次采样），独立性弱于两个不同模型；C 无关。

### Q4 — 答案：B

讲义："Reality check: predictions without actuation are dashboards. The operational question is 'when we predict, what do we do?'" skill 文件也把"预测 → 自动修复作为第一个功能"列为拒绝条件。A 忽略了误报：89% 是召回率类指标，讲义没有给出误报率；C、D 都不是讲义观点。另外讲义未给出这项 MIT 研究的具体出处，引用时应注明"讲义所述"。

### Q5 — 答案：B

实际计算出的三个键：

| Agent | 根因 | key |
|-------|------|-----|
| LogAgent | `vLLM OOM from KV cache spike on /api/llm` | `'vLLM OOM from KV cache spike'` |
| MetricAgent | `GPU memory utilization hit 98% ...` | `'GPU memory utilization'` |
| RunbookAgent | `Matches runbook RB-017: KV cache OOM ...` | `'Matches runbook RB-017: KV cac'` |

三者说的都是"KV cache 导致显存 OOM"，但字符串完全不同，被分成三组，每组 1 个 agent，`len(top_agents) >= 2` 永远不成立。

- A：语义上三者是一致的。
- C：RunbookAgent 胜出是"分成三组后按置信度排序"的**结果**，不是原因。
- D：事故描述 `/checkout/generate-summary` 含 "checkout"，LogAgent 返回了 OOM 根因（0.78）。

### Q6 — 答案：D

`sum(h.confidence for h in top_agents) / len(top_agents)` 是平均值。两个 0.8 的 agent 一致，平均仍是 0.8，并没有"boost"。注释 `# agreement = confidence boost` 只体现在**排序**（组内求和）上，而不是输出的置信度上。C 是假设各 agent 独立时的"至少一个正确"类组合方式，代码没有实现。

### Q7 — 答案：A

讲义："Team turnover is the silent kill of traditional SRE — tribal knowledge leaves. AI SRE stores runbooks + post-mortems in a vector DB; agents retrieve on every new incident." 其余选项与运维记忆无关。

### Q8 — 答案：C

讲义："Runbooks evolve from Confluence pages to versioned markdown with structured sections (symptom, hypothesis, verify, act)... Start any AI-SRE rollout by turning unstructured runbooks into structured." skill 文件把"非结构化 runbook 作为知识库"列为 hard reject。B 把文档变成可执行代码，跳过了人工审批边界；D 会丢失低频但关键的知识。

### Q9 — 参考答案

1. 见 Q5 的表格：`'vLLM OOM from KV cache spike'`、`'GPU memory utilization'`、`'Matches runbook RB-017: KV cac'`（截断到 30 个字符，"cache" 被切成 "cac"）。
2. 三组各 1 个 agent，按组内置信度之和排序：0.88（Runbook）> 0.82（Metric）> 0.78（Log），所以 top 是 RunbookAgent，`adversarial_agreement = False`，安全门输出 `human approval required`。
3. LogAgent 返回 `"unclear"` 时 key 为 `'unclear'`，依然自成一组；排序结果仍是 RunbookAgent 第一，**输出与原来完全相同**（只是 LogAgent 的证据变了）。也就是说，按当前实现，supervisor 根本"感受不到"日志与指标是否一致——讲义练习 1 问"agents 不一致时 supervisor 如何解决"，答案是它无法区分一致与不一致，只是挑置信度最高的单个 agent。正确做法：先归一化根因，再看一致性；不一致时把各方假设和证据一起交给人（这正是 adversarial evaluation 的要求）。

### Q10 — 参考答案

```python
CAUSE_KEYWORDS = {
    "kv_cache_oom": ["kv cache", "oom", "gpu memory", "kv_cache_allocation_failed"],
}

def tag(h):
    text = (h.root_cause + " " + " ".join(h.evidence)).lower()
    for t, kws in CAUSE_KEYWORDS.items():
        if any(k in text for k in kws):
            return t
    return "unknown"

def supervisor2(hs, min_agree=2, min_conf=0.75):
    groups = {}
    for h in hs:
        groups.setdefault(tag(h), []).append(h)
    k, agents = max(groups.items(), key=lambda kv: sum(h.confidence for h in kv[1]))
    agree = len(agents) >= min_agree and k != "unknown"
    conf = sum(h.confidence for h in agents) / len(agents)
    gate = ("auto-approve narrow action" if agree and conf >= min_conf
            else "human approval required")
    return dict(top=k, agents=[h.agent for h in agents], conf=round(conf, 3),
                agree=agree, gate=gate)
```

实际运行：

- 原事故：三个 agent 都被打上 `kv_cache_oom`，`agents = ['LogAgent', 'MetricAgent', 'RunbookAgent']`，`conf = 0.827`，`agree = True`。
- 事故换成 "Latency spike in /search"：LogAgent 变为 `unknown`，但 MetricAgent 与 RunbookAgent **仍然**被判一致（`conf = 0.85`，自动批准）。

暴露的问题：`metric_agent` 和 `runbook_agent` 根本不读取 `incident` 参数，永远返回同一结论。它们的"一致"不是独立证据，而是共同的偏差。推广到真实系统：多个 agent 若共享同一检索结果、同一基座模型或同一错误上下文，它们的一致并不能提高置信度。讲义的 adversarial evaluation 强调"two models independently"，正是为了保证独立性。生产中还应：用结构化的根因 schema（服务、组件、故障类型）而不是关键词；要求每个结论附带可验证的证据（查询语句、日志行链接），由 supervisor 复核证据是否真的指向本次事故的时间窗口和服务。

### Q11 — 参考答案

问题：

1. **动作硬编码**：无论根因是什么（哪怕是 `unclear`），都提出同一个动作；动作应来自匹配到的 runbook 的 `act` 段落。
2. **动作本身不完全"窄"**：`restart pod` 在安全集合里，但 `lower --gpu-memory-utilization` 是修改引擎配置/资源配额，接近讲义"modify resource limits"的不安全类别，至少应拆开：重启可自动，改配置需人工审批并走变更流程。
3. **一致即自动批准**：`"safe action auto-approved"` 只看 agent 数量，不看置信度、不看动作是否在 allowlist，也没有限速（同一 Pod 1 小时内最多重启几次）、没有 blast radius 限制。
4. **没有验证与回滚**：执行后应检查错误率是否恢复，失败则升级给人。

改写示例：

```python
SAFE_ACTIONS = {"restart_pod", "rollback_deploy", "scale_within_bounds", "enable_preapproved_flag"}

def decide(top_tag, agents, conf, runbook):
    actions = runbook.get("act", []) if runbook else []
    auto, needs_human = [], []
    for a in actions:
        if a["type"] in SAFE_ACTIONS and len(agents) >= 2 and conf >= 0.8 and a.get("auto", False):
            auto.append(a)
        else:
            needs_human.append(a)
    gate = "auto" if auto and not needs_human else "human approval required"
    return {"root_cause": top_tag, "auto_actions": auto,
            "pending_approval": needs_human, "gate": gate,
            "verify": runbook.get("verify", []) if runbook else []}
```

对 RB-017（三个 agent 一致、置信度 0.827）实际运行的结果：`restart_pod` 进入 `auto_actions`；`set_gpu_memory_utilization=0.85` 进入 `pending_approval`；因为仍有待审批动作，整体 `gate = "human approval required"`。

### Q12 — 参考答案

```yaml
id: RB-017
title: KV cache OOM under burst concurrency
owner: inference-platform-oncall
last_verified: 2026-01-14
services: [llm-gateway, vllm-checkout-summary]
symptoms:
  - 5xx 错误率 > 2% 持续 3 分钟（/checkout/generate-summary）
  - 日志出现 'kv_cache_allocation_failed'
  - DCGM_FI_DEV_FB_USED >= 97% 持续 > 120s
hypotheses:
  - 突发并发导致 KV cache 抢占/分配失败
  - 最近部署提高了 max_num_seqs 或 max_model_len
verify:
  - promql: max_over_time(DCGM_FI_DEV_FB_USED[10m])
  - logs: '{app="vllm"} |= "kv_cache_allocation_failed"'
  - deploy: kubectl rollout history deploy/vllm-checkout-summary
act:
  - type: restart_pod            # 窄动作，可自动
    target: 受影响的单个 Pod
    auto: true
    rate_limit: 每 Pod 每小时最多 2 次
  - type: rollback_deploy        # 若 30 分钟内有相关部署
    auto: false
  - type: set_gpu_memory_utilization
    value: 0.85
    auto: false                  # 改配置，需审批并走变更流程
rollback:
  - 恢复原 gpu-memory-utilization；回滚到上一个 ReplicaSet
escalation: 15 分钟内未恢复 → 呼叫 inference-platform 二线
post_incident: 复盘写入 operational memory，更新 last_verified
```

要点：字段固定、可被检索和机器解析；动作带 `auto` 标记与限速；每个验证步骤有具体命令；有负责人与最后验证日期（过期 runbook 不应被自动执行）。

### Q13 — 参考回答要点

- **Supervisor**：接收事故（告警 + 上下文），拆成子查询（"这个时间窗口的错误日志"、"相关指标是否异常"、"有没有匹配的 runbook"、"最近有什么部署"），分派给专用 agent，汇总成假设 + 证据，按一致性与置信度排序。
- **专用 agent**：各自拥有工具权限——日志 agent（Loki/Datadog 日志搜索）、指标 agent（PromQL）、runbook agent（向量检索 runbook 与复盘）、可选的部署 agent（CI/CD 历史）。每个结论必须附带可点击、可复现的证据。
- **人在哪里**：审批判断类决定（根因是否成立、是否执行非窄动作）；看到冲突假设时做裁决；作为事故指挥（incident commander）对外沟通。
- **执行层**：只执行 allowlist 内的窄动作，带限速、审计日志和自动验证。
- 加分点：讲义架构图中 supervisor → 三个 agent → 假设 + 证据 → 人工审批 → 窄动作，最后的复盘写回运维记忆形成闭环；讲义列出的产品（Datadog Bits AI、Azure SRE Agent）都以托管方式提供这一模式。

### Q14 — 参考回答要点

- **为什么有效**：幻觉往往是随机的、模型特有的；两个**独立**模型同时编造出同一个错误根因的概率较低，因此一致是置信度信号，不一致是"需要人看"的信号。
- **失效场景**：
  - 两个模型看到的是同一份错误或不完整的上下文（相同检索结果、日志被截断），会"一致地错"；
  - 两个模型来自同一家族/同一训练数据，偏差相关；
  - 用字符串匹配判断一致（本节代码的问题），语义相同被判为不一致，或者笼统的"可能是资源问题"被判为一致；
  - agent 不读输入、返回固定答案（本节 `metric_agent` / `runbook_agent`），一致完全没有信息量。
- **改进**：不同模型家族、不同证据子集；结构化根因 schema；把证据可验证性纳入打分；一致性只作为"可否自动执行窄动作"的必要条件之一，而不是充分条件。
- 常见误区：把"多个 agent 投票"当作 adversarial evaluation。

### Q15 — 参考回答要点

- **可以自动（窄、可逆、影响面小）**：重启单个 Pod、回滚某个特定部署、在预批准上下限内扩容、开启预批准的 feature flag（如降级到小模型）。
- **必须人工**：改服务拓扑、改资源限制/引擎配置、部署新代码、改 IAM、动数据库、跨区域切流。
- **判定维度**：可逆性、影响半径（单 Pod vs 全集群）、是否有成熟 runbook、历史执行成功率、是否触及数据或权限。
- **Policy as code**：用 OPA/Rego 或代码中的 allowlist 定义"动作类型 × 目标范围 × 频率上限"；每次执行写审计日志（谁/哪个 agent、依据哪条证据、何时、结果）；执行后自动验证，失败自动升级。
- **逐步放宽**：先 suggest-only 运行数周，统计"AI 建议 vs 人实际执行"的一致率，再把高一致率、低风险的动作移入自动集合（讲义："The safe set grows as AI SRE matures, but the boundary is real"）。
- 加分点：skill 文件给出 12 周节奏——第 1–4 周结构化 runbook、5–8 周 triage agent、9–12 周窄范围自动修复。

### Q16 — 参考回答要点

- **先问误报率**：讲义只给出"89% 的故障被提前预测"，没有给出 precision。若误报率高，自动 pre-drain 会频繁减少容量，反而制造事故。
- **决策框架**：
  - 低置信度或误报率未知：只发低优先级通知/工单，不叫醒人；
  - 中置信度：pager 给 on-call，附带预测依据与建议动作；
  - 高置信度且动作窄、可逆、代价低（例如提前扩容一个副本、把新流量从某个 GPU 温度异常的节点上摘走）：自动执行 + 通知；
  - 代价高的动作（全区域切流）：永远人工。
- **12 分钟够做什么**：Karpenter 起节点约 45–60 秒（17 · 03），但大模型冷启动可能要数分钟（17 · 10），所以"预先扩容"比"事后扩容"更有价值。
- **度量闭环**：记录每次预测的结果（真阳性 / 假阳性 / 漏报），定期重新标定阈值。
- 讲义原话："predictions without actuation are just dashboards"——答案的核心是给出明确的执行策略。

### Q17 — 参考回答要点

- **看三件事**：
  - **事故量**：skill 文件规则——每月事故少于 10 起时拒绝全面上 AI SRE，成本大于收益，只建议先做结构化 runbook；
  - **可观测性成熟度**：日志不可搜索、指标稀疏时，AI SRE 只会放大坏数据；
  - **风险容忍度**：小团队无法承受自动化误操作的后果。
- **小团队的合理路径**：先把 runbook 结构化并纳入 git；如果已经用 Datadog / incident.io 等平台，开启托管的 AI triage（suggest-only），而不是自建多 agent 系统；不做自动修复，或只做重启 Pod 这一个动作。
- **支持采用的理由**：3 个人轮值 on-call 负担重，第一轮 triage 能显著缩短 MTTR；运维记忆能缓解单人离职带来的知识流失。
- **反对的理由**：自建维护成本、成本与数据外发合规（日志进 LLM）、以及"set it and forget it"的幻觉。
- 结论表达方式：给出条件化答案，而不是简单的"该"或"不该"。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：AI SRE 依赖的日志、指标、trace 数据源。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../../16-multi-agent-and-swarms/05-supervisor-orchestrator-pattern/docs/zh.md)：supervisor + 专用 agent 的通用模式。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：运维记忆与 runbook 检索的基础。
- [阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：日志/指标 agent 调用工具的方式。

### 本节被哪些后续内容用到
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：用故障注入验证 AI SRE 的 triage 与自动修复是否可靠。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../25-security-secrets-audit/docs/zh.md)：自动修复动作必须写审计日志、受权限约束。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)："AI 提议、人审批"的通用设计。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：自动修复的护栏。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../../16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/zh.md)：多 agent "一致地错"的原因。
- [阶段 19 · 06 面向 Kubernetes 的 DevOps 故障排查 Agent](../../../19-capstone-projects/06-devops-troubleshooting-agent/docs/zh.md)：综合项目中实现类似的故障排查 agent。

### 延伸关键词
`AI SRE` · `supervisor agent` · `incident commander` · `MTTR` · `runbook as code` · `post-mortem` · `operational memory` · `adversarial evaluation` · `self-consistency` · `auto-remediation allowlist` · `policy as code / OPA` · `predictive detection` · `precision / recall` · `Datadog Bits AI` · `NeuBird Hawkeye`
