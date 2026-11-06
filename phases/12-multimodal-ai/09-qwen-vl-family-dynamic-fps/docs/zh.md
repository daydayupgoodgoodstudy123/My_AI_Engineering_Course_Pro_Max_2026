<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="qwen-vl-family-and-dynamic-fps-video"></a>

# Qwen-VL 系列与动态帧率视频

> 该 Qwen-VL家庭 - - -我爱她 Qwen- VL(2023年)、Quen2-VL(2024年)、Quen2.5-VL(2025年)、Quen3-VL(2025年)——是最具影响力的开放 vision-language model 2026年的家族关系 每一代人都做出一个决定性的建筑赌注 rest 12个月内复制的开放生态系统:通过M-RoPE动态FPS sampling 绝对时间 alignment窗口 attention 在 ViT结构 agent 输出格式。 到 Quen3- VL, 配方已经稳定了: 2D-RoPE-ViT encoder 具有本地版图投入,MLP投影器进入一个大型的Quen3语言基础,以及强调OCR的培训阶段, grounding, 和 agent 行为作为一流的目标。这个课按时间顺序读取家庭,这样你就能理解为什么每个把手都在那里。

**类型:** 学习
**语言:** Python (斯迪利布,M -)RoPE encoder +动态-FPS取样器)
**先修要求:** 阶段12 · 06 (patch-n'-pack)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 计算M -RoPE三个轴的旋转( 时空、 高度、 宽度) 并解释为什么需要全部三个轴。
- 选择动态FPS sampling 视频和理由的策略 tokens-每秒对事件的检测精确度
- 说四 Qwen-VL代际升级 以及每个代际的提升
- Quen2.5-VL 型电线 JSON agent 输出格式和结构分析 tool calls 由VLM反应。

<a id="the-problem"></a>

## 问题

Qwen-VL于2023年8月发货,直接回应LLAVA-1.5和BLIP-2。 Qwen 目标小组有三重:分辨率、视频和 structured output.

决议:LALVA-1.5的运行量为336x336,照片罚款,中文发票或密集的电子表格截图无用。 Qwen-VL的第一个创新是448x448 和有根的捆绑框输出, 让模型点在东西上。

视频:视频-LLaMA 每框架堆叠 encoders 并把他们喂养到 LLM。它的工作是短片,而不是多分钟的视频,因为时间轴是信号。 Qwen 团队想要一个 encoder 了解时间

Structured output:LLAVA 释放自由格式文本。 agent needs JSON. Qwen- 接受明确培训的VL JSON 输出格式,包括以文本形式显示的捆绑框坐标。

每个 Qwen-VL世代是这三个轴中的一个

<a id="the-concept"></a>

## 概念

<a id="qwen-vl-august-2023"></a>

### Qwen- VL(2023年8月)

第一代:开放CLIP ViT- 大G/14为 encoder (2.5B 参数), LLama- 符合Q- 以前的(1步,256个查询), Qwen-7B基数,捐款额:

- 448x448分辨率(开放VLM为SOTA)。
- Grounding:在有明确协调的图像文本对面方面接受培训token 输出。 "猫在 <box>(112, 204), (280, 344)</box>".
- 中文+英文培训,从一开始就进行。

基准时:与 GPT-英语4V,中文占优势 grounding 监管才是真正的头条新闻

<a id="qwen2-vl-september-2024--m-rope-and-native-resolution"></a>

### Quen2-VL (2024年9月) - M-RoPE 和当地解决办法

Quen2-VL 用本地动态分辨率替换固定分辨率+Q- 格式堆栈 ViT encoder关键变化:

- 本地动态分辨率。 ViT 接受任何 HxW 的可变28 ()patch 14 和 2x 空间合并。 图像在 1120 x 672 处( 40x24 合并) patches制作960个视觉 tokens. 不调整大小,不打砖,不缩略图。
- M-RoPE (Multimodal RoPE). 每个 token 带有3D 位置(t, h, w) 而不是 1D。 对于 T= 0, 视频 t = 框架_index. RoPE 按轴旋转查询/关键矢量的频率。 embedding table.
- MLP 投影器。 丢弃 Q- 格式; 在合并时使用 2 层 MLP patch tokens.
- 视频带动态 FPS。 默认情况下, 1-2 FPS 取样的视频, 但模型接受任意框架计数 。

结果: 匹配 Quen2-VL-7B GPT-4o,采用若干多式联运基准,并用DocVQA(94.5诉88.4)胜过该标准。

<a id="qwen25-vl-february-2025--dynamic-fps--absolute-time"></a>

### Quen2.5-VL(2025年2月)-动态FPS+绝对时间

Quen2.5-VL的大转变是视频。动态FPS不只是“在需要时抽样更多框架”。

- 绝对时间 tokens。 使用实际的时间戳,而不是位置指数(框架0, 1, 2...) 。 “ 04时, 猫跳动。 ” 模型看到 `<time>0.04</time>` tokens 与框架间断 tokens.
- 动态 FPS. 在 1 FPS 样本中显示慢镜头, 4+ FPS 动作。 用户或训练师选择; M-RoPE adapts.
- Window attention 在 ViT空间 attention 窗口(区块内为本地)用于输送; 全局 attention 每一层
- Explicit JSON 输出格式。 工具呼叫数据培训 : “ {\"tool\": \"click\", \"coords\": [380, 220]}". Agent- 已经出柜了
- MROPE- v2 缩放。 位置比例尺具有最大输入大小, 这样一个10分钟的视频不会超过频率范围 。

基准: Quen2.5-VL-72B节 GPT- 4o 多数视频基准,匹配 Gemini 2. 0 显示文档,并为 GUI 设定开放型号 SOTA grounding (ScreenSpot: 准确度84%,而38%) GPT-4o).

<a id="qwen3-vl-november-2025"></a>

### Quen3-VL(2025年11月)

Quen3-VL 是渐进式升级, 合并而不是重塑: 大 LLM 骨干(Quen3-72B),扩大训练数据,改进了OCR, 通过 Quen3 “思考模式” 强化推理。 ViT 和M - - 都已经...RoPE 本文的重点是关于建筑的数据和训练改进。

离子系取走:到2025年 Qwen变压器结构已经稳定下来了, 更多的代际规模计算和数据, 不是原始的。

<a id="m-rope-mathematically"></a>

### M-RoPE mathematically

Classical RoPE 旋转查询 `q` 维度 `d` 按位置 `m` 使用对齐坐标 :

```
q_rot[2i]   = q[2i]   * cos(m * theta_i) - q[2i+1] * sin(m * theta_i)
q_rot[2i+1] = q[2i]   * sin(m * theta_i) + q[2i+1] * cos(m * theta_i)
theta_i     = 10000^(-2i/d)
```

M-RoPE 将隐藏的暗暗分成三个乐团 `d = 96`。将32个暗点指定为时间,32个暗点指定为高度,32个宽度。每个波段按自己的轴位置旋转。A patch 时值为 (t=5, h=10, w=20) 时, 获得旋转 `R_t(5)`, `R_h(10)`, `R_w(20)` 适用于它的三波段。

Text tokens 使用 `t = text_index, h = 0, w = 0` 保持兼容性( 或一个常规选项) 。 视频框架使用 `t = frame_time, h = row, w = col`使用单个图像 `t = 0`.

好处是:一个位置编码处理文本、图像和视频,不使用分支代码或不同的位置表格。

<a id="dynamic-fps-sampling-logic"></a>

### Dynamic-FPS sampling logic

给一段持续时间的视频 `T` 秒和一个目标...tokens budget `B`:

1. 计算您能够负担的最大 FPS : `fps_max = B / (T * tokens_per_frame)`.
2. 从目标 FPS 中选择 `{1, 2, 4, 8}` 满足的 `fps <= fps_max`.
3. 如果运动(光流或直线用户要求)高,请选择更高的 FPS 。如果运动低,请选择较低的 。
4. 在选定的 FPS 上统一样本; 插入 `<time>t</time>` tokens 介于两边

Quen2.5-VL 暗含地训练这一逻辑; inference 用户控件 `fps` parameter4个FPS和81个60秒的动作序列 tokens 每个框架=19440 tokens,在32k的背景下可以控制。

<a id="structured-agent-output"></a>

### Structured agent 输出

Qwen2.5-VL's agent 明确制定培训目标 tool calls:

```
{
  "tool": "mouse_click",
  "coords": [1024, 512],
  "button": "left",
  "modifier": null
}
```

分析是决定性的: JSON。 分隔模型输出。 比较自由形式“ 点击 1024, 512 ” , 需要正则和模糊处理。 改变是Qwen2.5- VL的屏幕波分数从 Quen2- VL 的55%跳到 84%的原因 。

```figure
mm-mrope-axes
```

<a id="use-it"></a>

## 实际应用

`code/main.py` implements:

- M-RoPE 用于混合文本、图像的包装序列的位置计算 patches,以及视频框。
- 动态- FPS 取样器: 给定( 期限、 预算、 动议)_),选择 FPS 并发布框架时间戳。
- 玩具 Quen2.5-VL JSON- 处理工具呼叫响应的输出分析器,与协调字段连接。

