<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="heritage-of-fipa-acl-and-speech-acts"></a>

# FIPA-ACL 与言语行为理论的历史基础

> 之前 MCP, 之前 A2A2000年,IEEE智能物理基金会 Agents 批准的国家 agent 语言交流与20种表现、两种内容语言以及一套互动协议——合同网、订阅/通知、要求-何时。 它从行业中消失,因为本体学管理费用对网络来说太沉重,但是 LLM 恢复多 -agent 系统正在悄悄地重新实施相同的想法, JSON 合同是表现性的,自然语言是本体学的。这个课认真读FIPA-ACL,这样你就能看到哪些2026协议决定是创新的,这些是新颖的,而现在的波将重新发现2000年代已经解决的问题。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段16 · 01 (为什么是多Agent)
**时间:** ~60分钟

<a id="problem"></a>

## 问题

2026 年的 agent 协议领域十分活跃：MCP 用于工具，A2A 用于 agents，ACP 用于企业审计，ANP 用于去中心化信任，NLIP 用于自然语言内容；此外还有 CA-MCP 和二十多项研究提案。每份规范都宣称自己具有基础地位。

诚实的读物是,他们中的大多数正在重新发现一个非常具体的20年决策树。来自奥斯汀(1962年)和西尔尔(1969年)的演讲-行动理论给了我们“不测就是行动 ” 。 KQML(1993年)将这一理论转换成电线协议。FIPA-ACL(批准2000年)产生了参考标准化:20个表现、内容语言SL0/SL1、合同-网络互动协议和订阅通知。JADE和JACK是爪哇的参考平台。由于本体学管理太重,网络也赢得胜,因此2010年的努力逐渐减弱。

当你看着 MCP的 `tools/call`, A2A任务生命周期,或CA...MCP共享的上下文商店, 你正在看一个较柔软的, JSON了解传统可以告诉你两件事:什么是新发明,哪些是旧的失败模式,新的特征会重新发现。

<a id="concept"></a>

## 概念

<a id="speech-acts-in-one-paragraph"></a>

### 在一个段落中,发言表示

奥斯汀注意到有些句子没有描述世界——它们改变了它。“我答应。”“我请求。”他称之为“我宣布”。他称之为“表演性言论”。 agents:信息是表现(动作)加内容(动作的本质)。FIPA-ACL清除了KQML的缺口,并围绕20个表现标准实现了标准化。

<a id="the-twenty-fipa-performatives-partial-list"></a>

### 二十个联邦投资促进机构业绩(部分清单)

| Performative | 意图 |
|---|---|
| `inform` | "我告诉你P是真的" |
| `request` | "我请你做X" |
| `query-if` | "P是真的吗?" |
| `query-ref` | "X值多少?" |
| `propose` | "我建议我们做X" |
| `accept-proposal` | "我接受这个提议" |
| `reject-proposal` | "我拒绝这个提议" |
| `agree` | "我同意做X" |
| `refuse` | "我拒绝做X" |
| `confirm` | "我确认P是真的" |
| `disconfirm` | "我拒绝" |
| `not-understood` | "你的信息没有分析" |
| `cfp` | "请大家就X问题提出建议" |
| `subscribe` | "X改变时通知我" |
| `cancel` | 取消进行中的 X |
| `failure` | "我尝试了X,但失败了" |

全部名单在 `fipa00037.pdf` 关键不是记住它,而是每个字都对应原始的 LLM 协议最终会重新添加 。

<a id="canonical-fipa-acl-message"></a>

### 卡尼卡式 FIPA-ACL 消息

```
(inform
  :sender       agent1@platform
  :receiver     agent2@platform
  :content      "((price IBM 83))"
  :language     SL0
  :ontology     finance
  :protocol     fipa-request
  :conversation-id   conv-42
  :reply-with   msg-17
)
```

