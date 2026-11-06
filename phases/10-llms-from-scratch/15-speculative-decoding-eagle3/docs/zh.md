<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="speculative-decoding-and-eagle-3"></a>

# Speculative Decoding 与 EAGLE-3

> 第7阶段 · 课程16证明了数学:利维坦拒绝规则保留了核查者的分布。这是2026年生产的训练堆积式视图 speculative decodingEAGLE-3 将模型草案从一个廉价的近似转换成一个专门设计的小型网络,在核查者自己的隐藏状态上培训,然后添加一个训练时间测试循环,使其列车和列车对齐。 inference 结果: 3x至6.5x端到端加速,每token 聊天时高于0.9,没有分配交易。 inference 在2026年的船堆中默认。

**类型:** Build
**语言:** Python (斯迪利布)
**先修要求:** 第7阶段 16(b)speculative decoding 数学,第10阶段 12(inference 优化)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 将利维坦定理在一个句子中说明,并证明投机性循环产生样品时,向核查者同样分布。
- 从香草分解编码(Leviathan 2023)到EAGLE、EAGLE-2和EAGLE-3,历时两年,并列出每个步骤的准确限制。
- 从接收率中计算预期的加速率 `α` 和预发核查费用比率 `c`,并选择最佳的长度草案 `N` 每个制度都适用。
- 从零开始执行全面投机循环: 起草、 校验、 拒绝样本, 滚动 KV cache 被拒后再发奖金 token 完全接受时

<a id="the-problem"></a>

## 问题

Autoregressive 70B模型的解码运行时间可能为35 tokens per second H100 上,我们 GPU 内存带宽是天花板: token 70B的负载 weights 从 HBM 中, 做一个计算步骤, 产生一个浮点。 计算单位大多空闲 。

Speculative decoding 将它变成一个可以真正解决的输送问题。 `N` tokens 在 `N` 小 forward passes。验证器在前缀上运行过一次,加上全部 `N` 草稿。 如果核查员的分布位置 `i` 我们同意草案(从统计意义上说,我们将作出精确的判断),我们接受;如果不同意,我们拒绝对剩余分布进行校正,并对之进行抽样。 `N+1` accepted tokens 而不是一个。

关键理论是利维坦、卡尔曼、马提亚斯(ICML 2023):产出分布与 sampling 直接从验证器上可以产生。 不是大约。 完全相同。 这是全部原因 speculative decoding 在生产中可以接受——这是一种纯潜伏优化,没有质量上的权衡。

第七阶段 · 16课给了你什么数学。 这个课给你的就是训练堆。 一个好的草稿比一个便宜的草稿值2x多。 EAGLE, EAGLE-2和 EAGLE-3 (Li等人,2024-2025年) 将“草稿 ” = 同一模型的较小版本” 转变成一个精确的工程学科。 2026年的生产 inference 服务器默认为 EAGLE-3 。

<a id="the-concept"></a>

## 概念

<a id="the-invariant-leviathan-rejection-sampling"></a>

### 贪婪者:利维坦拒绝 sampling

Let `p(t)` 是下一个版本的草稿 token 给出了前缀, 并 `q(t)` 做个核对员 试一份草稿 token `d ~ p`。以概率接受 `min(1, q(d) / p(d))`。在拒绝时,从剩余分布中提取样本 `(q - p)_+ / ||(q - p)_+||_1`所采集的样本按照 `q`。无论多么糟糕,这是真的 `p` 更糟糕的是,你拒绝的次数越多,但产出仍然精确。

Stack `N` 使用一个核查器将这些电话回过头来 forward pass 在 `prefix + d_1 + ... + d_N`。核查者返回 `q_1, q_2, ..., q_{N+1}` 左转向右走,在位置上第一次拒绝 `j`,样本来自 `residual(q_j, p_j)` 完全接受后,试一试奖金 token 来自 `q_{N+1}`.

<a id="what-determines-speedup"></a>

### 加速比由什么决定

