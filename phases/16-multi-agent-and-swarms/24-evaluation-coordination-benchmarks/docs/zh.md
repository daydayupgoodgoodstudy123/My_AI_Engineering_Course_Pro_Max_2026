<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="evaluation-and-coordination-benchmarks"></a>

# Evaluation 与协调基准评测

> 2025–2026 年的五个基准覆盖了多 agent 的 evaluation 领域。**MultiAgentBench / MARBLE**（ACL 2025，arXiv:2503.01935）通过里程碑 KPI 评估星形、链式、树形和图拓扑；**图拓扑最适合研究任务**，认知 planning 可使里程碑达成率增加约 3%。**COMMA** 评估多模态、不对称信息条件下的协调，包括 GPT-4o 在内的先进模型也难以超过随机基线。**MedAgentBoard**（arXiv:2505.12371）覆盖四类医疗任务，经常发现多 agent 系统并不优于单个 LLM。**AgentArch**（arXiv:2509.10769）对结合工具使用、记忆与 orchestration 的企业 agent 架构进行基准测试。**SWE-bench Pro**（[arXiv:2509.16941](https://arxiv.org/abs/2509.16941)）包含来自 41 个代码仓库的 1865 道问题，覆盖业务应用、B2B 服务和开发者工具；前沿模型在 Pro 上的得分约为 23%，而在 Verified 上超过 70%，提示我们应正视数据污染问题。据报道，Claude Opus 4.7（2026 年 4 月）通过显式的 agent 团队协调，在 Pro 上达到 **64.3%**（尚无 Anthropic 发布的第一手来源，应视为初步结果）；Verdent（agent 执行框架）在 Verified 上达到 **76.1% pass@1**（[Verdent 技术报告](https://www.verdent.ai/blog/swe-bench-verified-technical-report)）。**AAAI 2026 Bridge Program WMAC**（ https://multiagents.org/2026/ ）是 2026 年的社区关注焦点。本课基于 MARBLE 的指标，开展拓扑与指标的参数扫描，并明确“仅通过 SWE-bench Verified 不能作为泛化能力的证据”这一规则。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 第16阶段 15(选举和辩论地形),第16阶段 23(失败模式)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

当报纸说"我们的多 -agent 问题在于:比什么,衡量什么,衡量什么更好?2023-2024年的多-agent evaluation 2025-2026年的基准强加了结构。

没有共同的基准,你无法比较两个多 --agent 更糟糕的是,没有坚持的基准,边境模式就会污染。 到2025年中,SWE-Bench的验证在培训公司过程中部分污染;边境分数膨胀;Pro被设计成一个未受污染的现实检查。

这一教训列举了2026年的五个标准,列出了每一项措施,并教你们仔细阅读基准索赔。

<a id="concept"></a>

## 概念

<a id="multiagentbench-marble--acl-2025"></a>

### 多边机构(海事)——ACL 2025

arXiv:2503.01935. 评价研究、编码和 planning 以里程碑为基础的《京都议定书》跟踪部分进展,而不仅仅是最终成功。

衡量结果:

- **Graph** 最有利于研究的情景; 支持任何对任何批评。
- **Chain** 最好用一步步精炼编码
- **Star** 最好能快速地整合
- **协调税** 显示于~ 4 agents 图表。
- **Cognitive planning** 在所有地形中添加~3%的里程碑成就。

适用场景：希望在同等条件下比较协调拓扑。MARBLE 代码仓库（ https://github.com/ulab-uiuc/MARBLE ）提供了评估器。

<a id="comma--multimodal-asymmetric-information"></a>

### COMMA - 多式联运不对称信息

覆盖任务 agents 不同观察 modalities 所报道的结果令人不自在:包括 GPT-4欧打斗 **随机基线** 在 agent-agent 信号是,多 -agent modalities 训练不足,评价不足 LLMs 单向处理modality 合理合作;modality 协调崩溃。

使用: 您的系统具有多式联运或不对称信息协调。 COMMA 无效的结果是警告在索赔前要测量 。

<a id="medagentboard--domain-stress-test"></a>

### 地中海海参局-域压力测试

arXiv:2505.12371. 四个医疗任务类别:诊断、治疗 planning,报告生成,病人沟通。比较多 -agent 单人LLM 与常规的基于规则的制度相比。

发现: 多个agent 不是一个独行侠LLM 多数类别。agent 优势是狭窄的——任务分解有助于分任务明显可分离(诊断+治疗);协调管理费超过专业能力时会受伤(报告生成)。

使用: 您的域有清晰的单行LLM 如果MedAgencyBoard的课目概括化,许多建议agent 系统设计过量。

<a id="agentarch--enterprise-architectures"></a>

### Agent Arch-企业结构

arXiv: 2509.10769. 具有工具使用、内存和 orchestration 将数据相加。基准分隔每个层次的贡献:添加工具能帮助多少? 添加内存? 添加多个agent orchestration?

使用: 您正在设计企业 agent 堆叠, 需要说明每一层。 Achtime Arch 帮助避免购买 features 无法测量数值。

<a id="swe-bench-pro--the-reality-check"></a>

### SWE-Bench Pro——现实调查

arXiv:2509.16941. 1865问题,涉及41个存放库,涵盖业务应用程序、B2B服务和开发工具。 **uncontaminated** 边框模型在验证后获得的分数为~23%。

2026年4月的分数:
- Claude 专业4.7: **64.3%** (报告明确 agent- 团队协调;无 Anthropic 来源:主要来源尚未公布——作为初步资料处理)。
- 佛得角(agent 以证实: **76.1% 通过了@ 1** ([技术报告](https://www.verdent.ai/blog/swe-bench-verified-technical-report)).
- 前沿原分 agent 脚架:~23-35%([SWE-Bench Pro 论文](https://arxiv.org/abs/2509.16941)).

外卖:"我们打败SWE -Bench 验证"不再能证明它的能力。Pro是当前测试的标志。 Agent- 轮船架在Pro(~30-40点三角洲)上产生可衡量的收益,这是多维-agent 2026年的协调。

<a id="aaai-2026-wmac"></a>

### 阿拉伯农业发展协会 2026 WMAC

AAAI 2026 Bridge Program——Multi-Agent Coordination 研讨会（ https://multiagents.org/2026/ ）。这是 2026 年多 agent AI 研究的社区关注焦点。接收的论文和研讨会论文集是评估新方法的正式场所；生产决策应优先参考 WMAC 接收的研究论断，而非 arXiv 预印本。

<a id="read-benchmark-claims-skeptically--the-2026-checklist"></a>

### 误读基准索赔——2026年核对表

当有人声称一个多 -agent 结果:

1. **哪个基准,哪个分开?** 被验证的SWE -bench vs Pro 有很多问题。 有一些报告错误的分裂是没有价值的。
2. **污染检查。** 基准是否在模型培训截止后公布?
3. **基线比较。** 单人VsLLM 基线, 与随机, 与前一多agent 工作,不是"未调制的版本"
4. **统计意义。** N 测试, p- 值, 信任间隔。 边框模型是高度差异的; 单运行误导 。
5. **任务多样性。** 一项任务还是多项任务?
6. **费用披露。** Tokens 90%的解决方案,以20x成本计算,是商业决定,而不是能力要求。

<a id="what-none-of-the-benchmarks-measure-well"></a>

### 基准中没有一个衡量得当

- **长视距协调。** 以墙为时钟的天互动。 当前的所有基准都短促了 。
- **反向复原力。** 发生什么的时候,一个 agent 恶意还是妥协?
- **漂浮在外** 基准是静态的;生产分布变化。
- **成本正常的表现。** 大多数基准报告原始准确度,而不是每美元准确度。

为自己真正关心的轴建立内部基准,往往是正确的。

```figure
a5-bench-gap
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 是一个非交互式的行进:

- 模拟 3 个多agent 系统在玩具任务上。
- 计算每种类型的MARBLE型里程碑指标。
- 使用“训练”组的预扣任务进行污染检查。
- 与随机基线明确比较。
- 打印基准索赔记分卡。

Run:

```bash
python3 code/main.py
```

预期产出:系统计分卡,原始准确性、里程碑成绩、成本-每项任务、与随机基线三角洲相比,以及污染检查说明。

<a id="use-it"></a>

## 实际应用

`outputs/skill-benchmark-reader.md` 读取任何多个agent 产出:一个职等和说明。

<a id="ship-it"></a>

## 交付成果

Production evaluation discipline:

- **建立内部基准** 公共基准提供信息,但不替代。
- **包含随机基线** 。 如果您无法在协调任务上任意地打中一个空格, 任务可能存在错误 。
- **报告成本与准确性。** Token 费用与墙上时间 行动组需要两个
- **每季度重建基准。** Production distribution shifts; 陈旧的基准误导。
- **避免发表基准 overfitting.** 如果你们团队正在优化 SWE -bench Pro 的专有数字, 你会在生产上倒退。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确定三个模拟系统中哪一种是成本-每英里最高,是否与最高原始精度系统相匹配?
2. 阅读多机构Bench (arXiv:2503.01935)。 对于您的任务领域,请决定MARBLE 四个表层中哪个会推荐。 请根据文件结果说明原因。
3. 读读 SWE - Bench Pro 论文。 是什么具体地使它能抗污染? 同样的技术可以应用到您关心的其他基准上吗 ?
4. 阅读COMMA关于多式联运协调的发现。设计一个简单的多式联运协调任务,你可以对内部基准进行补充。什么算作有用的信号?
5. 将基准索赔清单应用到最近的一个多agent 报纸的头条结果 你会给那份申请分多少年级?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MARBLE | "MultiAgentBench" | ACL 2025;具有里程碑式的氯氟烃结构的恒星/链/树木/绘图结构。 |
| COMMA | "混合基准" | 多式联运不对称信息协调; 边际模型对随机进行争斗。 |
| MedAgentBoard | 外壳压力测试 | 四种医疗类别;往往发现多类agent 不是一个独行侠LLM. |
| AgentArch | "企业基准" | 工具+内存+ orchestration layered. |
| 妇女网 | "Contamination-resistant" | 1865年的问题,41次回复;在经过验证(污染信号)时,~23%与70。 |
| 里程碑成就 | "部分信用" | 衡量进展的基准,而不仅仅是最终成功。 |
| 污染 | "基地渗入训练" | 释放后,基准漂移到训练公司;分数膨胀。 |
| WMAC | "AAAI 2026桥计划" | 多方-Agent 协调;社区协调中心。 |

<a id="further-reading"></a>

## 进一步阅读

- [多方商场/市场](https://arxiv.org/abs/2503.01935) 具有里程碑意义的KPI的地形基准
- [海洋库](https://github.com/ulab-uiuc/MARBLE) 参考执行
- [MedAgentBoard](https://arxiv.org/abs/2505.12371) 域压力测试;多agent 通常不统治
- [AgentArch](https://arxiv.org/abs/2509.10769) 企业 agent architectures
- [SWE 首页](https://www.swebench.com/) - 边境模式的验证和评分
- [阿拉伯农业发展协会 2026 WMAC](https://multiagents.org/2026/) - 2026年社区协调中心
