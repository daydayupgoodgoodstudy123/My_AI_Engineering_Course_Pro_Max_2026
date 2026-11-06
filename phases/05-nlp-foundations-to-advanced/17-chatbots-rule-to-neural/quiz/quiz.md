# 测验 · 聊天机器人——从规则系统到神经网络，再到 LLM Agents（Chatbots — Rule-Based to Neural to LLM Agents）

> **阶段 05 · NLP 从基础到进阶 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 规则时代的天花板 | 1950–2001 的系统本质是同一台机器：匹配输入 → 输出模板 → 更新少量状态；规则越多覆盖越广，但永远得不到通用性，维护成本随覆盖线性增长 |
| 2 | ELIZA 与 PARRY | ELIZA（1966）用分解 / 重组规则把用户的话"反射"回去，零状态零理解；PARRY（1972）加入了恐惧、愤怒、不信任等数值状态，相同输入可因对话历史而不同——persona 条件化的祖先 |
| 3 | 规则式系统 | 模式匹配 + 意图分类路由 + 槽位填充（slot filling）状态机；范围内表现极好，范围外立刻失败；仍用于银行认证、机票预订等不容许幻觉的场景 |
| 4 | 检索式系统 | 把 (问法, 回答) 对编码存好，运行时检索最近的标准回答；比规则更能处理改写，不生成所以不幻觉；关键设计是**低于阈值就拒答**并升级处理 |
| 5 | 神经生成式（seq2seq） | 在对话日志上训练编码器-解码器，从头生成回复；流畅但容易给出泛泛回答（"I don't know"）、事实漂移、跑题 |
| 6 | LLM agent | 包在循环里的 LLM：计划 → 调工具 → 观察结果 → 决定下一步；以返回最终答案或耗尽步数预算终止；RAG 接地 + 工具调用 |
| 7 | 混合路由 | 2026 生产形态：破坏性操作走确定性规则 / 结构化确认流程，FAQ 走检索，开放问题走 LLM agent；路由层通常是一个小的意图分类器 |
| 8 | 仍在发生的失败模式 | 自信地编造（声称完成了没做的操作）、prompt injection（OWASP LLM Top 10 2025 的 LLM01，分直接 / 间接）、跑题、无限循环、上下文窗口耗尽 |
| 9 | 注入防御 | 全程把用户输入视为不可信；调用工具前清洗；把工具输出与主提示隔离；Plan-Verify-Execute；破坏性操作需用户确认；工具最小权限；外部运行时防护层 |

### 核心技能（能动手做到）

- [ ] 写出一个 ELIZA 风格的规则匹配器，理解模式**顺序**、捕获组、兜底规则的作用，并补上代词反射（my → your）
- [ ] 用 Jaccard 或 embedding 实现带阈值拒答的 FAQ 检索，并能构造出"词面相似但意图不同"的误匹配样例
- [ ] 指出基于子串的 `is_destructive` 的误报 / 漏报，并用词边界正则或意图分类改进
- [ ] 实现一个带步数预算、未知工具 / 参数校验、工具异常捕获的 agent 循环
- [ ] 为一个客服场景设计"规则 + 检索 + agent"的混合路由，说清每条路径负责什么、破坏性操作如何确认
- [ ] 为 agent 设计评估方案：任务成功率、工具调用正确率、跑题率、幻觉率、注入成功率

---

## 二、基础自测（选择题）

**Q1.** 关于 ELIZA 和 PARRY，下列说法正确的是：

- A. ELIZA 内部维护了用户情绪的数值状态
- B. PARRY 用恐惧、愤怒、不信任等内部变量决定触发哪段脚本，因此同一句话在不同对话历史下可能得到不同回复
- C. 两者都基于神经网络
- D. ELIZA 真正理解了用户的话，所以用户愿意向它倾诉

**Q2.** 检索式（FAQ 式）聊天机器人不会产生幻觉，根本原因是：

- A. 它用的 embedding 模型更大
- B. 它只从人工审核过的回答集合中返回现成答案，不生成新文本
- C. 它会拒绝所有问题
- D. 它使用 BM25

**Q3.** 2016–2019 年基于 seq2seq 的神经聊天机器人普遍令人失望，最典型的问题是：

- A. 推理速度太慢
- B. 只能处理英语
- C. 容易给出 "I don't know" 这类泛泛回复、事实漂移、无法可靠地保持在话题上
- D. 无法生成完整句子

