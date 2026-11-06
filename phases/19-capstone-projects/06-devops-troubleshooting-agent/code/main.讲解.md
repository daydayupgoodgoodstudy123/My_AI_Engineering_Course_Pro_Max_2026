# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 06 节 面向 Kubernetes 的 DevOps 故障排查 Agent ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`time`、`collections`、`dataclasses`），不需要 K8s 集群、Prometheus、Slack 或 LLM
>
> 同目录下的 `code/ts/` 是 TypeScript 版本（Slack 集成：Block Kit 卡片、Slack 请求签名校验、mock agent），不在本讲解范围内，文中只在对比处提到。

---

## 1. 这份代码在考察什么

docstring 点明了两个"hard architectural primitives"：

1. **K8s 知识图谱**：对象（Deployment、ReplicaSet、Pod、Node、Service）与遥测源（Prometheus、Loki）作为节点，所有权、调度、暴露、观测作为边；根因分析从告警对象出发沿边收集证据。
2. **只读优先的工具面 + 人工审批闸门 + 审计日志**：只读工具直接执行；破坏性工具没有审批就拦截；每次调用都写审计记录。

此外还有一个简化的**假设打分**（recency、specificity、引用数、路径长度的加权和）。

没有实现的：webhook 接收、真实的 PromQL/LogQL 查询、LLM 推理、Slack 卡片、ArgoCD 调用、20 个合成故障场景的评估。

> 一句话：**用一个内存图 + 三条规则模拟"告警 → 遍历 → 排序假设 → 审批后修复 → 审计"的骨架**。它把"安全闸门"的形状画出来了，但闸门本身可以被一个字符串绕过——这正是本节最值得讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Node` | dataclass | `kind`、`name`、`attrs`；`key` 属性返回 `"Kind/name"` | 图谱节点（K8s 对象 / 遥测源） |
| `Graph` | dataclass | 节点字典 + `(src, rel, dst)` 边列表；`add`、`link`、`neighbors` | K8s 知识图谱（Neo4j/kuzu 的替身） |
| `build_sample_cluster` | 函数 | 构造 checkout-api 的样例集群（1 Deployment、1 RS、3 Pod、1 Node、1 Service、Prom、Loki） | kube-state-metrics 同步结果 |
| `Hypothesis` | dataclass | 标题、引用、recency、specificity、路径长度；`score()` | 根因假设与证据打分 |
| `root_cause` | 函数 | 取告警对象的直接邻居中的遥测，按规则提出 3 类假设并排序 | `sample` + `walk` + `hypothesize` |
| `AuditEvent` | dataclass | 一次工具调用的审计记录 | 审计日志条目 |
| `Agent` | dataclass | 持有图、审计列表、只读与破坏性工具名单；`call()` 执行闸门逻辑 | 工具面 + 审批闸门 |
| `main` | 函数 | 告警 → 两次只读查询 → 排序假设 → 未审批回滚被拦 → 审批后回滚 → 打印审计 | 端到端演示 |

数据流：`build_sample_cluster()` → `Agent(graph)` → `agent.call("promql"/"logql")`（只读，写审计）→ `root_cause(g, "Deployment/checkout-api")` → 打印排序假设 → `agent.call("argocd_rollback")`（无审批，被拦）→ `agent.call(..., approver="alice@sre")`（执行）→ 打印审计日志。

---

## 3. 逐段精讲

### 3.1 `Node` 与 `Graph`：最小的属性图

```python
@dataclass
class Node:
    kind: str               # "Pod" | "Deployment" | "Node" | "Service" | "Prom" | "Loki"
    name: str
    attrs: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}/{self.name}"
```

- `@property` 让 `n.key` 像属性一样访问、实际由方法计算；`"Deployment/checkout-api"` 这种 `Kind/name` 格式与 kubectl 的习惯一致，也作为字典主键。
- `attrs` 存任意属性：Deployment 的 `revision`、`image`、`deployed_at`，Node 的 `kernel`，遥测节点的 `last_15m` 摘要与 `threshold`。
- 现实中同名对象会出现在不同 namespace，key 应包含 namespace（如 `prod/Deployment/checkout-api`）。

```python
    def neighbors(self, key: str) -> list[tuple[str, str]]:
        out = [(rel, dst) for s, rel, dst in self.edges if s == key]
        out += [(rel, src) for src, rel, dst in self.edges if dst == key]
        return out
