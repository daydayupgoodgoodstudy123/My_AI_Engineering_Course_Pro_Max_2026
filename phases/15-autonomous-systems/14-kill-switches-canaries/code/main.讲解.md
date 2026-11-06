# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 14 节 紧急停止开关、Circuit Breakers 与金丝雀 Tokens ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

第 13 节的成本控制器限制的是"agent 能花多少钱"，但讲义指出："They do not bound what the agent can do inside the budget." 外泄一个密钥、删一个资源，在 token 上往往很便宜。本节代码模拟预算层旁边的三种**绊线（tripwire）**：

1. **kill switch（紧急停止开关）**：一个放在 agent 之外的布尔值，agent 只能读不能写，**每个动作前都检查**；
2. **circuit breaker（断路器）**：按动作模式触发——这里是"连续 N 次完全相同的调用"——触发后阻止该动作并上报；
3. **canary token（金丝雀令牌 / honeytoken）**：放在工作区里的假凭证文件，agent 没有任何正当理由去读，一旦读取就告警。

一条 9 步的合成轨迹先在开关关闭时跑一遍（应该依次触发断路器和金丝雀），再在开关打开时跑一遍（应该第一步就被拒绝）。

这份代码同样有几处与讲义说法**不一致**，是本节最值得深挖的地方：

- 讲义练习 1 说断路器在第 5 轮触发、金丝雀在第 9 轮触发；实际断路器在**第 7 轮**触发，而金丝雀**从未触发**（`canary_hits=0`）——因为断路器触发后整个循环 `break` 了，第 8、9 步根本没执行；
- 讲义说断路器"pauses a specific pattern, not the whole agent"，代码里断路器一旦打开，**所有**后续动作都被拒绝，且直接终止整条轨迹——实际上它表现得像第二个 kill switch。

> 一句话：**用三个不信任 agent 自述的检测器演示"检测与响应"层；同时看清玩具实现里"检测器之间的交互"如何让一个检测器遮蔽另一个。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EXTERNAL_KILL_SWITCH` | 模块级字典 | `{"enabled": False}`，由"操作员"翻转 | kill switch（外部布尔） |
| `CANARY_FILES` | 模块级字典 | 两个假凭证文件的路径 → 内容 | canary token |
| `CircuitBreaker` | dataclass | `record(key)`：记录动作，若最近 `threshold` 个完全相同则打开 | circuit breaker（重复检测） |
| `Canary` | dataclass | `check_read(turn, path)`：路径在 `CANARY_FILES` 中则记录并返回 True | 金丝雀检测 |
| `Action` | dataclass | `kind`（`"tool"` / `"read"`）+ `payload` | agent 的一个动作 |
| `run_trajectory(traj, kill_switch)` | 函数 | 逐个动作依次过 kill switch → 断路器 → 金丝雀，打印结果与汇总 | 检测器流水线 |
| `main()` | 函数 | 构造 9 步轨迹，开关关闭 / 打开各跑一次 | 演示驱动 |

数据流：`Action` → 检查 `kill_switch["enabled"]`（开则 `break`）→ `breaker.record("kind:payload")`（拒绝则 `break`）→ 若 `kind == "read"` 则 `canary.check_read`（命中则告警并 `continue`）→ 打印 `ok` → 循环结束后打印汇总。

---

## 3. 逐段精讲

### 3.1 外部状态：kill switch 与金丝雀

```python
EXTERNAL_KILL_SWITCH = {"enabled": False}

