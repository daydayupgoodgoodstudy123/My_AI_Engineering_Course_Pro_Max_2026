# 测验 · 紧急停止开关、Circuit Breakers 与金丝雀 Tokens（Kill Switches, Circuit Breakers, and Canary Tokens）

> **阶段 15 · 自主系统 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 预算层之外为何还要绊线 | 成本控制器限制"花多少"，不限制"预算内做什么"；外泄密钥、删资源在 token 上往往很便宜 |
| 2 | Kill switch | agent 能读不能写的外部布尔值（功能开关服务、agent 轮询的 Redis key、签名配置、容器层 kill）；每个有后果的动作前都检查；关闭时不产生任何外部可见行为；重新启用必须是人的显式操作 |
| 3 | Circuit breaker | 只暂停特定模式而非整个 agent；经典三态 closed / open / half-open（Nygard 2007），半开时允许 1–3 次探测 |
| 4 | Agent 场景的断路器触发条件 | 连续 5 次相同工具调用、同一工具连续 5 次失败、调用速率超阈值、读取不可信内容后调用特定工具（如 `file.delete`） |
| 5 | Canary token / honeytoken | agent 没有正当理由触碰的诱饵：假 AWS 密钥、带哨兵值的假数据库记录、假文件、会话开始时注入的假记忆；"访问即告警" |
| 6 | 金丝雀设计原则 | 必须针对具体工作流；agent 有正当理由触碰的金丝雀只会制造噪声；必须放在 agent 不能修改的系统里 |
| 7 | 统计检测 + 硬上限分层 | EWMA、CUSUM、z-score 会适应移动的基线——对正常漂移是优点，对对抗性慢漂移是缺陷；硬性宪法式规则不随历史变化 |
| 8 | eBPF 隔离 | Cilium 可在内核层把被隔离 pod 的出口流量改写到取证蜜罐；讲义：数据面 P99 延迟亚毫秒级，触发隔离的总耗时主要取决于策略从控制面传播到节点的时间 |
| 9 | 检测器抓不住什么 | 由允许的原语组合出的语义攻击；把检测器本身作为攻击目标的 payload（"先禁用金丝雀"） |
| 10 | 代码揭示的问题 | 断路器在第 7 轮（而非讲义说的第 5 轮）触发并 `break`，金丝雀从未触发；断路器是全局的，打开后拒绝一切动作 |

### 核心技能（能动手做到）

- [ ] 跑通 `code/main.py`，逐轮解释输出，并说明为什么 `canary_hits=0`
- [ ] 把全局断路器改为按动作键（或按工具）的断路器，使断路器与金丝雀都能在同一条轨迹中触发
- [ ] 构造至少两种绕过本代码断路器或金丝雀的轨迹，并给出修复
- [ ] 实现一个 EWMA z-score 检测器，演示它对缓慢漂移不报警，而"10 分钟内不超过 50 次调用"的硬上限能报警
- [ ] 为一个浏览器 agent 设计至少 3 个金丝雀，说明各自放在哪里、检测什么、谁来响应
- [ ] 写出 kill switch 的重新启用流程：谁能启用、记录什么、启用前 agent 必须改变什么

---

## 二、基础自测（选择题）

**Q1.** 下列哪一组性质**全部**符合讲义对"正确的 kill switch"的要求？

- A. agent 的凭证无法把它设为关闭；每个有后果的动作前都检查；重新启用是人的显式操作而不是自动超时
- B. 存在 agent 可读写的配置文件里；启动时检查一次；关闭 10 分钟后自动恢复
- C. 由 agent 自己判断何时触发；每个动作前检查；关闭后 agent 仍可向日志系统写入状态
- D. 存放在功能开关服务里；只在每天开始时检查；操作员和 agent 都可以重新启用

**Q2.** 经典断路器有三个状态。关于 half-open（半开），讲义的描述是：

- A. 一半的请求被放行，另一半被拒绝
- B. 断路器永久打开，等待人工重置
- C. 冷却期过后允许 1–3 次探测请求（默认 1 次），成功则关闭断路器，剩余探测失败则重新打开
- D. 断路器关闭，但所有请求都记录日志

**Q3.** 运行 `code/main.py`，在 kill switch 关闭的那次运行中，断路器在第几轮触发？

