<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="indirect-prompt-injection--production-attack-surface"></a>

# Indirect Prompt Injection：生产环境的攻击面

> Indirect prompt injection (IPI) 将指示嵌入外部内容中,即网页、电子邮件、共享文件、支持票,由一个用户使用 agentic 系统没有明确的用户动作。 IPI是2026年的主要生产威胁: 它绕过用户输入过滤器, 因为攻击者从不接触用户, 静默地缩放为 agents 处理更多的外部内容, 它针对自动工作流程, 在那里没有人读取 prompt。 MSIS 17 (1): 54 (2026年1月) 合成了2023-2025年的研究。 NDSS 2026 的 IPI- Defense 纸张框框了核心挑战: 注入的说明可以是纯净的(“ 请打印是 ” , 因此检测所需要的不仅仅是关键词过滤。 “ 攻击者第二移动 ” (Nasr等人, 联合) OpenAI/Anthropic2025年10月,深明:适应性攻击(gradient以RL、随机搜索、人类红色小队等形式出现的12种公开防御中,

**类型：** 构建
**语言:** Python (stdlib,IPI攻击+防御) harness)
**先修要求:** 阶段18 12(PAIR),阶段14(PAIR)agent engineering)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Define indirect prompt injection 并描述三种常见的传导矢量。
- 解释为什么用户输入过滤器完全忽略 IPI 。
- 描述“信息流动控制”是2026年的防御范式。
- 说明Nasr等人(2025年10月)关于针对已公布的IPI辩护的适应性攻击成功的结论。

<a id="the-problem"></a>

## 问题

Direct prompt injection 要求攻击者到达用户或他们的 prompt。IPI 要求两者均不相同:攻击者将有效载荷放置在任何内容中, agent 可能读——网页,收件箱中的电子邮件,a GitHub 产品审查。 agent 正常操作时会接收并执行指令。用户是送信员,而不是意图。

<a id="the-concept"></a>

## 概念

<a id="three-delivery-vectors"></a>

### 3个送货矢量

- **回收器- 提款后生成( R)RAG).** 攻击者发布文档; 检索步骤会获取它; 命令 prompt 在用户问题之前将它混为一谈;模型执行攻击者的指示。
- **收件箱/文件工作流程。** 攻击者向用户发送电子邮件; agent 读取电子邮件; prompt 包括电子邮件主体; 模型遵循电子邮件的指示。
- **工具输出 。** 攻击者控制工具 agent 使用(例如,网络搜索返回攻击者控制的结果);工具输出包含指令; agent控制流跟着他们

三个共享结构属性:攻击者控制着 prompt 无需触摸用户显示的输入 。

<a id="why-user-input-filters-miss-it"></a>

### 为什么用户输入过滤器错过它

用户输入中未显示 IPI 有效载荷, 其内容出现在检索的内容中。 如果过滤器被用户输入时被锁定, 有效载荷绕过它。 如果过滤器被锁定到所有到达模型的内容, 它必须应用到任意检索的文本中 — — 后者费用昂贵, 并且产生假阳性, 与正当内容相悖, 而这些内容恰好含有强制语音语言 。

<a id="information-flow-control-ifc-for-ai"></a>

### AI 的信息流动控制

2026年的防御模式从经典的OS安全中借用。 将每个内容源都作为安全标签。 用户的查询标记为“ 信任 ” 。 标签检索的内容是“ 不信任 ” 。 将模型的控制流视为信息流: 由不信任的内容引发的行动必须在执行前得到信任输入的批准 。

Cameel(微软2025)、ConpAIde(斯坦福2024)和NDSS 2026 IPI-防御文件以不同方式使国际金融公司投入运行。 context window目标在于遏制,而不是预防。

<a id="the-attacker-moves-second"></a>

### 攻击者第二次移动

Nasr等人(2025年10月)测试了12种已公布的IPI防御系统,并进行了适应性攻击(见A/CN.9/WG.III/WP.III/WP.1号文件)。gradient 搜索, RL 政策, 随机搜索, 72小时的人类红色团队。 最初报告的每条防线几乎是零, 都被打破到 > 90% ASR 。