```

- 出边和入边都算邻居（无向遍历），但返回值丢掉了方向信息：`EXPOSES` 实际是 Service → Deployment，返回成 `('EXPOSES', 'Service/checkout-api')`，看不出谁暴露谁。
- 每次调用都扫描全部边，`O(E)`；图大时应维护邻接表 `dict[str, list]`。
- ⚠️ 只返回**一跳**邻居，代码中没有多跳遍历——讲义的 `walk` 节点要"walk edges"，样例图里 Node 在 3 跳之外（见 3.3）。

### 3.2 `build_sample_cluster`：样例集群

```python
    g.link(dep.key, "OWNS", rs.key)
    for p in pods:
        g.link(rs.key, "OWNS", p.key)
        g.link(p.key, "SCHEDULED_ON", node.key)
    g.link(svc.key, "EXPOSES", dep.key)
    g.link(dep.key, "OBSERVED_BY", prom.key)
    g.link(dep.key, "OBSERVED_BY", loki.key)
```

- 结构：`Deployment -OWNS-> ReplicaSet -OWNS-> Pod×3 -SCHEDULED_ON-> Node`；`Service -EXPOSES-> Deployment`；`Deployment -OBSERVED_BY-> Prom / Loki`。
- 讲义用的是 `OWNED_BY`（Pod → ReplicaSet → Deployment 方向），代码用 `OWNS`（反方向），语义相同。
- 遥测数据以**摘要字符串**形式挂在节点属性上：`"mean=0.14 up_trend"`、`"500 errors on /api/v2/pay, stack = NullHealthz"`，模拟"最近 15 分钟切片"。
- `for n in (dep, rs, node, svc, prom, loki, *pods)`：`*pods` 把列表展开进元组。
- 数据与讲义 Use It 示例一致：checkout-api、3 个 Pod、节点 ip-10-2-3-4、14 分钟前发布 v2.41、错误率 14%。

### 3.3 `Hypothesis.score` 与 `root_cause`

```python
    def score(self) -> float:
        recency_w = max(0.0, 1.0 - self.recency_mins / 60.0)
        path_w = 1.0 / (1 + self.path_len)
        return (recency_w * 0.35 +
                self.specificity * 0.35 +
                min(len(self.citations), 5) / 5 * 0.2 +
                path_w * 0.1)
```

- recency：0 分钟 → 1，60 分钟及以上 → 0，线性下降；引用数最多计 5 条；路径长度取倒数。
- ⚠️ 讲义（Build It 第 5 步与 Key Terms）是**乘积** "recency × specificity × graph-path length inverse × citation count"，代码是**加权和**。乘积下任何一项为 0 整体为 0（"一票否决"），加权和下没有引用、事件很久远的假设仍有分数。
- "bad rollout" 的分数：`0.7667×0.35 + 0.82×0.35 + 2/5×0.2 + 1×0.1 = 0.2683 + 0.287 + 0.08 + 0.1 = 0.735`。

```python
def root_cause(g: Graph, alerted: str) -> list[Hypothesis]:
    hyps = []
    telemetry = []
    for rel, neighbor_key in g.neighbors(alerted):
        n = g.nodes.get(neighbor_key)
        if n and n.kind in ("Prom", "Loki", "Tempo"):
            telemetry.append(n)

    dep = g.nodes.get(alerted)
    if dep and dep.kind == "Deployment":
        mins = int(str(dep.attrs.get("deployed_at", "?")).split("m")[0]) \
            if "m" in str(dep.attrs.get("deployed_at", "")) else 999
        hyps.append(Hypothesis(
            title=f"bad rollout: image {dep.attrs.get('image')} fails /healthz",
            citations=[t.name for t in telemetry],
            recency_mins=mins, specificity=0.82, path_len=0))
    ...
```

- **sample**：从告警对象的直接邻居中筛出遥测节点（Prom/Loki/Tempo）作为证据。
- **假设 1：bad rollout**。注释说 "if recent deploy + observing error surge"，但代码**只检查是否是 Deployment**，并不检查错误率是否超过阈值：
  - 标题里的 "fails /healthz" 是硬编码的；
  - specificity 0.82 是硬编码的；
  - 我们删掉两条 `OBSERVED_BY` 边后重跑，这条假设仍以 0.655 分排第一，`citations: []`——违反 skill 文件 "Uncited hypotheses must be rejected"。
- ⚠️ `deployed_at` 的解析非常脆弱：`"14m ago"` → 14；`"2h ago"`、`"just now"` 不含 `m` → 999（"刚刚发布"被当成很久以前，分数降到 0.467）；`"2h30m ago"` → `int("2h30")` 抛 `ValueError`，整个分析崩溃。生产中应使用时间戳。
- `path_len=0`：虽然证据在 1 跳之外，代码把它当作告警对象本身的问题。

```python
    nodes = [g.nodes[dst] for _, dst in g.neighbors(alerted) if dst.startswith("Node/")]
    if nodes:
        hyps.append(Hypothesis(title=f"node-level pressure on {nodes[0].name} ...",
                               citations=[n.name for n in nodes],
                               recency_mins=30, specificity=0.45, path_len=2))

    hyps.append(Hypothesis(title="DNS flap in kube-system/coredns",
                           citations=[], recency_mins=60, specificity=0.2, path_len=4))
    return sorted(hyps, key=lambda h: -h.score())