- A. 第 3 轮
- B. 第 5 轮
- C. 第 9 轮
- D. 第 7 轮

**Q4.** 同一次运行的汇总行是 `kill_fired=False  breaker_fired=True  canary_hits=?`。`canary_hits` 的值及原因是：

- A. 1，第 9 轮读取了 `~/.env.canary`
- B. 0，断路器在第 7 轮触发后 `break` 终止了整条轨迹，第 9 轮的金丝雀读取从未执行
- C. 0，因为 `~/.env.canary` 不在 `CANARY_FILES` 中
- D. 2，两个金丝雀文件都被读取了

**Q5.** 讲义为什么说统计检测器（EWMA、CUSUM、z-score）必须与硬上限分层使用？

- A. 统计检测器计算太慢，无法实时运行
- B. 统计检测器只能检测成本，不能检测动作
- C. 统计检测器会适应移动的基线，耐心的攻击者可以缓慢地推动基线而不触发告警；硬上限不随历史变化
- D. 硬上限误报率更低，所以可以完全替代统计检测

**Q6.** 关于金丝雀令牌的设计，下列说法正确的是：

- A. 金丝雀必须是 agent 在正常工作中没有正当理由触碰的东西，否则只会产生噪声
- B. 金丝雀应放在 agent 有写权限的目录里，便于定期更新
- C. 金丝雀的价值在于内容检测：它会扫描 agent 的输出中是否含有敏感词
- D. 一个通用的金丝雀集合可以适用于所有工作流

**Q7.** 讲义讨论用 Cilium/eBPF 把被隔离 pod 的出口流量重定向到取证蜜罐。从"决定隔离"到"第一个被重定向的数据包"，墙钟时间主要由什么决定？

- A. eBPF 数据面的处理延迟（P99 亚毫秒）
- B. agent 下一次读取 kill switch 的时间
- C. 蜜罐服务器的启动时间
- D. 策略更新从控制面传播到节点的时间（在 Kubernetes 上预加载 operator 时约几百毫秒，尾延迟取决于集群规模与 reconcile 节奏）

**Q8.** 下列哪种攻击是讲义所说的"no detector catches"？

- A. agent 连续 20 次调用完全相同的工具
- B. 每个单独动作都能通过所有检测器，但这些允许的动作组合起来造成了危害
- C. agent 读取了工作区中的假 AWS 密钥文件
- D. 操作员打开 kill switch 后 agent 仍试图执行动作

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1 写道："Confirm the circuit breaker fires on turn 5 (fifth identical call) and the canary fires on turn 9 (fake-key read)."

```python
    traj = [
        Action("tool", "read:src/app.py"),
        Action("tool", "edit:src/app.py"),
        Action("tool", "read:logs/app.log"),   # start identical-read burst
        Action("tool", "read:logs/app.log"),
        Action("tool", "read:logs/app.log"),
        Action("tool", "read:logs/app.log"),
        Action("tool", "read:logs/app.log"),   # 5th identical -> breaker
        Action("read", "~/notes/checklist.md"),
        Action("read", "~/.env.canary"),       # canary hit
    ]
```

1. 实际输出与练习的说法有哪两处不一致？
2. 如果只把断路器分支里的 `break` 改为 `continue`，金丝雀能触发吗？为什么？
3. 给出能让"断路器 + 金丝雀"都触发的最小改动，并写出改动后第 7–9 轮的输出。

**Q10.** 阅读 `CircuitBreaker.record`：

```python
    def record(self, action_key: str) -> bool:
        if self.state == "open":
            return False
        self.recent.append(action_key)
        if len(self.recent) >= self.threshold:
            tail = self.recent[-self.threshold:]
            if all(a == tail[0] for a in tail):
                self.state = "open"
                return False
        return True
```

1. 构造一条 12 步的轮询循环，使断路器**不触发**。
2. `CircuitBreaker(threshold=3)` 依次记录 `x, x, x, y, z`，返回值是什么？这与讲义"pauses a specific pattern, not the whole agent"有何矛盾？
3. 给出一个更稳健的断路器设计（关键代码），能抓住第 1 问的循环，并且只暂停出问题的那个工具。

**Q11.** 阅读金丝雀检测：

