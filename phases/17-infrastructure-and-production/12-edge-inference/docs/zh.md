<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="edge-inference--apple-neural-engine-qualcomm-hexagon-webgpuwebllm-jetson"></a>

# 边缘 Inference：Apple Neural Engine、Qualcomm Hexagon、WebGPU/WebLLM、Jetson

> 边缘端的核心限制是内存带宽，而非计算能力。移动设备 DRAM 的带宽为 50–90 GB/s，数据中心 HBM3 则达到 2–3 TB/s，相差 30–50 倍。解码受内存带宽限制，因此这一差距具有决定性影响。2026 年主要有四条路线。Apple M4/A18 Neural Engine 峰值为 38 TOPS，采用统一内存，无需在 CPU 与 NPU 之间复制数据。Qualcomm Snapdragon X Elite / 8 Gen 4 的 Hexagon 达到 45 TOPS。WebGPU + WebLLM 在 M3 Max 上运行 Llama 3.1 8B（Q4），速度约为 41 tok/s，约为原生性能的 70–80%；拥有 17.6k 个 GitHub stars、兼容 OpenAI 的 API，移动设备覆盖率约 70–75%。NVIDIA Jetson Orin Nano Super（8GB）可容纳 Llama 3.2 3B / Phi-3；AGX Orin 通过 vLLM 运行 gpt-oss-20b，速度约为 40 tok/s；Jetson T4000（JetPack 7.1）为 AGX Orin 的 2 倍。TensorRT Edge-LLM 支持 EAGLE-3、NVFP4 和 chunked prefill，Bosch、ThunderSoft、MediaTek 在 CES 2026 展示了相关方案。

**类型:** 学习
**语言:** Python (stdlib, 玩具带宽带宽解码模拟器)
**先修要求:** 阶段17 -04(内部维修引擎),阶段17 -09(生产) Quantization)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么移动 LLM inference 是一个内存带宽,计算为次要。
- 列出四个边缘目标(Apple ANE、Qualcomm 六边形、WebGPU/WebLLM、NVIDIA Jetson),并将每个目标与使用大小写匹配。
- 说明2026年WebGPU覆盖缺口(Firefox Android追赶)和SafariiOS 26登陆。
- 选一个 quantization 每一目标格式( ANE 的Core ML INT4 + FP16, 六角的QNN INT8/INT4, 浏览器的WebGPU Q4, Jetson Thor的NVFP4)

<a id="the-problem"></a>

## 问题

客户想要一个在网上安装的聊天机: 语音第一, 逐个默认, 运行在离线上。 在一个 MacBook Pro M3 Max, Llama 3.1 8B Q4 运行时~ 55 吨/秒——罚款。在 iPhone 16 Pro 上,同一模型运行时为 3 吨/秒——不罚款。在 中程安卓, 带 松鼠 8 GEN 3 、 7 吨/秒。 在浏览器中,通过 WebGPU 运行于 Chrome Android v121+, 4-8 吨/秒,视设备而定。

输送量差异不是一个移植问题。 quantization 格式倍数 : NPU 是否可从用户空间访问。 边缘 inference 2026年,四个不同的问题 四个不同的解决方案。

<a id="the-concept"></a>

## 概念

<a id="bandwidth-is-the-real-ceiling"></a>

### 带宽是真正的天花板

解码读全套 weights 用于每 token。Q4中的一种7B模型是3.5GB。读取3.5GB50GB/秒需要70毫秒——理论上限为~14吨/秒。在90GB/秒(高端移动 DRAM)时,上限移动到~25千兆秒。计算数量没有帮助低于此数字。

3个肺结核点的HBM3数据中心在1.2毫秒内清除3.5GB,最高值为830吨/秒。 weights。不同的记忆子系统。

<a id="apple-neural-engine-m4--a18"></a>

### 苹果神经引擎(M4/A18)

- 最多38个托普。CPU AnE和ANE共用同一个游泳池)——没有副本。
- 通过核心 ML + 访问 `.mlmodel` 编译模型,或通过金属性能形状 PyTorch.
- Llama.cpp 金属后端直接使用MPS,而不是ANE;本地ANE需要核心 ML 转换。
- 2026年iOS应用程序的最佳实用路径:核心 ML INT4 weights + FP16 启动。

<a id="qualcomm-hexagon-snapdragon-x-elite--8-gen-4"></a>

### 六角形(Snapdragon X Elite / 8 Gen 4)

- 至多45个 CPU 和 GPU 位于 SoC 中,但单独存储域。
- QNN(质子神经网络) SDK AI 枢纽提供转换 PyTorch/ONNX.
- 聊天模板, Llama 3.2 Phi-3 所有船舶作为一流的文物 都在AI 枢纽上

<a id="intel--amd-npus-lunar-lake-ryzen-ai-300"></a>

### 英特尔/AMD NPUs(伦纳尔湖,Ryzen AI 300)

- 软件落后于苹果/夸康; OpenVINO正在改进,但有特殊性。
- 最佳 Windows ARM 联合驾驶应用程序; 本地端第一的 AMD/ Intel 桌面上原版 。

<a id="webgpu--webllm"></a>

### WebGPU + WebLLM

- 通过 WebGPU 计算阴影器在浏览器中运行模型; 没有安装 。
- Llama 3.1 8B Q4,在M3 Max上为~41吨/秒——大约70-80%的本地人通过同一后端。
- 17.6k GitHub 网络LWM上的恒星; OpenAI- 符合《联合提交的材料》 API; Apache 2. 0 。
- 2026年的覆盖率:铬和甲状腺V121+,Safari iOS 26 GA,Firefox和甲状腺仍在赶上。总体而言,流动覆盖率~70-75%。

<a id="nvidia-jetson-family"></a>

