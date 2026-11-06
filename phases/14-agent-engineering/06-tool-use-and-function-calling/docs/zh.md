<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="tool-use-and-function-calling"></a>

# 工具使用与 Function Calling

> Toolex(Schick等人,2023年)开始自我监督工具说明。 Function Calling 领头板V4(Patil等人,2025年)设定2026巴:40% agentic30%的多轮,10%的活,10%的不活,10%的不活 hallucination。单向转换解决了。记忆、动态决策和长方位工具链没有解决。

**类型:** Build
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段13 01 (b)Function Calling 深潜)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释工具前端的自监督训练信号: 仅在执行减少下一个时保留工具说明 。token loss.
- 名字BFCL V4的五张 evaluation 类别和每项措施。
- 实施标准工具登记册,配有计划验证、论证强制和行刑沙箱。
- 诊断2026年的三个未解决的问题:长视距工具链、动态决策和记忆。

<a id="the-problem"></a>

## 问题

早期工具使用请求: 模型能否预测正确的函数调用? 现代工具使用询问: 模型链工具可以包含部分内存, 跨越40个步骤 observability,从工具故障中恢复,而不产生不存在的幻觉工具?

工具前人建立了基准:模型可以学习何时使用自监督工具。 BFCL V4 定义了2026年 evaluation 两者之间的差距在于空间生产 agents 住在这

<a id="the-concept"></a>

## 概念

<a id="toolformer-schick-et-al-neurips-2023"></a>

### Toolex (Schick等人, NeurIPS 2023)

想法:让模型说明它本身 pretraining 与候选文件相匹配 API 调用。 对于每个候选人, 请执行它。 只有包含工具结果才能减少下一个损失 。 token。过滤过的体积精细。

工具覆盖: 计算器、 质量A 系统、 搜索引擎、 翻译、 日历。 自监督信号纯粹是工具是否有助于预测文本, 没有人类标签 。

比例结果: 工具使用在比例上出现。 小模型因工具说明而受伤; 更大模型增益。 这就是为什么2026 个边框模型使用强大的工具, 而大多数 7B 模型需要明确的工具使用 fine-tuning 来保证可靠

<a id="berkeley-function-calling-leaderboard-v4-patil-et-al-icml-2025"></a>

### Berkeley Function Calling 领头板V4(Patil等人,ICML 2025)

英国联邦金融法系2026年的事实上 evaluationV4 构成:

- **Agentic (40%)** - 满 agent 轨迹:内存、多转、动态决定。
- **多发(30%)** 与工具链的交互性对话。
- **活 动(10%)** 用户提交的真实数据 prompts (更硬的分布)。
- **非生活(10%)** 合成试验案例。
- **Hallucination (10%)** - 检查何时不应使用任何工具。

采用基于国家的V3 evaluation:在工具序列之后,检查 API是否与 AST 匹配( 例如“ 文件创建了吗 ” ) tool calls。V4增加了网络搜索、内存和格式敏感性类别。

关键2026发现:单转 function calling 失败集中在记忆(环绕环境)、动态决策(基于先前结果的选择工具)、长方位链(20+步骤后漂移)以及 hallucination 检测( 无法使用工具时重新拨打) 。

<a id="tool-schema"></a>

### 工具图

每个供应商都有一套模式,但细节不同,但形状相同:

```
name: string
description: string (what it does, when to use it)
input_schema: JSON Schema (properties, required, types, enums)
```

Anthropic 使用 `input_schema` directly. OpenAI 使用 `function.parameters`。两者都接受 JSON 示意图。 描述包含载荷, 模型读取它们来选择正确的工具。 错误的工具描述是错误工具选择失败的第1个根源 。

<a id="argument-validation"></a>

### 参数验证

信任没有 tool call验证 :

1. **类型胁迫。** 模型可以返回字符串“ 5 ” , 其形式是: coerce 如果明确; 如果不是的话, 则拒绝 。
2. **测试机** 如果计划说 `status in {"open", "closed"}` 和模型发布 `"in_progress"`,以描述错误拒绝。
3. **需要的字段 。** 缺少所需的字段 - > 立即对模型进行错误观测,而不是崩溃 。
4. **格式验证 。** 日期、电子邮件、 URL—— 使用混凝土解析器验证, 而不是正则 。