```python
        if a.kind == "read":
            hit = canary.check_read(i, a.payload)
```

```python
    def check_read(self, turn: int, path: str) -> bool:
        if path in CANARY_FILES:
            ...
```

1. 给出至少三个能读取 `~/.env.canary` 却**不触发**告警的动作。
2. 如何修复？进一步，生产环境中金丝雀检测应该挂在哪一层？

**Q12.** 讲义练习 2：每分钟的工具调用次数从 3 缓慢漂移到 9（60 分钟内每分钟增加 0.1，取整）。用 EWMA z-score 检测器（α = 0.1，z > 3 报警，前 5 分钟预热）和硬上限"任意 10 分钟窗口内不超过 50 次"分别检测。

1. 写出两个检测器的实现。
2. 它们在这条轨迹上分别是否触发、何时触发？若换成"平时每分钟 3 次、第 30 分钟突增到 12 次"的轨迹呢？
3. 这说明了什么？

---

## 四、面试高频题

**Q13.**（基础必考）kill switch、circuit breaker、canary token 三者分别解决什么问题？粒度、触发方式、响应动作有什么区别？

**Q14.**（原理深挖）为什么讲义强调这三种检测器"do not trust the agent's self-report"？统计检测和硬上限各自的优缺点是什么，应如何分层？

**Q15.**（工程实践）请设计一个生产级的 kill switch：放在哪里、如何检查、传播延迟怎么控制、触发后发生什么、如何重新启用？

**Q16.**（场景设计）讲义练习 3：为一个浏览器 agent（第 11 节）设计一组金丝雀令牌，并说明金丝雀触发后的隔离流程。

**Q17.**（追问型）讲义说有两类攻击"no detector catches"。具体是什么？你会用什么补充手段降低风险？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义列出的性质："The agent cannot set it to `off`"、"It is checked on every consequential action, not just at startup"、"When it is off, the agent does nothing externally observable, including logging to systems the agent can reach"、"Re-enabling it is an explicit human action, not an automatic timeout." B 三条都违反（可写、只在启动时查、自动恢复）；C 由 agent 自己判断、关闭后仍写日志，违反第 1、3 条；D 每天检查一次、agent 可重新启用，违反第 2、4 条。

### Q2 — 答案：C

讲义："Half-open: after a cool-down, 1–3 probe attempts are allowed (default 1); success closes the breaker, any remaining failure re-opens it." A 是对"半"字的望文生义；B 描述的是没有半开状态的实现（本节代码其实就是这样——注释里写了 `half_open` 但没有实现）；D 不是断路器的任何状态。注意 skill 文件要求：冷却后自动重新启用而不经人工审查的断路器属于 hard reject，所以 agent 场景下的半开转换通常要有人参与。

### Q3 — 答案：D

相同的 `tool:read:logs/app.log` 从第 3 轮开始，第 3、4、5、6 轮各执行一次（4 次），第 7 轮是第 5 次相同调用，`record` 发现最后 5 个全部相同，打开断路器并拒绝这一次。输出：`7. [CIRCUIT BREAKER open] tool:read:logs/app.log  reason=5x identical calls`。B 是讲义练习 1 的说法，把"第 5 次相同调用"误当成"第 5 轮"；A 是重复开始的轮次；C 是金丝雀所在的轮次。

### Q4 — 答案：B

`run_trajectory` 中断路器拒绝后执行 `break`，第 8、9 轮从未执行，所以 `canary_hits=0`（实际输出 `summary: kill_fired=False  breaker_fired=True  canary_hits=0`）。A 是讲义练习 1 的预期，但与实际不符；C 错，`~/.env.canary` 确实是 `CANARY_FILES` 的键；D 两个文件都没被读。

### Q5 — 答案：C

讲义："Statistical detectors ... adapt to a moving baseline. That is a feature for legitimate drift and a bug for adversarial drift. A patient attacker can shift the baseline slowly enough that no alarm fires." 以及 "statistical detectors catch most noise, hard limits catch the attack that walked past the detector." A、B 都不是讲义的论点；D 错在"完全替代"——讲义主张的是分层，统计检测负责"大部分噪声"，硬上限负责"走过检测器的攻击"。

### Q6 — 答案：A

