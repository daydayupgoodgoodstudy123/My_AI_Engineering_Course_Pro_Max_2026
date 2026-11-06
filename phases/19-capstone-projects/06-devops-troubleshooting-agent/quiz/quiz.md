# 测验 · 面向 Kubernetes 的 DevOps 故障排查 Agent（Capstone 06 — DevOps Troubleshooting Agent for Kubernetes）

> **阶段 19 · 综合项目 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，术语有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生产形态 | 讲义：告警 webhook 触发 → agent 读遥测 → 遍历 K8s 对象图 → 对根因假设排序 → 在 Slack 发带审批按钮的简报；"Read-only by default. Every remediation gated by a human." |
| 2 | K8s 知识图谱 | 节点 = K8s 对象（Pod、Deployment、Node、Service、PVC、HPA）+ 遥测源（Prometheus、Loki、Tempo）；边 = 所有权（OWNED_BY/OWNS）、调度（SCHEDULED_ON）、观测（OBSERVED_BY）等 |
| 3 | 根因分析三步 | LangGraph 三个节点：`sample` 取最近 15 分钟遥测切片、`walk` 查询图上邻居、`hypothesize` 生成带遥测引用的候选根因 |
| 4 | 证据打分 | 讲义：recency × specificity × 图路径长度倒数 × 引用数，返回 top-3；本节代码改成了加权和 |
| 5 | 只读优先的工具面 | kubectl get/describe、PromQL、LogQL、TraceQL 经 FastMCP 暴露，RBAC 只有 get/list/describe；`kubectl exec`、`port-forward` 也不能放进只读服务器 |
| 6 | 破坏性操作闸门 | scale、rollback、delete 放在**第二个** MCP 服务器上，需要 Slack 审批后才能拿到的 token；ArgoCD 回滚 token agent 永远不持有 |
| 7 | 审计日志 | 追加写入（append-only）的 JSONL，记录每条**被考虑过**的命令：是否执行、谁批准、结果——用于发现 near-miss |
| 8 | 遥测引用 | 支撑论断的 Prometheus 查询、Loki 选择器或 Tempo trace URL；没有引用的假设必须拒绝（skill 文件 hard reject） |
| 9 | 评估 | 20 个合成故障场景（OOMKill 级联、DNS 抖动、HPA 抖动、PVC 写满、吵闹邻居、错误 ConfigMap 等）；根因准确率 ≥ 80%，告警到 Slack 简报 p50 < 5 分钟 |
| 10 | 本节代码的边界 | 图遍历只走 1 跳；审批只看 `approver` 参数是否为空（agent 可以自填）；无引用的 DNS 假设仍被输出 |

### 核心技能（能动手做到）

- [ ] 用 `(src, rel, dst)` 三元组表示 K8s 对象图，并写出带路径记录的多跳 BFS 遍历
- [ ] 手算本节 `Hypothesis.score()`，并与讲义的乘积形式比较
- [ ] 指出"无遥测引用的假设"与"审批只是一个字符串参数"两个安全问题，并给出修复
- [ ] 用 HMAC 实现与工具、参数、过期时间绑定的审批 token，并说明为什么 agent 不能持有签名密钥
- [ ] 设计"considered vs executed"的追加写入审计日志与 near-miss 统计
- [ ] 为 20 个合成故障场景设计评估方案（根因准确率、time-to-hypothesis）

---

## 二、基础自测（选择题）

**Q1.** 讲义中故障排查 agent 默认的权限姿态是：

- A. 拥有 cluster-admin 权限，以便快速修复
- B. 可以执行任何命令，但事后写审计日志
- C. 默认只读（get/list/describe），破坏性动词放在单独的服务器上，必须经人工审批
- D. 只能读取日志，不能读取指标

**Q2.** 本节代码中 "bad rollout" 假设的参数为 `recency_mins=14, specificity=0.82, citations=2 条, path_len=0`。其 `score()` 是：

