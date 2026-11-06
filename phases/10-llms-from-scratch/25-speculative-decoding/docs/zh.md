<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="speculative-decoding-and-eagle"></a>

# Speculative Decoding 与 EAGLE

> 边界 LLM 生成一个 token 需要一个完整的 forward pass 超过10亿 parameters. 该 forward pass 大部分时候,一个小得多的模式可以猜到下一个3-5 tokens 正确,而大模型只需要 *verify* 猜对了,你才5岁 tokens 以一个的价格。 Speculative decoding (Leviathan等人,2023年)对此作了精确解释,EAGLE-3(2025年)将接受率推至~4.5。 tokens 4-5x 以匹配的产出分布加速。

**类型:** Build
**语言:** Python (与 numpy)
**先修要求:** 第10阶段 课程12Inference 第10阶段第4课(预备培训)GPT)
**时间:** ~75分钟

<a id="the-problem"></a>

## 问题

70B级H100模型的解码量通常为40-80 tokens/秒。 token 需要一个完整的 forward pass 读取全部模型 weights 从 HBM 。 您无法在不修改输出的情况下使模型变小 。 您无法增加 batch size 超出记忆范围。你卡住了——除非你能让模型输出多于一个 token 每 forward pass.

Autoregressive 生成看起来具有内在序列性 : `x_{t+1} = sample(p(· | x_{1:t}))`如果你有一个便宜的预测器说"接下来的4个" tokens 可能是 [a、b、c、d]"你可以确认所有5个位置 **single forward pass 大模型中的** 并接受最长的匹配前缀。

利维坦,卡莱,马提亚斯(2023年) Inference 来自 Transformers 通过 Speculative Decoding")通过一个聪明的接受/拒绝规则 来保持目标模型的精确度 sampling 输出分布相同, 2-4x 更快 。

<a id="the-concept"></a>

## 概念

<a id="the-two-model-setup"></a>

### 双模式设置

- **目标模式** `M_p`: 您想要的大型、 慢速、 高质量模型。 分布 : `p(x)`.
- **模式草案** `M_q`:一个小的、快速的、质量较低的模型。 `q(x)`. 5-30x 小点。

每步 :

1. B. 提议的模式草案 `K` tokens 自动递减 : `x_1, x_2, ..., x_K ~ q`.
2. 目标模型运行 1 forward pass 覆盖全部 `K+1` 平行职位,生产 `p(x_k)` 每项拟议 token.
3. 接受/拒绝 token 左对右通过修改后的拒绝sampling 规则。接受最长匹配的前缀。
4. 如果有的话 token 被否决, 从更正的分布中抽取替换样本并停止。 否则, 将抽取一个奖金 token 来自 `p(· | x_1...x_K)`.

如果草稿与目标完全吻合, 你会得到 K+1 tokens 目标向前。 如果草稿在位置 1 错误, 您只能得到 1 token.

<a id="the-exactness-rule"></a>

### 精确规则

Speculative decoding 是 **分配到 sampling 从p**否决规则:

```
For each drafted token x_t:
    r ~ Uniform(0, 1)
    if r < p(x_t) / q(x_t):
        accept x_t
    else:
        sample replacement from residual: (p - q)+ / ||(p - q)+||_1
        stop
```

where `(p - q)+` 表示点差的积极部分。 当草案和目标一致时( )`p ≈ q`接受率接近1. 当它们不同意时,剩余分配率的计算是为了使整个样本仍然精确 `p`.

**贪婪的案子。** 用于 temperature=0 sampling 只是检查 `argmax(p) == x_t`如果回答为 " 是 " ,则接受;如果否,则产出 `argmax(p)` 停下来。

<a id="expected-speedup"></a>

### 预期的加速

如果模型草案 token- 水平接受率是 `α`,预期 tokens 每个目标forward pass 是:

```
E[tokens] = (1 - α^{K+1}) / (1 - α)        # K = draft length, α in [0, 1]
```

在 `α = 0.8, K = 4`: `(1 - 0.8^5)/(1 - 0.8) = 3.36` tokens 单一目标前方费用 `cost_q * K + cost_p` (K 步骤草案加一个目标核实)。 `cost_p >> cost_q * K` 加速率为 `3.36× / 1 = 3.36×` 已经过关了

唯一真实的 parameter 是 `α`,这完全取决于 草案目标 alignment良好的草案就是一切。

<a id="training-the-draft-distillation"></a>

### 培训草案:提炼

一个随机的小模型会产生一个差的草稿。 标准配方是从目标中蒸馏 :

1. 选择一个小建筑( 70B 目标~ 1B , 7B 目标~ 500M )。
2. 运行目标模型在大文本堆中; 保存下一个 --token 分布。
3. 以 KL 与目标分布的差异( 而不是地面真相) 来训练草稿 tokens).