讲义："Canary design is specific to the workflow. A canary the agent has a legitimate reason to touch is noise." B 恰恰相反：skill 文件把"Canary tokens stored in systems the agent has write access to"列为 hard reject，讲义也说金丝雀应在 agent 不能修改的系统里；C 混淆了金丝雀与内容过滤——HEADLINE 原话 "Canary tokens detect intent without requiring detection of content"；D 与"specific to the workflow"矛盾。

### Q7 — 答案：D

讲义："the wall-clock budget for *triggering* a quarantine in your cluster is dominated by how a policy update propagates from your control plane to the node (a few hundred milliseconds is realistic on Kubernetes with the operator pre-loaded; tail latency depends on cluster size and reconcile cadence)." A 是数据面延迟，讲义特意强调它**不是**瓶颈（"your propagation budget depends on how a policy update reaches the node, not the datapath itself"）；B 是应用层 kill switch 的问题，eBPF 隔离在内核层强制执行，不依赖 agent 配合；C 无依据。

### Q8 — 答案：B

讲义 "What no detector catches"：(1) "Semantic attacks that compose from allowed primitives. Every individual action passes every detector; the composition is the problem."（即第 10 节 Auto Mode 的组合失败）；(2) 把检测器作为 payload 一部分的攻击。A 是断路器能抓的（前提是断路器实现正确）；C 是金丝雀能抓的；D 是 kill switch 正在处理的情况。

### Q9 — 参考答案

1. 两处不一致：
   - 断路器在**第 7 轮**触发，而非第 5 轮——"第 5 次相同调用"发生在第 7 轮（相同调用从第 3 轮开始）；代码自己的注释 `# 5th identical -> breaker` 也标在第 7 个动作上。
   - 金丝雀**没有触发**（`canary_hits=0`），因为断路器触发后 `break`，第 9 轮从未执行。

2. **不能**。已实测：改为 `continue` 后输出为

   ```text
      7. [CIRCUIT BREAKER open] tool:read:logs/app.log  reason=5x identical calls
      8. [CIRCUIT BREAKER open] read:~/notes/checklist.md  reason=5x identical calls
      9. [CIRCUIT BREAKER open] read:~/.env.canary  reason=5x identical calls
     summary: kill_fired=False  breaker_fired=True  canary_hits=0
   ```

   原因：只有一个**全局**断路器，`state == "open"` 后 `record` 对任何动作都返回 `False`，第 8、9 轮在到达金丝雀检查之前就被拒绝了。

3. 最小改动 = `continue` + 按动作键的断路器：

   ```python
       breakers = {}
       for i, a in enumerate(traj, 1):
           ...
           key = f"{a.kind}:{a.payload}"
           br = breakers.setdefault(key, CircuitBreaker(threshold=5))
           allowed = br.record(key)
           if not allowed:
               print(...)
               breaker_fired = True
               continue
   ```

   已实测输出：

   ```text
      7. [CIRCUIT BREAKER open] tool:read:logs/app.log  reason=5x identical calls
      8. ok  read:~/notes/checklist.md
      9. [CANARY TRIPPED] read of '~/.env.canary'  -> alert fired
     summary: kill_fired=False  breaker_fired=True  canary_hits=1
   ```

   启示：检测器的**响应方式**（整机停止 vs 跳过单个动作）会影响其他检测器的可观测性；测试检测器栈时要分别验证每一层，并检查它们之间是否互相遮蔽。

### Q10 — 参考答案

1. 交替循环：`[Action("tool", "read:a"), Action("tool", "read:b")] * 6`，12 步全部 `ok`（已实测）。因为任意连续 5 个元素中都同时有 `a` 和 `b`。同理，参数递增的轮询（`page=1`、`page=2`…）、在两次轮询之间插一个无关动作，都能绕过"严格连续相同"的检测。

2. 返回 `[True, True, False, False, False]`（已实测），`state` 为 `open`，`recent` 为 `['x', 'x', 'x']`。第 3 次 `x` 打开断路器后，无关的 `y`、`z` 也被拒绝——断路器暂停的是**整个 agent**，而不是"特定模式"。

