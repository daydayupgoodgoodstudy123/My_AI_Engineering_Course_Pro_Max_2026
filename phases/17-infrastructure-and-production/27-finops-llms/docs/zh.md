<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="finops-for-llms--unit-economics-and-multi-tenant-attribution"></a>

# LLMs 的 FinOps：单位经济性与多租户成本归因

> 传统 FinOps 断开 LLM 支出。 token- 交易,不是资源更新时间。 API 电话是交易,不是资产。prompt design, context window2026年的《手册》在第一天有三个属性层面:每个用户(A/C.5/49/70,第1页)。`user_id`)用于座位定价和扩建,每个任务(`task_id` + `route`产品表面成本和优先顺序,每租户(`tenant_id`单位经济与更新。 token 层 - prompt工具、记忆、反应——一个桶子隐藏。 rate limits 每个租户(2-3x预期高峰,清除429+重试);每日支出上限(1.5-3x合同上限;触发率加紧+警报);在支出Z-score > 4(自动暂停+页面待命)上杀死开关。trace- 开单;最高准确度) sampling-外推、基于模型的分配、事件源头、实时 streaming单位计量:每个解答查询的费用,每个生成的文物的费用——不是美元/兆 tokens。反向标记总是丢失;应请求创建仪器。

**类型:** 学习
**语言:** Python (点定,玩具成本归属模拟器,配有断开器)
**先修要求:** 阶段17 · 13 (Observability阶段17 14(入门)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么传统的 FinOps (标签+级) 中断 LLM 花费并命名三个新的属性维度。
- 计算四个 token 层( 平面)prompt工具、记忆、反应)和为什么单桶账单会隐藏成本。
- 设计一个多租产品的执行梯(用高压开关)
- 选择单位计量(每个解答查询/人工制品的成本),而不是$/M tokens.

<a id="the-problem"></a>

## 问题

你账单上写着四万块 你不知道
- 哪个租户花掉的
- 哪个产品 feature 开车
- 是否有任何个人使用者滥用。
- 是否 prompt bloat, tool calls,或者记忆放大是罪魁祸首。

供应商端的标签和集合装置用于云源(EC2, S3),标记在云中传播到线条项目。 LLM API 电话不自动挂牌,您必须在呼叫站点上贴上用户/任务/租户的标签,并携带。 反向属性总是忽略边缘大小写 。

<a id="the-concept"></a>

## 概念

<a id="three-attribution-dimensions"></a>

### 三个归属层面

**Per-user** (`user_id`:谁在计算什么。驱动座位定价,扩大对话,识别电力用户。

**Per-task** (`task_id` + `route`:哪个产品表面成本是什么。 feature 优先排序,杀人费用features decisions.

**Per-tenant** (`tenant_id`) :哪个客户有利可图。驱动单位经济学、更新定价、分层阈值。

第一天在呼叫站点 3个都乐器 反向反应总是更糟

<a id="four-token-layers"></a>

### Four token layers

| 图层 | 示例 | 占总数百分比的典型 |
|-------|---------|---------------------|
| Prompt | 系统+用户输入 | 40-60% |
| 工具 | 工具调用结果反馈到后面 | 20-40% (agent workloads) |
| 内存 | 先前的对话框/ 检索文件 | 10-30% |
| Response | 模型输出 | 10-30% |

玩耍四人在一起,就让优化变得盲目的。

<a id="enforcement-ladder"></a>

### 执行梯子

1. **Rate limit** 估计最高值2-3。 `Retry-After`. 房客看到摩擦;没有意外账单。

2. **每日支出上限** 合同上限1.5-3x。 rate limit + 提醒客户成功。

3. **杀死开关** 相对于租户基线,支出为 Z -score > 4。自动挂载租户;页面待调用;升级为业务+ CS。

<a id="attribution-patterns"></a>

### 归属模式

- **Tag-and-aggregate**: 标记元数据页眉; 汇总后。 简单; 粗略。
- **遥测加入器**:加入到一起 traces 开帐单 trace 身份证明,最高准确度,成熟的队伍做什么
- **Sampling + 外推法**:样本 5-10%,乘以。对于粗略支出来说,成本效益高;尾巴漏掉。
- **基于模式的分配**:回归到推算成本驱动器。对于没有标记的遗留数据。
- **Event-sourced**:成本作为流中事件(Kafka / Kinesis) 。
- **Real-time streaming**: 仪表板更新秒。

<a id="cost-per-x-is-the-unit-metric"></a>

### 每X单位成本是衡量标准

$/M tokens 产品量度:

- 解决的每张支助票的费用。
- 每件产品的成本。
- 成功者费用 agent task.
- 每用户会议分钟的费用。

成本跟产品结果挂钩 否则优化就无法实现

<a id="cost-attribution-trace-shape"></a>

### 费用归属 trace shape

```
trace_id: abc123
  user_id: u_42
  tenant_id: t_7
  task_id: task_classify_doc
  route: model_haiku
  layers:
    prompt_tokens: 1800
    tool_tokens: 600
    memory_tokens: 400
    response_tokens: 150
  cost_usd: 0.0135
  cached_input: true
  batch: false
```

随时随地发射,储存在数据湖中,每个维度的总和。 observability 堆叠是这里的家

<a id="the-compounded-savings-stack"></a>

### 复合储蓄堆

堆叠: 缓存 +批次+ 路径+网关。 全部四个 :
- 缓存 L2( 17 阶段 14) :~ 10x 便宜的输入 。
- 批量(第17阶段 15: 50%关闭)
- 通往廉价模式(第17阶段 16)的路线:成本降低60%。
- 网关效率(第17阶段 · 19):冗余 + 重试。

最佳的堆叠:~5-10%天真基线。 大多数团队都使用2-3杠杆; 全部四个团队都很少。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 归属层面:每个用户、每个任务、每个租户。
- Four token layers: prompt工具,记忆,反应
- 切换: 花费 Z -score > 4.
- 单位计量:每个已解决查询的费用,而不是美元/元 tokens.
- 堆放优化: 可能~ 5- 10%的基准 。

```figure
i4-spend-ladder
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟多租户 LLM 使用三级执行梯子。 注射一个虐待性租户, 并演示杀机开关。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-finops-plan.md`. 根据产品和规模设计归属图案和执法阶梯。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`以什么Z为起点的火?
2. 设计一个每租户,每任务的成本仪表板。 您首先构建的5个视图是什么 ?
3. 你最大的租户是单位经济负数, 提出三次按客户影响命令的干预。
4. 计算每张已解决的辅助产品票的费用:3M tokens票,~800张/日票, GPT- 5个缓存率
5. 质疑追溯标记是否有效。 什么时候可以接受?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 用户归属 | "用户级费用" | `user_id` 每一个电话都贴上印子 |
| 任务归属 | "feature 成本" | `task_id` + `route` 识别产品表面 |
| 租户归属 | "客户成本" | `tenant_id`; 驱动单位经济学 |
| Four token layers | "成本层" | prompt +工具+内存+响应 |
| Rate limit | "429个警卫" | 在网关上强制执行的租户人均上限 |
| 每日支出上限 | "天花板" 每天在天花板上,我说 | 租赁范围预算,备有警报 |
| 杀死开关 | "auto-pause" | 零分 > 4 触发自动暂停 |
| 解决费用 | “产品单位测量” | 与产品结果挂钩的费用,而不是 tokens |
| 遥测加入器 | "trace-to-billing" | 最高精确归属模式 |
| 堆叠优化 | "cache+batch+route+gateway" | 将节省的金额加在一起,达到~5%-10%的基准 |

<a id="further-reading"></a>

## 进一步阅读

- [FinOps基金会——AI公司概况](https://www.finops.org/wg/finops-for-ai-overview/)
- [FinOps学校——每单元2026年指南的费用](https://finopsschool.com/blog/cost-per-unit/)
- [数字应用 LLM Agent 2026年费用归属](https://www.digitalapplied.com/blog/llm-agent-cost-attribution-guide-production-2026)
- [点五 - 管理 LLMs 以阿苏语写 OpenAI](https://www.pointfive.co/blog/finops-for-ai-economics-of-managed-llms-in-azure-open-ai)
