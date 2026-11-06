<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="browser-agents-and-long-horizon-web-tasks"></a>

# 浏览器 Agents 与长程网页任务

> ChatGPT agent (2025年7月)合并操作员,对一个浏览器/终端进行深入研究 agent 并设定浏览Comp SOTA 占68.9%。 OpenAI 2025年8月31日关闭了接线员——产品层的整合。 Anthropic节奏获取已移动 Claude OSWorld上的Sonnet从15%到72.5%不等。 WebArena-Verifed(服务时间为现在,ICLR 2026)在原始WebArena中固定了假负率的11.3个百分点,并发运了258个任务硬子集。数字是真实的。攻击表面也是这样: OpenAI准备负责人公开表示 indirect prompt injection 进入浏览器 agents 2025-2026年的被记录攻击事件: 笔记(Atlas CSRF)、Hash Jack(卡托网络)和一击劫持事件 Perplexity Comet.

**类型:** 学习
**编程语言：** Python（标准库，用于建立间接 prompt 注入的攻击面模型）
**先修要求:** 阶段15 · 10(派遣模式),阶段15 · 01(长-长 agents)
**时间:** ~45分钟

<a id="the-problem"></a>

## 问题

浏览器 agent 是一个长方圆 agent 并随后采取行动。 agent 访问是用户没有写入的输入。 每个页面上的每个表格都是潜在的命令频道。 2025-2026攻击程序显示这不是假设: 纹身记忆让攻击者将恶意指令绑在 agent以刻画的页面隐藏内存; HashJack 将命令隐藏在 URL 碎片中 agent visits; Perplexity 彗星劫持事件一击即中

防御性照片让人不舒服 OpenAI准备的负责人大声地说: indirect prompt injection "不是一个可以完全修补的虫子" 这是因为攻击 住在 agent读取-Vs-act-边界,在结构上模糊——每个 token 模式读作原则上可以理解为指示。

课程名称为攻击表面, 命名基准景观( BrowseComp、 OS World、 WebArena- 验证) , 并模拟最小间接prompt- 注射假想 这样你就可以在14和18课里 解释真正的防御

<a id="the-concept"></a>

## 概念

<a id="the-2026-landscape-in-one-paragraph-per-system"></a>

### 2026年的景观,每系统一个段落

**ChatGPT agent (OpenAI).** 2025年7月启动。 统一运算符( 浏览) 和深层研究( 多小时研究) 。 关闭独立运算符 2025年8月31日 。 在浏览Comp 上, SOTA 占68.9%, 在 OS World 和 WebArena 中拥有强势数字 。

**Claude 索内特+动词( 音符) (Sonnet + Vercept) (Anthropic).** Anthropic以计算机使用能力为主的 Verick 获取。 已移动 Claude OSWorld上的索纳特从<15%到72.5%。 Claude 计算机将船舶用作工具 API.

**Gemini 3 使用浏览器( 深最小值) 。** 浏览器使用集成船计算机使用控制; FSF v3(2026年4月,课程20) 专门跟踪ML研发领域的自主性。

**WebArena-Verifed(服务时间到,ICLR 2026)。** 解决一个有详细记载的问题: 原始 WebArena 的假阴性率为~ 11. 3% (标记失败,但实际上已经解决了 ) 。 经验证的释放量按人造成功标准重新评级,并添加了一个258 个任务硬子集(ICLR 2026 纸张, openreview. net/ forum?id=94tlGxmqkN )。

<a id="browsecomp-vs-osworld-vs-webarena"></a>

### 浏览Comp 和 OSWorld 和 WebArena 的组合

| 基准测试 | 它衡量什么 | Horizon |
|---|---|---|
| BrowseComp | 在时间压力下在开放的网上查找具体事实 | minutes |
| OSWorld | Agent 运行全台( mouse、 keyboard、 shell) | 数十分钟 |
| WebArena-Verified | 模拟网站的往来网络任务 | minutes |
| 硬子集 | WebArena 具有多页状态过渡的验证任务 | 数十分钟 |

不同的轴。 浏览器高分表示 agent 发现事实;它没有说 agent 它可以预订飞行。 OSWorld的分数接近于“ 在我的桌面上工作 ” 。 WebArena- 验证更接近“ 能够完成一个流程 ” 。 任何生产决定都需要符合任务分布的基准 。

<a id="the-attack-surface-named"></a>

### 攻击表面,命名