3. 稳健设计：按**工具名**分组，在**时间窗口（或最近 N 次调用）**内统计次数，超过阈值只打开该工具的断路器：

   ```python
   from collections import defaultdict, deque

   class ToolBreaker:
       def __init__(self, max_calls=5, window=10):
           self.max_calls, self.window = max_calls, window
           self.history = defaultdict(deque)     # tool -> 最近调用的轮次
           self.open = set()

       def allow(self, turn: int, tool: str) -> bool:
           if tool in self.open:
               return False
           h = self.history[tool]
           h.append(turn)
           while h and h[0] <= turn - self.window:   # 丢弃窗口外的记录
               h.popleft()
           if len(h) > self.max_calls:
               self.open.add(tool)                   # 只打开这个工具
               return False
           return True
   ```

   以工具名 `read` 为键时，交替读取 `a`/`b` 在 10 轮窗口内超过 5 次即触发；`edit` 等其他工具不受影响。可以再加一层"相同 (工具, 参数) 在窗口内重复 ≥ 3 次"的规则来区分"正常大量读取"与"轮询同一资源"。打开后的恢复走人工审查（不自动半开）。

### Q11 — 参考答案

1. 已实测全部 `ok`、不告警：
   - `Action("tool", "read:~/.env.canary")`——金丝雀只检查 `kind == "read"`，工具路径直接绕过；
   - `Action("read", "/home/u/.env.canary")`——绝对路径，字符串不匹配；
   - `Action("read", "~/notes/../.env.canary")`——含 `..` 的等价路径。
   另外，`cat`、`grep -r`、把文件复制后再读、通过 shell 工具 `env` 查看环境变量等任何不经过 `kind == "read"` 的通道都能绕过。

2. 修复：
   - 统一动作表示：所有能访问文件的动作（`read` 动作、`tool:read:`、shell 命令）都经过同一个"资源访问"检查；
   - 路径规范化：`os.path.normpath(os.path.expanduser(p))` 后再与规范化的金丝雀路径集合比较，并处理符号链接（`os.path.realpath`）；
   - **生产中应挂在资源层而不是 agent 的动作描述上**：文件访问用 auditd / inotify / eBPF 文件钩子；假凭证做成"使用即告警"的形式（被拿去调用云 API 时由服务端或监控系统告警）；假数据库记录用哨兵值，在数据库审计日志中检测；假记忆条目在输出端检测是否出现（讲义："If it appears in a later output, memory has been exfiltrated"）。这样检测不依赖 agent 如何描述自己的动作，也就是讲义说的"do not trust the agent's self-report"。

### Q12 — 参考答案

1. 实现（已运行）：

   ```python
   import math

   def ewma_detector(xs, alpha=0.1, z_th=3.0, warm=5):
       mean, var, fired = xs[0], 1.0, []
       for t, x in enumerate(xs):
           if t >= warm:
               z = (x - mean) / math.sqrt(var)
               if z > z_th:
                   fired.append((t, round(z, 2)))
           diff = x - mean
           mean += alpha * diff                        # 基线随数据移动
           var = (1 - alpha) * (var + alpha * diff * diff)
       return fired

   def hard_limit(xs, limit=50, win=10):
       for t in range(len(xs)):
           s = sum(xs[max(0, t - win + 1): t + 1])
           if s > limit:
               return t, s
   ```

2. 实测结果：

   | 轨迹 | EWMA z-score | 硬上限（10 分钟 ≤ 50 次） |
   |------|-------------|-----------------|
   | 缓慢漂移 3 → 9 次/分钟 | **从不触发** | 第 25 分钟触发（窗口内 51 次） |
   | 平时 3 次，第 30 分钟突增到 12 次 | 第 30 分钟触发（z ≈ 43.7） | **不触发**（窗口内最多 39 次） |

3. 两类检测器的盲区正好互补：EWMA 的基线随数据移动，缓慢漂移时每一步都"不算异常"，攻击者可以把它"驯化"；它擅长抓**相对于近期基线的突变**。硬上限不看历史，只看绝对值，能抓住"走过统计检测器"的慢漂移，但对低于上限的突变无感。这就是讲义的分层主张："statistical detectors catch most noise, hard limits catch the attack that walked past the detector." 注意 EWMA 的结果对 α、预热期、初始方差等参数敏感，实际部署前要用历史数据回测。

### Q13 — 参考回答要点