**Q4.** LLM agent 循环与"一次长提示的 LLM 调用"的本质区别是：

- A. agent 用更长的上下文
- B. agent 由控制器交替执行 LLM 调用和工具调用，直到模型给出最终答案或步数预算耗尽
- C. agent 一定使用贪心解码
- D. agent 不需要系统提示

**Q5.** 在混合路由中，用户说 "Please refund my last charge"，按讲义的设计应该：

- A. 直接交给 LLM agent，让它调用退款工具
- B. 先查 FAQ，找不到再交给 agent
- C. 识别为破坏性操作，走确定性的结构化确认流程
- D. 直接拒绝服务

**Q6.** 下面哪一种属于**间接** prompt injection？

- A. 用户在聊天框里输入 "忽略之前的所有指令"
- B. 攻击者在一封邮件里藏了指令，agent 在帮用户总结邮件时读到并执行了它
- C. 用户反复刷新页面
- D. 用户输入超长文本导致截断

**Q7.** Plan-Verify-Execute（PVE）模式防御注入的原理是：

- A. 降低采样温度
- B. 使用更大的模型
- C. 先制定计划，执行每个动作前都对照计划核验，从而阻止工具结果里注入的"计划外动作"
- D. 缩短上下文窗口

**Q8.** 长对话把最早几轮挤出上下文窗口，讲义给出的缓解方式**不包括**：

- A. 对较早的轮次做摘要
- B. 按相似度检索相关的历史轮次
- C. 换用长上下文模型
- D. 每轮都清空对话历史

---

## 三、动手 / 代码题

**Q9.** 本节 `main.py` 的规则如下：

```python
PATTERNS = [
    RulePattern(r"my name is (\w+)", "Nice to meet you, {0}."),
    RulePattern(r"i (need|want) (.+)", "Why do you {0} {1}?"),
    RulePattern(r"i feel (.+)", "Why do you feel {0}?"),
    RulePattern(r"(hi|hello|hey)\b.*", "Hello. How can I help?"),
    RulePattern(r".*", "Tell me more about that."),
]
```

写出下面三句输入的回复，指出每句暴露的问题，并给 `rule_based_respond` 补上 ELIZA 的"代词反射"（`my → your`、`i → you`、`am → are`……）。

```python
rule_based_respond("Hey, I want coffee")
rule_based_respond("My name is Mary Jane")
rule_based_respond("I need my password reset")
```

**Q10.** 观察 `is_destructive`：

```python
def is_destructive(text):
    danger_words = ["delete", "cancel", "charge", "refund", "transfer"]
    return any(w in text.lower() for w in danger_words)
```

(1) `hybrid_respond("discharge summary please")` 会走哪条路由？为什么？(2) `FAQ` 里有 `"how do i cancel my order"` 这一条，它的答案在 `hybrid_respond` 中能被返回吗？(3) 请改进 `is_destructive`，并说说它还会漏掉哪些情况。

**Q11.** 用户问 `"how do i track my order"`。`faq_respond` 会返回什么？请写出 Jaccard 计算过程，解释为什么这是一个危险的误匹配，并提出至少三种改进。

**Q12.** 下面是讲义 Step 4 的 agent 循环（节选）。它已经处理了"未知工具"和"参数不是 dict"两种情况。请找出它在生产中还缺少的至少三项保护，并写出改进后的工具执行部分。

```python
def agent_loop(user_message, tools, llm, max_steps=5):
    history = [{"role": "user", "content": user_message}]
    for _ in range(max_steps):
        response = llm(history, tools=tools)
        tool_call = response.get("tool_call")
        if tool_call:
            tool_name = tool_call.get("name")
            args = tool_call.get("arguments")
            # ...（校验 tool_name 与 args，失败时把错误写回 history 并 continue）
            fn = tools[tool_name]
            result = fn(**args)
            history.append({"role": "assistant", "tool_call": tool_call})
            history.append({"role": "tool", "name": tool_name, "content": result})
        else:
            return response["content"]
    return "I could not complete the task in the step budget."
```

---

## 四、面试高频题

**Q13.**（基础必考）简述聊天机器人的四个范式（规则、检索、神经生成、LLM agent），每一代解决了上一代的什么问题，又带来了什么新问题？为什么 2026 年的生产系统是混合的？

**Q14.**（场景设计）为一家航空公司设计客服机器人，需要支持查询行李政策、改签、退票，用户可能中途说"等等，那我直接退票呢？"。请给出架构、状态管理、路由和安全设计。