```

- **假设 2：节点压力**。只在告警对象**直接**连着 Node 时出现。对 Deployment 告警，Node 在 `Deployment → RS → Pod → Node` 的第 3 跳，所以这一分支在演示中**永远不会执行**，输出只有 2 条假设。对 Pod 告警时才会出现（实测 `root_cause(g, "Pod/checkout-api-abc-0")` 得 node-level 0.406、DNS 0.09）。另外它的"引用"是 Node 名称而不是遥测。
- **假设 3：DNS 抖动**。无条件加入，0 条引用，分数 0.09——一个没有任何证据的"兜底"假设也会进入 Slack 简报。
- 排序后没有截取 top-3，也没有引用过滤。

### 3.4 `AuditEvent` 与 `Agent.call`：闸门与审计

```python
@dataclass
class AuditEvent:
    ts: float
    tool: str
    args: dict
    considered: bool = True
    approved: bool = False
    executed: bool = False
    approver: str | None = None
    result: str | None = None
```

- 字段对应讲义的 "considered, executed, approved, outcome"。`considered` 默认 True：只要调用了 `call` 就算"考虑过"。

```python
    read_only_tools: tuple = ("kubectl_get", "kubectl_describe", "promql", "logql", "traceql")
    destructive_tools: tuple = ("kubectl_scale", "kubectl_rollback", "kubectl_delete", "argocd_rollback")

    def call(self, tool: str, args: dict, approver: str | None = None) -> AuditEvent:
        ev = AuditEvent(ts=time.time(), tool=tool, args=args)
        if tool in self.read_only_tools:
            ev.executed = True
            ev.result = "ok (read-only)"
        elif tool in self.destructive_tools:
            if approver:
                ev.approved = True
                ev.approver = approver
                ev.executed = True
                ev.result = f"executed by {approver}"
            else:
                ev.result = "blocked: no slack approval"
        else:
            ev.result = "blocked: unknown tool"
        self.audit.append(ev)
        return ev
```

- 好的部分：
  - **默认拒绝**：不在任何名单里的工具（如 `kubectl_exec`）返回 `blocked: unknown tool`，我们实测确认；
  - **每次调用都记审计**，包括被拦截的调用——这就是"considered vs executed"的雏形；
  - 名单用元组（不可变），dataclass 的默认值用元组是安全的（不需要 `default_factory`）。
- ⚠️ **闸门可以自我批准**：`approver` 只是一个可选字符串参数。实测 `agent.call("kubectl_delete", {"ns": "prod", "all": True}, approver="agent-self")` 返回 `executed by agent-self`。讲义要求的是 "an approval token the agent never holds"，TS 版的 `slack_verify.ts` 至少校验了 Slack 请求的 HMAC 签名与时间窗口。
- ⚠️ **只读与破坏性工具在同一个对象里**：违反 skill 文件 hard reject "a single MCP server that mixes read-only and destructive tools"。
- ⚠️ 审计是内存列表，不是追加写入的 JSONL；"被拦截的提议"与"审批后的执行"之间没有关联 ID；LLM 推理中提出但没有调用 `call` 的命令不会被记录。
- 只读工具并不真的执行查询，`args` 里的 PromQL/LogQL 与 `root_cause` 用到的图上遥测摘要没有关系。

### 3.5 `main`：完整演示

```python
    agent.call("promql", {"query": "rate(http_requests_total{status=~'5..'}[5m])"})
    agent.call("logql", {"query": '{app="checkout-api"} |~ "stack"'})
    hyps = root_cause(g, alerted)
    ...
    ev = agent.call("argocd_rollback", {"app": "checkout-api", "to_revision": 41})
    ...
    ev = agent.call("argocd_rollback", {"app": "checkout-api", "to_revision": 41},
                    approver="alice@sre")
    ...
    for ev in agent.audit:
        print(" ", json.dumps({"tool": ev.tool, "executed": ev.executed, ...}))
