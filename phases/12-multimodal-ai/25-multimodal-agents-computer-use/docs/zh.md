<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="multimodal-agents-and-computer-use-capstone"></a>

# 多模态 Agents 与计算机操作（综合项目）

> 2026年的前沿产品是多式联运 agent ,读取截图,单击按钮,浏览网络用户名,填充表格,完成流程端到端。见Click和 CogAgency (2024) 证明了 GUI-grounding 原始的, Ferret-UI 添加移动。 图表显示器引入了图表的视觉工具。 视觉WebArena 和 AgentVista (2026) 是前沿追踪的基准 。 Gemini 3 PL和3 高级 Claude 操作4.7分~30% 用于代理Vista的硬任务。 这个综合项目将第12阶段的每一个线拉在一起: 感知(高射速VLM),推理( 推理) (Green- reps VLM)LLM 使用工具), grounding (坐标输出)、长方位内存和 evaluation.

**类型:** Capstone
**语言:** Python (stdlib, 动作计划+) agent loop skeleton)
**先修要求:** 阶段12 -05(LLAVA),阶段12 -09(PS)Qwen-VL JSON),第14阶段(Agent Engineering)
**时间:** ~240分钟

<a id="learning-objectives"></a>

## 学习目标

- 设计一个多模态 agent loop：感知 → 推理 → 行动 → 观察 → 重复。
- 构建一个图形用户界面 grounding 输出 sema (单击坐标、键入文本、滚动、拖动) JSON.
- 比较仅屏幕抓图 agents 与无障碍树 agents 混合体 agents.
- 建立多式联运 agent benchmark evaluation 在一个小的视觉网片。

<a id="the-problem"></a>

## 问题

订书站的工作流程:“找到我4月15日去东京的航班,

多式联运 agent 需要:

1. 浏览器截图
2. 将截图+ URL+目标分析为计划 。
3. 退出一个结构化动作: 单击 (x,y), 键“ 东京” (在元素 E) , 滚动, 选择( radio 按钮) 。
4. 将动作应用到浏览器 。
5. 观察新状态( 下个截图) 。
6. 重复到任务完成为止

每一步都是多式VLM调用。 VLM 输出必须可分析 JSON。跨步错误复数,因此,回收很重要。

<a id="the-concept"></a>

## 概念

<a id="gui-grounding--the-primitive"></a>

### GUI grounding - 原始的

GUI grounding :给定截图和自然语言教学,输出(x, y)坐标以单击(或其他动作)。

见Click (arXiv:2401.10935) 是第一个比例显示的开放结果: 将合成的 + 真实的 GUI 数据微调 VLM, 输出坐标为纯文本 tokens工作时

CogAgenti( arXiv: 2312. 08914) 添加了 1120x1120 密闭 UIs 的高分辨率编码。 评分: 在网络导航中~ 84% 。

Ferret-UI(arXiv:2404.05719)侧重于移动性UI,与iOS无障碍数据相结合。

输出格式通常 JSON:

```json
{"action": "click", "x": 384, "y": 220, "element_desc": "Search button"}
```

该 `element_desc` 帮助恢复: 如果在截图之间坐标漂移, 语义提示会让系统重新降落 。

<a id="action-schemas"></a>

### 行动计划

典型的行动方案有6-10个行动类型:

- `click`: (x, y) :
- `type`: (文本, x? y?)
- `scroll`: (指令、数量)
- `drag`: (x0, y0, x1, y1)
- `select`: (选项)_index)
- `hover`: (x, y) :
- `navigate`: (URL) 数据
- `wait`: (单位:百万美元)
- `done`: (成功,解释)

该 agent 一次播放一个动作。 浏览器包装执行并返回新状态 。

<a id="screenshot-only-vs-accessibility-tree"></a>

### 仅屏幕截图与无障碍树

两种输入模式:

- 仅屏幕截图: 全图像, 没有结构信息。 多数一般; 工作于任何应用程序 。
- 可获取性树:结构化的DOM/iOS无障碍信息。 grounding;在树可用之处工作。
- 混合:两者,以树为原子行动的可靠地面和语义背景的截图。

Production agents 可能时使用混合。浏览器自动化( +无障碍) 总是有树; 桌面应用程序有时会这样做 。

<a id="long-horizon-memory"></a>

### 长方位内存

20步工作流程生成 20 个截图。 VLM 的上下文快速填充 。 三种压缩策略 :

- 简链:每5步后,总结一下所发生的事情,放出旧的截图。
- 跳过框: 保留第一个,最后一个, 和每个三分镜头。
- 工具记录的日志: 执行动作, 保存完成的文字日志; 不要重看旧的抓图 。

Claude计算机使用 API 使用日志模式。 简单些, 更可靠一些 。

