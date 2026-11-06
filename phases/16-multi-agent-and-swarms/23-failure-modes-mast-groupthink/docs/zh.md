<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="failure-modes--mast-groupthink-monoculture-cascading-errors"></a>

# 失效模式：MAST、群体思维、同质化与级联错误

> 2026年的参考分类法是 **MAST** (Cemri等人,NeurIPS 2025,arXiv:2503.13657),源自1642年的处决 traces 7个最先进的开放源码MAS显示 **41-86.7%的失败率**三个根类别: **具体问题** (41.77%)——角色模糊不清,任务定义不明确; **协调失败** (36.94%)——通讯中断,州通信; **核查差距** 质量检查。 **Groupthink** 家庭(arXiv:2508.5687)加上:单一栽培崩溃(同样的基本模型_相关故障)、合规偏差(agents reinforce 重复:在支付失败引发订单重置的暴风雨中,触发库存重整,从而压倒库存服务(10x秒后负荷-需要) circuit breakers内存中毒:一 agent的 hallucination 进入共享内存, 下游 agents 把它当作事实; 精确度逐渐衰减, 使根的原因诊断痛苦。 **STRATUS** (NeurIPS 2025)报告 1.5x通过专门检测/诊断/验证,减缓成功改进 agents。这一课将故障模式作为一流工程目标。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 第16阶段 13(共有记忆),第16阶段 14(共识和BFT),第16阶段 15(辩论和辩论地形)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

Multi-agent 系统在实际任务上失败的时间为41-86.7%(Cemri等人,2025年在7个开放源码MAS中测量到这一点)。 agents失败有结构性原因。MAST分类方法给了您分类。 这个课程将每个类别绘制成一个具体的检测、诊断和缓解模式, 这样数字就不再显得任意了。

2026年的生产实践是将故障模式作为设计投入。 您的建筑不够好, 直到您能够指向每个 MAST 类别并命名您使用的缓解 。

<a id="concept"></a>

## 概念

<a id="mast-categories"></a>

### MAST 类别

**具体问题(41.77%的失败)。** 该 agent任务定义不够严格。 例如 :

- 作用模糊性:二 agents 都认为他们是审查者
- 任务未说明:当用户想要特定角度时, “ 概括一下” 。
- 成功标准隐含: agent 无法显示是否成功 。

Mitigations:
- 写明角色合同 agent的 prompt 说明它的作用 *以及它所不做的事,*.
- 每项任务接受测试。 agent 开始,定义"看起来像X。"
- 飞行前检查: 单独 agent 在发送前先审查任务定义。

**协调失败(36.94%)。** 通讯或国家崩溃。

示例:
- Two agents 更新共享状态, 不同步 。
- 信件在 agents (排队失败,超时)
- 状态漂移 : agent 认为任务已经完成; agent B还在执行中

Mitigations:
- 版本共享状态, 乐观的同价货币 。
- 明确承认关键信息(在锁定前尝试)
- 定期状态同步 checkpoints; 检测早期漂移。

**核实差距(21.30%)。** 没有独立检查产出。

示例:
- One agent 索赔成功;没有人核实。
- 链 agents 每个人相信前一输出。
- 测试覆盖缺失 新生构成的行为。

Mitigations:
- 独立核查员 agent (教训13). 仅读、独立源访问。
- Explicit handoff 合同:"A的输出必须在B开始之前通过C检查。"
- 进行热后分析的结果记录。

<a id="groupthink-family-arxiv250805687"></a>

### 集体思维家庭(arXiv:2508.5687)

五个相关的失败 agents 相互同质或模仿:

**单产业崩溃** 相同的基准模型或训练数据  相关错误。 当 3 agents 共享 a LLM,他们分享它 hallucinations.

**合规性偏差。** Agents 适应最吵或最自信的对等点,即使错误的时候。

**缺乏运动力** Agents 未能树立彼此信仰的榜样;协调不力(Lesson 18)。

**混合运动动力** Agents 部分的刺激措施 向妥协的中间方向转移, 这没人能满足。

**连锁可靠性故障** 一个部件的错误模式触发了附属部件的错误模式。

<a id="cascading-example--the-retry-storm"></a>

### 连锁例子——重试风暴

典型的2026事件模式:

```
payment service fails 10% of requests
   ↓
order agent retries payment (exponential backoff but naive)
   ↓
each retry is a new order-inventory check
   ↓
inventory service sees 2x normal load
   ↓
inventory service starts timing out
   ↓
every order retries inventory check
   ↓
inventory service sees 10x normal load
   ↓
cluster goes down
```

修补是古典的: **circuit breakers**。当下游错误率超过阈值时,会使用缓存或默认结果的短路。加上上限 retry budgets 请求。

Circuit breakers 是一个少数的多 -agent 无法从分布式系统直接借出

<a id="memory-poisoning-revisited"></a>

### 内存中毒(重访)

取自13课:1 agent的 hallucination 成为共同记忆中的事实; agents 以MAST术语来说,这是在共享的分子层的核查漏洞。

渐变精度衰减是症状。 您不会发生崩溃; 缓慢的漂移会很难根化 。

缓解: 仅附单日志、 来源、 不可写校验程序。 已经在13课中覆盖了 。

<a id="stratus--specialized-agents-for-failure-detection"></a>

### 特派 agents 检测失败

2025年NeurIPS报告,在部署时,1.5x减缓成功率的提高:

- **Detection agent.** 观察症状模式(高度分歧、重试钉子、精确度漂移)。
- **Diagnosis agent.** 根据症状推断,可能源于MAST分类。
- **Validation agent.** 施用减量后,检查症状是否清晰。

这是SRE式的 incident response,适用于 agent 三个角色都可能是 LLM agents 专门 prompts.

<a id="the-failure-mode-audit"></a>

### 失败模式审计

2026年的最佳做法是每年(或按主要放行)一次的失败模式审计:

1. **Trace sample.** 收集~ 1 000 实际执行 traces.
2. **Categorize.** 每种 trace失败, 映射到 MAST + Group think 类别 。
3. **按类别计算故障率。** 哪个类别主宰你的系统?
4. **降级。** 哪种办法能消除最大的失败?
5. **选2 -3减量** 执行; 下季度重新审计。

纪律比具体选择更重要。 没有审计,失败就会被混入噪音中,永远得不到系统的解决。

<a id="when-systems-fail-silently"></a>

### 当系统无声失灵

最危险的故障类别是静默的正确性失败。 一个大错特错( 崩溃、 例外、 警报) 的系统可以被监控。 一个产生合理但错误的输出的系统无法通过例外日志检测出来。 这就是为什么核查缺口是每个失败的最昂贵的类别, 尽管它们按计数只有21.30% 。

投资于:
- 以样本为基础的人类审查。
- Golden-dataset regression tests.
- Cross-agent 核对重要产出。

<a id="failure-vs-slow-failure"></a>

### 失败与缓慢失败

有些失败是直接的;有些是缓慢的。 即时失败( 超时、 机率错配、 验证错误) 很容易被发现。 缓慢失败( 模拟中毒、 单种漂移、 角色模糊) 检测和预防成本高昂。

2026年工程移动: 仪器慢故障代言人, 这样您就可以在明显错误发生之前抓住漂移。 协议率、 重试速率、 输出长度分布以及连续时间的编辑距离 agent 版本都是有用的代名词。

```figure
a5-retry-cascade
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `FailureTaxonomy` - 将模拟事件分类为MAST+群思类。
- `CircuitBreaker` - 经典模式;当错误率超过阈值时打开。
- `RetryStormSimulator` 显示串联失败; 切换 circuit breaker 关上/关闭。
- `DetectionAgent` - 脚本式的STRATUS症状匹配器

Run:

```
python3 code/main.py
```

预期产出:
- 重试无风暴 circuit breaker:库存错误爆炸(模拟)。
- 与 circuit breaker:阈值上限;已衰减的响应。
- detection agent 标出模式并命名 MAST 类别 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-mast-auditor.md` 运行一个MAST型失败模式的多功能审计agent system. Traces · 分类  缓解等级。

<a id="ship-it"></a>

## 交付成果

生产中的失败模式纪律:

- **MAST审计每季度一次。** 年薪不高,随着系统的增长,类别会变
- **Circuit breakers everywhere.** 每个外向呼叫任何自定义的服务。 默认打开阈值为 5- 10% 错误率 。
- **黄金数据集** 低级的,高质量的,手工审核的,每周一次的反向测试
- **斯特拉特斯三重奏。** 检测+诊断+验证 agents 监测生产。 agent 仅; 当症状吵闹时添加诊断。
- **失败预算。** 以失败率分类的 SLO 明确。 超过预算会触发中断对话 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认 circuit breaker 控制了再试风暴, 忽略了故障门槛, 并观察了权衡结果。
2. 执行a **缓慢失败代理**: 3个平行协议率 agents。当它急剧下降时,触发警报。通过逐渐关联来模拟单种的漂移 agent 输出.
3. 读 Cemri 等人(arXiv:2503.13657),选择其7个MAS系统中的一个系统,并绘制其前3个故障类别图。这些系统与MAST预测的相比如何?
4. 阅读小组思考文件(arXiv:2508.5687),确定在生产过程中最难检测到的五个模式中的哪一个。
5. 设计一个STRATUS型的检测诊断-验证三重体,用于特定的多维-agent 检测的症状会观察哪些?诊断建议什么缓解?验证如何证实它们有效?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MAST | "2026年分类学" | Cemri 2025; 3根类别+14次失败类型。 |
| 具体问题 | 模糊不清 | 任务或作用未得到充分界定; agents 不知道该怎么办。 |
| 协调失败 | "国家漂移" | 信息通报或同步分类 agents. |
| 校验差距 | "没有人检查" | 未经独立验证而接受的产出。 |
| 群体思考家庭 | "合身性失灵" | 单体培养,符合性, 缺乏的托姆,混合运动, 串联。 |
| 单产业崩溃 | "同样的模型,相同的 hallucinations" | 共享基准模型或训练数据中出现相关错误。 |
| 重试风暴 | “ 加速错误” | 一次失败触发重压 增加下游的负荷 |
| Circuit breaker | 错误率快速失败 | 当错误率超过阈值时打开; 默认的短路 。 |
| STRATUS | "Incident response trio" | 检测+诊断+验证 agents1.5x缓解成功。 |
| 内存中毒 | "Hallucinations propagate" | 共享记忆事实污染;下游 agents 是因为毒药 |

<a id="further-reading"></a>

## 进一步阅读

- [Cemri等人——为什么要做多Agent LLM 系统失效?](https://arxiv.org/abs/2503.13657) - 2025年NeurIPS,最高科技教育分类
- [群組在多數中思考失敗agent LLMs](https://arxiv.org/abs/2508.05687) 单一文化、符合性和五家庭分类
- [特派 agents MAS 代表 incident response](https://neurips.cc/) - NeurIPS 2025程序条目(检测+诊断+验证)
- [释放它!](https://pragprog.com/titles/mnee2/release-it-second-edition/) 开关断路器
- [Anthropic - 多重 - 多重 -agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) 生产失败 -- -- 模式说明
