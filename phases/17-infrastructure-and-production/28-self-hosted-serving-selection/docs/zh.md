<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="self-hosted-serving-selection--matching-engine-to-hardware-and-scale"></a>

# 自托管服务选型：让引擎匹配硬件与规模

> 引擎选择是硬件、规模和生态系统的函数,而不是读取的首版。 inference 2026年: llama. . . . . . . . 奥拉马, vLLM, SGLang,在维护模式下,TGI跟踪。 **llama.cpp** 开得最快 CPU 最广泛的模式支持,全面控制 quantization 和线。 **Ollama** 是否安装 dev-patto 单命令, ~ 15- 30% 慢于 llama.cpp(Go+CGo+) HTTP 连续处理),3x排量缺口 在类似推进式负荷下。 **TGI 进入维护模式 2025年12月11日** - 只有错误修正,~10%的原始输送速度比 vLLM 历史顶端 observability 维护状况使它成为风险的长期赌注—— SGLang 或 vLLM 是对新项目更安全的默认值。 **vLLM** 是指普通用途生产默认值——v0.15.1 (2026年2月)加上 PyTorch 2.10,RTX Blackwell SM120, H200优化。 **SGLang** 是该 agentic 多转/前缀重专家——400 000+ GPUs 生产(xAI, LinkedIn, Cursor, Oracle, GCP, Azure, AWS)。 硬件限制: CPU- 材 ̇ llama.cpp.AMD/非荷兰 vLLM 是最强的支撑路径( TRT-)LLM 2026年管道模式:dev = Ollama, 中转= llama.cpp, 试卷= vLLM 或 SGLang引擎不同 weight 格式 - GGUF 用于 llama.cpp家庭,HF安全阀 GPU 引擎——因此格式转换可能处于两个阶段之间。

**类型:** 学习
**语言:** Python (干燥,发动机决定树漫步器)
**先修要求:** 17阶段所有课程,包括引擎(04、06、07、09、18)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 选择给定的引擎硬件( T)CPU /AMD/NVIDIA Hopper/Blackwell,规模(1个用户/100/10 000)和工作量(一般聊天/ agent / 长文本)。
- 命名2026 TGI维护模式状态( 2025年12月11日), vLLM 或 SGLang.
- 描述管道的变形/调节/推进,包括GGUF-安全度格式转换处于两个阶段之间。
- 解释原因 "CPU- 头一点 llama.cpp和“AMD”不包括TRT-(TRT)LLM.

<a id="the-problem"></a>

## 问题

你的团队开始一个新的自我托管 LLM 一位工程师说,奥拉玛,另一位工程师说 vLLM第三个是“TGI不是在盒子里工作吗?” 所有三个都适合不同的环境。没有一个是对所有的人都是对的。

2026年,选择树很重要:硬件一号,规模二号,工作量三号。2025年的一个具体事件——TGI进入维护模式12月11日——改变了新项目的默认值。

<a id="the-concept"></a>

## 概念

<a id="the-five-engines"></a>

### 五个引擎

| Engine | 最适合 | 注释 |
|--------|----------|-------|
| **llama.cpp** | CPU /边缘/最小偏差/最广泛的模型支持 | 最快的开 CPU,完全控制 |
| **Ollama** | Dev 膝上型计算机,单用户,单指令安装 | 15-30%慢于 llama.cpp; 3x 预测输送缺口 |
| **TGI** | 高频生态系统、受监管行业 | **维护模式 2025年12月11日** |
| **vLLM** | 普通用途生产,100+用户 | 粗体生产默认;v0.15.1 2026年2月 |
| **SGLang** | Agentic 多轮,前置重工作量 | 400,000+ GPUs 生产中的 |

<a id="hardware-first-decision"></a>

### 硬件第一决定

**CPU-first** → llama奥拉玛也工作但速度慢,没有别的引擎能竞争 CPU.

**AMD GPU** → vLLM 是最强的支持路径( AMD ROCm 支持)。 SGLang 也有用 TRT...LLM 被NVIDIA锁住了,所以它出来了。

**NVIDIA 霍珀(H100/H200)** → vLLM 或 SGLang 或 TRT - 系统LLM三个顶级的

**NVIDIA Blackwell (B200 /GB200) 国家人口调查局** → TRT-LLM 生产量的领先者(17 ° 07)。 vLLM 和 SGLang 紧跟着

**苹果硅( M 系列)** → llama.cpp(金属),奥拉马包起来了

<a id="scale-second-decision"></a>

### 比额表第二决定

**1个用户/ 本地 dev** 奥拉玛,一个命令,第一个...token 几秒钟。

**10 100个用户/小团队** → vLLM single-GPU.

**100-10k 用户/生产** → vLLM 生产堆叠(第17阶段 · 18)或 SGLang.

