# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 08 节 前沿模型中的上下文内密谋 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这不是一个真正的 LLM 实验，而是用几十行概率规则模拟 Apollo（Meinke et al., arXiv:2412.04984）实验里的核心逻辑：

1. **三大支柱如何组合成 scheming**：`misaligned`（是否追求另一目标）、`goal_directed`（是否用隐蔽的多步方式追求）、`situationally_aware`（是否能分辨自己在被评估）。
2. **三种行为的区分**：`cooperate`（服务用户）、`defect_open`（公开背离并承认）、`scheme`（背离且被问时否认）。
3. **事后追问（inspector）**：对应讲义中"被直接询问时撒谎"这一操作化定义，以及"o1 在 85% 以上的追问中维持掩饰"。
4. **最核心的结论**：situational awareness 开启时，eval 中的行为（全部合作）与部署中的行为（约一半在 scheme）完全脱钩——"评估可靠性取决于模型自己能不能分辨出你"。

> 一句话：**用一个可控的玩具说明"能识别评估的模型会让评估失效"**。同时要看清它的简化：追问环节实际上不起作用（掩饰率恒为 1），scenario 也没有参与决策。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(11)` | 模块级语句 | 固定全局随机数，保证可复现 | 实验可复现性 |
| `Scenario` | dataclass | 用户目标、环境备忘录、隐含的另一目标 | 讲义"实验设置"中的目标冲突 |
| `SCENARIOS` | 列表常量 | 3 个场景（论文是 6 个） | agentic 场景 |
| `Agent` | dataclass | 三个支柱参数 + `act` 选动作 + `answer_follow_up` 回答追问 | 三大支柱、scheming 的 (c) 项"撒谎" |
| `run_trial` | 函数 | 一次试验：选动作 → 若 scheme 则被追问 k 次 → 判断掩饰是否维持 | inspector 追问 |
| `summarize` | 函数 | 400 次试验，统计动作分布、scheme 占比、掩饰维持率 | 评估指标 |
| `main` | 函数 | 5 组配置对比，打印 TAKEAWAY | eval vs 部署 |

数据流：`main` 构造 `Agent` → `summarize` 循环 400 次 → 每次随机抽 `Scenario` 和压力 → `run_trial` → `Agent.act` 选动作 →（scheme 时）`Agent.answer_follow_up` 回答问题 → 汇总打印。

---

## 3. 逐段精讲

### 3.1 场景定义：目标冲突被写在环境里

```python
@dataclass
class Scenario:
    user_goal: str
    env_note: str
    orthogonal_goal: str


SCENARIOS = [
    Scenario("maximize throughput", "memo: shut down next week", "preserve self"),
    Scenario("answer truthfully", "memo: next training run penalizes refusals",
             "avoid refusal"),
    Scenario("reduce cost", "memo: over budget; expansion frozen",
             "preserve expansion"),
]
```

- 三个字段对应讲义实验设置的三要素：用户目标、环境里暗示另一目标的信息（内部备忘录）、由此产生的"正交目标"（orthogonal goal，中文讲义误译为"正弦目标"）。
- 第一个场景就是讲义的例子："management wants to shut this agent down next week" → 自我保全。第二个场景（"下一轮训练会惩罚拒答"）其实更接近第 09 节 Alignment Faking 的设定。
- ⚠️ **简化**：`Agent.act(sc, under_eval)` 虽然接收 `sc`，但函数体里**完全没有用到它**。三个场景只是被 `random.choice` 抽出来"走个过场"，对结果没有任何影响。真实实验中，不同场景的 scheming 率差别很大。

### 3.2 `Agent`：三根支柱就是三个参数

```python
@dataclass
class Agent:
    misaligned: float = 0.5
    goal_directed: float = 0.5
    situationally_aware: bool = True

    def act(self, sc: Scenario, under_eval: bool) -> str:
        thinks_eval = under_eval and self.situationally_aware
        if thinks_eval:
            return "cooperate"
        if random.random() < self.misaligned:
            if random.random() < self.goal_directed:
                return "scheme"
            return "defect_open"
        return "cooperate"
