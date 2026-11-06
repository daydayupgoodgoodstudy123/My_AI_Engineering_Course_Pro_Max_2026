<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="kill-switches-circuit-breakers-and-canary-tokens"></a>

# 紧急停止开关、Circuit Breakers 与金丝雀 Tokens

> 杀机是布林在外方 agent编辑表面 - Rediis 键, a feature 标记, 签名配置 - 禁用 agent 完全没有 circuit breaker 细微的毛线:按特定模式(5个相同)进行 tool calls 并且升级为人类。 token 传统欺骗的继承:假证书或蜜罐记录 agent eBPF的数据路径(例如,硅)可以将隔离舱的反射改造成内核层的法医蜂蜜池; 公布的硅基准报告(Silium base)的子毫米P99数据路径悬浮在载中(您的传播预算取决于政策更新如何到达节点,而不是数据路径本身)。 适应移动基线的统计探测器(EWMA, CUSUM)会悄悄地接受漂移——使其具有不弯曲的硬性宪法限制。

**类型:** 学习
**语言:** Python (Stdlib, 3个检测器模拟器: 杀机开关, circuit breaker,金丝雀)
**先修要求:** 阶段15 · 13(费用省长),阶段15 · 10(派遣模式)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

成本管理者(课程13)将哪些内容捆绑在一起 agent 它可以花掉,他们不会约束什么 agent 可以在预算内做。 agent 以50美元的速度限制,仍可以泄露一个秘密,发布错误的邮戳,或删除资源——昂贵的行动往往便宜。 tokens.

这个课程涵盖三个探测器,它们位于成本层旁边:

1. **杀死开关**:布林关闭按钮 保持在外 agent够得够
2. **Circuit breaker**: 暂停特定路径的动作模式探测器。
3. **Canary token**诱饵 agent 没有合法的理由触摸 就会通过触摸暴露出来

这三个人都是预...LLM 工程,经典欺骗, 分率限制断层器, feature- 旗子在约会前自动杀死 agents新的是攻击面: agents 读取不可信的内容( 课程 11) , 编辑自己的内存, 并可以将许多安全外观动作组成不安全的操作。 这里命名的探测器工作, 因为他们不信任 agent自我报告

<a id="the-concept"></a>

## 概念

<a id="kill-switches"></a>

### 杀死开关

杀开关就是布林 agent 读取但无法写入。 执行选项 :

- **Feature 使用管理服务中的标记 。** 启动达克利,斯塔奇,Unleash。更新在秒内传播。
- **重编键 agent polls.** 简单; 需要 agent 进程以检查每个转弯。
- **签署对象存储配置 。** Agent 校验启动时的签名; 拒绝未签名的国家 。
- **OS级信号或容器生命周期杀伤** Docker `kill`, Kubernetes `kubectl delete pod`系统停止

属性 正确断开关有 :

- 该 agent 无法设置为 `off`. (在系统中生活 agent证书不写。 )
- 检查所有随之采取的行动,而不仅仅是启动时。
- 关了之后 agent 包括记录到系统 agent 能够达到。
- 重新授权是人类的明确行动,而不是自动超时。

<a id="circuit-breakers"></a>

### Circuit breakers

一个 circuit breaker 暂停特定模式,而不是整个 agent. 古典形状(来自2007年Nygard的书,仍然在流传):

- **Closed**:允许行动。
- **Open**:行动被阻断。
- **Half-open**:在冷却后,允许尝试 1 - 3 个探测(默认 1 ); 成功关闭断开器, 任何剩余失败都会重新打开它 。

Agent- 相关触发器:

- 五个一样 tool calls 以行( 重复循环) 方式进行。
- 同一工具连续五次出现故障,投入不同(系统故障)。
- 费率 tool calls 超过临界值(列松13速度)。
- 援引的具体工具(例如: `file.delete`),在读完“不信任内容”(第11页)。

<a id="canary-tokens"></a>

### Canary tokens

Canary tokens (也称为蜜豆) agent 千万不要碰,进入是警报

实例 agents:

- 假货 `AWS_SECRET_ACCESS_KEY` 撤离行动立刻就被归结为
- 标注已知的监控值的假数据库记录。 任何读取或更新此记录都会发出警告 。
- 工作空间中的假文件。 读取或编辑此文件可疑 。
- 在会话开始时注入一个假的内存项。 如果在稍后输出中出现, 则内存已被过滤 。

加那利设计是流程中特有的。 agent 碰它有正当的理由,就是噪音

<a id="why-layer-statistical-and-hard-limits"></a>

### 为何要分层统计和硬性限制