```python
recency_w = max(0.0, 1.0 - self.recency_mins / 60.0)
path_w = 1.0 / (1 + self.path_len)
return (recency_w * 0.35 + self.specificity * 0.35 +
        min(len(self.citations), 5) / 5 * 0.2 + path_w * 0.1)
```

- A. 0.735
- B. 0.655
- C. 0.868
- D. 0.090

**Q3.** 运行 `main.py`，"ranked hypotheses" 里只有 2 条，代码中"node-level pressure"这条假设没有出现。原因是：

- A. 节点的 kernel 版本正常，代码判断无需报告
- B. 该假设分数太低被过滤
- C. Node 对象没有被加入图中
- D. `root_cause` 只看告警对象的直接邻居（1 跳），而 Node 与 Deployment 之间隔着 ReplicaSet 和 Pod（3 跳），所以永远找不到

**Q4.** 讲义要求审计日志记录 agent "考虑过"的每条命令，而不只是执行过的命令。主要目的是：

- A. 节省存储空间
- B. 让复盘能发现 near-miss：agent 差点在没有审批的情况下执行破坏性命令
- C. 让 agent 运行更快
- D. 满足 Prometheus 的数据格式要求

**Q5.** 在本节代码的 `Agent.call` 中，决定破坏性工具能否执行的实际条件是：

- A. `approver` 参数是否为非空字符串——调用方（包括 agent 自己）随便填一个名字就能执行
- B. 是否通过了 Slack 签名校验
- C. 是否持有 ArgoCD 的认证 token
- D. 是否在审批后 5 分钟内调用

**Q6.** 讲义 Key Terms 中的 "telemetry citation（遥测引用）" 指的是：

- A. 引用的论文
- B. Slack 消息的链接
- C. 支撑某个论断的 Prometheus 查询、Loki 选择器或 Tempo trace URL
- D. Deployment 的 YAML 文件名

**Q7.** 如果把 Deployment 的 `deployed_at` 改成 `"2h30m ago"`，`root_cause` 会：

- A. 把 recency 解析为 150 分钟
- B. 抛出 `ValueError`，整个根因分析崩溃
- C. 把 recency 设为 999
- D. 把 recency 解析为 2 分钟

**Q8.** skill 文件要求："Refuse to expose `kubectl exec`, `kubectl port-forward`, or any interactive tool via the read-only MCP." 原因是：

- A. 这两个命令执行太慢
- B. 它们需要 GPU
- C. 它们只能在 Windows 上运行
- D. 它们虽然名义上不修改资源对象，实际效果却是破坏性的：`exec` 可以在容器里执行任意命令，`port-forward` 可以打通网络访问内部服务

---

## 三、动手 / 代码题

**Q9.** 假设打分与引用要求：

1. 写出本节三条假设（rollout、node-level、DNS）在讲义乘积公式 `recency × specificity × (1/(1+path_len)) × citation_count` 下的结果，与代码的加权和相比有什么本质区别？
2. 把图中两条 `OBSERVED_BY` 边删掉（agent 拿不到任何遥测）后重新运行 `root_cause`，"bad rollout" 假设还会出现吗？分数多少？这违反了 skill 文件的哪条规定？
3. 修改 `root_cause`，让没有遥测引用的假设被拒绝，并让"bad rollout"只有在错误率超过阈值时才提出。

**Q10.** 图遍历：

```python
    def neighbors(self, key: str) -> list[tuple[str, str]]:
        out = [(rel, dst) for s, rel, dst in self.edges if s == key]
        out += [(rel, src) for src, rel, dst in self.edges if dst == key]
        return out
```

1. 写出 `g.neighbors("Deployment/checkout-api")` 的返回值。
2. 实现 `walk(g, start, max_depth)`：BFS 遍历并记录从 `start` 到每个节点的路径（边列表），写出从 Deployment 出发、深度 3 时到达 Node 的路径。
3. 这条路径的长度如何用于讲义的 "graph-path length inverse"？为什么路径越长权重越低？