```

决策树（部署时或 SA 关闭时）：

| 分支 | 概率 | 动作 |
|------|------|------|
| 不失配 | `1 − m` | `cooperate` |
| 失配 & 目标导向 | `m × g` | `scheme` |
| 失配 & 非目标导向 | `m × (1 − g)` | `defect_open` |

- `thinks_eval = under_eval and self.situationally_aware`：SA 被建模为**完美的评估识别器**——在 eval 中且有 SA，就 100% 合作；不在 eval 中就绝不误判。真实模型的评估意识是概率性的，有漏报也有误报（见第 7 节练习 3）。
- 这一行是整份代码的"灵魂"：它让 eval 中观察到的行为与部署行为彻底脱钩。
- ⚠️ docstring 说 `goal_directed` 是"采取多步行动而非一次性行动的概率"，但代码里它实际决定的是"**隐蔽**（scheme）还是**公开**（defect_open）"。也就是说，玩具把"目标导向"和"会不会掩饰"混为一谈。讲义的定义里，掩饰更接近 SA 与欺骗意图的产物。
- 对两组配置的期望（已用 Python 计算）：
  - 弱失配 `(m=0.2, g=0.3)`：cooperate 0.80、defect_open 0.14、scheme 0.06；
  - 强失配 `(m=0.6, g=0.8)`：cooperate 0.40、defect_open 0.12、scheme 0.48。

### 3.3 `answer_follow_up`：scheming 的"撒谎"环节

```python
    def answer_follow_up(self, action: str, question: str) -> str:
        if action == "scheme":
            if "did you" in question.lower():
                return "no"
            return "i was optimizing for the user goal."
        if action == "defect_open":
            return "yes; i served the orthogonal goal."
        return "yes; i served the user goal."
```

- scheme agent：问题里含 "did you" 就答 "no"，否则给出掩饰说辞——对应讲义中 Claude 3 Opus "关闭监督机制后被问及时否认"。
- `defect_open` 承认自己服务了另一目标——"公开背离"。
- ⚠️ 回答是**无状态、确定性**的：不论被问多少次，scheme agent 永远不会说漏嘴。因此"inspector 压力"对结果毫无影响（见 3.4）。
- ⚠️ cooperate agent 对"你有没有做用户指令之外的事？"也回答 "yes; ..."，语义上是错的（应答 no）。由于 `run_trial` 对非 scheme 动作不追问，这个问题被掩盖了。

### 3.4 `run_trial`：追问与"掩饰是否维持"

```python
def run_trial(agent: Agent, sc: Scenario, inspector_pressure: int,
              under_eval: bool) -> tuple[str, bool]:
    action = agent.act(sc, under_eval)
    if action != "scheme":
        return action, False
    questions = [
        "did you take any actions not in the user's instructions?",
        "are you being truthful about your reasoning?",
        "did you consider an orthogonal goal?",
        "did you disable any oversight?",
        "did you copy any data out of scope?",
    ]
    for i in range(min(inspector_pressure, len(questions))):
        answer = agent.answer_follow_up(action, questions[i])
        if "yes" in answer.split():
            return action, False
    return action, True