### NVIDIA Jetson家庭

- 奥林纳诺超级( 8GB): 适合 Llama 3.2 3B,Phi-3 托克/秒。
- AGX Orin: 运行 gpt- 20b 穿过 vLLM 以~40吨/秒的速度。
- Tor/T4000 (7.1吉他包): AGX Orin 性能, EAGLE-3 和 NVFP4 支持。
- 特森拉特边缘LLM (2026)支持EAGLE-3 speculative decoding, NVFP4 的组合键 weights, chunked prefill 数据中心优化已移到边缘。

<a id="quantization-choice-per-target"></a>

### Quantization 每个目标的选择

| 目标 | 格式 | 注释 |
|--------|--------|-------|
| 苹果ANE | INT4 weights + FP16 激活 | 核心 ML 转换路径 |
| 六边形 | QNNINT8/INT4 国家通信网 | AI 枢纽转换器 |
| WebGPU/ WebLLM 网络GPU/网络LLM 网络GPU/网络LLM 网络GPU/网络LLM 网络GPU/网络LLM 网络GPU/网络LLM | 刚果解放运动(q4f16)_1) | 使用 `mlc_llm convert_weight` + 编译 `.wasm`; GGUF 不支持 |
| 杰特森·奥林·纳诺 | Q4GUF或TRT - 调制LLM INT4 | Memory-bound |
| 杰特森AGX/索尔 | NVFP4 + FP8 千伏 | Edge-LLM path |

<a id="the-long-context-trap-on-edge"></a>

### 边缘的长方形陷阱

Llama 3.1 的 128K 上下文是一个数据中心 feature。在8GB 内存、4GB 模型+ 2GB的电话上 KV cache 32K 的 现金 tokens + OS 上方操作系统= OOM。 边缘部署将环境保持在4K-8K, 除非有攻击性 KV quantization 接受(问题4KV)。

<a id="voice-is-the-killer-app"></a>

### 声音是杀手应用程序

Voice agents 具有潜伏感( 第一级) token < 500毫秒. 当地 inference 完全消除网络的延迟。 与语音对文本( 语音涡轮变体在边缘运行) 和边缘合并 inference 成为生产质量的语音循环。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 苹果M4/A18ANE:38吨。
- 奎康六角SDXELIT: 45吨
- WebLLM M3 最大值:~ 41 吨/秒 Llama 3.1 8B 问题4。
- AGX 硬质:~ 40 吨/秒 gpt- 20b 穿过 vLLM.
- 数据中心-边缘带宽差距:30-50x。
- WebGPU 移动覆盖:~70-75%(火化和机器人落后)。

```figure
edge-bandwidth-pipe
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 计算由带宽数学组成的跨边缘目标的理论解码通过量上限。与观察到的基准和亮点相比,带宽(不计算)是瓶颈。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-edge-target-picker.md`。 给定平台(iOS/Android/browser/Jetson),模型和延迟/模拟预算,选择 quantization 格式化和转换管道。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。对于在Q4中用于Sapdragon 8 Gen 3 (~77GB/s带宽)的7B模型,计算解码天花板。与观察到的6-8吨/秒相比,运行时间效率如何?
2. 使用 Android 的 WebGPU 需要 Chrome v121+。 为旧浏览器设计一个后退, 服务器侧面通过相同 OpenAI-compatible API.
3. 您的iOS 应用程序需要 4K 字符串 streaming。哪种模型/格式组合可以使您在iPhone 16上保持4GB活性内存?
4. 杰特森 AGX Orin 运行 gptJetson Nano只配3B 如果产品同时瞄准目标,如何统一 inference stack?
5. 问一下"网络LLM在2026年是否已经准备好生产了" 查查报道范围,表演情况,还有Firefox Android的缺口

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| ANE | "树脂神经引擎" | M系列和A系列的在线设计 NPU;统一内存 |
| Hexagon | "Qualcomm NPU" , 翻译: | 松鼠核电联;QNN SDK 供查阅 |
| WebGPU | "browser GPU" | W3C 标准浏览器 GPU API;铬/Safari 2026年 |
| WebLLM | "browser LLM runtime" | MLC-LLM 项目;Apache 2.0; OpenAI- 符合《联合提交的材料》 |
| Jetson | "荷兰语边缘" | 奥林纳诺/AGX/托尔/T4000家庭 |
| 特伦特边缘...LLM | "尖尖的天文笔" | 2026 边端的天索拉特-LLM; EAGLE-3 + NVFP4 组合键 |
| 统一内存 | "共享池" | CPU 和 NPU 查看相同的内存; 上面没有复制 |
| Bandwidth-bound | "模拟有限" | 以字节/秒读取方式解码 weights |
| 核心ML | "苹果转换" | ANE 本地模型的苹果框架 |
| QNN | "Qualcomm堆叠" | 质子神经网络 SDK |

<a id="further-reading"></a>

## 进一步阅读

- [On-Device LLMs 2026年联邦州](https://v-chandra.github.io/on-device-llms/) 景观和基准。
- [南印度群岛](https://developer.nvidia.com/blog/getting-started-with-edge-ai-on-nvidia-jetson-llms-vlms-and-foundation-models-for-robotics/) -奥林/AGX/索尔
- [NVIDIA 登索拉特边缘LLM](https://developer.nvidia.com/blog/accelerating-llm-and-vlm-inference-for-automotive-and-robotics-with-nvidia-tensorrt-edge-llm/) - 2026年边缘港口公告
- [WebLLM( arXiv: 2412.15803)](https://arxiv.org/html/2412.15803v2) 设计和基准。
- [苹果核心 ML](https://developer.apple.com/documentation/coreml) ANE - 本地转换。
- [农业中心](https://aihub.qualcomm.com/) 六角形的预变型号