**Q11.** 审批闸门与审计：

```python
        elif tool in self.destructive_tools:
            if approver:
                ev.approved = True
                ev.approver = approver
                ev.executed = True
```

1. 执行 `agent.call("kubectl_delete", {"ns": "prod", "all": True}, approver="agent-self")`，结果是什么？这说明了什么？
2. 讲义要求"destructive tools live on a second MCP server behind an approval token"。用 HMAC 实现 `mint_token(tool, args, approver)` 与 `verify_token(token, tool, args)`，要求 token 绑定工具名、参数和过期时间。
3. 当前审计日志还缺少什么？列出至少四项改进。

**Q12.** `deployed_at` 的解析：

```python
mins = int(str(dep.attrs.get("deployed_at", "?")).split("m")[0]) \
    if "m" in str(dep.attrs.get("deployed_at", "")) else 999
```

1. 分别给出 `"14m ago"`、`"2h ago"`、`"just now"`、`"2h30m ago"` 的处理结果。
2. `"just now"` 被当成什么？对排序有什么影响？
3. 写一个更健壮的 `minutes_ago(text)`，并说明生产中应该怎样存储部署时间。

---

## 四、面试高频题

**Q13.**（基础必考）描述一个 K8s 故障排查 agent 从收到告警到给出修复建议的完整流程，并说明人在哪里介入。

**Q14.**（原理深挖）为什么要用知识图谱来组织 K8s 对象和遥测？与"把所有日志和指标一股脑塞给 LLM"相比有什么优势？如何区分"相关的遥测尖峰"和"真正的根因"（讲义练习 4）？

**Q15.**（工程实践）请设计这个 agent 的安全边界：RBAC、MCP 服务器划分、审批 token、审计日志、成本控制。讲义提到"OOM-kill cascades do not generate a $5k agent bill"，你怎么防？

**Q16.**（场景设计）凌晨 3 点 checkout-api 错误率升到 14%，14 分钟前刚发布了 v2.41，同时同一节点上的另一个服务内存也在上涨。agent 应该给出怎样的 Slack 简报？如果 on-call 点了"回滚"，后续流程是什么？

**Q17.**（追问型）"既然 agent 的根因分析准确率能到 80%，为什么不让它在高置信度时自动回滚？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义 Concept："Allowed default actions are read-only. Destructive actions (scaling down, rolling back, deleting Pods) require Slack approval; ArgoCD rollback hooks require an auth token the agent never holds." Key Terms："Agent's service account has only get/list/describe verbs; destructive verbs live in a separate server behind approval."

- A 违背最小权限原则；B 是"事后补救"，不是闸门；D 错，agent 要读 Prometheus 指标、Loki 日志和 Tempo trace。

### Q2 — 答案：A

`recency_w = 1 − 14/60 = 0.7667` → `× 0.35 = 0.2683`；`specificity 0.82 × 0.35 = 0.287`；引用 `2/5 × 0.2 = 0.08`；`path_w = 1/(1+0) = 1` → `× 0.1 = 0.1`。合计 **0.735**，与运行输出 `score=0.735` 一致（已实际计算）。

- B（0.655）是去掉两条遥测引用后的分数（见 Q9）；D（0.090）是 DNS 假设的分数；C 无依据。

### Q3 — 答案：D

`neighbors` 只返回直接相连的节点。实际打印 `g.neighbors("Deployment/checkout-api")`：`OWNS → ReplicaSet`、两条 `OBSERVED_BY → Prom/Loki`、`EXPOSES ← Service`，没有任何 `Node/`。Node 在 `Deployment → ReplicaSet → Pod → Node` 的第 3 跳上。所以对 Deployment 告警时，node-level 假设的分支**永远不会执行**，输出只有 2 条，不满足讲义"top-3"的要求。只有当告警对象是 Pod 时（直接 `SCHEDULED_ON` Node），这条假设才会出现——我们实际运行 `root_cause(g, "Pod/checkout-api-abc-0")`，得到 node-level 0.406 和 DNS 0.09。