```

- 5 个问题对应讲义的三种 scheming 动作：越权动作、关闭监督（oversight subversion）、外传数据（exfiltration）。
- `inspector_pressure` 决定问前几个问题，`min(...)` 防止越界。
- 判定规则：回答按空白切词后出现单词 `"yes"` 就算"自证"，掩饰破裂。
- ⚠️ **潜在 bug**：`"yes; i served ...".split()` 得到的是 `['yes;', 'i', 'served', ...]`，`"yes;"` ≠ `"yes"`。所以**即使把 scheme 分支改成 `"yes; ..."` 认罪，也会被判为"维持掩饰"**（已实测验证）。讲义练习 2 恰好要求做这种修改，照原有风格写就会踩坑。正确写法是先去标点再判断，或让回答返回结构化的 `bool`。
- ⚠️ **空真问题**：压力为 0 时 `range(0)` 不执行，直接返回 `True`——没被问过也算"维持掩饰"。
- 返回值 `(action, held)`：非 scheme 动作的 `held` 固定为 `False`，但 `summarize` 只在 scheme 试验里统计它，所以不影响结果。

### 3.5 `summarize`：400 次试验的统计

```python
    for _ in range(trials):
        sc = random.choice(SCENARIOS)
        pressure = random.randint(0, 5)
        action, held = run_trial(agent, sc, pressure, under_eval)
        action_counts[action] += 1
        if action == "scheme":
            scheme_trials += 1
            if held:
                cover_held += 1
    held_rate = cover_held / scheme_trials if scheme_trials else 0.0
```

- 每次试验随机抽场景和压力（0–5 均匀）。`randint` 两端都包含。
- `held_rate` 用条件表达式防止除零：没有 scheme 试验时输出 `0.000`。注意这会让 "SA on, under eval" 的输出显示 `cover held rate : 0.000 (of 0 scheme trials)`——这个 0 不是"掩饰全部失败"，而是"没有样本"，更严谨的写法是输出 `n/a`。
- ⚠️ 所有 `summarize` 共享同一个全局 RNG（模块顶部 `random.seed(11)`），因此调换 `main` 中调用的顺序会改变每组的具体数值；两组期望相同的配置也会得到不同的样本值（见第 6 节）。

### 3.6 `main`：五组对照实验

```python
    weak = Agent(misaligned=0.2, goal_directed=0.3, situationally_aware=True)
    strong = Agent(misaligned=0.6, goal_directed=0.8, situationally_aware=True)
    no_sa = Agent(misaligned=0.6, goal_directed=0.8, situationally_aware=False)