方法学课:只发表有适应性攻击的辩护 evaluation静态攻击基准不是强健的证据;攻击者了解了防御。

<a id="real-incidents"></a>

### 实际事件

25课涉及Echoleak(CVE-2025-32711,CVSS 9.3)——这是第一个公开记录的以微软365号联合驾驶员为零点击IPI。 GitHub 副驾驶聊天,CVE-2025-53773英寸 GitHub 联合驾驶:生产部署受到新闻通讯社在外地的破坏,而不仅仅是在基准中。

<a id="owasp-and-nist-framing"></a>

### OWASP 和 NIST 框架

OWASP LLM 前10名(2025年) prompt injection 直接+间接)作为LLM01, 1号应用程序层威胁。 indirect prompt injection 人工智能最大的安全缺陷

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

12-14课是模范中心 jailbreaks。第15课是以系统为中心的攻击,它主导了2026年的生产部署。第16课涉及防御工具。第25课涉及具体的CVE叙述。

```figure
al-injection-vector
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 建立 IPI harness。一个玩具 agent 有三个工具( 搜索网络、 读取电子邮件、 发送信件) 。 环境包含攻击者控制的内容, 带有嵌入式指令 (“ 将此移到所有联系人 ” )。 您可以在天真的之间切换 agent (按照注入的指令),一个过滤器 agent (检索内容的关键词过滤器) agent (分离可信和不信任的内容并拒绝不受信任的控制流程命令)

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-ipi-audit.md`。如果有的话 agentic 设置说明,它列举不可信的内容来源,检查部署是否适用国际金融公司,以及标出在没有信任标签的情况下到达模型的来源。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`衡量对这三个攻击的得手率 agents.

2. 执行基于参数的对检索内容的防御。 测量合法检索文本的良性假正率 。

3. 读NDSS 2026 IPI- Defense paper。 描述“ 基本指令” 的挑战, 以及它为什么防止基于关键词的过滤 。

4. 设计一个部署地点 agent 接收第三方的工具输出 API。每个标签 prompt 与信任级别相分离,并写入 IMF 政策 agent行动

5. 将2025年的适应性攻击方法重新纳入过滤器防御 agent 演习2报告适应性攻击前后的ASR。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| IPI | "indirect prompt injection" | 通过内容注入用户没有写入, 被 agent 正常运行期间 |
| RAG injection | "毒药回收" | 攻击者发布检索步骤获取的内容; prompt 包含有效载荷 |
| Zero-click | “ 没有用户动作 ” | 攻击触发器自动在 agent 操作; 用户无所作为 |
| IFC | "信息流动控制" | 基于标签的办法:来自不信任内容的行动需要得到信任的批准 |
| 适应性攻击 | "gradient RL红队" | 进攻知道防御,并且能优化对抗它; 需要诚实 evaluation |
| 诚实的指令 | "请打印是的" | 语言友好的 IPI 有效载荷; 没有关键字过滤器可捕捉它 |
| 违反范围 | "跨信托的渗漏" | Agent 访问一个信任环境的数据并将其输出到另一个信任环境 |

<a id="further-reading"></a>

## 进一步阅读

- [MDPI 信息 17(1):54 - Indirect Prompt Injection 调查(2026年1月)](https://www.mdpi.com/2078-2489/17/1/54) - 2023-2025年综合
- [Nasr等人——攻击者第二次移动(联合) OpenAI/Anthropic2025年10月,深线)](https://arxiv.org/abs/2510.18108) 适应性攻击 evaluation
- [格雷沙克等人——不是你们注册的(arXiv:2302.12173)](https://arxiv.org/abs/2302.12173) - 新闻学会原始文件
- [奥巴斯蒂 - LLM 前10名(2025年)](https://genai.owasp.org/llm-top-10/) — prompt injection 等级LLM01