Let `α` 是每份草案的预期接受率 token。让我们 `c = cost(draft) / cost(verifier)` 是成本比率。 tokens 每个前置核查器为:

```
E[accepted] = (1 - α^(N+1)) / (1 - α)
```

预计每个接受的隔离墙总时间 token 是 `(N * c + 1) / E[accepted]`尽量缩小这一影响 `N` 你得到甜蜜的地方。 `α = 0.8, c = 0.05`: 优化 `N` 大约5 -7,加速为3.2x。 `α = 0.95, c = 0.02`: 优化 `N` 大约8 -10,加速推进5x。

最大的杠杆是 `α`。从 `α = 0.6` (香草草案)至 `α = 0.9` (EAGLE-3) 固定 `N = 5` 取自2.2预期被接受 tokens 每个核查者向4.1. 同一核查者提供将近2x的通过量。

<a id="the-two-year-progression"></a>

### 两年的进度

**香草投机(Leviathan,2023年)。** 草案模式是经过独立培训的较小部分 LLM 从同一个家庭。 `α ≈ 0.6`,在最多2x左右加速。

**EAGLE-1(李等人,2024年)。** 潮流是小的 transformer 通常是一至两层,将核查员的最后一个隐藏状态作为输入并预测下一个 token 因为草案看到核查员的 feature 表示,它的分布 更接近核查者的。 `α` 升至0.7-0.8。

**EAGLE-2(李等人,2024年)。** 添加动态草图: 而不是建议单个序列 `N` tokens,提出一棵小树的候选人,每人得分 forward pass (树 attention长度草案将逐步适应。 `α` 接受的路径 token 攀升到0.85以上。

**EAGLE-3(李等人,2025年,NeurIPS)。** 再来两个,首先,放下 featureEAGLE-1/2对草稿进行了培训,以与核查员隐藏的状态匹配,后者对数据有多大帮助作了限制。 token 第二,培训时间测试(TTT):在培训阶段,将草案本身先前的预测反馈到多个步骤上作为投入。 inference。这样可以对列车和测试分布进行对齐,并停止错误累积。测量速度:聊天时达到6.5×,64批中达到38%的输送量改进 SGLang H100号公路

<a id="kv-cache-rollback"></a>

### KV cache rollback

验证延伸验证器 KV cache 通过 `N` 在一个关卡中输入。如果拒绝发生于位置 `j`,缓存内容通过位置 `j-1` 现在错了。 两个常见的执行: 写入一个抓取缓冲和 commit (b) 接受(或接受)vLLM特索瑞特, 特索瑞特... ...LLM),或保留一个物理 KV cache 加上逻辑长度,在拒绝时截断。 rollback 成本是每层人均一字节,可忽略不计,与前方通行费用相邻。

EAGLE-2 树搜索,验证程序运行 attention 工程学是平坦的,但计算是标准的闪光attention 用自定义的面具打电话

<a id="draft-architectures-in-2026"></a>

### 2026年结构草案

| 策略 | 草稿类型 | `α` | 加速比 | 培训费用 |
|----------|-----------|-----|---------|---------------|
| Vanilla | 分开小 LLM | 0.55-0.70 | 1.8-2.3× | 无(再使用现有的小模型) |
| 美杜莎 | 验证器上的额外 LM 头 | 0.65-0.75 | 2-3× | ~ 1B 键 SFT tokens |
| EAGLE-1 | 1级 transformer 隐藏状态 | 0.70-0.80 | 2.5-3× | ~60B tokens |
| EAGLE-2 | EGOLE-1 + 动态树草 | 0.80-0.88 | 3-4× | ~60B tokens |
| EAGLE-3 | Multi-layer feature 聚变+ TTT | 0.88-0.92 | 3.5-6.5× | ~60-200B tokens |
| 前瞻 | 无草稿( Jacobi 迭代) | 不适用 | 1.3-1.6× | 无 |

在2026年的生产中: vLLM 和 SGLang 默认值为 EAGLE-3, 如果可用的话, EAGLE-2 。 TensorRT-LLM 拥有梅塔和NVIDIA公共模型最快的美杜莎路径。 llama.香草船 CPU 部署。