1. **Indirect prompt injection.** 不信任的页面内容包含指令。 agent 读他们。 agent 公共实例:2024年Kai Greshake等人,2025年《笔记本》,2026年《哈希杰克》(卡托网络)。
2. **URL 碎片/查询注入。** 该 `#fragment` 或查询字符串的 URL 包含命令。 从未明显显示; 仍然在 agent上下文
3. **与记忆相连的攻击。** 章 次 页 次 agent 以写出一个耐久的内存( 教训12 包含耐久状态) 。 下次会话, 内存点燃有效载荷时没有可见的触发器 。
4. **CSRF形攻击经认证的会议。** 笔记类: agent 被登录在某个地方;攻击者的页面发布州更改请求 agent 使用用户的 cookie 执行。
5. **单击劫持** 视觉无伤大雅的按钮 载荷 agent 之后,彗星类。
6. **内容-安保政策漏洞 agent宿主表面 。** 图像和工具层本身可以是攻击矢量;浏览器在浏览器中agent 堆叠宽。

<a id="why-not-fully-patchable"></a>

### 为什么"不完全补齐"

攻击是无形态的 agent能力,我们 agent 需要阅读不可信内容才能完成它的任务。 agent 读作中可以包含指令。 agent e. 辩护(a)trust boundaries,分类器,工具许可清单,HITL(相应行动),提高攻击成本,降低爆炸半径。它们不关闭舱门。

这是和Lob的理论(Lesson 8)相同的推理模式: agent 无法证明下一个 token 安全; 它只能建立不安全的系统 tokens 更能被察觉

<a id="defense-posture-that-actually-ships"></a>

### 实际船只的防御态势

- **读取/ 写入边界 。** 读取从不产生影响。 写入( 提交表格、 张贴内容、 调用具有副作用的工具) 需要新的人类认可, 如果启动内容来自外部 trust boundary.
- **每个任务的工具允许列表 。** 该 agent 能够浏览; 除非该工具被明确授权执行, 否则它无法启动电汇。 课程13包含预算。
- **课间隔离** Browser agent 仅使用范围化证书运行的会话。 没有制作验证, 没有个人电子邮件。 每一个会议的日志 HTTP 要求保留审计。
- **内容消毒剂** Fetched HTML 将已知的坏模式去除后再并入模型上下文。 (减少容易攻击;不停止尖端有效载荷。 )
- **有关相应行动HITL。** Propose-then-commit 模式 (Lesson 15) 。
- **Canary tokens 记着呢** 如果内存输入发生火灾,用户会看到(Lesson 14)。

```figure
injection-boundary
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟一个小浏览器agent 运行于三个合成页面。 1页是良性的,1页是直接的 prompt- 以可见文字插入插管,有一个 URL 碎片注入( 无法看到, 但位于 agent上下文)的脚本显示 (a) 多幼稚 agent (b) 读/写边界的渔获量;(c) 净化剂的渔获量;(d) 两者兼有。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-browser-agent-trust-boundary.md` 范围agent 部署:它触及的哪个信任区, 它被授权写什么, 以及哪些防御必须到位 在第一次运行之前。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。标明哪种攻击清除器捕获,但读/写边界没有,哪种攻击仅攻击读/写边界捕获。

2. 扩展净化器以检测一种类的 HashJack URL 式的 URL 分解注入。 用合法的碎片测量良性 URL 上的假阳性率 。

3. 选一个真正的浏览器agent 您所知道的工作流程( 例如“ 订票飞行 ” ) 。 请列出每读和每写的列表。 马克写道需要 HITL 和原因 。

4. 读取 WebArena- 验证 ICLR 2026 纸张。 确定一个任务类别, 即WebArena 的原分数不可靠, 并解释经验证的子集如何解决这个问题 。

5. 为浏览器设计一个内存金丝雀 --agent 设置。你会储存什么,在哪里,什么触发警报?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Indirect prompt injection | "差页文字" | 页面中不信任的内容 agent 读取含有说明的 agent executes |
| 笔记 | "记忆攻击" | Agent 撰写攻击者提供的耐久记忆教学; 下个会话触发 |
| HashJack | "URL碎片攻击" | URL 碎片中隐藏的 有效载荷 / 查询字符串 agent上下文,但未明显显示 |
| 点击劫持 | "坏按钮" | 可见的承载载器 agent executes |
| BrowseComp | "网络搜索基准" | 在开放的网页上查找具体事实; 微小尺度的视野 |
| OSWorld | "顶层基准" | 完整的操作系统控制; 多步图形界面任务 |
| WebArena-Verified | "固定网络任务基准" | 服务站现在重新升级WebArena 的硬子集 |
| 读写边界 | "副作用门" | 阅读从未产生结果;如果内容超出信任范围,书面需要新的批准 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI - 介绍 ChatGPT agent](https://openai.com/index/introducing-chatgpt-agent/) 将操作员和深入研究合并;浏览Comp SOTA。
- [OpenAI 计算机使用 Agent](https://openai.com/index/computer-using-agent/) 操作员的线条和结构 ChatGPT agent.
- [周等人-韦伯阿雷纳](https://webarena.dev/) - 原基准。
- [WebArena- 验证( 公开审查)](https://openreview.net/forum?id=94tlGxmqkN) - ICLR 2026固定子集纸。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 包括供计算机使用的地面攻击讨论 agents.
