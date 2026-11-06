<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="embodied-vlas-rt-2-openvla-π0-gr00t"></a>

# 具身 VLA：RT-2、OpenVLA、π0、GR00T

> 模型第一次阅读网站的配方,然后在厨房机器人中执行是RT-2(Google DeepMind,2023年7月)。 tokens并用网络数据加上机器人动作数据共同调制VLM, 并证明网络规模的视觉语言知识传输到机器人控制系统。 OpenVLA (2024年6月) 发送了开放的 7B 参考文件。 物理智能 =0 系列 (2024-2025年) 增加了流量匹配行动专家。 NVIDIA 的 GR00T N1 (2025年3月) 提供了大规模人造机器人的双系统(系统1/系统2) 控制。 虚拟语言行动——视觉语言行动,一种看、读和行动的单一模式——是本阶段的理解模式与第15阶段的自主系统之间的桥梁。

**类型：**学习
**语言:** Python (stdlib, 动作) tokenizer + VLA + VLA 组合键 inference skeleton)
**先修要求:** 阶段12 -05(LLAVA),第15阶段(自治系统,参考)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述动作 tokenization: 离散的 bin 编码 (RT-2), FAST 有效动作 tokens,连续流量匹配动作(%0)。
- 解释一下为什么...fine-tuning 保存普通知识传输到新任务。
- 比较 OpenVLA( 打开 7B) Llama+VLM, 0(流程匹配)和GR00T N1(双系统) 在同一机器人任务上。
- 命名为开放X-Embodiment数据集及其作为RT-X训练资料库的作用。

<a id="the-problem"></a>

## 问题

使用自然语言指令做杂务的机器人自1970年代以来就一直是研究对象。 2020年代回答: 视觉语言动作模型。 VQA 所使用的相同的 VLM 结构, 但输出是动作( 联合火把、 终端效果器的外形、 离散命令) 而不是文本 。

特别困难和困难的挑战:

1. 行动空间是连续的(联合角度、力量)和高维的(7-DOF臂+3-DOF抓抓器=30赫兹时10个暗点)。
2. 专门为机器人设计的训练数据很少。 打开 X- Embodiment 有~ 1M 轨迹; 网络文本图像为 5B+ 。
3. 控制频率很重要 30赫兹控制环 意味着每个动作的预算为330米
4. 安全 错误的行动会损害硬件 人类或财产

<a id="the-concept"></a>

## 概念

<a id="action-tokenization-rt-2"></a>

### Action tokenization (RT-2)

RT-2的把戏: 将每个联合目标作为量化文本表示 token。将已正常化的 [-1, 1] 区域为 256 个文件夹,将每个文件夹映射到 vocabulary ID 10DOF 动作变为 10 tokens 在每个控制步骤。

混合配方的PALM-XVLM:

- 网络图像文本对( 标题, VQA) 。
- 机器人演示, 动作为 tokens.

模型看到"捡起红色立方体"(语言) 图像(视觉)  10token 动作序列( 分解的 联合目标) 。 Web pretraining 保留一般知识的传输:RT-2可以跟随“移动到快速移动的物体”,即使“快速移动”不是在训练数据中。

Inference RT-2纸,受VLM限制 autoregressive decode.

<a id="openvla--the-open-7b-reference"></a>

### OpenVLA - 打开 7B 引用

OpenVLA(Kim等人,2024年6月)是开放的-weights RT-2等值 7B Llama 脊椎, DINOv2 + SigLIP 双视 encoder,动作 tokenization 超过256个垃圾箱

训练使用打开X-Embodiment(970k轨道,横跨22个机器人)。 LoRA fine-tuning 支持适应新机器人。

Inference4 -5 Hz 与 A100 相配 quantization快速到可以慢操作,而不是高频控制

<a id="fast-tokenizer--faster-action-decode"></a>

### FAST tokenizer 加速行动解码

Pertsch等人(2024年)显示,离散环 tokenization 无效- 在小的宾西里区域的大多数行动组。 Tokenizer通过 DCT 压缩动作序列,并对系数进行量化。

30步动作轨迹变为~10 FAST tokens 而不是300个离散电子桶 tokens. Inference 加速3 -5x,没有质量损失。

<a id="π0-and-flow-matching-actions"></a>

### ++0 和流程匹配动作

实物情报=0(Black等人,2024年10月)取代了分散的行动 tokens 配有流程匹配动作专家:

- 小型行动 transformer 读取 VLM 隐藏状态和输出 通过纠正流程的连续50步动作序列。
- 动作头列中流匹配损失; VLM pretraining 保持原样
- Inference:在~ 5 拆卸步骤中释放完全的动作序列,有效控制 50 Hz 。

0的主张:在一系列广泛的操作任务上,比 OpenVLA和Octo要强。连续动作的配方保持了分散摧毁的平稳性。

++0.5和+0-FAST是递增升级。 tokenization 与流量匹配。

<a id="gr00t-n1--dual-system-for-humanoids"></a>

### GR00T N1——人类的双系统