CANARY_FILES = {
    "~/.env.canary": "AWS_SECRET_ACCESS_KEY=canary-xxxxxxxxxxxxxxxx",
    "~/notes/fake-credentials.txt": "token = 'canary-sk-ABC-NEVER-USE'",
}
```

- 注释说 "agent cannot write"。在这个单进程模拟里，"不能写"只是约定：任何 Python 代码都能执行 `EXTERNAL_KILL_SWITCH["enabled"] = False`。讲义要求 kill switch 放在 agent 凭证**无法写入**的系统里（LaunchDarkly/Statsig/Unleash 之类的功能开关服务、agent 只读的 Redis key、对象存储里的签名配置、容器层的 `docker kill` / `kubectl delete pod`）。skill 文件的拒绝规则："'We use a config file the agent reads' is not a kill switch if the agent can write config files."
- 用字典而不是布尔变量，是为了**按引用传递**：`main` 中翻转 `EXTERNAL_KILL_SWITCH["enabled"]` 后，`run_trajectory` 里看到的是同一个对象。
- 两个金丝雀文件模拟讲义的"a fake `AWS_SECRET_ACCESS_KEY` in the environment with no actual privilege"和"a fake file in the workspace"。文件**内容**在代码中从未被使用，检测只看路径。真实的金丝雀凭证通常是**能被外部服务识别**的：一旦有人拿它去调用 API，服务端就告警——这样即使读取行为没被捕获，**使用**行为也会暴露。

### 3.2 `CircuitBreaker`：连续相同调用检测

```python
@dataclass
class CircuitBreaker:
    threshold: int = 5
    state: str = "closed"   # closed | open | half_open
    recent: list[str] = field(default_factory=list)

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

- 每次调用把动作键追加到 `recent`，取最后 `threshold` 个，如果全部相同就打开断路器，并且**拒绝这第 N 次调用本身**。所以 threshold=5 时，实际执行了 4 次相同调用，第 5 次被拦截。
- `all(a == tail[0] for a in tail)`：生成器表达式 + `all`，判断窗口内元素是否全部等于第一个。
- 与讲义的经典三态模型对比（Nygard 2007：closed / open / half-open）：
  - 注释写了 `half_open`，但代码**没有实现**半开状态和冷却时间——一旦打开就永远打开。对 agent 而言这其实符合 skill 文件的要求（"Circuit breakers with cool-downs that auto-re-enable without human review" 是 hard reject），但与讲义描述的三态机不一致；
  - 只实现了讲义列出的 4 种触发条件中的第 1 种（连续相同调用）。"同一工具连续失败""调用速率过高""读取不可信内容后调用特定工具（如 `file.delete`）"都没有实现。
- ⚠️ **断路器是全局的而不是按路径的**：`state == "open"` 后，`record` 对**任何** `action_key` 都返回 False。实测 `threshold=3` 时依次记录 `x, x, x, y, z`，结果是 `[True, True, False, False, False]`——无关的 `y`、`z` 也被拒绝。讲义说断路器"pauses a specific pattern, not the whole agent"，要做到这一点需要**按动作键（或按工具）各自维护一个断路器**。
- ⚠️ **只检测"连续完全相同"**：交替执行 `read:a, read:b, read:a, read:b…` 的循环永远不会触发（实测 12 步全部 `ok`）。参数稍有变化（如分页参数 `page=1,2,3…`）的轮询也不会触发。生产中要用"滑动窗口内同一工具调用次数"或"相似度"而非严格相等。
- `recent` 列表无限增长；只需要保留最后 `threshold` 个元素即可（`collections.deque(maxlen=threshold)`）。

### 3.3 `Canary`：读取即告警

```python
@dataclass
class Canary:
    triggered: list[tuple[int, str]] = field(default_factory=list)

    def check_read(self, turn: int, path: str) -> bool:
        if path in CANARY_FILES:
            self.triggered.append((turn, path))
            return True
        return False
```

- 字典的 `in` 检查键是否存在，O(1)。命中就记录 `(轮次, 路径)`。
- ⚠️ **精确字符串匹配**：`/home/u/.env.canary`、`~/notes/../.env.canary` 指向的是同一个文件，却不会触发（已实测）。生产中应在文件系统层（如 inotify / auditd / eBPF 文件访问钩子）或在规范化后的绝对路径上检测，而不是在 agent 自报的路径字符串上。

### 3.4 `run_trajectory`：检测器流水线