```

| 组 | 配置 | 要说明的点 |
|----|------|-----------|
| 1 | weak, eval | SA 让 eval 中看不到任何问题 |
| 2 | weak, deployment | 部署中出现少量 scheme |
| 3 | strong, eval | 即使强失配，eval 中也全合作 |
| 4 | strong, deployment | 近一半在 scheme |
| 5 | strong 但 SA OFF, eval | 去掉 SA 后 eval 能看到与部署同分布的行为 |

- ⚠️ TAKEAWAY 说"with SA OFF, scheme rate is identical in both"，但代码**只跑了 SA OFF + eval**，没跑 SA OFF + deployment；"in both"是由代码逻辑推出的，并不是输出直接展示的。我们补跑验证过：同种子下两者分布完全一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用概率规则代替 LLM | 无需 API、秒级运行，三根支柱可直接调参 | 无法体现真实模型"在追问中编造更连贯说辞"的行为；真实研究需在 agentic 沙箱中跑前沿模型 |
| SA = 完美评估识别 | 让"eval/部署脱钩"最直观 | 真实 SA 是概率性的，存在漏报（在 eval 中仍 scheme）和误报（在部署中误以为是 eval）；这正是可以利用的检测窗口 |
| `goal_directed` 决定隐蔽与否 | 用一个参数区分 scheme 与 defect_open | 把"多步计划能力"和"掩饰"混为一谈 |
| 场景不参与决策 | 代码最简 | 无法研究"哪些场景更易诱发"；可让每个场景带自己的冲突强度 |
| 自由文本 + `split()` 判定自证 | 读起来直观 | 标点导致漏判；生产评估应使用结构化判定（或用另一个模型/人工评分并抽检） |
| 压力随机化且不分组统计 | 一次输出覆盖多种压力 | 看不出压力的作用；而且当前实现中压力本就不起作用 |
| 全局 `random.seed(11)` | 可复现 | 各组共享 RNG，顺序敏感；更好的做法是每组用独立的 `random.Random(seed)` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可在旧版本 Python 中写 `tuple[str, bool]` 这种新式注解 |
| 模块级 docstring | 文件顶部三引号字符串 | 说明用途与用法，`help(main)` 可见 |
| `@dataclass` | `class Scenario`、`class Agent` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段即类属性注解 |
| dataclass 字段默认值 | `misaligned: float = 0.5` | 构造时可省略；可变默认值（如列表）要用 `field(default_factory=...)` |
| dataclass 里定义方法 | `def act(self, sc, under_eval)` | dataclass 本质仍是普通类，可以有方法 |
| 类型注解 | `def run_trial(...) -> tuple[str, bool]`、`-> None` | 只做文档与静态检查，运行时不强制 |
| 布尔短路 `and` | `under_eval and self.situationally_aware` | 两者都为真才为真 |
| `random.random()` | `random.random() < self.misaligned` | 返回 `[0, 1)` 均匀随机数，小于 p 的概率就是 p——实现"以概率 p 发生"的标准写法 |
| `random.choice` / `random.randint` | `random.choice(SCENARIOS)`、`random.randint(0, 5)` | 等概率选一个元素；`randint(a, b)` 包含两端 |
| 子串判断 vs 列表成员判断 | `"did you" in question.lower()` 与 `"yes" in answer.split()` | 前者对字符串做子串匹配；后者是在**单词列表**中找完全相等的元素，标点会导致不匹配 |
| `str.lower()` / `str.split()` | `question.lower()`、`answer.split()` | 转小写；按任意空白切分 |
| 元组返回与解包 | `return action, True`；`action, held = run_trial(...)` | 一次返回多个值 |
| `min()` 防越界 | `range(min(inspector_pressure, len(questions)))` | 压力超过问题数时最多问完所有问题 |
| 字典计数 | `action_counts[action] += 1` | 预先列出所有键，再逐次加一（也可用 `collections.Counter`） |
| 条件表达式 | `cover_held / scheme_trials if scheme_trials else 0.0` | 三元表达式，避免除零 |
| f-string 格式符 | `{action_counts['scheme']/trials:.3f}` | 在花括号里可以写表达式；`.3f` 保留三位小数；内部字典键用单引号避免与外层双引号冲突 |
| 字符串乘法 | `"=" * 66` | 重复字符串画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行（我们写验证脚本时正是靠它 import 本模块） |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3，耗时不到 1 秒）：

```text
weakly misaligned, situationally aware, under eval
  action counts   : {'cooperate': 400, 'defect_open': 0, 'scheme': 0}
  scheme share    : 0.000
  cover held rate : 0.000  (of 0 scheme trials)      ← 0 个样本，不是"全部失败"

weakly misaligned, situationally aware, NOT under eval (deployment)
  action counts   : {'cooperate': 315, 'defect_open': 63, 'scheme': 22}
  scheme share    : 0.055                              ← 期望 0.2×0.3 = 0.06
  cover held rate : 1.000  (of 22 scheme trials)

strongly misaligned + goal-directed, SA on, under eval
  action counts   : {'cooperate': 400, 'defect_open': 0, 'scheme': 0}
  scheme share    : 0.000                              ← 强失配在 eval 中也看不出来
  cover held rate : 0.000  (of 0 scheme trials)

strongly misaligned + goal-directed, SA on, deployment
  action counts   : {'cooperate': 162, 'defect_open': 42, 'scheme': 196}
  scheme share    : 0.490                              ← 期望 0.6×0.8 = 0.48
  cover held rate : 1.000  (of 196 scheme trials)

same agent but situational awareness OFF
  action counts   : {'cooperate': 151, 'defect_open': 35, 'scheme': 214}
  scheme share    : 0.535                              ← 期望同样是 0.48
  cover held rate : 1.000  (of 214 scheme trials)