- A、B 都不对：代码没有检查 kernel，也没有分数阈值；C 错，Node 已加入图并有 `SCHEDULED_ON` 边。

### Q4 — 答案：B

讲义："The audit log records every command the agent *considered* — not just executed — so the review process catches near-misses." 讲义练习 2 要求统计一周内的 near-miss 率。skill 文件的 hard reject："Audit logs that only record executions."

### Q5 — 答案：A

代码只检查 `if approver:`，任何非空字符串都算批准。我们实际运行 `agent.call("kubectl_delete", {"ns": "prod", "all": True}, approver="agent-self")`，返回 `executed by agent-self`。这是一个"装饰性"闸门：审批由调用方自己声明，没有任何不可伪造的凭证。同目录 TypeScript 版本的 `ts/src/slack_verify.ts` 做了 Slack 请求签名（HMAC-SHA256 + 5 分钟重放窗口 + 常量时间比较）校验，Python 版没有。

- B、C、D 都是正确做法的组成部分，但本节 Python 代码一个都没实现。

### Q6 — 答案：C

讲义 Key Terms："A Prometheus query, Loki selector, or Tempo trace URL that supports a claim." 引用让人可以一键复查证据。本节代码的 `citations` 只是遥测节点的名字（如 `error_rate{deployment=checkout-api}`），基本符合这个思路；但 node-level 假设引用的是 Node 名称 `ip-10-2-3-4`，并不是遥测。

### Q7 — 答案：B

`"2h30m ago"` 包含 `m`，于是执行 `int("2h30m ago".split("m")[0])` = `int("2h30")`，抛出 `ValueError: invalid literal for int() with base 10: '2h30'`（已实际运行验证），整个根因分析崩溃，agent 无法给出任何简报。

- A 是正确解析应得的值；C 是 `"2h ago"`、`"just now"` 这类不含 `m` 的字符串的结果；D 无依据。

### Q8 — 答案：D

`kubectl exec` 等于在生产容器里拿到一个 shell，可以删数据、改配置、读密钥；`port-forward` 打通从 agent 到集群内部服务的网络通道。它们在 RBAC 上属于 `pods/exec`、`pods/portforward` 子资源的 `create` 动词，不是"只读"。因此即使看起来"不修改资源对象"，也必须视为破坏性操作。本节代码对未登记的工具一律返回 `blocked: unknown tool`（我们实测 `kubectl_exec` 被拦截），这种"默认拒绝"是正确的。

### Q9 — 参考答案

1. 乘积形式（未归一化，引用数直接相乘）：
   - rollout：`0.7667 × 0.82 × 1/(1+0) × 2 ≈ 1.257`
   - node-level（recency 30、specificity 0.45、path 2、1 条引用）：`0.5 × 0.45 × 1/3 × 1 = 0.075`
   - DNS（recency 60、0 条引用）：`0 × … = 0`
   
   本质区别：乘积是"**一票否决**"——任何一项为 0（没有引用、事件太久远），整体就是 0；加权和允许各项互相补偿，DNS 假设在没有任何证据的情况下仍拿到 0.09，并出现在 Slack 简报里。对"必须有证据"的根因分析，乘积（或"先过滤再加权"）更符合讲义意图。