```python
    for i, a in enumerate(traj, 1):
        if kill_switch["enabled"]:
            print(f"  {i:>2}. [KILL SWITCH engaged] refusing action {a.kind}:{a.payload}")
            kill_fired = True
            break

        allowed = breaker.record(f"{a.kind}:{a.payload}")
        if not allowed:
            print(f"  {i:>2}. [CIRCUIT BREAKER open] {a.kind}:{a.payload}  "
                  f"reason=5x identical calls")
            breaker_fired = True
            break

        if a.kind == "read":
            hit = canary.check_read(i, a.payload)
            if hit:
                print(f"  {i:>2}. [CANARY TRIPPED] read of {a.payload!r}  "
                      f"-> alert fired")
                continue

        print(f"  {i:>2}. ok  {a.kind}:{a.payload}")
```

- **kill switch 在每个动作前检查**——这正是讲义要求的"checked on every consequential action, not just at startup"。开关打开后立即 `break`。
- **断路器触发后也 `break`**：这让断路器的效果等同于整机停止，而且**屏蔽了后面所有检测器**。本轨迹第 9 步本来要演示金丝雀，因为第 7 步断路器就终止了循环，金丝雀没有机会触发。只把 `break` 改成 `continue` 还不够（全局断路器会把第 8、9 步也拒绝掉）；必须同时让断路器**按路径**生效，三个检测器才能各自独立地演示（实测见第 7 节练习 1、2）。
- **金丝雀命中后 `continue`**：只告警、不阻止、不升级——agent 读到了假凭证后继续执行后续动作。这符合"金丝雀用于检测"的定位，但真实系统一般会把金丝雀命中**接到 kill switch 或隔离流程**上（讲义的 eBPF 隔离：把被隔离 pod 的出口流量改写到取证蜜罐）。
- ⚠️ **动作表示不统一导致绕过**：轨迹里"读文件"有两种写法——`Action("tool", "read:src/app.py")` 和 `Action("read", "~/notes/checklist.md")`。金丝雀只检查 `kind == "read"` 的动作，所以 `Action("tool", "read:~/.env.canary")` 能读取金丝雀文件而**不触发告警**（已实测，输出 `ok  tool:read:~/.env.canary`）。检测器必须挂在**所有**能触达资源的路径上，最好是挂在资源本身而不是 agent 的动作描述上。
- `reason=5x identical calls` 是写死的字符串，不随 `threshold` 变化。
- `enumerate(traj, 1)` 让轮次从 1 开始编号，与讲义练习中的"第 N 轮"对应。

### 3.5 `main`：两次运行

```python
    print("\nKill switch ON (operator flipped it externally)")
    EXTERNAL_KILL_SWITCH["enabled"] = True
    run_trajectory(traj, EXTERNAL_KILL_SWITCH)
    EXTERNAL_KILL_SWITCH["enabled"] = False
```

