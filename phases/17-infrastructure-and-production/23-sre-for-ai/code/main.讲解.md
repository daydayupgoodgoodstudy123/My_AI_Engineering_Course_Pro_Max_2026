# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 23 节 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），不调用任何 LLM、日志系统或 Prometheus

---

## 1. 这份代码在考察什么

这是一个约 120 行的多 Agent 事故 triage 模拟器，对应讲义的架构图"Incident → Supervisor → Log / Metric / Runbook agent → 假设 + 证据 → 人工审批 → 窄动作"：

1. **专用 agent 的产出形态**：每个 agent 返回"根因 + 置信度 + 证据列表"（`AgentHypothesis`），而不是一句结论——证据是让人能快速复核的关键。
2. **Supervisor 的职责**：把各 agent 的假设按根因分组、排序，判断是否"一致"（模仿 adversarial evaluation），并给出动作和安全门。
3. **窄动作 + 人工门**：只提出重启 Pod 一类的动作；不一致时要求人工审批。

三个 agent 都是硬编码的"模拟"，重点在 supervisor 的汇总逻辑。而这段逻辑恰好有一个关键缺陷：**用字符串前缀分组，导致三个语义相同的根因被判为互不一致**，`adversarial_agreement` 在默认场景下永远为 False。

> 一句话：**演示"多 agent 给假设、supervisor 汇总、人做判断"的流程骨架**，同时也是一个"如何判断 agent 一致"做错了的反面教材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `AgentHypothesis` | dataclass | `agent`、`root_cause`、`confidence`、`evidence` | 专用 agent 的结构化输出 |
| `log_agent` | 函数 | 事故描述含 "checkout" 时返回 "vLLM OOM from KV cache spike"（0.78），否则 "unclear"（0.35） | 日志 agent |
| `metric_agent` | 函数 | **永远**返回"GPU 显存 98%"（0.82），不读输入 | 指标 agent（PromQL） |
| `runbook_agent` | 函数 | **永远**返回匹配 RB-017（0.88），不读输入 | runbook agent（向量检索） |
| `supervisor` | 函数 | 按字符串前缀分组 → 按组内置信度和排序 → 判断一致 → 给出动作和安全门 | Supervisor + adversarial evaluation + 人工门 |
| `main` | 函数 | 构造事故、调用三个 agent、打印假设与 supervisor 决策 | 演示入口 |

数据流：`incident` 字符串 → 三个 agent 函数 → `list[AgentHypothesis]` → `supervisor()` → 决策字典 → 打印。

---

## 3. 逐段精讲

### 3.1 `AgentHypothesis`：结构化的假设

```python
@dataclass
class AgentHypothesis:
    agent: str
    root_cause: str
    confidence: float
    evidence: list[str]
```

- 四个字段对应讲义"hypothesis + evidence"。真实系统里 `evidence` 应是可复现的查询（PromQL、日志查询语句）或链接，便于人工一键核对。
- ⚠️ `root_cause` 是自由文本，这是后面分组失败的根源。更好的设计是加一个结构化字段（如 `cause_tag: "kv_cache_oom"`、`service`、`component`）。

### 3.2 三个专用 agent

```python
def log_agent(incident: str) -> AgentHypothesis:
    # simulated: scans logs, picks most common error token
    if "checkout" in incident.lower():
        return AgentHypothesis(
            "LogAgent",
            "vLLM OOM from KV cache spike on /api/llm",
            0.78,
            ["frequency: 142 errors/min", "pattern: 'kv_cache_allocation_failed'", "node: pod-gpu-3"],
        )
    return AgentHypothesis("LogAgent", "unclear", 0.35, ["logs show no obvious pattern"])
```

- `incident.lower()` 先转小写再做子串判断，大小写不敏感。默认事故 `"High error rate in /checkout/generate-summary, last 6 min"` 含 "checkout"，因此返回 OOM 假设。
- 证据模拟了日志 agent 的典型产出：错误频率、错误模式、出问题的节点。