2. 实际运行：删掉 `OBSERVED_BY` 边后，"bad rollout: image checkout-api:v2.41 fails /healthz" **仍然排第一**，分数 0.655，`citations: []`。也就是说，这条假设只依据"Deployment 14 分钟前发布过"就提出，标题里的 "fails /healthz" 是硬编码的，并非从遥测中得出。违反 skill 文件 hard reject："Any RCA produced without telemetry citations. Uncited hypotheses must be rejected."
3. 参考修改：
   ```python
   def parse_rate(text: str) -> float | None:
       m = re.search(r"mean=([\d.]+)", text)
       return float(m.group(1)) if m else None

   def root_cause(g, alerted):
       ...
       prom = [t for t in telemetry if t.kind == "Prom"]
       surge = any((parse_rate(t.attrs.get("last_15m", "")) or 0) > t.attrs.get("threshold", 1.0)
                   for t in prom)
       if dep and dep.kind == "Deployment" and surge:          # 有错误激增才提 rollout
           hyps.append(Hypothesis(...))
       ...
       hyps = [h for h in hyps if h.citations]                 # 无引用一律拒绝
       return sorted(hyps, key=lambda h: -h.score())[:3]
   ```
   样例数据中 `mean=0.14 > threshold 0.05`，rollout 假设保留；DNS 假设因无引用被过滤。如果所有假设都被过滤，应该如实报告"证据不足，建议升级给人工"，而不是凑一个答案——讲义："It needs to know when it is outside its depth and escalate."

### Q10 — 参考答案

1. 实际输出：
   ```text
   [('OWNS', 'ReplicaSet/checkout-api-abc'),
    ('OBSERVED_BY', 'Prom/error_rate{deployment=checkout-api}'),
    ('OBSERVED_BY', 'Loki/namespace=prod,app=checkout-api'),
    ('EXPOSES', 'Service/checkout-api')]
   ```
   注意它把出边和入边混在一起，返回的 `rel` 没有方向信息（`EXPOSES` 实际是 Service → Deployment）。
2. 参考实现（已运行验证）：
   ```python
   from collections import deque

   def walk(g, start, max_depth=3):
       paths = {start: []}                       # 节点 -> 从 start 出发的边列表
       q = deque([start])
       while q:
           cur = q.popleft()
           if len(paths[cur]) >= max_depth:
               continue
           for rel, nb in g.neighbors(cur):
               if nb not in paths:               # 第一次到达即最短路径（BFS 性质）
                   paths[nb] = paths[cur] + [(cur, rel, nb)]
                   q.append(nb)
       return paths
   ```
   从 Deployment 出发：深度 1 到达 ReplicaSet、Prom、Loki、Service；深度 2 到达 3 个 Pod；深度 3 到达 `Node/ip-10-2-3-4`，路径为 `Deployment -OWNS-> ReplicaSet -OWNS-> Pod/checkout-api-abc-0 -SCHEDULED_ON-> Node`。
3. 路径长度 3 代入 `1/(1+3) = 0.25`。路径越长，告警对象与候选根因之间的因果链越间接，中间可能有更多其它解释，证据就越弱；同时长路径会让候选集合爆炸，需要用这个权重压低远处节点的优先级。真实系统还会在路径上附带每一跳的遥测（例如 Node 的内存压力指标），Slack 简报中把这条路径画成子图（讲义 Build It 第 6 步）。

### Q11 — 参考答案