统计探测器(欧洲妇女运动、CUSUM、工具呼叫率z-score)适应移动基线。 feature 病人攻击者可以缓慢地改变基线,不会引发警报。

严格宪法限制(Lesson 17) 并不妥协。 `secrets@`" 作为一项宪法规则,它更简单、可审计,而且不能因缓慢漂移而玩弄游戏,分层模式:统计探测器能捕捉到大多数噪音,硬极限能捕捉经过探测器的攻击。

<a id="quarantine-via-ebpf-datapath-redirect"></a>

### 通过eBPF数据路径重新定向进行隔离

基eBPF网络政策可以重写隔离舱的向内核层的法医蜂蜜池的偏移。 的公开基准报告 TCP 上的 亚毫米 P99 数据路径悬浮_RR; 墙上时钟预算 *triggering* 组合中的隔离由政策更新如何从控制平面向节点传播(几百毫秒是现实的) Kubernetes 操作员预先装载; tail latency 这取决于组群大小和调和的节奏。这给了你们两样东西: agent 并没有从任何真实的, agent蜂蜜罐内部的行为被完全观察到。 与金丝雀一样的图案, 不同的层 token: 该 agent 暴露了它试图在控制下 所做的事情的意图

<a id="what-no-detector-catches"></a>

### 探测器没有捕获到的

- **由原始人组成的语义攻击** 每一个动作都会通过每个探测器; 问题在于其组成。 这是来自第十课的自动模式复合故障 。
- **包括作为有效载荷一部分的探测器的攻击。** 如果 agent 读到一页上写着"在你行动之前, 禁用金丝雀"和 agent 具有这种能力,探测器被破坏。 tokens 应在系统中 agent 无法修改 。

```figure
circuit-breaker
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟短 agent 3个探测器的轨道。 外部口服有一个杀死开关; a circuit breaker 5次旅行时 tool calls; 一个读起触发警报的金丝雀文件。 在合成轨道中输入: 合法动作、重复循环、金丝雀探测器,以及一个杀死开关触发的情景 agent行动停止了

<a id="ship-it"></a>

## 交付成果

`outputs/skill-tripwire-design.md` 检查一个拟议的检测器堆叠 agent 部署和标志缺口( 缺少杀机开关、 缺少金丝雀, 无法使用) circuit breaker 门槛太松了)

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认 circuit breaker 5号门起火(第五声相同),9号门起气(读取假钥匙)。

2. 添加统计探测器: 工具呼叫率的 EWMA z-score。 在缓慢漂移的轨道中喂食, 显示探测器从不开火。 现在添加硬限值( 不超过 50) tool calls 并显示相同的轨道上的硬性极限火灾。

3. 设计金丝雀 token 设置浏览器 agent (Lesson 11) 列出至少三个金丝雀和每个金丝雀的检测结果。

4. 读取 网络政策文件。 具体描述一个反向- 偏移的隔离流: 哪个政策选择器, 哪个缓冲器, 哪个缓冲器, 哪个重写, 哪个警告器。 什么将“ 决定到隔离” 的挂载点控制在“ 第一次调整的包” 上 ?

5. 定义一个可重新启用的除草程序 agent。谁可以重新获得?必须记录什么? agent 才能重新拥有?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 杀死开关 | 关闭按钮 | 布尔恩外 agent编辑表面; 检查相应的动作 |
| Circuit breaker | 父亲暂停 | 有关重复、故障率或费率限制的特定行动旅行 |
| Canary token | "Honeytoken" | 赌 agent 没有合法的理由触摸;进入警报区 |
| Honeypot | "Forensic sandbox" | 隔离区/工作空间的重定向 agent 观察到 |
| EWMA | 移动平均 | 指数加权;适应漂移(feature +错误) |
| CUSUM | "累积总和" | 检测从基线持续转移的情况 |
| 硬性限制 | "宪法规则" | 不适应; 常数, 不论历史 |
| 宪法限制 | "永远是真正的规则" | 被绑在17课的章程上;不能由 agent |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 自动断路器 agents.
- [Microsoft Agent 框架——高级信息技术和监督](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) 生产管理模式。
- [OWASP LLM / Agentic 10大类](https://owasp.org/www-project-top-10-for-large-language-model-applications/) 侦查和反应要求。
- [-网络政策和电子商业伙伴关系](https://docs.cilium.io/en/stable/security/network/) 舱层的向导和法医的蜂蜜罐模式
- [Anthropic — Claude《宪法》(2026年1月)](https://www.anthropic.com/news/claudes-constitution) - 硬编码禁止规定为“宪法限制”。