<a id="visual-tool-use"></a>

### 视觉工具的使用

图表代理(arXiv:2510.04514)介绍了用于了解图表的视觉工具:作物、放大、OCR、呼叫外部检测。 agent 输出“ 切到区域( 100, 200, 300, 400) ” , 然后调用 OCR , 以 a tool call。工具返回文本;VLM继续推理。

这个模式概括了:标记提示、区域注释和外部检测工具都符合相同的“输出” tool call接受一个有条理的反应"的策略。

<a id="the-2026-benchmarks"></a>

### 2026年基准

- 屏幕站- Pro. GUI grounding 。打开 SOTA Qwen2.5-VL-72B~85%。边框~90%。
- 视觉网络。端到端的网络任务( 商店、 论坛、 分类) 。 打开 SOTA~ 20% 。 Gemini 3 Pro~27%。
- AgentVista (arXiv: 2602.23166). 最难的 2026 基准。 12个域的现实工作流程。 边框模型得分 27- 40%; 开放模型 10- 20% 。
- WebArena/WebShop. 较老的基准; 饱和于边界。

<a id="why-its-still-hard"></a>

### 为何还这么难

Agent 业绩瓶颈:

1. Visual grounding 点击小X 通常在移动分辨率上失败 。
2. Long-horizon planning。在10次行动之后, agent 偏离了目标
3. 错误恢复。 当点击失败( 错误按钮) , 检测 + 恢复 很少被训练过 。
4. 跨页上下文。 在制表符或长式之间跳动会失去状态 。

研究方向:记忆结构、明确的重新规划、多式联运核查(截图与成功行动匹配)。

<a id="the-capstone-build-it"></a>

### 盖石造的

综合项目任务: 建立计算机使用 agent 该:

1. 读取 HTML + 预订站模拟页面的截图。
2. 计划一个多步序列:搜索 __ 选择 __ 填充 __ 提交 。
3. Emits JSON 匹配动作图的动作 。
4. 以固定的10个任务切片进行估量。

课程提供了很容易扩展到一个真正的浏览器的脚手架代码。

```figure
mm-agent-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是顶石脚架:

- 行动计划 JSON 定义(10项行动)。
- 嘲笑浏览器的状态为dict 。
- Agent loop 骨骼:接收状态,发布动作,应用,循环。
- 10个任务小型基准(合成页面),以测量端到端的成功率。
- 操作失败时的错误回收钩 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-multimodal-agent-designer.md`。如果使用计算机的产品(域、行动集、 evaluation 目标,设计全 agent loop记忆策略 grounding 模式,和预期的基准分数。

<a id="exercises"></a>

## 练习

1. 扩展行动计划 `screenshot_region` 工具( rop+ 缩放) 。 什么任务的好处 ?

2. 阅读代理Vista (arXiv: 2602.23166). 描述最难的任务类别和前沿模型仍然失败的原因。

3. 长视距内存压缩:设计一个有 ++4 截图的简要链, 任何数字都记录下来 。

4. 创建错误回收钩: 在动作失败( 未找到按钮) 时, 是什么 agent 下一个呢?

5. 比较仅屏幕抓图 Claude 4.7至混合截图+可访问性树 Quen2.5-VL 10项网络任务。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| GUI grounding | "点击坐标" | 屏幕截图指示目标的模型输出(x,y) |
| 行动计划 | "工具定义" | JSON 有效动作描述( 单击、 键入、 滚动、 拖动) |
| 无障碍树 | 结构化的DOM | 从浏览器/iOS 中可读取的机界面等级 APIs |
| Hybrid agent | "闪光+树" | 使用图像和结构化信息;比单独两种信息都可靠 |
| 视觉工具的使用 | "Zoom/crop/detect" | Agent 称为外部视觉工具(OCR, 检测) |
| Summary-chain | "记忆压缩" | 定期文本摘要取代长截图历史 |
| VisualWebArena | "E2E网凳" | 2024年终端至终端网络任务基准 |
| AgentVista | "2026年长凳" | 12个主页实际工作流程; Gemini 3 分到-30% |

<a id="further-reading"></a>

## 进一步阅读

- [Cheng等人——见Click(arXiv:2401.10935)](https://arxiv.org/abs/2401.10935)
- [Hong等人—— 科格阿根特(arXiv:2312.08914)](https://arxiv.org/abs/2312.08914)
- [费雷特-UI(arXiv:2404.05719)](https://arxiv.org/abs/2404.05719)
- [图表(arXiv:2510.04514)](https://arxiv.org/abs/2510.04514)
- [Koh等人——视觉网(arXiv:2401.13649)](https://arxiv.org/abs/2401.13649)
- [代理Vista(ARXiv:2602.23166)](https://arxiv.org/abs/2602.23166)
