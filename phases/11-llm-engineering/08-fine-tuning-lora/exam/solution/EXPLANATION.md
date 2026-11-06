# AdapterForge 参考讲解

## Part 1

source 行向量公式是 xA→B，A=input×rank、B=rank×output，scale=alpha/rank。loader 保留 A/B；正确 primitive 不替 producer 猜方向。merge 只加一次 A@B，再保留 frozen base+bias。未 merge forward 走因子化残差，完整 base 工作仍在 timer；不能删 base、bias 或后续请求的真实输入。

完整连续 3slow/3fast 实测：慢 1.434830/1.421377/1.076481 秒，快 0.010510/0.010779/0.010943 秒，限值 0.1 秒，余量 10.76/9.14 倍；六次完整输出 hash 一致且独立坐标核对通过。完整证据在 SCOPE 的绝对外部路径。人为宽矩阵/高 rank fixture 只放大重复 dense AB 成本，不是生产 rank 推荐、训练加速或 GPU 性能证据。

## Part 2

正确 GIVEN 本地 LRA1 envelope 声明 UTF8 metadata/payload 长度，完整 framing 仅作 integration guard。metadata 保留 path/input/rank/output，payload 用 binary64 依次 alpha、A、B。decode 校验精确完整长度、shape 所需坐标数和 finite adapter，再按各自宽度还原。exact regression 比较 packed bytes，所以 -0.0、低 mantissa、tiny 值不会被近似相等掩盖。zero B 正常保存。

## Part 3

flat 补足 block，逐 block absmax/7 并 clamp scale 至 1e-8；全负 block 也按最大绝对值定尺度。round ties-to-even 并 clamp [-8,7]。signed code 两个一字节，先 high nibble，奇数末尾 storage-only zero nibble。解码按每 block scale 还原，按原 shape 去 numerical padding，不能在 pad=0 时用 flat[:-0]。这对应 source 均匀整数近似，不是真 NF4；packing 是诚实的本地扩展。

## Part 4

每个 source Adapter 直接用自己的 path 与 archive 编码，交给正确 GIVEN frame，再 yield；下一次输出不能携带此前已发布的 frame。没有先收齐 modules，也不因为 B 全零省略产物。UTF8 字节计数和完整帧解析正确给定，候选负责模块归属与何时可观察。resource wrapper 负责关闭。

## Part 5

先快照原 leaves，对 exact path/final-name 计算选中的 physical ids。不同路径的同名物理层分别处理，根下直接子层与嵌套层都按各自 parent 安装。所有 Linear 冻结；已有 wrapper 也冻结其原 base，并保留 wrapper、base 和 adapter 的对象 identity。每个选中物理 Linear 只 factory 一次，共享 wrapper 安装到全部 aliases。report 分别去重 base 与 adapter identity，同时保留 alias path 列表。merge 每物理 wrapper 使用 P1 已正确 merge 依赖一次，再将所有 alias 替换回同一个 base。source 的 substring 策略在此明确强化为 exact targets，alias 行为是本题小图合同，不冒充 torch 细节。

## 这套题证明了什么，没证明什么

它检查本地矩阵与模块产物合同、数值存储、教学量化、流式边界和物理共享图。没有训练/自动微分/GPU、模型质量、真实 NF4/PEFT 互通、线上时延或真人面试校准证据。
