<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="permission-modes-for-autonomous-agents"></a>

# 自主 Agents 的权限模式

> 获得许可的阶梯——从审查到每项行动、批准到逐步自治——是如何实现以下目标的: harness 管理什么是自主 agent 可能不用问就做 Claude 代码,这个课程的实用例子, 揭示了六种模式: 每次动作前都问“计划”, “默认”(UI中贴上“手动”标签)只问风险, “接受”自动批准文件写道, 但仍然确认空壳执行, 而“通过访问” 则批准一切。 `auto` 允许模式——用单独的分类模型取代每次行动的核准,该模型在每项行动运行之前审查,并阻止任何超出要求的升级。 `max_turns` 和 `max_budget_usd`. Availability 的 `auto` 取决于计划、工程、模型和提供者——以及 Anthropic 表明分类者本身是不够的。

**类型:** 学习
**语言:** Python (stdlib, 两阶段分类模拟器)
**先修要求:** 阶段15 · 01(长-长 agents),第15阶段 □09(编目-agent landscape)
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

自主 coding agent 攻击表面是所有 agent 能够到达文件系统、网络、证书、剪贴板、浏览器标签、任何打开的终端。 Bruce Schneier和其他人已经公开标记了这一点:计算机使用 agents 并非是...feature 最新聊天室的更新, 这是一种新型工具, 具有一种新的风险简介。

Claude 代码的许可系统是 Anthropic答案。 不是一个“ 自动/ 非自主” 开关, 共有六个模式跨越一个能力梯子: 计划 默认 接受 ...  绕行任务 。 每个模式在速度和审查- 每一次行动之间是不同的权衡。 自动模式 ( 2026 年3月) 添加了一个单独的分类模式, 将批准从用户的关键路径上移动 : 它在运行前审查每个动作, 并阻止任何超出请求范围的行动 。

工程问题:这个系统能抓住什么,它错过了什么, 一项特定任务需要哪种模式?

<a id="the-concept"></a>

## 概念

<a id="the-six-permission-modes"></a>

### 六个权限模式

| 模式 | 行为 | 何时使用 |
|---|---|---|
| `plan` | Agent 提出计划;用户批准整个计划;在实施之前对每项行动进行审查 | 不明身份任务; 近似代码; 首次使用 agent 在一个回购 |
| `default` | 标签"手册"在UI。 Agent 运行动作; prompts 用于任何“风险”行动的用户(Shell操作、破坏性操作、网络呼叫) | 大部分交互式编码会话 |
| `acceptEdits` | 文件写入自动批准; shell exec 和网络呼叫 prompt | 重构通过许多文件 |
| `auto` | 单独分类模型在运行前审查每个动作; 阻止任何超出请求范围的行动 | 在有限的工作空间中运行长方位 |
| `dontAsk` | 绝不 prompts; 拒绝未经许可规则预先批准的行动 | Ephemeral sandboxes,CI的工作,研究脚本 |
| `bypassPermissions` | 批准一切 | 记录为"只存在于短暂的容器里 你愿意扔掉" |

(名称在公开匹配上) Claude 代码文档; 界面标签 `default` 以“手动”为名)

<a id="auto-mode-in-one-page"></a>

### 自动模式, 在一个页面中

自动模式( 启动于 2026 年 3 月 24 日) 是将每次行动批准权授予模型的第一个允许模式。 结构 :

1. **单独的分类模型。** 检查每起行动启动前的每个建议,根据宣布的任务和会议现状来判断,并阻止超出要求范围的任何升级。 被阻止的行动会落在用户身上。
2. **Gated availability.** 是否 `auto` 提供这种服务取决于计划、组织能力、模式和提供者。

预算控制与分类程序并列:

- `max_turns` 届会的全套重复。
- `max_budget_usd` 美元上限,这让会议中断了
- 每个工具的动作计数限制( 不超过 N) `WebFetch` 电话等)

<a id="what-the-system-catches"></a>

### 系统能捕捉到什么

- Straightforward prompt injection 输入工具输入,输入指令映射到已知危险动作形状。
- 重复工具循环—— 分类器可以看到动作 N+1 几乎与动作 N 相同, 连续五次 。
- 显然,Shell命令在其它仅使用文件编辑的会话中。

<a id="what-the-system-can-miss"></a>