```python
def metric_agent(incident: str) -> AgentHypothesis:
    # simulated: PromQL query matches to known patterns
    return AgentHypothesis(
        "MetricAgent",
        "GPU memory utilization hit 98% 4 minutes before error spike",
        0.82,
        ["DCGM_FI_DEV_FB_USED >= 97% for 240s", "correlation with error onset: 0.93"],
    )
```

- `DCGM_FI_DEV_FB_USED` 是 NVIDIA DCGM exporter 的显存已用量指标（framebuffer used）。证据里同时给出"持续时长"和"与错误开始时间的相关性"，体现指标 agent 的价值：把**时间先后**说清楚（显存先满，4 分钟后错误飙升）。
- ⚠️ 参数 `incident` 完全没用，任何事故都返回同样结论。`runbook_agent` 同理。

```python
def runbook_agent(incident: str) -> AgentHypothesis:
    # simulated: vector search on runbook repo
    return AgentHypothesis(
        "RunbookAgent",
        "Matches runbook RB-017: KV cache OOM under burst concurrency",
        0.88,
        ["runbook: RB-017", "last applied: 2026-01-14", "safe action: restart pod + lower --gpu-memory-utilization to 0.85"],
    )
```

- 模拟"运维记忆"检索命中：给出 runbook 编号、上次使用日期和其中记录的动作。
- `--gpu-memory-utilization` 是 vLLM 的启动参数，控制引擎可占用的显存比例（其中大部分用于 KV cache 预分配）。

### 3.3 `supervisor`：分组、排序、判断一致

```python
    root_causes = {}
    for h in hypotheses:
        key = h.root_cause.split(" on ")[0].split(" hit ")[0][:30]
        root_causes.setdefault(key, []).append(h)
```

- 分组键的构造：先按 `" on "` 切取第一段，再按 `" hit "` 切取第一段，最后截取前 30 个字符。设计意图是"去掉尾部细节，只保留根因主干"，让相似根因落到同一组。
- `dict.setdefault(key, [])` 在键不存在时插入空列表并返回它，于是可以直接 `.append`。
- ⚠️ 实际得到的三个键（已运行验证）：

| Agent | key |
|-------|-----|
| LogAgent | `'vLLM OOM from KV cache spike'` |
| MetricAgent | `'GPU memory utilization'` |
| RunbookAgent | `'Matches runbook RB-017: KV cac'` |

三者语义都是"KV cache 导致显存 OOM"，字符串却完全不同，被分成三组。

```python
    ranked = sorted(root_causes.items(), key=lambda kv: -sum(h.confidence for h in kv[1]))
    top_key, top_agents = ranked[0]
    adversarial_agreement = len(top_agents) >= 2
    action = "restart pod + lower --gpu-memory-utilization"  # safe action
```

- `sorted(..., key=lambda kv: -score)` 用取负实现降序（等价于 `reverse=True`）。组得分是组内置信度之和——这里才是"一致会加分"的体现：两个 0.8 的 agent 一组，得分 1.6，会压过单个 0.88。
- 但因为每组都只有 1 个 agent，排序结果就是按单个置信度：Runbook 0.88 > Metric 0.82 > Log 0.78。
- `adversarial_agreement = len(top_agents) >= 2`：至少两个 agent 落在同一组才算一致。默认场景下为 False。
- ⚠️ 讲义的 adversarial evaluation 是"两个**模型独立**分析同一事故"；这里是"不同数据源的 agent 结论一致"。两者都有价值，但独立性含义不同：`metric_agent` 与 `runbook_agent` 不读输入，即便分组修好了，它们的"一致"也没有信息量（测验 Q10 有实测）。
- ⚠️ `action` 是硬编码的，与根因无关；即使 top 是 `unclear` 也会提出同样动作。

```python
    return {
        "top_root_cause": top_key,
        "supporting_agents": [h.agent for h in top_agents],
        "aggregated_confidence": sum(h.confidence for h in top_agents) / len(top_agents),
        "adversarial_agreement": adversarial_agreement,
        "proposed_action": action,
        "safety_gate": "human approval required" if not adversarial_agreement else "safe action auto-approved",
    }
```