结果: `α` 通常为0.6-0.8的编码,0.7-0.85的自然语言聊天。

<a id="eagle-tree-drafting--feature-reuse"></a>

### EAGLE: 树形起草+ Feature Reuse

李伟、张张张(2024年),"EAGLE:投机 Sampling 需要重新思考 Feature ) 观察到两个标准效率低下的情况。 speculative decoding:

1. 草案做了K级序列步骤,每个满满的堆放。但草案可以重复目标 features (隐蔽状态)从最近的核查中得出——目标已经计算出草案正从零开始重新提交的丰富的表述。
2. 草案产生线性链条。如果草案能够输出 *tree* 目标对象的单 forward pass 可以通过树平行校验多个候选路径 attention 遮罩,选择最长的被接受 branch.

EAGLE-1 更改 :
- 输入草稿 = 目标位置 t 的最后隐藏状态,而非原始状态 tokens.
- 结构草案=1 transformer decoder 层( 不是一个单独的小模型) 。
- 产出=K树=每深度4至8名候选人,深度4至6

EAGLE-2 (2024年) 增加了动态树的地形学: 在草原不确定的地方, 树会长得更大, 而在有自信的地方则会保持狭小。 提高 。 `α_effective` 但不增加核查费用。

EAGLE-3(Li等人,2025年),“EAGLE-3:扩大规模 Inference 通过训练时间测试加速大语言模型”)删除固定的顶层 feature 草案内容是:与目标的测试时间分布相匹配的产出,而不是教师强制培训分布。 接受率从0.75(EAGLE-2)提高到0.82(EAGLE-3)和平均值 tokens/核查3.0至4.5。

<a id="tree-attention-verification"></a>

### Tree Attention Verification

当起草一棵树时,目标模型将用单一的 forward pass 使用 **tree attention mask** - 一种因果面具,它编码了树的地形,而不是纯线。 token 只有树上的祖先才有。 校验通行证还是向前的, 一个马图姆; 地形遮罩只花几条KV条目。

```
        root
       /    \
      a      b
     / \    / \
    c  d   e   f
```

如果 `a, b` 竞争先...token 候选人和 `c, d, e, f` 是第二个 -token 候选人,所有6个职位都在一个职位内核实 forward pass。产出是任何公认路径上最长的前缀。

<a id="when-it-wins-when-it-doesnt"></a>

### 当它赢,当它不赢

**赢家 :**
- 带有可预测的文字的聊天/完成(代码、通用英文、 structured output). `α` 是高的 高的 高的 高的 高的 高的
- 未使用设置 GPU 在解码过程中计算( 模拟连接阶段) 。 树的起草使用可用的 FLOP 。

**输了/没有赢:**
- 高度随机输出( 高时的创造性写作) temperature). `α` 向着 `1/|vocab|`.
- 批量服务使用非常高的货币——批量已经填满了FLOP,几乎没有树的核查空间。
- 非常小的目标模型 其草稿并不小。

制作店通常报告聊天时2-3x倒数时速,代码生成时速3-5x,创意写作时速接近零。

```figure
speculative-decoding
```

<a id="build-it"></a>

## 动手实现

`code/main.py`:

- 参考文献 `speculative_decode(target, draft, prompt, K, temperature)` 执行准确拒绝规则并核实其维持目标分布(经验KL < 0.01相对于简单目标) sampling).
- 一个EAGLE型的树起草器,用来建造一个带有顶部树枝的深K树。
- 一棵树 attention 制造出正确因果模式的遮罩制造者。
- 接受率 harness 两者都在一个小LM上运行(再用一个) GPT- 小到2个 GPT- 中等目标)

```python
def speculative_step(p_target, q_draft, K, temperature=1.0):
    """One round of speculative decoding. Returns list of accepted tokens."""
    # 1. Draft K tokens
    draft_tokens = []
    q_probs = []
    state = draft_state_init()
    for _ in range(K):
        probs = softmax(q_draft(state) / temperature)
        t = np.random.choice(len(probs), p=probs)
        draft_tokens.append(t)
        q_probs.append(probs[t])
        state = draft_step(state, t)

    # 2. Target computes p at every drafted position + 1 extra
    p_probs_all = target_forward_batched(p_target, draft_tokens, temperature)

    # 3. Accept/reject left-to-right
    accepted = []
    for k, tok in enumerate(draft_tokens):
        r = np.random.uniform()
        if r < p_probs_all[k][tok] / q_probs[k]:
            accepted.append(tok)
        else:
            residual = np.maximum(p_probs_all[k] - q_probs[k], 0)
            residual /= residual.sum()
            accepted.append(np.random.choice(len(residual), p=residual))
            return accepted
    # 4. All K accepted → sample bonus token from target
    accepted.append(np.random.choice(len(p_probs_all[-1]), p=p_probs_all[-1]))
    return accepted
```