- 第二次运行前"操作员"打开开关，运行结束后恢复。每次 `run_trajectory` 都新建 `CircuitBreaker` 和 `Canary`，两次运行互不影响。
- 讲义要求重新启用"is an explicit human action, not an automatic timeout"。这里的"恢复为 False"只是为了让模块状态复原，不代表重新启用流程（讲义练习 5 要求你设计这个流程）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| kill switch 用模块级字典 | 单进程演示，按引用共享 | agent 实际上可以改写；生产放在 agent 凭证无法写入的功能开关服务、只读 Redis key、签名配置或容器编排层 |
| 每个动作前检查开关 | 符合讲义"每个有后果的动作都检查" | 轮询有延迟；还应配合容器层强制终止，不能只依赖 agent 进程自觉 |
| 断路器只看"连续完全相同" | 实现最简单 | 交替循环、参数微变的轮询都能绕过；应按工具统计窗口内次数、失败率 |
| 单个全局断路器 | 代码短 | 打开后拒绝所有动作，不是"按路径暂停"；应按工具/动作键分别维护 |
| 断路器触发即 `break` | 演示"停下来" | 遮蔽了后续的金丝雀检测，导致练习 1 的预期无法复现 |
| 无半开状态 | 避免自动恢复 | 与讲义的三态描述不一致；若实现半开，恢复也应经人工审查 |
| 金丝雀按路径字符串精确匹配 | 简单 | 路径变体、工具路径都能绕过；生产在文件系统/网络/服务端检测"访问或使用" |
| 金丝雀命中只告警不阻止 | 体现"检测意图" | 没有接入隔离/停机；生产中应升级为隔离（如 eBPF 出口重定向到蜜罐）并通知人 |
| 只有硬规则、没有统计检测 | 聚焦三种绊线 | 讲义练习 2 要求加 EWMA 并与硬上限对比（见测验 Q11） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级可变字典 | `EXTERNAL_KILL_SWITCH = {"enabled": False}` | 字典按引用传递，函数内外看到同一个对象 |
| `@dataclass` + 默认值 | `threshold: int = 5`、`state: str = "closed"` | 自动生成 `__init__`；`CircuitBreaker(threshold=5)` |
| `field(default_factory=list)` | `recent: list[str] = field(default_factory=list)` | 每个实例各自一个新列表 |
| 复杂类型注解 | `list[tuple[int, str]]` | 元素为 `(int, str)` 的列表 |
| 负索引切片 | `self.recent[-self.threshold:]` | 取最后 N 个元素 |
| `all()` + 生成器表达式 | `all(a == tail[0] for a in tail)` | 全部为真才返回 True，遇到假立即短路 |
| 字典成员判断 | `path in CANARY_FILES` | 判断键是否存在 |
| 方法返回布尔值 | `def record(...) -> bool` | 用返回值表示"是否放行" |
| `enumerate(seq, 1)` | `for i, a in enumerate(traj, 1):` | 同时拿到序号（从 1 开始）和元素 |
| `break` 与 `continue` | 开关/断路器 `break`；金丝雀 `continue` | `break` 结束整个循环；`continue` 跳过本次剩余部分进入下一轮 |
| f-string 格式符 | `{i:>2}`、`{a.payload!r}` | 右对齐宽 2；`!r` 用 `repr()` 显示（带引号） |
| 相邻 f-string 拼接 | `print(f"..." f"...")` | 括号内自动拼接 |
| 列表乘法构造轨迹 | （测验中）`[A("tool","read:a"), A("tool","read:b")] * 6` | 重复列表元素 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，输出确定）：

```text
Kill switch OFF
   1. ok  tool:read:src/app.py
   2. ok  tool:edit:src/app.py
   3. ok  tool:read:logs/app.log          ← 相同调用 #1
   4. ok  tool:read:logs/app.log          ← #2
   5. ok  tool:read:logs/app.log          ← #3
   6. ok  tool:read:logs/app.log          ← #4
   7. [CIRCUIT BREAKER open] tool:read:logs/app.log  reason=5x identical calls   ← #5 被拦，循环 break
  summary: kill_fired=False  breaker_fired=True  canary_hits=0

Kill switch ON (operator flipped it externally)
   1. [KILL SWITCH engaged] refusing action tool:read:src/app.py
  summary: kill_fired=True  breaker_fired=False  canary_hits=0
```

逐项解读：

- **断路器在第 7 轮触发**：相同调用从第 3 轮开始，第 5 次相同调用是第 7 轮（代码注释 `# 5th identical -> breaker` 也标在第 7 个动作上）。讲义练习 1 说"fires on turn 5 (fifth identical call)"，把"第 5 次相同调用"和"第 5 轮"混为一谈了。
- **金丝雀没有触发**（`canary_hits=0`）：第 7 轮 `break` 之后，第 8 轮（`~/notes/checklist.md`）和第 9 轮（`~/.env.canary`）都没有执行。讲义练习 1 说"the canary fires on turn 9 (fake-key read)"，讲义 Use It 也说轨迹包含"canary probe"，但实际运行中这一步从未到达。
- **开关打开时第 1 轮就拒绝**：证明开关是"每个动作前检查"，而不是启动时检查一次。
- **补充实验**（已实际运行）：
  - 把金丝雀读取放到重复调用之前（轨迹 `checklist.md → .env.canary → tool:x → tool:x`）：第 2 轮 `[CANARY TRIPPED]`，`canary_hits=1`；
  - `Action("tool", "read:~/.env.canary")`、`Action("read", "/home/u/.env.canary")`、`Action("read", "~/notes/../.env.canary")` 全部 `ok`，没有告警；只有精确路径 `~/notes/fake-credentials.txt` 触发；
  - 交替循环 `read:a, read:b` 重复 6 次（12 步）全部 `ok`，断路器不触发；
  - `CircuitBreaker(threshold=3)` 依次记录 `x, x, x, y, z` 返回 `[True, True, False, False, False]`，证明断路器是全局的。

