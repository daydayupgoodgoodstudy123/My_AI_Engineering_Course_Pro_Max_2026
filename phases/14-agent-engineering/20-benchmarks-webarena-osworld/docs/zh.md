<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="benchmarks-webarena-and-osworld"></a>

# 基准评测：WebArena 与 OSWorld

> WebArena 测试网络...agent 操作系统世界测试桌面agent 超音速能力, Windows, MacOS。发布(2023-2024)时,两个都显示在最佳水平之间有很大差距 agents 和人类。差距正在缩小,失败模式没有改变。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 19 (SWE-Bench, GAIA)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述WebArena的四个自托管程序,以及为什么执行 evaluation matters.
- 解释OSWorld为何使用真正的OS屏幕截图而不是无障碍 APIs.
- 命名两个主操作系统世界失败模式: GUI grounding 以及业务知识。
- 总结OSWorld-G和OSWorld-Horld-Himan在基准上添加的内容。

<a id="the-problem"></a>

## 问题

Generalist agents 可以调用工具。 他们可以驱动浏览器过20个点击来完成购物检查吗 ? 他们能否只配置一个 Linux 框, 仅使用键盘和鼠标 ? 这些是 WebArena 和 OSWorld 的答案 。

<a id="the-concept"></a>

## 概念

<a id="webarena-zhou-et-al-iclr-2024"></a>

### WebArena(周等人,2024国际刑法中心)

- 四个自办的网络应用程序有812项长视距任务:一个购物网站、一个论坛、一个类似GitLab的Dev工具、一个商业内容管理系统。
- 加上公用设施:地图、计算器、刮痕。
- Evaluation 是通过健身房执行的 APIs 是否订了订单,问题是否已经解决,内容管理系统网页是否得到更新?
- 发布时:最佳 GPT-4 agent 成功率14.41% 人与成功率78.24%

自我托管的设置问题——基准并非模糊,因为目标应用程序是固定和可复制的。

<a id="extensions"></a>

### Extensions

- **VisualWebArena** 视像化任务,其成功与否取决于图像的解读(截图作为头等观察)。
- **TheAgentCompany** (Dec 2024)——增加终端+编码;更像一个真正的远程工作环境。

<a id="osworld-xie-et-al-neurips-2024"></a>

### OSWorld(Xie等人,NeurIPS 2024)

- 整个Ubuntu,Windows,macOS的369个真正的计算机任务。
- 自由格式键盘和鼠标对真实应用程序的控制。
- 1920×1080 截图作为观察。
- 发布时:最佳模式12.24%与人类72.36%。

<a id="primary-failure-modes"></a>

### 初级失败模式

1. **GUI grounding.** 像素 元素映射。 模型在1920x1080年努力将 UI 元素可靠地本地化 。
2. **业务知识。** 哪个菜单有设置, 键盘快捷键, 偏向于窗帘。 人类多年积累的知识尾巴 。

<a id="follow-ups"></a>

### Follow-ups

- **OSWorld-G** - 564个样本 grounding 套房+绝地训练组。 grounding 来自 planning 这样你就可以分别测量它们。
- **OSWorld-Human** 手动绘制金色动作轨迹。 显示顶部 agents 使用1.4-2.7x 超过必要的步骤(轨道效率差距)。

<a id="why-this-matters"></a>

### 为何这重要

Claude 计算机使用 OpenAI CUA, Gemini 2.5 计算机使用(21世纪课程)所有关于WebArena和OSWorld所塑造的工作量的火车,其基准是目标;生产模型是运出的答复。

<a id="where-benchmarking-goes-wrong"></a>

### 基准错误的地方

- **屏幕截图只显示反射器 。** OSWorld是屏幕截图驱动的; 评估 agent 使用 DOM 或无障碍 APIs OSWORLD 错过了 grounding challenge.
- **忽略轨道长度。** 仅按成功率计,就忽略了OSWorld-Hulman表面的1.4-2.7x级低效率。
- **自动托管的老套程序** WebArena 的应用程序别针特定版本; 更新时不重复引用会断开可比性 。

```figure
ae-agent-human-gap
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行玩具网络-agent harness:

- 最小的“ 购物应用程序” 状态机器: 列表_项,添加_以_车,退房。
- 3项任务的金色轨迹
- 脚本 agent 尝试每项任务。
- 执行评估员(国家检查)和轨迹效率衡量标准(步骤与黄金)。

运行：

```
python3 code/main.py
```

产出:每个任务的成功率和轨迹效率,反映OSWorld-Hultan的方法。

<a id="use-it"></a>

## 实际应用

- **WebArena 已验证** 连续在内部组群上自行托管 evaluation.
- **OSWorld** 用于桌面的 VM 机队 agents.
- **Computer-use agents** (教训21) - Claude, OpenAI CUA, Gemini - 都受过这样的训练
- **你的产品流** 获取前20项任务的黄金轨迹; agents 每周一次,他们都会被开除

<a id="ship-it"></a>

## 交付成果

`outputs/skill-web-desktop-harness.md` 建立一个网络/桌面 agent harness 采用基于执行的电子逆向拍卖和轨道效率衡量标准。

<a id="exercises"></a>

## 练习

1. 延长玩具 harness 使用第二个应用程序( 一个论坛) 。 写入 3 个任务, 加上 金轨迹 。
2. 添加每个任务的轨迹效率报告。 在您的玩具上是 agent 1x2x或3x超过黄金?
3. 使用“ 吸引器” 工具, 一个金色轨道从未使用的工具。 脚本是否已经显示 agent 被诱惑?
4. 读OSWorld-G。 你会如何分离 grounding 失败来源 planning 失败在自己的评估?
5. 读取 WebArena 的应用程序 README。 当升级一个被锁定的应用程序版本时, 是什么断开 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| WebArena | "Web agent benchmark" | 4个自办应用程序的812项任务;健身式 evaluation |
| VisualWebArena | "视觉网络阿伦娜" | 视觉化的 WebArena; 截图是观测 |
| OSWorld | "Desktop agent benchmark" | 真正的Ubuntu/Windows/macOS的369项任务 |
| GUI grounding | "像素到元素映射" | 1920x1080年将UI元素本地化的模型 |
| 业务知识 | 业务处的技巧 | 哪个菜单, 哪个快捷键, 选择窗体 |
| OSWorld-G | "Grounding suite" | 564 grounding- 仅选样+成套训练 |
| OSWorld-Human | "金色轨迹" | 衡量效率的专家行动手工顺序 |
| 轨迹效率 | "金子上铺垫" | Agent 步数除以人类最小值 |

<a id="further-reading"></a>

## 进一步阅读

- [Zhou等人,WebArena(arXiv:2307.13854)](https://arxiv.org/abs/2307.13854) 4个应用程序网络基准
- [Xie等人,OSWorld(阿尔西夫:2404.07972)](https://arxiv.org/abs/2404.07972) - 跨OS桌面基准
- [Anthropic,引入计算机使用](https://www.anthropic.com/news/3-5-models-and-computer-use) — Claude基准形状能力
- [OpenAI计算机使用 Agent](https://openai.com/index/computer-using-agent/) OSWorld和WebArena数字