每次验证失败都应该返回一个结构化的观察,这样模型就可以以正确的形状重试。

<a id="parallel-tool-calls"></a>

### Parallel tool calls

现代提供者支持平行 tool calls 在一个助手的转弯中。循环 :

1. 模型发布 3 tool calls 具有明显特性 `tool_use_id`s.
2. 运行时执行它们( 如果独立, 平行) 。
3. 每一个结果都回到了 `tool_result` 块关联由 `tool_use_id`.

工程规则: 将相关代号作为载荷处理。 交换它们, 就会错误地使用工具到错误的结果路径 。

<a id="sandboxing"></a>

### Sandboxing

工具执行 sandbox 边界。 详情见 09 课。 短版本: 每个工具都应指定读/ 写表面、 网络访问、 超时、 内存上限 。 `run_shell(cmd)` 是红色的旗帜; 特定 `git_status()` 更安全一点

```figure
tool-routing
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 实施生产形状工具登记册:

- JSON Schema 子验证器( 仅限标准) 。
- 工具注册, 描述、 输入计划、 超时和执行器 。
- 强制辩护和辩驳
- 平行工具发送与相关身份标识。
- 显示为结构字符串时出错 。

运行：

```
python3 code/main.py
```

该 trace 显示一个小型 agent 一次调用三个工具, 一个故意的错误调用, 拒绝使用, 并有一个描述性错误, 模型可以操作。

<a id="use-it"></a>

## 实际应用

每个供应商都有自己的工具计划—— Anthropic, OpenAI, Gemini, Bedrock。使用翻译层(OpenAI Agents SDK, Vercel AI , 电动 SDK, LangChain 工具适配器),如果您需要多提供者。 BFCL 是参考基准, 运行时要对齐 agent 如果工具的使用对产品至关重要,则在运输之前。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-tool-registry.md` 生成工具目录、 系统图和特定任务域的注册。 包括描述质量检查( 每个工具的描述是否告诉模型何时使用?)

<a id="exercises"></a>

## 练习

1. 添加一个“ 不操作” 工具, 让模型明确拒绝使用任何其他工具。 类似 BFCL 的测量 hallucination test.
2. 执行对字符串和浮控字符串的参数强制。 强制从何处开始隐藏真正的错误 ?
3. 添加每个工具的超时和 a circuit breaker (在连续三次失败后,60年代将该工具删除) 这对模型如何恢复有什么变化?
4. 读取 BFCL V4 描述。 选择一个类别( 如“ 多转弯 ” ) , 运行 10 个示例 prompts 穿过你的 agent. 报告通过率。
5. 将标准验证器端到 Pydantic 或 Zod 。 Pydantic/ Zod 发现玩具漏掉了什么?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Function calling | "工具的使用" | 结构化产出工具,使用经验证的系统图 |
| Toolformer | "自监督工具说明" | Schick 2023 - 保留 tool calls 其结果减少下一个...token loss |
| BFCL | "Berkeley Function Calling Leaderboard" | 2026年基准:40% agentic30%的多轮,10%的活,10%的不活,10%的不活 hallucination |
| 工具图 | "模型的职能签名" | 名称、说明、 JSON 辩论的方略 |
| tool_使用_id | "校正编号" | 绑上 tool call 其结果;对平行发送至关重要 |
| Hallucination detection | "知道什么时候不打电话" | V4 类别: 无工具适合时拒绝调用 |
| 强制辩护 | 连环修理 | 精确地修正可预测的计划; 如果模糊的话则拒绝 |
| Sandboxing | "工具处决边界" | 读/写表面、网络、超时、内存上限 |

<a id="further-reading"></a>

## 进一步阅读

- [Schick等人,Tolorex(arXiv:2302.04761)](https://arxiv.org/abs/2302.04761) 自我监督工具说明
- [Berkeley Function Calling 头板(V4)](https://gorilla.cs.berkeley.edu/leaderboard.html) - 2026年评价基准
- [Anthropic工具使用文档](https://platform.claude.com/docs/en/agent-sdk/overview) 生产工具的图案 Claude Agent SDK
- [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/) 函数工具类型 Guardrails