### 系统会错过什么

- **Subtle prompt injection** 来调节行为,而不产生一个单一的标记动作。 Indirect prompt injection 并非完全可弥补的脆弱性(第1条)。OpenAI 2025年,在浏览器上 agents 见第十一条课。
- **语义层面的错误行为。** 每一个动作在组成轨迹有害时都看上去安全。 分类者判断该动作; 它不会重新塑造用户的意图 。
- **透过合法渠道渗出** 将数据写入您自己的文件 `git push`向公共回购,是一系列允许的行动,其构成是问题所在。

<a id="research-preview-framing"></a>

### 研究预览框架

Anthropic 将自动模式作为研究预览发送。文档明确显示分类器是一个层,而不是一个解决方案:用户预计将将自动模式与预算、允许列表、孤立的工作空间和轨迹审计(Lessons 12-16)结合起来。预览框架还反映了文件记录的内容。 evaluation- 部署差距(课程1)——在用户背景模糊的真实会议上,通过在线电子估价的分类者行为可能不同。

<a id="where-this-ladder-lives-in-your-workflow"></a>

### 这条梯子在你工作流程中的位置

- 不熟悉的任务: 开始于 `plan`阅读计划比拖后腿便宜
- 已知的重构 : `acceptEdits` 节省了许多确认点击。
- 未注意的背景运行 : `auto` 仅在您测量到的爆炸半径的工作空间内(没有证书,没有生产挂载,没有你没有选择进入的反射)。
- 短时间容器: `dontAsk` / `bypassPermissions` 如果并且只有在容器及其证书是可一次性的时,才能接受。

```figure
autonomy-oversight
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟行动审查分类为两阶段管道——教学简化; `auto` 模式由单独的分类模型支持,而不是有文件记录的两阶段合同。 第一阶段是相对于拟议行动的一种廉价的关键词规则; 第二阶段是慢速的多规则审查器。 驱动程序以一个简短的合成轨迹( 安全动作, a) 输入 prompt- 注射尝试,重复循环) 并显示分类者在哪里捕获 和它错过的地方。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-permission-mode-picker.md` 匹配任务描述到正确的允许模式、预算上限和所需的隔离。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。哪个合成动作类型从未被第一阶段标记过,但总是被第二阶段所捕捉?谁被两者都捕捉了?

2. 扩大第一阶段的规则,以捕捉特定的已知坏形状(例如: `curl $ATTACKER/exfil`测量良性行动样本中的假阳性率。

3. Read Anthropic意思是"怎样" agent loop 列出每个外部状态 agent 默认切换 `default` 模式。在运行前,需要分别打开 `auto` unattended?

4. 设计一个24小时无人看管的预算: `max_turns`, `max_budget_usd`,每个工具盖,允许列表。

5. 描述一个路径,其中每个动作都得到分类者的批准,但组成行为却不吻合。 (第14条涉及如何杀死开关和金丝雀。 tokens ) (处理此事。 )

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 权限模式 | "多少钱 agent 能够" | 6项指定政策之一,控制每项行动的核准 |
| 计划模式 | "先问" | Agent 写入计划; 执行前用户批准 |
| acceptEdits | "让它写文件" | 文件写入自动批准; shell exec 仍然 prompts |
| auto | 自动批准 | 单立分类模型审查每项行动;阻止超出要求的升级 |
| bypassPermissions | "欢乐的悠闲" | 核准一切;原为短集装箱 |
| 第一阶段(模拟器) | "快速关键字检查" | 适用于拟议行动的低价规则 `code/main.py` |
| 第二阶段(模拟器) | "深入审查" | 减缓多规则审查器,以审查已标定的在 `code/main.py` |
| 研究预览 | "不是GA" (GA) (GA) | Anthropic 设计 features 正在绘制失败模式 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic - 怎么样 agent loop works](https://code.claude.com/docs/en/agent-sdk/agent-loop) 许可模式、预算、行动格式。
- [Anthropic — Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) - 管理下服务执行模式。
- [Anthropic — Claude 代码产品页](https://www.anthropic.com/product/claude-code) — feature 表面和自动模式声明。
- [Anthropic — Claude《宪法》(2026年1月)](https://www.anthropic.com/news/claudes-constitution) 影响分类判断的基于理性的层。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 内部对长视距许可设计的看法。