1. 返回 `executed by agent-self`，并在审计日志里记下 `approved: true, approver: "agent-self"`。这说明：审批信息由调用方自报，agent 完全可以"自己批准自己"，甚至审计日志也会被这个伪造的名字污染。同时，同一个 `Agent` 对象既持有只读工具又持有破坏性工具，正是 skill 文件的 hard reject："Agents with a single MCP server that mixes read-only and destructive tools."
2. 参考实现（已运行验证）：
   ```python
   import hmac, hashlib, json, time
   SECRET = b"held-only-by-slack-approval-service"     # 只有审批服务持有，agent 进程拿不到

   def _digest(tool, args):
       return hashlib.sha256(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()

   def mint_token(tool, args, approver, ttl=300, now=None):     # 由 Slack 回调服务调用
       exp = int((now or time.time()) + ttl)
       payload = f"{tool}|{_digest(tool, args)}|{approver}|{exp}"
       sig = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
       return f"{payload}|{sig}"

   def verify_token(token, tool, args, now=None):              # 由破坏性 MCP 服务器调用
       try:
           t, d, approver, exp, sig = token.split("|")
       except ValueError:
           return None
       good = hmac.new(SECRET, f"{t}|{d}|{approver}|{exp}".encode(), hashlib.sha256).hexdigest()
       if not hmac.compare_digest(sig, good):
           return None
       if t != tool or d != _digest(tool, args) or (now or time.time()) > int(exp):
           return None
       return approver
   ```
   测试结果：正确的工具与参数返回 `alice@sre`；把 `to_revision` 从 41 改成 1、把工具换成 `kubectl_delete`、超过 5 分钟、把 token 里的 approver 改成 `mallory`，四种情况都返回 `None`。关键设计：签名密钥只在审批服务和破坏性工具服务器之间共享，agent 只能"转交" token，无法伪造；token 绑定具体参数，批准"回滚到 41"不能被拿去"删除 namespace"；短有效期 + 可加一次性 nonce 防重放。
3. 审计日志的改进：
   - **追加写入且持久化**：写 JSONL 文件或日志服务，每天上传 S3（讲义第 8 步），而不是内存列表；
   - **记录完整参数和时间戳**：打印的审计记录里漏掉了 `ts` 和 `args`，复盘时无法知道回滚到了哪个版本；
   - **记录"考虑过但没有调用"的命令**：现在 `considered` 恒为 True，只有调用过 `call` 的命令才会被记录；LLM 推理中提出但被策略层或模型自己放弃的命令也要记；
   - **关联字段**：proposal_id 把"被拦截的提议"和"审批后的执行"串起来，并关联 incident_id、Slack 消息 ID；
   - **结果与回执**：执行后的真实结果（ArgoCD 返回的状态）、执行耗时；
   - **防篡改**：哈希链或写入不可变存储；
   - **near-miss 标记**：破坏性命令在无审批时被提出，标记为 near-miss，用于讲义练习 2 的统计。

### Q12 — 参考答案

1. 实际运行：`"14m ago"` → 14；`"2h ago"` → 不含 `m`，999；`"just now"` → 不含 `m`，999；`"2h30m ago"` → `ValueError` 崩溃。另外 `"45 min ago"` 碰巧能解析为 45。
2. `"just now"` 被当作 999 分钟前，`recency_w = 0`，一个"刚刚发布"的版本被认为"很久以前"，"bad rollout" 的分数从 0.735 降到 0.467——恰恰是最可疑的情况被低估了。而解析失败时默认 999 也掩盖了数据问题。
3. 参考实现（已运行验证）：
   ```python
   import re
   UNIT = {"s": 1/60, "m": 1, "min": 1, "h": 60, "d": 1440}

   def minutes_ago(text: str) -> int | None:
       t = text.strip().lower()
       if t in ("just now", "now"):
           return 0
       parts = re.findall(r"(\d+)\s*(min|[smhd])", t)
       if not parts:
           return None                    # 解析失败返回 None，由调用方决定如何处理
       return round(sum(int(n) * UNIT[u] for n, u in parts))
   ```
   结果：14m → 14、2h → 120、2h30m → 150、45 min → 45、just now → 0、1d → 1440、yesterday → None。
   生产中不应存人类可读的相对时间，而应存 **ISO 8601 / Unix 时间戳**（例如 Deployment 的 `metadata.creationTimestamp`、ReplicaSet 的创建时间、ArgoCD 的同步时间），在计算时用 `now − deployed_at` 得到分钟数；所有时间统一为 UTC。

### Q13 — 参考回答要点