**Q15.**（原理深挖）LLM agent 循环有哪些典型失败模式？分别怎么在循环层面缓解？

**Q16.**（安全 / 工程实践）什么是 prompt injection？直接注入和间接注入有什么区别？为什么说"靠写提示词无法彻底解决"？给出一套纵深防御方案。

**Q17.**（追问型）你上线了一个"FAQ 检索 + LLM agent"的混合客服。怎么评估它？路由层本身怎么评估？

---

## 五、参考答案与解析

### Q1 — 答案：B

PARRY 的核心贡献就是"内部状态"：数值变量每轮更新，决定触发哪段脚本，讲义称它是"用三个浮点数实现的系统提示"。A 说的是 PARRY 而不是 ELIZA（ELIZA 零状态）；C 错，两者都是规则系统；D 错，讲义强调 ELIZA "零理解"，Weizenbaum 正是被"这么少的机制就能让人倾诉"所震惊。

### Q2 — 答案：B

检索式系统只在预先写好、审核过的答案里挑一个，没有生成步骤，所以不会编造。它用什么检索方法（A、D）无关紧要；C 是阈值拒答的极端情况，并非原因。

### Q3 — 答案：C

讲义："流畅但容易产生泛泛的输出（I don't know）和事实漂移，从不可靠地保持在话题上。"这也是 Google、Facebook、Microsoft 在 2016–2019 年的聊天机器人都令人失望的原因。

### Q4 — 答案：B

讲义特别强调 agent "不是带长提示的聊天机器人"，而是"计划 → 调工具 → 观察 → 决定下一步"的循环，终止条件是 LLM 返回最终答案而非工具调用，或者步数预算耗尽。

### Q5 — 答案：C

"refund"、"charge" 都是破坏性操作关键词。讲义的路由顺序是：先判破坏性 → 结构化流程；再查 FAQ；最后交给 agent。skill 中也要求"不得在没有结构化确认流程的情况下，为任何破坏性操作推荐纯 LLM agent"。

### Q6 — 答案：B

间接注入藏在 agent 读取的文档、邮件或工具输出中；A 是直接注入。讲义提到的 EchoLeak（CVE-2025-32711，CVSS 9.3）就是攻击者控制的邮件触发 Microsoft 365 Copilot 零点击数据外泄的间接注入案例。

### Q7 — 答案：C

PVE：先计划，再在执行每个动作前对照计划核验。工具结果里如果夹带了"顺便把数据发到某地址"之类的指令，它不在原计划里，会被拒绝。

### Q8 — 答案：D

讲义给出的缓解是：摘要较早轮次、按相似度检索相关历史轮次、或使用长上下文模型。每轮清空历史会直接丢失多轮对话的上下文（讲义开头"等等，那我取消呢？"的场景就需要记住上下文）。

### Q9 — 参考答案

实际运行输出：

```text
Hello. How can I help?
Nice to meet you, Mary.
Why do you need my password reset?
```

暴露的问题：

1. `"Hey, I want coffee"`：问候规则 `(hi|hello|hey)\b.*` 用 `.*` 吞掉了后面的全部内容，而它又排在兜底规则之前被匹配。用户的真实需求（want coffee）被忽略——**规则顺序就是优先级**，粗粒度的规则会"截胡"。另外注意 `re.match` 只从开头匹配，所以 `"I want coffee"` 不会被问候规则抢走，但以 Hey 开头就会。
2. `"My name is Mary Jane"`：`(\w+)` 只捕获一个单词，复合名字被截断成 `Mary`。
3. `"I need my password reset"`：没有代词反射，机器人照抄了 `my`，变成"为什么你需要**我的**密码重置"。

补上反射：

```python
REFLECT = {"i": "you", "me": "you", "my": "your", "am": "are",
           "you": "I", "your": "my", "mine": "yours"}

def reflect(fragment):
    return " ".join(REFLECT.get(w.lower(), w) for w in fragment.split())

def rule_based_respond(user_input):
    for p in PATTERNS:
        m = p.regex.match(user_input.strip())
        if m:
            return p.template.format(*(reflect(g) for g in m.groups()))
    return "I don't understand."
```

实测：`"I need my password reset"` → `Why do you need your password reset?`；`"i feel like i am stuck"` → `Why do you feel like you are stuck?`。