运行它,然后感觉不同 当你交换固定的FPS 换动态-FPS 在5分钟的视频。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-qwen-vl-pipeline-designer.md`。如果有视频任务(监控, agent,动作识别,可访问性),它释放了Quen2.5-VL配置(框架预算、FPS战略、窗口-attention flag, agent- 输出模式)和潜伏估计。 Qwen-VL家庭模型 视频产品。

<a id="exercises"></a>

## 练习

1. 计算M -RoPE 旋转 patch 显示每个带头三对的旋转角度。

2. 10分钟的监控摄像头记录在1 FPS 中, 产生多少个框架? 3x 3 分辨率为 384 度, 总共有多少 tokensQuen2.5-VL的默认 32k 上下文是否处理它?

3. 选择FPS参加30秒的网球比赛 与30秒的配方演示 与30秒的UIagent 记录,用动态FPS逻辑来说明每个目标的正确性

4. Qwen2.5-VL 完全下降了 Q- 格式。 为什么一个简单的 MLP 在 2025 年工作, 而在 2023 年不工作? (提示: 数据比例和大小) encoder 质量.)

5. 分析三支Quen2.5-VL JSON 工具调用输出到 Python dicts. 错误的失败 JSON 以及复苏战略如何 Qwen 厨师本推荐?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| M-RoPE | "Multimodal RoPE" | 3D 旋转位置 embedding 隐藏暗暗处有时间、高度和宽度带 |
| 动态 FPS | "Smart sampling" | Frame sampling 视频的播放率 token budget |
| 绝对时间 token | "Timestamp token" | `<time>t</time>` 序列中断开, 模型看到实际秒而不是框架索引 |
| Window attention | “本地attention” | Spatial self-attention 限于小窗口, 速度; 全局 attention 定期增加 |
| Structured agent 输出 | "JSON mode" | 训练数据监督,教VLM发送可分析 JSON 带有coords 和工具名 |
| min_像素/ 最大_pixels | "解析界限" | Quen2.5-VL 控制器,约束像素总数,因此 token count |
| Grounding | "Point-at-it" | 将捆绑框坐标输出为文本 tokens; 之后使用 Qwen-VL v1 级 |

<a id="further-reading"></a>

## 进一步阅读

- [Bai等人 - Qwen- VL(arXiv:2308.12966)](https://arxiv.org/abs/2308.12966)
- [王等人——Quen2-VL(arXiv:2409.12191)](https://arxiv.org/abs/2409.12191)
- [Qwen 团队-Quen2.5-VL技术报告(arXiv:2502.13923)](https://arxiv.org/abs/2502.13923)
- [Qwen 工作队-Quen3-VL(ARXiv:2511.21631)](https://arxiv.org/abs/2511.21631)
- [Zhu等人——实习生(arXiv:2504.10479)](https://arxiv.org/abs/2504.10479)