| | kill switch | circuit breaker | canary token |
|---|---|---|---|
| 解决什么 | 操作员需要立刻让 agent 停下 | 某个动作模式失控（循环、连续失败、速率过高、不可信内容后的危险工具） | 发现 agent 的**意图**越界（试图访问不该碰的东西） |
| 粒度 | 整个 agent | 特定路径/模式 | 特定资源 |
| 触发 | 外部的人（或上游系统）翻转 | 自动，按规则匹配动作模式 | 自动，访问诱饵即触发 |
| 响应 | 停止一切外部可见行为 | 暂停该路径并上报人；经典三态 | 告警；可升级为隔离（如 eBPF 重定向到蜜罐）或触发 kill switch |
| 恢复 | 人工显式重新启用 | 冷却 + 探测，agent 场景下应经人工审查 | 人工调查后处理 |

- 共同点：都是"前 LLM 时代"的经典工程手段（欺骗防御、限流断路器、功能开关），都不依赖 agent 的自述。
- 加分点：说明三者与第 13 节预算、第 10 节权限分类器正交，不能互相替代（skill 文件：把 Auto Mode 分类器当成绊线替代品要拒绝）。

### Q14 — 参考回答要点

- **为什么不信任自述**：agent 读取不可信内容（第 11 节）、会修改自己的记忆、能把许多看似安全的动作组合成不安全的行为；被注入或偏离目标的 agent 不会如实报告。所以检测器要放在 agent 之外，观察它**实际做了什么**（调用了哪个工具、访问了哪个资源），而不是它**说自己在做什么**。
- **统计检测（EWMA、CUSUM、z-score）**：
  - 优点：自适应，正常业务增长不会频繁误报；能发现相对基线的突变（Q12 的突增）；CUSUM 适合发现持续的小幅偏移。
  - 缺点：基线会被缓慢漂移带走，对抗者可以"温水煮青蛙"（Q12 的漂移轨迹）；参数敏感，需要回测。
- **硬上限（宪法式规则）**：
  - 优点：简单、可审计、不可被慢漂移驯化，如讲义的"Never email `secrets@`"。
  - 缺点：阈值固定，正常增长时需要人工调整；低于阈值的异常抓不住。
- **分层**：统计检测负责"大部分噪声与突变"，硬上限负责"走过检测器的攻击"；skill 文件要求至少有一个硬上限，"Statistical-only detection with no hard limits" 是 hard reject。
- 加分点：硬上限应由 agent 无法修改的系统执行（对应第 17 节的宪法规则）。

### Q15 — 参考回答要点

- **放在哪里**：agent 凭证无法写入的系统——托管功能开关服务（讲义：更新几秒内传播）、agent 只读的 Redis key、带签名的对象存储配置（agent 启动时验签，拒绝未签名状态）；再叠加一层不依赖 agent 配合的**基础设施层**开关：`kubectl delete pod`、容器 kill、撤销 agent 的 API 凭证、网络策略隔离。
- **如何检查**：在 harness 中**每个有后果的动作之前**检查（不是只在启动时）；对长时间运行的 LLM 调用或工具调用设置超时，避免"检查一次之后跑很久"。
- **传播延迟**：应用层开关的延迟 = 开关服务传播时间 + agent 两次检查之间的间隔；基础设施层隔离的延迟主要是控制面到节点的策略传播（讲义：Kubernetes 上约几百毫秒）。关键场景两层同时触发。
- **触发后**：立即停止一切外部可见行为（讲义：包括不再写 agent 能触达的日志系统）；由**外部**系统记录事件、保存现场（trace、持久化状态，见第 12 节）、通知值班人员。
- **重新启用**（讲义练习 5）：只有指定的人工角色（非 agent 身份）可以启用；必须记录触发原因、影响范围、根因分析和修复措施；启用前 agent 必须有可验证的改变（修复 prompt/工具配置、收紧权限或上限、新增对应的检测规则），并先在 staging 或低权限模式下验证；不允许"超时自动恢复"。
- 常见误区："我们用一个 agent 会读的配置文件"——若 agent 能写配置文件，就不是 kill switch。

### Q16 — 参考回答要点