```figure
l5-spec-decode-eagle
```

<a id="build-it"></a>

## 动手实现

See `code/main.py`。这是全利维坦的投机循环,包括所有作品:N草案、校验平行通行证、按位置拒绝、剩余 sampling, 奖金 token, KV rollback,并用经验核实输出分布是否与直接输出匹配 sampling 来自 `q`.

<a id="step-1-the-rejection-rule"></a>

### 第1步:拒绝规则

```python
def accept(q_prob, p_prob, u):
    if p_prob <= 0:
        return True
    return u < min(1.0, q_prob / p_prob)
```

<a id="step-2-residual-distribution"></a>

### 步骤2：残差分布

```python
def residual(q, p):
    raw = [max(0.0, qi - pi) for qi, pi in zip(q, p)]
    s = sum(raw)
    if s == 0:
        return list(q)
    return [r / s for r in raw]
```

<a id="step-3-a-full-speculative-step"></a>

### 步骤3:一个完全推测的步骤

该 `spec_step` 函数草稿 `N` tokens 来自 `p`,然后同时核对 `q` evaluation. 每项草案 token 它应用了拒绝规则,在第一次拒绝时,它从残留物中提取了更正。如果所有东西都接受,它会发放奖金 token 来自 `q_{N+1}`.

<a id="step-4-kv-rollback-bookkeeping"></a>

### 步骤4:科索沃核查团 rollback bookkeeping

模拟器跟踪逻辑 `kv_length` 每一工人在被接受时 `k` 草稿 `kv_length += k`。在位置上拒绝 `j`,缓存已被写入过去 `j`,但逻辑长度被设定为 `prefix_length + j + 1` - 一经更正 token。随后读取的文字与逻辑长度脱节。

<a id="step-5-the-leviathan-check"></a>

### 步骤5:利维坦检查

运行5万个猜测步骤。 计算被接受的实验分布 tokens与50 000个直接样本相比, `q`。 奇平方统计应该处于关键值之下, 理论在实际中流传。

<a id="step-6-speedup-vs-α"></a>

### 步骤6:加速对α

通过扰动清除草稿质量 `p` 远离 `q` 在不同的振幅上,测量 `α`,然后期待绘图 tokens 每个核查员的呼叫 `α` 和 `N`。代码打印一个表格,显示 EAGLE-3 类草稿质量(EAGLE-3)`α ≈ 0.9`解锁 4 -5 tokens 每个核查员的电话。

<a id="use-it"></a>

## 实际应用

Production-level `vllm serve` 与 Eagle-3 :

```bash
vllm serve meta-llama/Llama-3.3-70B-Instruct \
  --speculative-config '{
    "model": "yuhuili/EAGLE3-LLaMA3.3-Instruct-70B",
    "num_speculative_tokens": 5,
    "method": "eagle3"
  }'
```

SGLang EAGLE-3在H100第64批:比EAGLE-3号纸上的第64批香草解码法增加约1.38x。

何时可以达到 speculative decoding:

- 任何交互式聊天工作量,如果第50页的延迟时间比最高输送量重要的话。
- 代码生成和 structured output (JSON, SQL). `α` 高于0.9,因为目标分布非常可预测。
- 长式(千) tokens摊还式的加速支付一直支付。

当不:

- 非常小的模型( < 3B)。 草案并不比核查者便宜得多。
- 少量批量-1 CPU 模型草案的内存管理可能不值得。
- Very-high-temperature creative sampling where `α` 崩溃 。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-eagle3-tuner.md`。如果有的话 inference 工作量(模型, batch size目标潜伏,任务配置, 它建议一个猜测 -decoding strategy 和调试 parameters (家庭草案, `N`,树深, temperature- 注意交换)

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认利维坦分配检查的奇夸尔统计,在50 000个样本中,该数据低于95%的关键值。

2. Sweep `N` 1至10岁 `α` 执行情况,第0.9和5.8段 `c` 预计于2004年4月10日举行 tokens 每个核查员的通话时间和实际的墙上时间 token。查找 `N` 尽量缩短墙壁时间,解释曲线的形状。

3. 修改代码以模拟 EAGLE-2 树搜索: 在每一步, 草案都提出一个形状树 `[2, 2, 2]` (8个候选路径) 验证器运行一次, 最高概率的路径获胜 。 计算 `α` 每叶和总数 tokens 与线性链分解编码比较,以等量计算。

4. 执行批量 KV rollback 两个并行序列的模拟器。 序列 A 已接受全部草稿; 序列 B 将拒绝 位置 2 显示正确 `kv_length` 按顺序更新,且不浪费任何工作。

5. 读读EAGLE-3文件第4节(培训-时间测试),用两句话解释为什么没有TT的幼稚培训草案会受到暴露偏差的影响,以及为什么在培训期间将自己的预测反馈给它。sampling 文献,后二类。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 利维坦规则 | 分钟(1, q over p) | Bernoulli 接受/拒绝可能性 `min(1, q(d)/p(d))`中,当您在拒绝时从剩余数据中抽取样本时,将保留验证器的分布 |
| 剩余分布 | "(q减去p)加, 正常化" | `(q - p)_+` 在零时被夹住,并重新整顿——从拒绝处向样本正确分配 |
| 接受率 | "怎么经常的草案是正确的" | 预期每 -token Bernoulli 在拒绝规则下的成功概率; 调节所有加速数学 |
| EAGLE-1 | "隐藏状态的草稿" | Tiny transformer 草案以核查员最后一层隐藏状态为条件(Li等人,2024年) |
| EAGLE-2 | "活性树草" | EAGLE-1 加上一棵树,用树来评分 attention 在一个验证器出入证中 |
| EAGLE-3 | "训练时间测试" | 放下枪 feature- 输了,直接上火车 token 在培训期间,用草稿预测自己的产出 |
| 培训时间测试(TTT) | "接触偏差修正" | 在培训期间自动调整草稿,使培训和测试输入分布相匹配—— 直接比照排定的 sampling |
| KV rollback | "未否决的草稿" | 重置验证器的簿记 KV cache 拒绝后被接受的前缀长度 |
| Bonus token | "自由的" | 当所有 `N` 接受草稿, 从 `q_{N+1}` 无需额外核查费用 |
| Tree attention | "立即核实许多候选人" | Attention 带有非因果面具,尊重树草的地形;计算 `q_i` 树上每一节点 forward pass |

<a id="further-reading"></a>

## 进一步阅读

- [利维坦、卡尔曼、马提亚斯——快速 Inference 来自 Transformers 通过 Speculative Decoding (arXiv:2211.17192,ICML 2023)](https://arxiv.org/abs/2211.17192) - 基础文件和等同理论
- [Chen等人——加速使用投机性大语言模型 Sampling (arXiv:2302.01318) (单位:美元)](https://arxiv.org/abs/2302.01318) - 具有干净证据的并行独立介绍
- [Li等人——EAGLE:投机性 Sampling 需要重新思考 Feature 不确定性(arXiv:2401.15077)](https://arxiv.org/abs/2401.15077) - EAGLE-1, 隐藏状态条件的草稿
- [李等人——EAGLE-2:更快 Inference 具有动态草稿树的语言模型(arXiv:2406.16858)](https://arxiv.org/abs/2406.16858) - 动态树搜索
- [Li等人——EAGLE-3:扩大规模 Inference 通过培训时间测试加速(arXiv:2503.01840, NeurIPS 2025)](https://arxiv.org/abs/2503.01840) - 2026年生产违约
- [Cai等人-Medusa:多重解码头(arXiv:2401.10774)](https://arxiv.org/abs/2401.10774) - 备选的无草案办法
- [vLLM Speculative Decoding documentation](https://docs.vllm.ai/en/latest/features/spec_decode.html) - 装有所有战略的金币生产参考