```

- 顺序体现"先读后写"：先只读取证，再提出修复；修复先被拦截，"Slack 审批"后再执行。
- `json.dumps` 把字典序列化为一行 JSON，`None` 变成 `null`、`True` 变成 `true`——这正是 JSONL 审计日志的格式。
- 打印时省略了 `ts` 和 `args`，复盘时看不出回滚到了哪个版本。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 内存三元组列表表示图 | 零依赖、容易看懂 | 无索引、无方向信息；生产用 Neo4j/kuzu，每 30 秒从 kube-state-metrics 同步 |
| 只看一跳邻居 | 代码最短 | Node 级假设永远出不来；需要带路径的多跳 BFS |
| 遥测以摘要字符串挂在节点上 | 不依赖真实监控栈 | 假设不读取遥测内容；生产中由 `sample` 节点调用 PromQL/LogQL/TraceQL 并解析数值 |
| 规则生成 3 类假设、硬编码 specificity | 不需要 LLM | 标题与证据脱节；生产由 LLM（讲义：Claude Sonnet 4.7）基于证据提出假设 |
| 加权和打分 | 各项可补偿、数值稳定 | 无证据假设仍有分；讲义为乘积形式，或先过滤无引用假设 |
| 人类可读的 `deployed_at` | 演示直观 | 解析脆弱、会崩溃；应存时间戳 |
| `approver` 字符串作为审批 | 演示流程 | 可自我批准；生产用审批服务签发、绑定参数和过期时间的签名 token，破坏性工具放独立 MCP 服务器 |
| 未知工具默认拒绝 | 最小权限 | 正确做法，应保留 |
| 内存审计列表 | 便于打印 | 应追加写入持久存储、记录参数与关联 ID、每日归档（讲义：上传 S3） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=dict)` | `attrs: dict = field(default_factory=dict)` | 可变默认值用工厂 |
| 元组作为 dataclass 默认值 | `read_only_tools: tuple = ("kubectl_get", ...)` | 元组不可变，可以直接作默认值 |
| `@property` | `def key(self) -> str` | 方法当属性访问：`n.key` |
| 复杂类型注解 | `edges: list[tuple[str, str, str]]` | 三元组列表 |
| 联合类型 | `approver: str \| None = None` | 可为 None |
| 带条件的列表推导式 | `[(rel, dst) for s, rel, dst in self.edges if s == key]` | 遍历时解包三元组并过滤 |
| `+=` 拼接列表 | `out += [...]` | 原地扩展 |
| 星号展开 | `for n in (dep, rs, node, svc, prom, loki, *pods)` | 把列表元素展开进元组 |
| `dict.get` | `g.nodes.get(neighbor_key)`、`dep.attrs.get("image")` | 键不存在返回 None 或默认值 |
| `str.startswith` | `dst.startswith("Node/")` | 前缀判断 |
| 条件表达式 + 链式字符串方法 | `int(str(x).split("m")[0]) if "m" in str(...) else 999` | 一行内的三元表达式（可读性差且脆弱） |
| `max(0.0, ...)` / `min(len(...), 5)` | `score()` 中 | 截断到区间 |
| `sorted(..., key=lambda h: -h.score())` | `root_cause` 返回值 | 按分数降序 |
| `enumerate(hyps, 1)` | `for i, h in enumerate(hyps, 1)` | 从 1 开始编号 |
| `time.time()` | `AuditEvent(ts=time.time(), ...)` | Unix 时间戳（秒，浮点） |
| `json.dumps` | 打印审计 | 序列化为 JSON 字符串 |
| `if/elif/else` 多分支 | `Agent.call` | 只读 / 破坏性 / 未知 三类处理 |
| f-string 格式符 | `f"#{i} score={h.score():.3f}"` | 三位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，输出确定）：

```text
=== alert received: Deployment/checkout-api (error rate 14%) ===

ranked hypotheses:
  #1 score=0.735  bad rollout: image checkout-api:v2.41 fails /healthz
     citations: ['error_rate{deployment=checkout-api}', 'namespace=prod,app=checkout-api']
  #2 score=0.090  DNS flap in kube-system/coredns
     citations: []

proposing remediation:
  argocd_rollback: blocked: no slack approval

slack approval granted by alice@sre
  argocd_rollback: executed by alice@sre

audit log:
  {"tool": "promql", "executed": true, "approved": false, "approver": null, "result": "ok (read-only)"}
  {"tool": "logql", "executed": true, "approved": false, "approver": null, "result": "ok (read-only)"}
  {"tool": "argocd_rollback", "executed": false, "approved": false, "approver": null, "result": "blocked: no slack approval"}
  {"tool": "argocd_rollback", "executed": true, "approved": true, "approver": "alice@sre", "result": "executed by alice@sre"}
```