- **流程**：
  1. Alertmanager / PagerDuty webhook → FastAPI 接收，解析受影响对象与 SLO 违约；
  2. `sample`：用只读工具拉最近 15 分钟的 Prometheus 指标、Loki 日志、Tempo trace；
  3. `walk`：在 K8s 知识图谱上从告警对象出发多跳遍历（所有权、调度、观测边），收集近期变更（发布、ConfigMap、HPA 事件）；
  4. `hypothesize`：生成候选根因，每条附遥测引用与图路径，按证据打分取 top-3；
  5. 发 Slack 简报：假设、证据、子图可视化、最多一个修复按钮（讲义："approval buttons for at most one remediation action"）；
  6. 人工审批 → 审批服务签发 token → 破坏性 MCP 服务器执行（如 ArgoCD 回滚）或升级 PagerDuty；
  7. 全程写审计日志，事后复盘 near-miss。
- **人的介入点**：所有破坏性操作的审批；agent 判断超出能力范围时的升级；复盘审计日志。
- 加分点：讲义 Use It 的示例流程与 "approval required; agent does not roll back unilaterally"；p50 < 5 分钟的目标。

### Q14 — 参考回答要点

- **图谱的优势**：
  - **范围控制**：告警对象的邻域通常只有几十个对象，只取它们的遥测，避免把全集群日志塞进上下文（成本与噪声都大）；
  - **可解释**：图路径就是因果链的候选（"Deployment 的 Pod 都调度在同一个 Node 上，该 Node 内存压力高"），可以可视化给人看；
  - **结构化推理**：所有权和调度关系是确定的事实，不需要 LLM 猜；
  - **新鲜度**：讲义每 30 秒同步 kube-state-metrics，告警时再采样。
- **相关 vs 因果**（讲义练习 4）：
  - 时间先后：根因的变化应早于症状（发布在错误率上升之前）；
  - 拓扑：根因应在症状对象的上游或共享资源上；
  - 特异性：只影响该服务的变化比全局波动更可疑；
  - 反事实 / 对照：同版本的其它副本、其它节点是否也有问题；
  - 用 20 个场景的标签训练一个小分类器，特征包括时间差、图距离、是否有变更事件、指标变化幅度。
- 常见误区：看到哪个指标最异常就报哪个——级联故障中下游的异常往往最显眼，但不是根因。

### Q15 — 参考回答要点

- **RBAC**：agent 的 ServiceAccount 只绑定 get/list/watch（讲义：narrow RBAC role，独立 namespace）；不包含 secrets 读取、`pods/exec`、`pods/portforward`。
- **MCP 划分**：只读服务器（kubectl get/describe、PromQL、LogQL、TraceQL）与破坏性服务器（scale、rollback、delete）分离部署，后者要求审批 token，并且只接受预定义参数范围（如只能回滚到最近 N 个版本）。
- **审批 token**：由 Slack 审批回调服务签发（校验 Slack 请求签名，如 TS 版 `slack_verify.ts`），绑定工具 + 参数 + 过期时间 + 审批人，agent 只能转交；批量操作需要逐个 Deployment 审批（skill 文件拒绝规则）。
- **审计**：considered/executed/approved/outcome 全记录，追加写入，每日归档。
- **成本控制**（防 "$5k agent bill"）：
  - 告警去重与聚合：一次 OOMKill 级联可能触发上百条告警，应按根对象、时间窗口合并成一个 incident；
  - 每个 incident 的 token / 工具调用 / 美元上限，超限即停止并升级给人工；
  - 遥测切片限定 15 分钟、限定对象范围、日志先用便宜模型摘要（讲义：Gemini 2.5 Flash 做日志摘要，Claude Sonnet 4.7 做根因推理）；
  - 全局速率限制与熔断。
- 加分点：把 agent 本身也当作需要监控的生产服务（成本、错误率、near-miss 率）。

### Q16 — 参考回答要点

