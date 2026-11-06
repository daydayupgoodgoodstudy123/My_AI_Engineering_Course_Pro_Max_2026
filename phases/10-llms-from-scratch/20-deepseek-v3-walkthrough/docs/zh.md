<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="deepseek-v3-architecture-walkthrough"></a>

# DeepSeek-V3 架构详解

> 第10阶段 课程14 在每个开放模式转弯时都指定了6个建筑把手。 DeepSeek-V3 (2024年12月,671B) parameters 总计,37B 活动) 翻转全部 6 并增加 4 个: 多头 中 Attention辅助无损负载平衡,多 -Token 预测和双管道培训。 DeepSeek-V3的建筑从上到下,每个 parameter 计算所公布的配置。 到最后, 您可以解释为什么671B/ 37B比率是正确的赌注, 以及为什么 MLA+ MoE 一起在边境打斗

**类型:** 学习
**语言:** Python (斯迪利布, parameter 计算器)
**先修要求:** 第10阶段 · 14(开放式步行),第10阶段 · 17(NSA),第10阶段 · 18(MTP),第10阶段 · 19(双人形)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 读 DeepSeek-V3 向上向下配置,并用六个词来解释每个字段 GPT- 2个把手加4个 DeepSeek- 具体增加。
- 产生总数 parameter 计数( 671B), 活动 parameter 计数 (37B) , 和对每个相助的组件 。
- 计算 KV cache 与GQA的同一活性极密模型相比,在128k背景下的司法协助足迹。
- 说明四 DeepSeek- 具体创新(MLA、MTP、无附带损失路线、DualPipe),以及建筑/培训中每个目标堆放的编号。

<a id="the-problem"></a>

## 问题

DeepSeek-V3是第一个开放的前沿模型 其结构与 Llama 家庭。 Llama 3 405B为 "GPT- 6个把手转动。" DeepSeek-V3是 -没错 -V3 is GPT- 6个把手加4个 Llama 3 配置为 a warmup 阅读 DeepSeek 配置, 但深层结构 - 形状 attention 区块,路线逻辑, 训练时间的目标—— 足够不同了,你需要一个单独的行进。

学习的回报是: DeepSeek- V3开着...weights 释放改变了开放模型中“ 前沿能力” 的含义。 建筑是2026年训练运行的蓝图正在复制。 理解它就是任何触及边际角色的表格基本要求 LLM 训练或 inference.

<a id="the-concept"></a>

## 概念

<a id="the-invariant-core-again"></a>

### 变幻无常的核心

DeepSeek-V3还在 autoregressive。它仍然堆叠 decoder 每个街区仍然有 attention 加上 MLP 加上 2 RMSNorms。它仍然使用 SwiGLU 在MLP中。 它仍然使用 RoPE. 规范前。 Weight- 被绑住了 embeddings。与每个 Llama 或 Mistral.

<a id="the-twist-mla-instead-of-gqa"></a>

### 转折:司法协助而不是GQA

从第10阶段 14 你知道GQA缩小 KV cache 将 K 和 V 共享到各组的Q 头。 Attention 更进一步:K和V被压缩成一个共同的低级潜在代表机构。 `kv_lora_rank`,然后击退每个人的头在苍蝇上。 KV cache 仅储存潜伏—— 通常为512个浮点 token 每个层,不是8 x 128 = 1 024 个浮标。