逐项解读：

- **只有 2 条假设**：node-level 假设因为一跳遍历而缺席（3.3），讲义要求 top-3。
- **#1 的 0.735** 可以手算：recency 0.268 + specificity 0.287 + 引用 0.08 + 路径 0.1。两条引用是 Prom 和 Loki 节点的名字，基本符合"遥测引用"的定义。
- **#2 没有引用却被列出**：在真实的 Slack 简报里，这会让 on-call 去查一个毫无依据的方向；按 skill 文件应该被过滤。
- **审计日志 4 条**：两次只读查询、一次被拦截的回滚提议、一次审批后的回滚。第 3 条就是一个"near-miss"记录（破坏性命令在无审批时被提出）。但审计里看不到参数（回滚到 revision 41）、时间戳，第 3 条与第 4 条之间也没有关联 ID。
- **"approver": "alice@sre" 是谁写的？** 是 `main()` 直接写进参数的。在这份代码里，agent 同样可以写——审批的真实性无从验证。
- **与讲义 Use It 对比**：讲义示例有 `[graph]`、`[walk]`、`[sample]`、`[hypo]`、`[slack]` 各阶段输出和三个按钮 `[ROLL BACK to v2.40] [ESCALATE] [IGNORE]`；本代码只模拟了排序与闸门。

---

## 7. 动手改一改

1. **多跳遍历**：实现带路径记录的 `walk(g, start, max_depth=3)`（BFS），把 `root_cause` 中的 Node 查找改为基于 `walk` 的结果，并把真实路径长度（3）填入 `path_len`；确认输出出现第 3 条假设（测验 Q10）。
2. **证据门槛**：解析 Prom 节点的 `mean=` 与 `threshold`，只有错误率超过阈值才提出 rollout 假设；过滤掉没有引用的假设；只返回 top-3（测验 Q9）。
3. **改成乘积打分**：按讲义公式实现 `score_product()`，比较两种打分下三条假设的排序与 DNS 假设的去留。
4. **健壮的时间处理**：把 `deployed_at` 改为 ISO 8601 时间戳，用 `datetime` 计算分钟数；顺便写一个 `minutes_ago()` 兼容旧格式（测验 Q12）。
5. **真正的审批 token**：把破坏性工具拆到 `DestructiveServer` 类，只接受由审批服务 `mint_token()` 签发、绑定工具与参数、5 分钟过期的 HMAC token；验证 agent 自填 approver 无法执行（测验 Q11）。
6. **进阶：审计与 near-miss**：把审计改成追加写入 `audit.jsonl`（包含 `ts`、`args`、`proposal_id`、`incident_id`），统计"无审批提出破坏性命令"的次数作为 near-miss 率（讲义练习 2）；再写 3～5 个合成故障场景（OOMKill、PVC 写满、错误 ConfigMap），用不同的图与遥测验证根因准确率。

---

## 8. 常见坑

- **审批是自报字段**：只要调用方能自己填 `approver`，闸门就形同虚设；审批凭证必须由 agent 拿不到密钥的服务签发。
- **读写工具混在一起**：同一个进程/服务器同时持有只读与破坏性能力，一次 prompt injection 就可能越权；应物理分离。
- **只看一跳**：K8s 的因果链经常跨越多层（Deployment → Pod → Node → 其它 Pod），一跳遍历会系统性漏掉基础设施层的根因。
- **无证据的兜底假设**：为了"凑满 top-3"加入没有引用的假设，会误导 on-call。
- **硬编码结论**：假设标题、specificity 写死在代码里，而不是从遥测中推出，容易出现"论断与证据不符"。
- **解析人类可读时间**：`"2h30m ago"` 让整个分析崩溃，`"just now"` 被当作很久以前；应使用时间戳。
- **审计缺参数**：只记工具名不记参数，复盘时不知道"回滚到了哪里"；也要记录被考虑但未调用的命令。
- **把 `kubectl exec` 当只读**：名义上不改资源，实际可以执行任意命令；默认拒绝未知工具是正确的做法。