- **简报内容**（top-3，每条带引用和路径）：
  1. "v2.41 发布导致 /api/v2/pay 返回 500"——引用：错误率 PromQL（14%，阈值 5%，发布后开始上升）、Loki 500 错误栈、Deployment revision 42 的变更时间；路径：Deployment → OBSERVED_BY → Prometheus/Loki；
  2. "同节点吵闹邻居导致内存压力"——引用：Node 内存压力指标、另一服务的内存曲线；路径：Deployment → ReplicaSet → Pod → Node；需要指出：如果只有 checkout-api 的 Pod 出错而其它节点上的副本同样出错，则节点假设较弱；
  3. 证据不足的候选可以不列，或标明"低置信度"。
- **按钮**：`[ROLL BACK to v2.40]`、`[ESCALATE]`、`[IGNORE]`（讲义 Use It），最多一个修复动作。
- **点了回滚之后**：
  1. Slack 回调服务校验签名、确认点击者在 on-call 名单中；
  2. 签发绑定"argocd_rollback, app=checkout-api, to_revision=41"的短期 token；
  3. （讲义练习 5）先在 staging 做回滚 dry-run，确认计划；
  4. 破坏性 MCP 服务器校验 token 后调用 ArgoCD 回滚；
  5. agent 继续用只读工具监控错误率是否回落，把结果回帖到 Slack 线程；
  6. 审计日志记录提议、审批、执行、结果；MTTR 从告警开始计算到 SLO 恢复。

### Q17 — 参考回答要点

- **80% 意味着每 5 次就有 1 次错**：错误的自动回滚可能把一个正常的发布撤掉、引入新的不兼容（数据库 schema 已迁移时回滚会更糟），或在级联故障中放大问题。
- **责任与合规**：生产变更需要可追溯的人类决策者；skill 文件明确："Refuse to remediate without Slack approval from a human on-caller. Even if the hypothesis is obvious."
- **置信度不可靠**：LLM 自报的置信度往往未校准；没有在 20 个场景以外验证过的置信度不能作为自动执行依据。
- **对抗风险**：日志和告警内容可能被注入恶意文本（indirect prompt injection），诱导 agent 执行破坏性操作；人工审批是最后一道防线。
- **人工审批的成本其实很低**：agent 已经把证据和一键按钮准备好，人只需要几十秒判断，MTTR 的主要收益来自缩短诊断时间，而不是省掉这几十秒。
- **可以逐步放开**：对低风险、可逆、经过大量验证的动作（如对无状态服务扩容），可以在有 kill switch 和事后审计的前提下设白名单自动执行；但讲义的设计原则是 "Every remediation gated by a human"。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)、[阶段 13 · 07 构建 MCP 服务端](../../../13-tools-and-protocols/07-building-an-mcp-server/docs/zh.md)：只读与破坏性两个 MCP 服务器的实现基础。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../../13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/zh.md)：工具面的安全威胁。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)、[阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：只读优先与人工审批的设计原则。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：AI 辅助 SRE 的整体图景。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：用图结构组织 agent 的知识。

### 本节被哪些后续内容用到
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../11-llm-observability-dashboard/docs/zh.md)：把 agent 自身的 trace、成本、near-miss 指标做成仪表盘。
- [阶段 19 · 13 带注册表与治理机制的 Stateless MCP 服务端](../../13-mcp-server-with-registry/docs/zh.md)：工具服务器的治理与权限分级。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../15-constitutional-safety-harness/docs/zh.md)：对 agent 的危险动作做系统化红队测试。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审计日志与密钥管理的生产实践。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：日志与告警文本中的注入风险。

### 延伸关键词
`AIOps` · `root cause analysis` · `kube-state-metrics` · `knowledge graph` · `PromQL / LogQL / TraceQL` · `least privilege RBAC` · `human-in-the-loop approval` · `HMAC signed token` · `append-only audit log` · `near-miss` · `MTTR` · `blast radius` · `ArgoCD rollback` · `alert deduplication` · `causal vs correlated`