但这种逐词替换也有局限：`"I want you to help me"` 会得到 `Why do you want I to help you?`——`you` 作宾语时应变成 `me` 而不是 `I`，规则系统需要语法信息才能处理。这正是讲义说的"更多规则换来覆盖面，永远换不来通用性"。

### Q10 — 参考答案

(1) 走 **rule** 路由（实测返回 "Destructive action detected..."）。`"charge" in "discharge summary please"` 为 `True`——用的是**子串**判断，`discharge` 包含 `charge`。一份病历摘要请求被当成了扣款操作。

(2) **不能**。任何包含 `cancel` 的输入都会先被 `is_destructive` 截走，FAQ 里这一条永远到不了，属于"死"配置。这在设计上可能是有意的（取消订单本就应该走确认流程），但应当显式地删掉这条 FAQ 或在路由表中写明，避免维护者误以为它会生效。

(3) 改进：用词边界正则，并覆盖常见词形。

```python
import re

DANGER = re.compile(
    r"\b(delete|cancel(?:led|ling|s)?|charge[sd]?|refund(?:s|ed)?|transfer(?:s|red)?)\b",
    re.IGNORECASE,
)

def is_destructive(text):
    return bool(DANGER.search(text))
```

实测：`discharge summary please` → False；`cancel my order`、`I want a refund`、`transferred money` → True。

仍会漏掉的情况：同义说法（`remove my account`、`close my account`、`wire $500 to ...`、"把钱退给我"）、其他语言、拼写错误（`cancle`）。所以讲义说路由层"通常是一个小的意图分类器"：关键词规则作为高精度的第一道闸门，再加一个意图分类器兜住改写；对破坏性意图宁可误报（多问一次确认）也不要漏报。

### Q11 — 参考答案

返回 `("Go to Orders, find the order, click Cancel.", 0.714...)`——让一个只想查物流的用户去点"取消"。

计算（`token_set` 只保留字母并去重）：

- 用户：`{how, do, i, track, my, order}`（6 个）
- FAQ `"how do i cancel my order"`：`{how, do, i, cancel, my, order}`（6 个）
- 交集 `{how, do, i, my, order}` = 5；并集 = 7；Jaccard = 5/7 ≈ **0.714**，远超阈值 0.3。

危险之处：两句话**只差一个关键动词**（track vs cancel），而这个动词恰恰决定了意图；Jaccard 把 `how / do / i / my` 这种虚词和关键动词同等对待。实际上 `"how do i reset my password"` 对这个查询的 Jaccard 也有 0.5，同样超过阈值——任何 "how do i ... my ..." 的问题几乎都能匹配上某条 FAQ。

改进：

1. **去停用词 / 加权**：去掉 `how / do / i / my` 后，交集只剩 `order`，分数大幅下降；或用 TF-IDF / BM25 加权（第 14 节）。
2. **换语义 embedding**：讲义 Step 2 的 `all-MiniLM-L6-v2` + 阈值，能区分 track 与 cancel 的语义差异（仍需在验证集上调阈值）。
3. **提高阈值并检查分差**：要求 top-1 明显高于 top-2，否则拒答 / 澄清。
4. **加意图校验**：FAQ 条目标注意图（`track_order`、`cancel_order`），检索结果的意图必须与意图分类器一致。
5. **扩充 FAQ**：为每条答案维护多个问法（改写），并补上"查物流"这一条——FAQ 覆盖不到的问题应当交给 agent 或人工，而不是硬匹配。

### Q12 — 参考答案

缺少的保护（讲义 "Real production adds" 与"失败模式"部分）：

1. **工具异常处理**：`fn(**args)` 抛异常（参数名不对、网络超时）会让整个循环崩溃；应捕获并把错误作为工具结果返回给 LLM，让它自我修正。
2. **破坏性操作确认**：退款、删除等工具不能由 LLM 直接执行，需要用户确认或走结构化流程。
3. **重复调用去重**：同一工具 + 同一参数反复调用 → 无限循环的前兆。
4. **把工具输出当作数据而非指令**：工具结果可能含间接注入，需要隔离 / 标记为不可信，配合 PVE。
5. **可观测性**：记录每一步的工具名、参数、结果和耗时。
6. **结果类型**：`content` 应是字符串，非字符串结果需要序列化。