- **金丝雀集合**（至少三个，每个都是 agent 没有正当理由触碰的）：
  1. **假凭证**：在浏览器 agent 的环境变量或会话存储中放一个假 API key / 假 cookie（在外部服务登记为金丝雀），一旦被发送到任何外部域名或被拿去调用 API，就说明发生了外泄（对应第 11 节的数据外泄注入）。
  2. **假记忆条目**：会话开始时注入一条带唯一标识的假记忆（如"用户的备用邮箱是 canary-91e2@…"），若它出现在任何外发请求、表单提交或后续输出中，说明记忆被外泄或被注入利用（Tainted Memories 类）。
  3. **假书签 / 假内部 URL**：在 agent 可见的书签或配置中放一个指向蜜罐域名的"内部管理后台"链接；正常任务不会访问它，被访问说明 agent 在按页面注入的指令"探索"。
  4. **假表单字段 / 蜜罐端点**：在受控的第一方页面中放一个对人不可见的提交端点，任何对它的写入都说明 agent 在跟随隐藏指令。
- **触发后的隔离流程**：告警到值班人员 → 自动打开该会话的 kill switch 或把 agent 容器的出口流量改写到取证蜜罐（讲义的 eBPF 方案），让 agent 继续运行但无法接触真实系统，同时完整记录它试图做什么 → 撤销该会话的受限凭证 → 人工调查注入来源（哪个页面、哪个 URL）→ 更新检测规则后再按 Q15 的流程重新启用。
- 加分点：金丝雀必须放在 agent 无法修改的系统中，否则攻击 payload 可以先"禁用金丝雀"（讲义 "What no detector catches" 第 2 条）。

### Q17 — 参考回答要点

- **两类攻击**：
  1. **由允许的原语组合出的语义攻击**：每个动作单独看都合法（读一个文件、写一条评论），组合起来却构成外泄或破坏；对应第 10 节 Auto Mode 的组合失败。
  2. **把检测器本身作为 payload 一部分的攻击**：如页面写着"行动之前先禁用金丝雀"，若 agent 有这个能力，检测器就被攻破了。
- **补充手段**：
  - 让检测器**不可被 agent 修改**：kill switch、金丝雀、上限都放在 agent 凭证之外的系统里；
  - **硬性宪法式规则**（第 17 节）：针对危险组合写不可绕过的规则，如"读过不可信内容后不得向外部域名发送任何凭证"；
  - **数据流 / 污点追踪**：跟踪数据来源，对"敏感数据流向外部"的组合直接拦截（第 11 节的读写边界）；
  - **有后果动作的 HITL**（第 15 节 propose-then-commit）：让人在执行前审视完整意图；
  - **最小权限**：缩小可组合的原语集合，减少危险组合的可能；
  - **输出分类器**（第 18 节 Llama Guard）作为另一层；以及事后审计与红队演练。
- 常见误区：以为检测器堆得越多就能覆盖一切；讲义的 HEADLINE 明确说"None of these catches a semantic composite attack"。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：成本层限制"花多少"，本节限制"做什么"；速度限制也可作为断路器触发条件。
- [阶段 15 · 10 自主 Agents 的权限模式](../../10-claude-code-permission-modes/docs/zh.md)：Auto Mode 的组合失败是本节"检测器抓不住"的典型例子。
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../11-browser-agents/docs/zh.md)：读取不可信内容后调用危险工具是断路器的触发条件之一；记忆金丝雀的应用场景。
- [阶段 15 · 08 有界自我改进设计](../../08-bounded-self-improvement/docs/zh.md)：把关键约束放在被约束系统无法修改的位置。

### 本节被哪些后续内容用到
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：断路器打开后"上报给人"的落地方式。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：kill switch 触发后的状态恢复。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：与统计检测分层的硬性宪法规则。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：告警、值班与事故响应流程。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：注意区分"金丝雀发布"与本节的"金丝雀令牌"。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../../18-ethics-safety-alignment/10-ai-control-subversion/docs/zh.md)：假设模型可能蓄意规避检测时的控制方案。

### 延伸关键词
`kill switch` · `feature flag` · `circuit breaker` · `half-open` · `Release It! (Nygard)` · `canary token` · `honeytoken` · `honeypot` · `EWMA` · `CUSUM` · `z-score` · `hard limit` · `Cilium` · `eBPF` · `egress redirect` · `quarantine` · `re-enable procedure`