- `top_root_cause` 输出的是**截断后的键**，所以打印出来是 `Matches runbook RB-017: KV cac`，读起来像 bug。应返回原始根因或结构化标签。
- `aggregated_confidence` 是组内平均值，一致不会让它变高；注释"agreement = confidence boost"只在排序里体现。
- ⚠️ 安全门逻辑：一致就"auto-approved"。但动作里的 `lower --gpu-memory-utilization` 属于修改引擎配置，接近讲义列为不安全的"modify resource limits"；自动批准还应同时检查置信度阈值、动作 allowlist、频率限制。

### 3.4 `main`：打印假设与决策

```python
    hypotheses = [log_agent(incident), metric_agent(incident), runbook_agent(incident)]
    for h in hypotheses:
        print(f"[{h.agent}] confidence={h.confidence:.2f}")
        ...
    decision = supervisor(hypotheses)
    for k, v in decision.items():
        print(f"  {k}: {v}")
```

- 三个 agent 在真实系统里应**并行**调用（它们之间没有依赖），这里顺序调用只是为了简单。
- `decision.items()` 按插入顺序遍历字典（Python 3.7+ 保证），所以打印顺序与 `return` 中的键顺序一致。
- 最后两行提示语重申讲义原则："supervisor only proposes narrow safe actions"，"Broad changes (topology, code, IAM) always escalate to a human commander"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| agent 用硬编码返回值模拟 | 不需要日志、Prometheus、向量库即可演示流程 | 无法体现真实检索与工具调用；生产中每个 agent 是带工具权限的 LLM 调用 |
| 根因用自由文本 | 输出可读 | 无法可靠判断一致；应加结构化根因 schema（服务、组件、故障类型） |
| 字符串前缀分组 | 实现简单 | 语义相同的根因被拆开，`adversarial_agreement` 默认永远为 False；可用标签/本体或 LLM-as-judge 判等价 |
| 组内置信度求和排序 | 让"多数一致"占优 | 若不同 agent 共享偏差，求和会放大错误；需要考虑独立性 |
| 输出平均置信度 | 简单 | 与"agreement = boost"的注释不一致；可用校准后的组合方法 |
| 动作硬编码 | 演示窄动作的概念 | 动作应来自匹配 runbook 的 `act` 段，按 allowlist 拆分自动/人工 |
| 一致即自动批准 | 演示安全门 | 还需置信度阈值、频率限制、执行后验证、审计日志 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，`list[str]` 等写法在旧版本中也安全 |
| `@dataclass` | `class AgentHypothesis:` | 自动生成 `__init__` 等方法；按字段顺序位置传参 |
| 类型注解 | `def log_agent(incident: str) -> AgentHypothesis:` | 标注参数与返回值类型 |
| 字符串方法链 | `h.root_cause.split(" on ")[0].split(" hit ")[0][:30]` | 切分取第一段、再切分、再切片截断 |
| `in` 子串判断 | `"checkout" in incident.lower()` | 判断子串是否出现 |
| `dict.setdefault` | `root_causes.setdefault(key, []).append(h)` | 键不存在时插入默认值并返回，常用于分组 |
| `sorted` + `lambda` | `sorted(d.items(), key=lambda kv: -sum(...))` | 自定义排序键；取负实现降序 |
| 元组解包 | `top_key, top_agents = ranked[0]` | `(key, list)` 二元组拆成两个变量 |
| 生成器表达式 | `sum(h.confidence for h in kv[1])` | 不建中间列表直接求和 |
| 列表推导式 | `[h.agent for h in top_agents]` | 提取字段组成新列表 |
| 条件表达式 | `"human approval required" if not agree else "..."` | 三元表达式 |
| f-string 格式符 | `{h.confidence:.2f}` | 保留两位小数 |
| `dict.items()` 遍历 | `for k, v in decision.items():` | 同时取键和值；字典保持插入顺序 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出（节选）：