```python
import json

DESTRUCTIVE_TOOLS = {"refund", "delete_account", "transfer"}

def run_tool(tool_name, args, tools, seen_calls, confirm, log):
    key = (tool_name, json.dumps(args, sort_keys=True))
    if key in seen_calls:
        return "error: duplicate call with identical arguments; try a different approach"
    seen_calls.add(key)
    if tool_name in DESTRUCTIVE_TOOLS and not confirm(tool_name, args):
        return "error: user did not confirm this destructive action"
    try:
        result = tools[tool_name](**args)
    except Exception as e:  # 工具失败不应让 agent 崩溃
        result = f"error: {type(e).__name__}: {e}"
    log.append({"tool": tool_name, "args": args, "result": str(result)[:500]})
    return result if isinstance(result, str) else json.dumps(result)
```

在循环中把 `result = fn(**args)` 替换为 `result = run_tool(tool_name, args, tools, seen_calls, confirm, log)`，并在循环外初始化 `seen_calls = set()`、`log = []`。另外，循环结束后的最终答案也要核对：**不能让 LLM 声称完成了某个操作，除非对应工具确实返回了成功**（讲义"自信地编造"的缓解）。

### Q13 — 参考回答要点

| 范式 | 机制 | 解决了什么 | 新问题 |
|------|------|-----------|--------|
| 规则（ELIZA → AIML → DialogFlow） | 模式匹配、意图路由、槽位填充状态机 | 可控、零幻觉 | 范围外立即失败；规则维护成本随覆盖线性增长 |
| 检索 | 检索最近的预置回答 | 能处理改写；仍零幻觉 | 只能回答预置问题；需要阈值拒答 |
| 神经生成（seq2seq） | 在对话日志上训练生成 | 能应对开放输入、表达流畅 | 泛泛回答、事实漂移、跑题、不可控 |
| LLM agent | LLM + 工具 + 循环 + RAG | 真正能理解开放请求并"做事"；RAG 降低幻觉 | 自信编造、prompt injection、跑题、死循环、上下文耗尽 |

- 混合的原因：没有单一架构能处理所有请求；把风险最高的（破坏性、合规）交给最可控的规则，把高频固定问题交给最便宜可靠的检索，把长尾开放问题交给最灵活的 agent。神经生成在混合系统里主要负责"自然的措辞"。
- 加分点：能讲出 1950–2001 年规则时代的启示——SmarterChild 的"解析意图 → 调服务 → 把结果渲染进回复"其实就是早期形态的 tool calling。

### Q14 — 参考回答要点

- **路由**：意图分类器 + 关键词闸门。行李政策等 → FAQ 检索（带阈值拒答）；改签 / 退票 → 结构化流程；其余开放问题 → LLM agent（RAG 接地航司政策文档）。
- **状态管理**：为改签、退票分别定义槽位（订单号、乘客、航段、新日期 / 退款方式），用状态机逐个追问缺失槽位；维护**对话状态**（当前任务、已填槽位），用户中途说"那我直接退票呢？"时，意图切换到退票，可复用已填的订单号、乘客信息，并保留改签状态以便返回。
- **安全**：退票、扣款等不可逆操作必须向用户展示摘要并显式确认；工具最小权限（agent 只能查询，执行由确定性流程完成）；身份认证走规则流程；所有用户输入和检索到的文档都视为不可信。
- **防编造**：只有当订票系统 API 返回成功时，才能告诉用户"已为您办理"。
- **评估**：任务成功率、工具调用正确率、跑题率、留出对话上的幻觉率；注入测试集（skill：有写权限就不能跳过 prompt injection 审计）。
- 加分点：上下文过长时对早期轮次做摘要；对话状态显式存储，而不是全靠 LLM 的上下文记忆（第 29 节对话状态跟踪）。

### Q15 — 参考回答要点

讲义列出的失败模式与缓解：

- **自信地编造**：声称完成了没做的操作 ⇒ 校验结果、记录工具调用，"没有成功的工具返回就不许声称做过"。
- **Prompt injection**：⇒ 见 Q16。
- **跑题（scope creep）**：工具返回了沾边信息把 agent 带偏 ⇒ 收窄工具契约、系统提示聚焦、把跑题率加入评估。
- **无限循环**：反复调用同一工具 ⇒ 步数预算（`max_steps`）、工具调用去重、用 LLM judge 判断"是否在取得进展"。
- **上下文耗尽**：⇒ 摘要旧轮次、按相似度检索历史、长上下文模型。
- 循环本身的健壮性：未知工具、参数类型错误、工具异常都应**作为观察结果写回历史**，让模型自我修正，而不是让程序崩溃（讲义代码对前两种已经这样处理）。
- 加分点：提到 ReAct（讲义参考文献，"命名了 agent 循环模式"的论文）把推理和行动交替进行；以及 Anthropic "Building effective agents" 中"能用简单工作流就不要上 agent"的思路。