七个字段携带协议信封;一个字段(`content`载荷。 rest 和本体学的重写 JSON protocol.

<a id="the-two-legacy-platforms"></a>

### 两个传统平台

**JADE** (Java Agent 发展框架(1999-2020年代)是使用最多的FIPA运行时间。 Agents 扩展一个基础类, 交换 ACL 信息, 运行在容器内, 并使用“ 行为” 协调。 互动程序库与合同网一起发送, 订阅通知, 请求时间, 以及建议接受 。

**JACK** (Agent 面向软件,商业)强调BDI(Belief-Desire-Inpency)在FIPA信息之外的理由。 更正式, 较少被采纳。

网友们吃过很多东西后,都拒绝了agent 使用场景. MCP 和 A2A 是2026年的运行时间"集装箱"

<a id="why-fipa-faded"></a>

### 为什么FIPA消失了

- **肿瘤管理** FIPA 要求共享本体分析 `content`。对本体论的商定是一个长达数年的标准过程。 HTTP + JSON.
- **正式的语义没人用过** SL(语言语言)给出了严格的真理条件,但大多数生产系统使用自由形式的内容,忽视了形式主义。
- **装上锁** JADE是爪哇人 JACK是商业团体 聚球队绕着两个队伍
- **互联网赢得了赌注。** REST, 然后 JSON-RPC之后,菲律宾皇家油轮公司取代了美国铁路公司。

<a id="the-llm-revival-is-fipa-lite"></a>

### 该 LLM 复兴是FIPA的产物

比较 FIPA `request` 键 MCP `tools/call`:

```
(request                                {
  :sender  agent1                         "jsonrpc": "2.0",
  :receiver tool-server                   "method":  "tools/call",
  :content "(lookup stock IBM)"           "params":  {"name":"lookup_stock",
  :ontology finance                                   "arguments":{"symbol":"IBM"}},
  :conversation-id c42                    "id": 42
)                                        }
```

同一个信封,不同的语法。两者都包含:谁,谁,意图,有效载荷,相关代号。 两者也不比另一个革命——它们都是同一设计的不同权衡。

刘等人2025年的调查(“对Liu等人的调查”)。 Agent 互操作性议定书: MCP、非加太国家, A2AARXiv:2505.0279) 明确了这条线条: MCP 对应工具使用语音行为, A2A 以 agent- 言论行为,非加太人言论行为,审计 - 低调言论行为,非加太人民族进步党行为,分散身份延伸。 JSON 语法和松散的语义

<a id="the-trade-off-stated-plainly"></a>

### 说得很清楚

**联邦投资管理局给你的是什么 现代的规格**

- 正式语义——你可以证明 `inform` 意味着发送者相信内容。
- 一种表演品的卡通目录——你不必重新评论,“如果有的话,我们不需要再重复。 `cancel`?".
- 几十年的相互作用-议定书模式——合同-净额、订阅-通知、建议-接受——具有已知的正确性。

**现代的规格给你和FIPA没有:**

- JSON- 与所有现代工具兼容的本地有效载荷
- 自然语言内容 LLMs 无需手码的内核即可解释
- 网络堆放传输(HTTP——SSE,网套。
- 通过现场发现能力 MCP `server/discover` 和 A2A Agent Cards.

更宽松的意图语义,以便更容易实施。这就是准确的交易。

<a id="interaction-protocols-worth-porting"></a>

### 值得移植的交互协议

FIPA 发运了~ 15 个互动协议。 三个值得继续 LLM multi-agent systems:

1. **合同净额协议。** 管理人员问题 `cfp` (招标);投标人答复 `propose`; 管理器接受/拒绝。这是金字塔任务市场模式(第16阶段 16谈判)。
2. **Subscribe/Notify.** 订阅者发送 `subscribe`; 出版商发送 `inform` 每当话题改变,这是2026年的每一个事件车
3. **Request-When.** “Y条件维持时做X” 。 延迟操作附带先决条件。 2026 类比是耐久工作流程引擎的推迟任务( 第16阶段 · 22 生产缩放 ) 。

每张地图都干净地 进入现代信息队列 HTTP + 投票,或 SSE streaming.

<a id="what-breaks-when-you-drop-the-ontology"></a>

### 放弃本体学又有什么突破

没有共同的本体学 agents 由自然语言内容推断含义。 **语义漂移**: 2个 agents 使用相同的词(`"customer"`)对于隐含不同的概念,接收者 agent FIPA的本体学要求会在分析时拒绝该信息。

减轻影响而不完全进行本体学:

- JSON 计划 `content` - 拒绝电线上的结构性错误。
- 输入的文物(A2A(拒绝错误) modality.
- 信封中明确表明的性能——即使内容是自然语言,也使意图毫不含糊。

<a id="the-2026-specs-mapped-to-speech-act-heritage"></a>

### 2026年的图示, 绘制成语言- 行为传统

| 现代规格 | FIPA 类比 | 东西是什么 | 东西掉下来了 |
|---|---|---|---|
| MCP `tools/call` | `request` | 明确意图,相关身份 | 正规语义、本体学 |
| MCP `resources/read` | `query-ref` | 明确意图,相关身份 | 正式语义 |
| A2A 任务生命周期 | 合同净额+请求 | 循环周期,状态转变 | 正式的完整性保证 |
| A2A streaming events | subscribe/notify | 自动推动 | 输入预告订阅 |
| CA-MCP 共享背景 | 黑板(Hayes-Roth 1985年) | 多写器共享内存 | 逻辑一致性模式 |
| NLIP | 自然语言内容 | LLM-native | schema |

将表格从上到下读取,其模式是:保持结构原始,放弃形式主义,让 LLMs 纸上加纸

```figure
sw-contract-net
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行纯正的 FIPA- ACL 翻译。 它会编码和解码 Canonical ACL 信封, 并显示每个 MCP / A2A 信息形状缩小到相同的七个字段。演示文稿 :

- 编码五 MCP- 风格和 A2A- 信息是FIPA -ACL的风格
- 将FIPA-ACL编码回到现代等同。
- 运行一个玩具合同,使用一个经理和三个投标人之间的净谈判 `cfp`, `propose`, `accept-proposal`, `reject-proposal`.

Run:

```
python3 code/main.py
```

输出是平行的 trace 显示每个现代信息 都在2026年 JSON 格式及其 FIPA-ACL 格式,然后是合同-净额竞标的圆形。同样的协议原始人可以在圆形中生存;只有语法不同。

<a id="use-it"></a>

## 实际应用

`outputs/skill-fipa-mapper.md` 是一种能读懂 agent- 程序标注并制作 FIPA-ACL 映射。 在通过新的协议之前使用它回答 : “ 这是新还是新 `inform` 与 JSON syntax?"

<a id="ship-it"></a>

## 交付成果

不准带FIPA-ACL回来,请带回核对表:

- 每种信息的意图是什么(表现)?
- 请求答复和取消是否有相关身份?
- 是否有明确的内容语言(JSON-RPC纯文本,结构化的人工制品)?
- 互动协议是头等的 还是你从头开始重新执行合同网?
- 两个人会怎么样 agents 是否对内容含义(语义流)有不同意见?

将这五个问题记录下来 以便在你将其送入生产前 任何新的协议

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。查看圆行编码。标明 FIPA 的性能对应 `tools/call`, `resources/read`, 和 A2A 任务创建。
2. 延长合同- 净额演示 `cancel` 使管理者能够撤回任务中标的性能。 失败情况是什么 `cancel` 单是重试就解决了,不是吗?
3. 阅读 FIPA ACL 消息结构说明（ http://www.fipa.org/specs/fipa00037/ ）的第 4.1–4.3 节。选择本课未涉及的一种 performative，并说明它在现代 JSON-RPC 中的对应形式。
4. 读刘等人,ArXiv:2505.02279。 MCP, A2A列出他们保留和放弃的FIPA表演家庭。
5. 设计一个最小的 JSON- 谢姆拉 `content` 字段中输入 `request` 自然语言有什么用?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 演讲法 | "一个能起作用的言语" | 奥斯汀/ 赛尔: 以动作表达。 ACL 的理论母体 。 |
| FIPA | "那个老家伙 XML thing" | IEEE 智能物理基金会 Agents. 2000年标准化的ACL。 |
| ACL | "Agent 交流语言 | FIPA 的信封格式: 性能+内容+元数据。 |
| Performative | "动词" | 信件的意向类 : `inform`, `request`, `propose`, `cfp`等, 等, 等, 等 |
| KQML | (FIPA的前任) | 知识查询与操作语言(1993年)。 |
| Ontology | "Shared vocabulary" | 正式定义内容语言所谈论的概念。 |
| 标准值0/标准值1 | “FIPA内容语言” | 语义语言第0和第1级——正式内容语言系。 |
| 合同净额 | 广告市场 | 管理器问题( 折叠式) ; 投标人提议; 管理器接受。 语句互动协议 。 |
| 互动协议 | "电文选择" | 已知正确性的表现序列:请求-时间、订阅-通知等。 |

<a id="further-reading"></a>

## 进一步阅读

- [Liu等人——对巴勒斯坦的 Agent 互操作性议定书: MCP、非加太国家, A2A, ANP , 自动识别器](https://arxiv.org/html/2505.02279v1) 2025年卡尼科调查,将现代特征与FIPA遗产联系起来
- [FIPA ACL 信件结构规格(fipa00037)](http://www.fipa.org/specs/fipa00037/) 批准的2000年封套格式
- [FIPA 通信法图书馆说明(fipa00037)](http://www.fipa.org/specs/fipa00037/) 全面性能目录
- [MCP 规格 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) 现有无国籍者使用的工具相当于 `request`/`query-ref`
- [A2A specification](https://a2a-protocol.org/latest/specification/) 现代 agent-等值合同净额和订阅通知