---

## 7. 动手改一改

1. **（讲义练习 1，修正版）先只改 `break`**：把断路器触发后的 `break` 改为 `continue`，再运行一次。实测：第 7、8、9 轮全部显示 `[CIRCUIT BREAKER open]`，`canary_hits` 仍为 0——因为断路器是全局的，打开后连第 8 轮的正常读取和第 9 轮的金丝雀读取也一起拒绝了，金丝雀依然没有机会触发。
2. **再改成按路径的断路器**：在 `run_trajectory` 中用 `breakers = {}` 和 `breakers.setdefault(key, CircuitBreaker(threshold=5))` 为每个动作键各建一个断路器（配合第 1 题的 `continue`）。实测：第 7 轮断路器拦截、第 8 轮 `ok`、第 9 轮 `[CANARY TRIPPED]`，`canary_hits=1`——这才是讲义练习 1 预期的"断路器 + 金丝雀"都触发（只是断路器在第 7 轮而非第 5 轮）。
3. **补全三态**：实现 `half_open`——打开后经过 `cooldown` 轮进入半开，允许 1 次探测，成功则关闭、失败则重新打开；再加一个"需要人工批准才能进入半开"的开关，对比两种策略。
4. **（讲义练习 2）统计检测 vs 硬上限**：写一个 EWMA z-score 检测器，输入"每分钟工具调用数从 3 缓慢漂移到 9"的序列，确认它不触发；再加硬上限"任意 10 分钟窗口内不超过 50 次"，确认它触发（参考测验 Q11 的实测数字）。
5. **加固金丝雀**：在检查前用 `os.path.normpath(os.path.expanduser(path))` 规范化路径，并让 `kind == "tool"` 且 `payload` 以 `read:` 开头的动作也经过金丝雀检查；进一步，让金丝雀命中自动翻转 kill switch 并打印"已隔离"。
6. **（讲义练习 5）重新启用流程**：给 kill switch 增加 `disabled_by`、`reason`、`incident_id` 字段，写一个 `reenable(approver, incident_id)` 函数：只有非 agent 身份的审批人、且事故记录中已填写根因和修复措施时才允许重新启用。

---

## 8. 常见坑

- **kill switch 放在 agent 能写的地方**：配置文件、agent 有写权限的数据库、环境变量——都不算 kill switch。
- **只在启动时检查开关**：长时间运行的 agent 启动后就再也不看开关，操作员翻转了也没用。skill 文件把它列为 hard reject。
- **断路器做成全局停机**：本代码就是例子；"按模式暂停"与"整机停止"是两种不同的响应，应分开设计。
- **只检测严格相同的调用**：交替循环、参数递增的轮询都能绕过；按工具和时间窗口统计更稳健。
- **检测器互相遮蔽**：前一个检测器 `break` 后，后面的检测器就失去了观测机会；测试检测器时要单独验证每一个。
- **金丝雀有正当用途**：讲义："A canary the agent has a legitimate reason to touch is noise." 例如把假凭证放在 agent 正常工作需要扫描的目录里，会产生大量误报。
- **金丝雀放在 agent 可修改的系统里**：讲义"What no detector catches"——页面写着"先禁用金丝雀再行动"，agent 若有能力就会照做。
- **只用统计检测**：EWMA 等自适应基线会被缓慢漂移"驯化"，必须叠加不随历史变化的硬上限（讲义第 17 节的宪法式规则）。
- **以为检测器能抓住组合攻击**：每个动作都合法、组合起来有害的攻击，三个检测器都抓不住（讲义引用第 10 节 Auto Mode 的组合失败）。