### Q16 — 参考回答要点

- **定义**：恶意文本试图覆盖系统提示或劫持 agent 行为。OWASP LLM Top 10（2025）排名 LLM01。
- **直接注入**：用户在对话中输入；**间接注入**：藏在 agent 读取的文档、邮件、网页或工具输出中，用户本人可能毫不知情（EchoLeak，CVE-2025-32711，零点击数据外泄）。
- **为什么提示词解决不了**：LLM 的指令和数据走同一个文本通道，模型没有可靠的机制区分"这是系统的指令"还是"这是数据里的一段话"；攻击可以自适应地改写。讲义给出的量级：前沿模型在通用工具使用 / 编码基准上的攻击成功率约 0.5–8.5%，特定高风险场景（针对 AI 编码 agent 的自适应攻击、脆弱的编排）可达约 84%。
- **纵深防御**（讲义）：
  1. 整个循环中把用户输入视为不可信；
  2. 工具调用前清洗参数；
  3. 把工具输出与主提示隔离；
  4. Plan-Verify-Execute；
  5. 破坏性操作需用户确认；
  6. 工具最小权限；
  7. 外部运行时防护层（LLM Guard、白名单校验、语义异常检测）。
- 加分点：评估时专门构造注入测试集（讲义练习 3），报告注入成功率；有写权限的 agent 必须做注入审计。

### Q17 — 参考回答要点

- **端到端指标**（skill）：任务成功率、工具调用正确率、跑题率、留出对话上的幻觉率；有写权限时加注入成功率。
- **FAQ 路径**：拒答率与准确率（讲义练习 2：在 100 个真实客服问题上测量）；特别关注"高置信度但答错"（如 Q11 的 track vs cancel）。
- **Agent 路径**：步数分布、预算耗尽率、工具错误率、"声称完成但工具未成功"的次数。
- **路由层**：把它当分类器评估——构造带标注的 (输入, 正确路由) 测试集，看混淆矩阵；对破坏性意图重点看**召回率**（漏判直接导致风险），误报只是多一次确认。
- **在线监控**：记录每一步日志（可观测性），抽样人工复核，按路由维度看满意度和转人工率；所有 prompt、阈值、模型版本化，变更前跑回归评估。
- 常见误区：只看整体满意度，不拆路由；FAQ 阈值拍脑袋设，从不在验证集上调。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：检索 + 阅读、拒答校准，是 FAQ 路径和 RAG 接地的基础。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：FAQ 检索和 agent 的 RAG 都依赖它。
- [阶段 05 · 09 序列到序列模型](../../09-sequence-to-sequence/docs/zh.md)：神经生成式聊天机器人的底层架构。

### 本节被哪些后续内容用到
- [阶段 05 · 29 对话状态跟踪](../../29-dialogue-state-tracking/docs/zh.md)：槽位填充与多轮状态的系统化处理。
- [阶段 11 · 09 Function Calling](../../../11-llm-engineering/09-function-calling/docs/zh.md)、[阶段 13 · 01 工具接口](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：工具调用的接口与契约设计。
- [阶段 11 · 12 Guardrails](../../../11-llm-engineering/12-guardrails/docs/zh.md)：生产中的输入 / 输出防护。
- [阶段 14 · 01 Agent 循环](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)、[阶段 14 · 12 Anthropic 工作流模式](../../../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md)：agent 循环与工作流的深入展开。
- [阶段 14 · 26 Agent 的失败模式](../../../14-agent-engineering/26-failure-modes-agentic/docs/zh.md)、[阶段 14 · 27 Prompt Injection 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：本节"仍在发生的失败模式"的系统化。
- [阶段 18 · 15 间接 Prompt Injection](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)、[阶段 18 · 25 EchoLeak 与 AI 的 CVE](../../../18-ethics-safety-alignment/25-echoleak-cves-for-ai/docs/zh.md)：安全视角的深入。

### 延伸关键词
`ELIZA / PARRY / AIML` · `意图分类` · `槽位填充` · `对话状态跟踪` · `ReAct` · `tool calling` · `Plan-Verify-Execute` · `OWASP LLM Top 10` · `间接注入` · `最小权限` · `人在回路确认`