<a id="use-it"></a>

## 实际应用

- **vLLM** 和 **SGLang** 船舶头等舱 speculative decoding. 在 vLLM,通过 `--speculative-config` 一个 JSON 对象 `method`, `model`, 和 `num_speculative_tokens`; EAGLE-3 是 `"method": "eagle3"`.
- **NVIDIA TensorRT(荷兰语)LLM** 当地支持美杜莎和埃格勒树
- **参考模型草案**: `Qwen/Qwen3-0.6B` (Quen3-32B草案), `meta-llama/Llama-3.2-1B-Instruct` (草案) Llama (三x70B)。
- **美杜莎头** (Cai等人,2024年,“Medusa:简单” LLM Inference 加速框架, 多位解码头 ” : 而不是一个模型草案, 在目标本身添加 K 平行的预测头 。 要部署更简单, 接受度略低于 EAGLE 。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-speculative-tuning.md` 一种描述目标模式工作量和选择的技能:模型草稿、K(长度草稿)、树宽度、 temperature,以及何时返回到普通解码。

<a id="exercises"></a>

## 练习

1. 执行准确的拒绝规则,并用经验来验证。 `speculative_decode` 和通过平坦的目标 sampling;计算两个输出分布之间的电视距离。应该 < 0.01。

2. 计算加速公式。 给定了 `α` 和 `K`, 需要绘图 tokens 每个目标向前。 找到α { 0. 5, 0. 7, 0. 9} 的最佳 K 。

3. 练一小口草,带一二四米 GPT-2个目标 蒸馏30米 GPT- 100米2个草稿 tokens 与 KL 损失一起计算。 `α` 预期:0.6-0.7。

4. 执行 EAGLE 型树的起草。 使用链条, 将输出草稿放在顶部 3 branches 在每个深度。 构建树 attention 掩码。 验证目标是否接受最长的正确值 branch.

5. 测量失败模式。 在 temperature=1.5 (高度随机性)。显示α崩溃和算法因管理费草案而比普通解码慢。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 目标模式 | "大模型" | 您想要从( p 分布) 中提取的慢、 高质量模型 |
| 草案模型 | "投机者" | 小型快速预测器(q分布);5-30x小 |
| K/ 草稿长度 | "快看,快看" (注: | 推测数 tokens 每张校验通行证 |
| α/接受率 | 击球率 | Per-token 草案提案被接受的可能性 |
| 确切的拒绝规则 | "接受测试" | r < p/q 比较保留目标分布 |
| 剩余分布 | (更正 p -q) | (p - q)+ / ||(p - q)+||_1, 从拒绝时分发到样本 |
| 树的起草 | "疯狂的猜测" | 起草一棵候选人树产出,用树结构在一个通行证中进行核查 attention mask |
| Tree attention mask | "心理面具" | 树的地形编码是因果面具 所以每个节点都只照顾到祖先 |
| 美杜莎头 | "围巾头" | K 额外预测目标本身;没有单独的模型草案 |
| EAGLE feature reuse | 《隐藏状态草案》 | 输入草稿是目标的最后隐藏状态, 不是原始状态 tokens,缩小草稿 |
| 试验时间模拟损失 | "EAGLE-3训练" | 培训与目标测试时间分布匹配的产出草稿,而不是教师强迫 |

<a id="further-reading"></a>

## 进一步阅读

- [莱维坦,卡拉伊,马提亚斯,2023年 Inference 来自 Transformers 通过 Speculative Decoding"](https://arxiv.org/abs/2211.17192) 确切拒绝规则和理论加速分析
- [陈、博尔格奥德、欧文等人,2023年——“加速大语言模型与投机性解释” Sampling"](https://arxiv.org/abs/2302.01318) - 同时推测...sampling 深明时的纸张
- [蔡、李、耿、王、王、朱、道,2024年——“梅杜萨:简单” LLM Inference 带多个解码头的加速框架”](https://arxiv.org/abs/2401.10774) 模式草案的平行头目
- [李伟、张张张 2024年 “Eagle:投机 Sampling 需要重新思考 Feature 不确定性"](https://arxiv.org/abs/2401.15077) — feature 重新使用和植树
- [Li等人,2024年-“EAGLE-2:更快” Inference 使用动态草稿树的语言模型”](https://arxiv.org/abs/2406.16858) - 动态树型学
- [Li等人,2025年-“EAGLE-3:扩大规模” Inference 通过培训时间测试加速大语言模型”](https://arxiv.org/abs/2503.01840) 培训时间测试时间匹配
- [Fu、Haotian、Peng等人,2024年——“打破了对A.A.A.A.A.A.A.A.A.A.的依次依赖。 LLM Inference 利用眼神化身"](https://arxiv.org/abs/2402.02057) - Jacobi/外观解码,无投机者替代
