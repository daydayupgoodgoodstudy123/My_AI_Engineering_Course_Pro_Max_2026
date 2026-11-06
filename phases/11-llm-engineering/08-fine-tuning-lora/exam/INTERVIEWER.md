# 面试官手册：AdapterForge（11/08）

计时期间不展示。开场 2 分钟，五关 12、12、12、10、12 分钟，合计 60；未经真人校准。候选人边做边解释，允许查文档。卡住约 5 分钟后一次给一级提示。

## 澄清问题标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | A/B 方向？ | "Use row vectors: A is input by rank, B is rank by output." |
| 1 | scale 与 merge？ | "Use alpha/rank; merging the same adapter twice leaves its output unchanged." |
| 1 | base 在计时内吗？ | "Yes. This is a complete dense base-plus-bias-plus-residual forward request." |
| 2 | 精度？ | "Preserve every binary64 bit, including negative zero and low mantissa bits." |
| 2 | 全零 B？ | "It is a valid initialized adapter, with shape and metadata intact." |
| 3 | 是真正 NF4 吗？ | "No. Implement the source uniform integer teaching approximation, with explicit nibble packing." |
| 3 | rounding/padding？ | "Use ties-to-even rounding, a 1e-8 scale floor, and remove only padding beyond the original shape." |
| 4 | framing 需要写吗？ | "The correct UTF8 framing primitive is supplied; publish each module's own complete artifact." |
| 5 | alias target？ | "Any matching alias selects that physical layer; install one shared wrapper at all its aliases." |
| 5 | exact target？ | "A target matches either a complete path or the exact final leaf name, never a containing substring." |

## Part 1 加载、forward、merge（12 分钟）

坑：
- loader 交换 A/B，矩形输入经 forward→lora_forward→正确 matmul 在 producer 外两次调用报真实 ValueError。不要改坏 consumer 或加假 IndexError。
- alpha 漏除 rank；非单位 alpha/r 与非零 base bias 共同验证。
- 第二次 merge 又累加 update，破坏幂等和 base identity。
- 每 input 重建 dense A@B；源公式本来允许先 xA 再乘 B。性能必须保留完整 dense base+bias+residual 和全部输出。

人为压力 fixture 384×512/r192 仅放大重复 AB 成本，不是实用 rank 推荐或训练加速结论。参数仍少于原 dense；所有必要计算在 timer。完整连续三慢 1.434830/1.421377/1.076481 秒、三快 0.010510/0.010779/0.010943 秒，限值 0.1 秒，双侧余量 10.76/9.14 倍；每次都保留全部 512 输出，六次完整 payload hash 一致且独立坐标 oracle 通过。证据 `/tmp/exam-11-16-work/draft11-08/timing-group1`。

H1 "Which matrix reached the failing primitive?" H2 "What changes after the second merge?" H3 指向方向、scale、merge 状态与因子化公式。追问：zero B 是否允许跳过 base？（不允许，base 与 bias 仍有意义。）

## Part 2 二进制产物（12 分钟）

坑：
- 二进制 float32 或展示四舍五入会丢低 mantissa/tiny 值；signed zero 也属于本题 exact payload。
- A 与 B 是两个不同矩形，shape 与 module path/alpha 要一起还原；读取时不能用默认 alpha 代替已保存值。
- zero B 是合法初始化状态；不等于未保存的 adapter。header/metadata/payload 必须完整且无 trailing bytes。

正确 UTF8 metadata/header envelope GIVEN，候选主责是 binary64 A/B/alpha 与各自 shape；多语与完整边界只作 integration guards。H1 "Which fields define this saved module?" H2 "Which coordinate bits must survive?" H3 指向 binary64 payload 与 shape 合同。追问：能声称 torch interchange 或 crash-atomic 吗？（不能，这只是声明的本地格式。）

## Part 3 uniform signed-int4（12 分钟）

坑：
- 每个 block 自己 absmax/7，零 block 用 1e-8 floor，不能共享 tensor scale。全负 block 也按绝对值最大幅度定 scale，不能取带符号的 max。
- nibble 是 signed [-8,7] 且 high-first；source absmax quantizer 通常不产生 -8，但公开 codec 仍要支持它。
- round 是 ties-to-even，int 截断会偏；原始 shape 决定只去最后 numerical padding，完整最后 block 不能删。

H1 "Which values share one scale?" H2 "How is a negative nibble represented?" H3 指向 per-block/code/extent 三个职责。追问：为何不叫真 NF4？（source 实际均匀 int8 近似没有分位数 codebook，本题仅加 nibble packing。）

## Part 4 module frames（10 分钟）

坑：
- module path、A/B、rank、alpha 属于当前完成模块，不能沿用第一模块或跨模块共享可变累积状态；每次输出恰好一份当前产物，不重发之前的 frame。
- zero B 仍输出完整 artifact，不能按残差非零才保存。
- 当前模块完成即 yield，再拉未来模块；正确 close wrapper 给定。

UTF8 字节长度/frame 与 P2 codec 正确依赖给定；多语、精度和 close 只作 integration guards，不再当主考。H1 "Who owns this snapshot?" H2 "When is this completed module observable?" H3 指向单模块产物。追问：这是不是 PEFT wire protocol？（不是，独立保存 adapter 的本地流式工程扩展。）

## Part 5 module graph（12 分钟）

坑：
- exact leaf/full path 不能退化为 substring，q_proj 不包括 q_projection。
- 遍历原 leaves 快照，不进入新 wrapper 重复注入；已有 wrapper 保留。不同物理层可以同名，完整路径不能被 leaf 名去重；根下直接子层和嵌套层都要正确安装。
- shared physical layer 只有一份参数/adapter，但保留所有 alias paths；每个 wrapper merge 一次后在全部 alias 恢复同一个 base。外部给定 existing wrapper 的 base 也要冻结，wrapper/base/adapter 原对象不能被替换。

H1 "Is that a path or a physical module?" H2 "Which nodes existed before replacement?" H3 指向原节点快照与物理 identity。追问：与 torch 的 named_modules 是否完全等同？（不声称，本题明示 alias 语义的小图合同。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，原测试通过即得 |
| 调试方法 | 20 | traceback 到 producer、矩阵数据验证、逐层修复 |
| 代码质量 | 15 | 必要输出与精度保留、命名与状态清楚、无死代码 |
| 沟通 | 15 | 主动澄清方向、精度、量化语义与 alias 合同 |
| 工程判断 | 10 | 说明压力 fixture、uniform/NF4和本地格式边界 |

没观察到的写“未观察”。提示、变绿时间与原 60 分钟成绩分开记录。