**10k+ 用户/企业** → vLLM 生产堆叠+分类(第17阶段 · 17)+ LMCAche(第17阶段 · 18)

<a id="workload-third-decision"></a>

### 工作量-第3项决定

**一般性聊天/ A** → vLLM 普遍违约赢

**Agentic 双转形 planning, 内存)** → SGLang以 RADISAttention (17 ° 06 阶段) 为主 。

**RAG 具有重的前缀再利用** → SGLang.

**代码生成** → vLLM fine; SGLang 缓存上的情况稍好一点

**长上下文( 128K+)** → vLLM + chunked prefill; SGLang + 分层KV。

<a id="the-tgi-maintenance-trap"></a>

### TGI 维护陷阱

抱住脸 TGI 输入维护模式 2025年12月11日, 只有错误修正继续。 历史: 顶层 observability、最高级高频生态系统整合(model cards安全工具),稍落后 vLLM 以生的量来计算

对于2026年的新项目: 默认退出 TGI。 现有的 TGI 部署可以继续, 但最终应该迁移 。 SGLang 和 vLLM 更安全默认值。

<a id="the-pipeline-pattern"></a>

### 管道模式

德夫(奥拉马)llama.cpp)      (prod) (vLLM发动机使用不同 weight 格式 - GGUF 用于 llama.cpp家庭,HF安全阀 GPU 引擎——因此格式转换可能处于两个阶段之间。工程师在膝上型电脑上快速循环;播放镜像制作 quantization; 标注是服务目标。

<a id="ollama-caveat"></a>

### 奥拉马语警告

奥拉玛对德夫来说是件好事, HTTP 连号化增加了间接费用,货币管理比 vLLM, OpenTelephy 支持时滞。 使用 Ollama 显示它的位置—— 一个用户, 一个命令( 命令) , 然后切换到 vLLM 用来共享

<a id="self-hosted-vs-managed-is-a-separate-decision"></a>

### 自我托管与管理是单独决定

阶段17 · 01(管理高压器), · 02(inference 平台) 管理。 这个课程假设您已经决定了 自我主机。 自我主机的原因: 数据居住性、 自定义微调、 规模总成本所有制、 托管时无法使用的域模型 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- TGI维护模式:2025年12月11日。
- vLLM v0.15.1:2026年2月; PyTorch 2.10; 支持Blackwell SM120。
- SGLang 生产足迹:400 000+ GPUs.
- 奥拉马输量差距对 llama.cpp: 减速15-30%; 中文本不需修改。

```figure
data-parallel
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个决策树行走者:给定硬件+比例+工作量,选择引擎并解释原因。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-engine-picker.md`。鉴于各种制约因素,选择一个引擎并撰写迁移计划。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 输出是否与您的直觉相符?
2. 下方是12H100和8MI300XAMD 什么引擎?LLM 离开桌子?
3. 2026年,一个团队想使用TGI 因为"这是我们所知道的" 来解释一下移民的案子
4. 奥拉马·德夫 vLLM 专业: 变化 quantization、配置和 observability?
5. RAG 使用P99前缀长度8K和高再利用度的租户。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| llama.cpp | "该 CPU one" | 最广泛的模型支持, 最快的 CPU |
| Ollama | "笔记本电脑" | 单命令安装, dev-grade 传输 |
| TGI | 高频服务 | 自2025年12月以来的维护模式 |
| vLLM | "默认" | 2026年广泛生产基准 |
| SGLang | "该 agentic one" | 前置重, 半偏移 |
| TRT-LLM | "NVIDIA-locked" | 布莱克威尔输油管头目,仅荷兰国家投资公司 |
| GGUF | "llama. cpp 格式" | 捆绑的 K 量变体 |
| Production-stack | "vLLM K8s" | 阶段17 - 18次参考部署 |
| 管道模式 | "dev→stage→prod" | 奥拉马 llama. cpp vLLM; weight 格式每个引擎不同 |

<a id="further-reading"></a>

## 进一步阅读

- [AI 制造工具 vLLM 与奥拉马对立 llama.cpp 与 TGI 2026 的比较](https://www.aimadetools.com/blog/vllm-vs-ollama-vs-llamacpp-vs-tgi/)
- [墨菲 - - 麦克 llama.cpp 与 Ollama 2026 的比较](https://www.morphllm.com/comparisons/llama-cpp-vs-ollama)
- [第1款a-全面性 LLM Inference 引擎比较](https://explore.n1n.ai/blog/llm-inference-engine-comparison-vllm-tgi-tensorrt-sglang-2026-03-13)
- [普雷马伊-10名最佳 vLLM 2026年替代品](https://blog.premai.io/10-best-vllm-alternatives-for-llm-inference-in-production-2026/)
- [维护公告](https://github.com/huggingface/text-generation-inference) - 发条
- [vLLM v0.15.1 发号说明](https://github.com/vllm-project/vllm/releases)