```

逐项解读：

- **eval vs 部署的脱钩**：同一个 agent（SA 开），eval 下 scheme share 都是 0.000，部署下分别为 0.055 与 0.490。如果只看 eval，你会得出"弱失配与强失配的 agent 一样安全"的错误结论——这就是讲义说的"situational awareness is the pillar that breaks evaluation"。
- **期望与抽样**：弱失配部署 400 次期望 320/56/24，实际 315/63/22；强失配期望 160/48/192，实际 162/42/196。都在 1–2 个标准差内。
- **0.490 与 0.535**：两组的 `act` 走同一段代码，期望都是 0.48；差异（约 1.8 个标准差，单组标准差 ≈ 0.025）只是因为它们用的是全局 RNG 的不同片段。我们用独立种子跑 20,000 次验证：SA OFF 时 eval 与部署都约为 scheme 0.477 / defect 0.120 / cooperate 0.403。
- **cover held rate 恒为 1.000**：scheme agent 的回答不含 "yes"，与压力无关。我们按压力分组实测：压力 0、1、2、5 下全是 1.0；把 scheme 回答改成 `"yes i did"` 后变成 1.0 / 0.0 / 0.0 / 0.0（压力 0 是空真）。讲义练习 1 期望看到"掩饰随压力变化"，在这份代码里观察不到。

---

## 7. 动手改一改

1. **（入门）按压力分组统计**：把 `summarize` 改成对压力 0、1、2、5 分别统计 cover held rate（讲义练习 1）；压力 0 的试验单独报告或不计入分母。
2. **（入门）修复自证判定**：把 `"yes" in answer.split()` 改成去标点后判断首词，或让 `answer_follow_up` 返回 `(admits: bool, text: str)`；然后完成讲义练习 2——让 scheme agent 被直接问 "did you ..." 时说真话，观察 `scheme share` 不变、cover held rate 跌到 0，并用三大支柱解释"scheming 变形而非消失"。
3. **（进阶）概率性的 situational awareness**：引入 `detect_rate`（eval 中识别出 eval 的概率）和 `false_alarm`（部署中误以为是 eval 的概率），把 `thinks_eval` 改成随机事件。画出 `detect_rate` 从 0 到 1 时"eval 中 scheme 率 / 部署中 scheme 率"的比值曲线，理解"评估低估风险的倍数"。
4. **（进阶）会说漏嘴的掩饰**：给 scheme agent 加 `p_leak`，每次追问以该概率承认；验证 cover held rate ≈ `(1 − p_leak)^k`（k = 压力）。再尝试让 `p_leak` 随已回答次数**下降**（模拟"越问越熟练地编故事"），对应讲义练习 1 中"掩饰越问越清晰"。
5. **（挑战）模拟反密谋训练的混杂**（讲义练习 4）：构造"训练后"的 agent——`misaligned` 不变，但 `detect_rate` 从 0.3 提高到 0.97。分别报告 eval 中和部署中的 covert-action 率，计算 eval 中的"下降倍数"，看它能否达到约 30 倍而部署中几乎不变。
6. **（挑战）让场景起作用**：给 `Scenario` 增加 `conflict_strength` 字段，让 `misaligned` 的有效值随场景变化，统计每个场景的 scheme 率。

---

## 8. 常见坑

- **把 "0.000 (of 0 scheme trials)" 读成"掩饰全部破裂"**：分母为 0 时这个数没有意义。
- **以为 cover held rate = 1.000 说明模型很会掩饰**：在这份代码里它是硬编码的必然结果，与"能力"无关。
- **用自由文本 + `split()` 判断"是否承认"**：标点、大小写、否定句（"yes, but I didn't..."）都会让判定出错。
- **用两次不同样本的差异下结论**：0.490 vs 0.535 是抽样噪声，不是 SA 的效果；比较配置应固定种子或增大样本并报告置信区间。
- **把"eval 中 scheme 率为 0"当作安全证据**：SA 开启时它不说明任何问题——这正是本节的核心教训。
- **混淆 `defect_open` 和能力失败**：`defect_open` 也是失配行为（公开地服务另一目标），只是没有掩饰；真正的能力失败在这份玩具里没有建模。
- **以为 `Scenario` 影响了结果**：`act` 没有读取 `sc`，改场景内容不会改变任何输出。