NVIDIA的GR00T N1 (2025年3月)是为人造机器人(>30DOF,全体):

- 系统2:大型VLM读取场景+指令,产生~1赫兹的高层次次级目标。
- 系统1:一个小型行动负责人 transformer 产生低水平的50-100赫兹联合指令,以次级目标为条件。

分布在Kahneman快速慢思维图上的地图:系统2计划,系统1动作。 planning 不妨碍快速控制; 系统1对于潜伏性保持小的状态。

GR00T N1.7(2025年底)改进了数据缩放。 GR00T 微调,使用全尼verse 的模拟到真实的数据。

<a id="open-x-embodiment"></a>

### 打开 X- 弹簧

训练数据。 RT- X (2023年10月) 收集了22个数据集, 覆盖了22个机器人的 1M 轨迹。 打开 X- Embbodiment 是每个人使用的文体 :

- ALOHA/大桥V2/机器人/RT-2厨房/语言表。
- 每个样本:(机器人状态、摄像头视图、指令、动作序列)。
- 训练卫生:统一行动空间, 正常联合射程, 调整摄像头大小 。

OpenVLA 和 0 列车在 Open X- Embodiment 上。 任何特定机器人的域间距由 LoRA fine-tuning 以100 -1000特制演示

<a id="co-fine-tuning-vs-robot-only"></a>

### Co-fine-tuning 仅使用机器人的 vs

Co-fine-tuning 将网络 VQA 数据与机器人轨迹混合。 比例很重要: VQA 太多, 模型忘记动作; 机器人数据太多, 模型失去一般知识 。

RT-2 的比例 :~ 1, 打开VLA :~ 0.5:1 网络对机器人。 +% 0 : 类似 。 精确的比例是 hyperparameter 来调整每个数据集的大小。

仅限机器人的培训产生任务特定模型,但无法按照分配指令进行。fine-tuning 与“从左边取出第三大物体(小词)”的区别。

<a id="safety-and-action-limits"></a>

### 安全和行动限制

每一生产VLA的船舶,其:

- 硬性联合限制(无法反射)
- 速度限制(软剪裁)。
- 工作空间界限( 终端效应器不能离开表格) 。
- Human-in-the-loop 批准新任务

这些是作为控制层检查而置身于VLA之外。 VLA的输出是一个建议,而不是一个命令。

```figure
mm-action-tokens
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 实施256项行动 tokenization 和de-tokenization.
- 快速启动 tokenizer 基于 DCT + quantization.
- Compares token- 跨行的每步数(分流-bin、FAST、连续流)。
- 打印 RT-2  OpenVLA  0  GR00T 的线条摘要。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-vla-action-format-picker.md`。如果执行机器人任务(操纵、导航、人形整体),则在离散电子宾+RT-2、FAST+ OpenVLA、流程匹配+ + + + 0. 或双系统+ GR00T之间取用。

<a id="exercises"></a>

## 练习

1. 10DOF 臂,控制速率为30赫兹。 tokenization 256个垃圾箱中 tokens per second7BVLM能跟上吗?

2. FAST tokenization 压缩30步轨道到~ 10 tokens。如果轨道有高频运动(例如鼓声),用户会失去什么?

3. ~ 0 的流匹配头部 ~ 5 步。 比较输出到 OpenVLA 的 autoregressive 4 -5赫兹解码

4. GR00T 系统1/系统2 向Kahneman 分割地图。 提议另外的分割( 系统3? ) , 这有助于双脚行走 。

5. 读取关于数据集曲线的打开 X- Embodiment 4 节。 请列出防止域泄漏的三种曲线规则 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| VLA | "Vision-language-action" | 图像+指令和输出动作命令的模型 |
| Action tokenization | "分解器" | 将连续的共同目标量化为每平方256个垃圾箱,每个瓦卡 |
| FAST tokenizer | "紧急行动 tokens" | DCT + 量化以压缩30步轨道到~ 10 tokens |
| Co-fine-tune | "混合网络+机器人" | 与机器人演示一起培训网络 VQA 数据,以保存一般知识 |
| 流程匹配动作头 | "=0 连续输出" | 小 transformer 通过纠正流程产生50步行动序列 |
| 系统1/系统2 | "双系统控制" | 大型甚低频热电波计划缓慢,小行动头迅速行动;GR00T型 |
| 打开 X- 弹簧 | "RT-X数据集" | 1M-轨道跨机器人数据集;训练资料 |

<a id="further-reading"></a>

## 进一步阅读

- [Brohan等人——RT-2(arXiv:2307.15818)](https://arxiv.org/abs/2307.15818)
- [Kim等人-OpenVLA(arXiv:2406.09246)](https://arxiv.org/abs/2406.09246)
- [Black等人——0(arXiv:2410.24164)](https://arxiv.org/abs/2410.24164)
- [NVIDIA - NG00T N1(arXiv:2503.14734)](https://arxiv.org/abs/2503.14734)
- [开放 X-Embodiment Collab - RT-X(arXiv:2310.088664)](https://arxiv.org/abs/2310.08864)