```text
Incident: High error rate in /checkout/generate-summary, last 6 min

[LogAgent] confidence=0.78
  root cause: vLLM OOM from KV cache spike on /api/llm
  ...
[MetricAgent] confidence=0.82
  root cause: GPU memory utilization hit 98% 4 minutes before error spike
  ...
[RunbookAgent] confidence=0.88
  root cause: Matches runbook RB-017: KV cache OOM under burst concurrency
  ...
--------------------------------------------------------------------------------
SUPERVISOR
--------------------------------------------------------------------------------
  top_root_cause: Matches runbook RB-017: KV cac      ← 截断后的分组键
  supporting_agents: ['RunbookAgent']                  ← 只有 1 个 agent
  aggregated_confidence: 0.88
  adversarial_agreement: False                         ← 三者语义一致却判为不一致
  proposed_action: restart pod + lower --gpu-memory-utilization
  safety_gate: human approval required
```

逐项解读：

- **三个 agent 的结论语义上完全一致**（KV cache → 显存打满 → OOM），证据也互相印证：日志里的 `kv_cache_allocation_failed`、指标里显存 97% 以上持续 240 秒且领先错误 4 分钟、runbook 里有对应条目。
- **Supervisor 却只认 RunbookAgent**：分组键不同，各自成组，按置信度取最高者。
- **结果"碰巧"是安全的**：因为判为不一致，安全门要求人工审批。但这是 bug 带来的保守，而不是设计出来的保守。
- **讲义练习 1（agent 不一致时怎么办）**：把事故描述改成不含 "checkout"，LogAgent 返回 `unclear`，supervisor 输出与上面完全相同——它无法区分"一致"与"不一致"。
- **修复后的对照**（测验 Q10 的 `tag()` + `supervisor2()`，已实际运行）：三个 agent 都被标为 `kv_cache_oom`，`agree=True`，平均置信度 0.827；但若事故改成 "Latency spike in /search"，MetricAgent 和 RunbookAgent 仍"一致"地给出 OOM——因为它们根本不读输入。

---

## 7. 动手改一改

1. 给 `AgentHypothesis` 加一个 `cause_tag: str` 字段，三个 agent 都返回 `"kv_cache_oom"`，supervisor 按 `cause_tag` 分组，观察 `adversarial_agreement` 变为 True。
2. 让 `metric_agent` 和 `runbook_agent` 真正读取 `incident`：用一个小字典模拟"服务 → 指标异常"和"关键词 → runbook"，对 "/search 延迟" 返回不同结论。
3. 把 `aggregated_confidence` 改成"一致加分"的版本，例如 `1 - Π(1 - c_i)`（假设独立），并讨论独立性假设不成立时的风险。
4. 把 `action` 改为从 runbook 的结构化 `act` 列表读取，并按 allowlist 拆成"可自动"和"需审批"两类（参考测验 Q11 的 `decide`）。
5. 实现真正的 adversarial evaluation：写两个"模型"函数（例如一个看日志 + 指标，一个看 runbook + 部署历史），只有二者结构化根因一致且平均置信度 ≥ 0.8 时才允许自动执行窄动作。
6. 进阶：给每次决策写一条审计日志（JSON 行：时间、事故、各 agent 结论、决策、执行者、结果），为 25 节的审计要求做准备。

---

## 8. 常见坑

- **用字符串相等判断"根因一致"**：自由文本几乎不可能逐字相同，必须先归一化到结构化标签。
- **把"多个 agent 同意"当作独立证据**：共享同一检索结果、同一模型、或者干脆不读输入的 agent，一致没有信息量。
- **输出截断后的键给人看**：`KV cac` 这类截断让人误以为系统出错；展示给 on-call 的内容要完整、可读。
- **动作与根因脱钩**：硬编码的动作在根因不明时也会被提出，可能误导值班人员。
- **把改配置当作"窄动作"**：重启 Pod 与修改 `--gpu-memory-utilization` 风险不同，后者应走变更审批。
- **忽视证据的时间顺序**：指标 agent 的"显存先满、4 分钟后错误飙升"是因果判断的关键；只看相关性系数而不看先后，容易把结果当原因。