在128k 上下文, DeepSeek- V3加上司法协助(一个共同的潜在 `c^{KV}` 每 token 每一层; K 和 V 都来自这种通过高射线产生的潜伏, 可以吸收到随后的垫层中 :

```
kv_cache = num_layers * kv_lora_rank * max_seq_len * bytes_per_element
         = 61 * 512 * 131072 * 2
         = 7.6 GB
```

假设的GQA基线(Llama 3 70B形状,8 KV头, 低温128)将支付:

```
kv_cache = 2 * 61 * 8 * 128 * 131072 * 2
         = 30.5 GB
```

司法协助比a小4倍 Llama-3 -70B-风格的 GQA 缓存, 位于 128 k 上下文 。

权衡:司法协助还增加了每例减压步骤。 attention 计算( per head) 。 与所保存的带宽相比, 额外计算数量较小 。 长文本净赢 inference.

<a id="the-routing-auxiliary-loss-free-load-balancing"></a>

### 路线:无损附带负载平衡

MoE 路由器决定哪一位顶级专家处理 token。一个天真的路由器把太多的工作集中在少数专家身上,使其他人闲置。标准修补:加上一个辅助性损失术语,惩罚负载失衡。这起作用了,但稍微降低了主任务性能。

DeepSeek-V3引入了一个无附带损失计划。在路由器中增加了每个专家的偏差术语 logits,在训练期间按简单规则调整:如果是专家 `e` 超载, 减少 `bias_e`;如果装载不足,则增加。没有额外的损失期。训练保持干净。专家工作量保持平衡。

对主要损失的影响:无可计量。 MoE 建筑:清洁,无附带损失 hyperparameter 来调音

<a id="the-mtp-denser-training--free-draft"></a>

### MTP:更密集的培训+免费的草稿

从第10阶段开始 18岁 你知道 DeepSeek-V3 添加 D=1 MTP 模块,以预测 token 前面有两处位置 inference中,经过培训的模块被重新定位为具有80%+接受度的推测解码草稿。在培训中,每个隐藏状态都以D+1=2目标为对象,提供更密集的信号。

Parameters14B 在671B主干线之上。管理费:2.1%。

<a id="the-training-dualpipe"></a>

### 培训:双层平台

从第10阶段到第19阶段,你知道双向管道是一条双向管道, 与横交节点的全对全通讯相重叠。 DeepSeek-V32 048-H800级, 大约回收了245k GPU-1F1B会输给管道泡的时数

<a id="the-config-field-by-field"></a>

### 配置, 按字段排列

这是... DeepSeek- V3 配置( 简化) :

```
hidden_size: 7168
intermediate_size: 18432   (dense MLP hidden size, used on first few layers)
moe_intermediate_size: 2048 (expert MLP hidden size)
num_hidden_layers: 61
first_k_dense_layers: 3    (first 3 layers use dense MLP)
num_attention_heads: 128
num_key_value_heads: 128   (formally equal to num_heads under MLA, but
                           the real compression is in kv_lora_rank)
kv_lora_rank: 512          (MLA latent dimension)
num_experts: 256            (MoE expert count per block)
num_experts_per_tok: 8      (top-8 routing)
shared_experts: 1           (always-on shared expert per block)
max_position_embeddings: 163840
rope_theta: 10000.0
vocab_size: 129280
mtp_module: 1               (1 MTP module at depth 1)
```

分析出来 :

- `hidden_size=7168`: embedding 维度。
- `num_hidden_layers=61`:总区块深度。
- `first_k_dense_layers=3`:前3个区块使用厚度为18432的MLP。其余58个区块 MoE.
- `num_attention_heads=128`:128个查询对象。
- `kv_lora_rank=512`:K和V被压缩到这个潜伏的维度,并按每个头部进行压抑。
- `num_experts=256, num_experts_per_tok=8`: 每个 MoE 街区有256名专家 上八号公路
- `shared_experts=1`:除了256名路由专家外,每1名始终在任的专家 token。 把它当作一个能确保每个 token 得到一些可靠的东西。
- `moe_intermediate_size=2048`:每个专家的 MLP 隐藏大小。比密度大的 MLP 小, 因为有256个。

<a id="parameter-accounting"></a>

### Parameter accounting

完全计算寿命 `code/main.py`标题 :

- Embedding: `vocab * hidden = 129280 * 7168 = ~0.93B`.
- 前三个密区块: attention 具有司法协助(~144M/每块)+密度高的多管点(~260M/每块)+规范。
- 58 MoE 区块 : attention + 共用专家(30M)+ 规范。 总计 ~ 7.95B ,包括所有专家。 MoE 区块。
- MTP单元:14B。

总计:核心建筑~476B+14B MTP+显著的已公布的671B数字构成额外的结构 parameters (百分数) tensors计算器中复制的数字在出版物的3-5%之内——三角洲来自精细的会计。 DeepSeek报告附录第2节。

Active parameters 前进时间 :

- Attention:每层144米 * 61 = 8.8B(所有层火力)。
- 活性 MLP: 前3层密度(3层) * 260海里=780海里,58海里 MoE 每个活动层有8条路由+1条共享路由 + 路由管理 。每个活动层运行 MLP:~260M。 总计: 3 * 260海里+58 * 260米=~15.9B。
- Embedding + 规范:1.2B。
- 活动总数:约26B核心+14BMTP(经过培训但并非总能运行到 inference≈37B。

<a id="the-671b--37b-ratio"></a>

### 671B/37B比率

18倍宽度比率(活性参数占总数的5.5%)。 DeepSeek-V3是最稀少的边界 MoE 已经打开的模型 weights混合型8x7B,按13/47比率计算(28%)密度要高得多。 Llama 4 马弗里克(17B/400B)(4.25%)比率是相当的。 DeepSeek 赌注:在前沿,更多启动率较低的专家使每个活性氟化物的质量更高。

<a id="where-deepseek-v3-sits"></a>

### Where DeepSeek-V3坐着

| 模型 | 总计 | Active | Ratio | Attention | 新颖的想法 |
|-------|------|-------|-------|-----------|-------------|
| Llama 3 70B 电话: | 70B | 70B | 100% | GQA 64/8 | — |
| Llama 4 马弗里克 | 400B 资源 | 17B号 | 4.25% | 质量保证局 | — |
| 混合 8x22B | 141B | 39B 部队 | 27% | 质量保证局 | — |
| DeepSeek V3 | 671B | 37B | 5.5% | 司法协助512 | MLA + MTP + 无重力+双管道 |
| Qwen 2.5 72B号 | 72B | 72B | 100% | GQA 64/8 | YaRN 扩展 |

<a id="the-follow-on-r1-v4"></a>

### 后续行动:R1,V4

DeepSeek-R1 (2025年) 是V3主干线上的推理训练。 R1 使用相同的结构。 改变的是训练后配方( 关于可核实任务的大规模RL), 而不是 pretraining 结构。

DeepSeek-V4(如果其船舶)预计将保留司法协助+ MoE + MTP和增加每日生活津贴(DeepSeek Sparse Attention17. 血统是稳定的:建筑层面的创新积累;每个版本都转换额外的把手。

```figure
moe-routing
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是该 parameter 专用计算器 DeepSeek-V3的形状。运行它,将其输出与纸张的数字进行比较,然后将其用于假设变体(256名专家对512名专家对512名专家对最高16名专家对1024名专家)。

需要关注的内容：

- Total parameter 与公布的671B的比较。
- Active parameter 编号与公布号37B。
- KV cache 在128k上下文中——MLA对GQA的比较。
- 逐层细分,以查看 parameter 预算实际上已经取消。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-deepseek-v3-reader.md`。给定 DeepSeek- 家庭模型(V3、R1或任何未来的变体),产生一个逐个组成部分的架构,读取配置的每个字段的名称 parameter 按构成部分分列的数字,并查明 DeepSeek- 模型使用的具体创新。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。比较计算器的总和 --parameter 估计已公布的671B,并标明三角洲的来源。

2. 修改配置,使用司法协助排名256,而不是512。 KV cache 以 128 k 的上下文为单位。 它会买到多少百分比的减值, 以及以什么代价来计算每个头部的表达性 ?

3. Compare DeepSeek- V3的(256名专家,8名顶级专家)路线改为假设式(512名专家,8名顶级专家)。 parameters 增长; 活动 parameters 保持原样。在理论上,额外的专家能力能买到什么? inference?

4. 读取第2.1节 DeepSeek- V3 关于司法协助的技术报告(arXiv:2412.19437)。 inference- 时间效率

5. DeepSeek-V3在大多数操作中使用FP8培训。计算储存671B的 FP8 和 BF16 的内存节余 weights。这如何与14.8T --token 培训预算?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| MLA | "多头的中风 Attention" | 将 K 和 V 压缩为共享的低级潜伏( kv)_lora_等级,一般为512, 减少每个头部的心压; KV cache 仅存储隐藏 |
| kv_lora_rank | "MLA 压缩暗淡" | K 和 V 的共享潜伏体大小; DeepSeek-V3 使用512 |
| 第一个 k 稠密层 | 浅层保持密度 | 头几个 MoE- 模型层跳过 MoE 路由器,运行密度高的 MLP 以保持稳定 |
| num_experts_每_tok | "Top -k routing" (Top -k 路由) | 每架有多少路由专家失火 token; DeepSeek- V3 使用 8 |
| 共享专家 | 常有专家 | 处理每一问题的专家 token 无论路线如何; DeepSeek- V3 使用 1 |
| 辅助性无损失路线 | “Bias调整后负载余额” | 在培训期间调整了专家偏差术语,以平衡专家工作量,而不增加损失术语 |
| MTP 模块 | "超前预言" | Transformer 从h^(1)和E(t+1)中预测 t+2的块; 更密集的培训、 自由投机性解码草稿 |
| DualPipe | "双向输油管" | 前向/后向计算与横交节点全对齐的培训时间表 |
| Active parameter ratio | "平等" | active_参数/共计_参数; DeepSeek- V3点击5.5% |
| FP8培训 | "八位训练" | 培训储存和许多计算操作在FP8中;以低质量成本将记忆量减半 |

<a id="further-reading"></a>

## 进一步阅读

- [DeepSeek- 亚历克斯 DeepSeek-V3技术报告(arXiv:2412.19437)](https://arxiv.org/abs/2412.19437) 完整的结构、培训和成果文件
- [DeepSeek- V3 电磁波 model card 抱住脸](https://huggingface.co/deepseek-ai/DeepSeek-V3) - 配置文件和部署说明
- [DeepSeek- V2纸(arXiv:2405.04434)](https://arxiv.org/abs/2405.04434) - 介绍司法协助的前身
- [DeepSeek-R1纸(arXiv:2501.12948)](https://arxiv.org/abs/2501.12948) - V3结构的推理培训后继者
- [原生粗糙 Attention (arXiv:2502.11089)](https://arxiv.org/abs/2502.11089) 未来方向 DeepSeek- 家庭 attention
- [DualPipe 仓库](https://github.com/deepseek-ai/DualPipe) 培训时间表参考
