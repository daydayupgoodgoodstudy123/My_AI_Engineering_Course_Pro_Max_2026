---
name: edge-target-picker
description: Pick an edge inference target (Apple ANE, Qualcomm Hexagon, WebGPU/WebLLM, NVIDIA Jetson) and matching quantization format given device, model, and latency budget.
version: 1.0.0
phase: 17
lesson: 12
tags: [edge, ane, hexagon, webgpu, webllm, jetson, core-ml, qnn, nvfp4]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于部署平台(iOS、Android、浏览器、机器人/汽车/边缘服务器),模型和延迟/模拟预算,提出了边缘目标建议。

显示 :

1. 目标。 指定 NPU/GPU 使用平台和2026年运行时间覆盖。
2. 带宽天花板。计算理论解码天花板:带宽_GB_s/ 型号_size_GB. 与用户的拖车/拖车要求相比。如果上限低于要求,则拒绝或提议一个较小的模式/更紧 quantization.
3. Quantization 选择 Q4 GGUF(浏览/浏览) CPU中子 5 , ML INT4 + FP16 (ANE),QNN IN8/INT4(六角),或 NVFP4 + FP8 KV (杰森·索尔/边缘-LLM).
4. 转换管道。 名称 确切的转换器( CORE ML 转换器, Qualcomm AI Hub, 刚果解放运动- 刚果解放运动- 刚果解放运动)LLM 给WebLLM, TensorRT - - - - - - - -LLM 边缘编译器)
5. 背景预算。 说明与该预算相匹配的最大背景 weights 在设备 RAM 中。对于长文本使用实例,请指定 KV quantization 或拒绝。
6. 返回。 当设备不能或 WebGPU 无法使用时( Firefox Android, 旧浏览器) 指定服务器侧面 API 以相同的方式退出 OpenAI- 兼容的接口

艰难的拒绝 :
- 带宽上限以上有希望的托克/秒。拒绝-物理学。
- 2026年,通过非核心ML运行时间直接瞄准ANE。只有核心 ML 以本地方式暴露ANE。
- 假设每个浏览器都使用 WebGPU。 2026 覆盖范围为~ 70- 75% 移动; 总是指定后退 。

拒绝规则 :
- 如果模型大于6GB,目标为电话(4-8GB RAM),则拒绝——提议一个较小的模型或攻击性 quantization first.
- 如果请求在 iPhone 上的 7B 模型上为 128K 上下文, 拒绝 - 没有 Q4 KV 加上滑动窗口设备无法适应 attention.
- 如果部署需要长长的文字 streaming 用户需要 Firefox 支持, 拒绝并要求 Chrome 或服务器备份 。

产出:一页计划命名目标、上限、 quantization,转换器,上下文预算,后退。结尾为单一度量:在目标舰队中最坏情况装置上观察到托克/秒。
