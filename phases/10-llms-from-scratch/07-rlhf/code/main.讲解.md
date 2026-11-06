# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 07 节 RLHF：奖励模型 + PPO ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；依赖仓库目录结构，从 `../../04-pre-training-mini-gpt/code/main.py` 导入模型组件） ｜ **依赖**：`numpy`（第三方）；`sys`、`os`（标准库）；无需 GPU、无需网络。

---

## 1. 这份代码在考察什么

这份代码用 NumPy 搭出 RLHF 三阶段流水线的骨架：

1. **偏好数据**：6 组 `(prompt, preferred, rejected)` 三元组，rejected 体现啰嗦、含糊、不精确等毛病。
2. **奖励模型（RM）**：复用 MiniGPT 的 Transformer 主体，把词表大小的输出头换成一个标量头，取最后一个位置的隐藏状态打分。
3. **Bradley-Terry 损失**：`−log σ(r_chosen − r_rejected)`，以及成对准确率。
4. **KL 散度**：策略与冻结参考模型在每个位置上的分布差异。
5. **"PPO" 循环**：采样回复 → RM 打分 → 减去 β·KL → 更新策略。
6. **评估**：比较 SFT 与 RLHF 策略生成内容的平均奖励、KL 是否越界。

> 一句话：**RLHF = 用成对偏好训练一个打分器，再在 KL 约束下让策略去追高分**。但请注意：本文件中 RM 的梯度是错的、PPO 的"更新"是随机噪声、RM 训练与打分的输入格式不一致——代码展示的是流程的"形状"，而不是能工作的算法。看清这些差距，比看懂代码本身更有价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `from main import MiniGPT, LayerNorm, Embedding, TransformerBlock` | 导入 | 复用第 04 节组件 | 共享 Transformer 主体 |
| `PREFERENCE_DATA` | 常量 | 6 组偏好三元组 | 偏好数据 |
| `RewardModel` | 类 | Embedding → 4 个 block → `ln_f` → 取最后位置 → 点乘标量头 | 奖励模型 |
| `tokenize_for_reward` | 函数 | `prompt + [0] + response` 的字节序列 | RM 输入格式 |
| `sigmoid` | 函数 | 分正负两支的数值稳定 sigmoid | σ 函数 |
| `bradley_terry_loss` | 函数 | `−log(σ(Δ) + 1e-8)` | BT 损失 |
| `train_reward_model` | 函数 | 逐对前向、算 loss / 准确率、（错误地）更新标量头 | RM 训练 |
| `compute_kl_divergence` | 函数 | 两组 logits → softmax → 逐位置精确 KL → 平均 | KL 惩罚 |
| `generate_response` | 函数 | 带 temperature 的自回归采样 | 策略 rollout |
| `copy_model_weights` | 函数 | 逐个数组 `.copy()`，从 SFT 复制到策略与参考模型 | 初始化策略 / 冻结参考 |
| `ppo_training` | 函数 | 采样 → 打分 → KL → `reward − β·KL` → 随机扰动 FFN | PPO（极度简化） |
| `compare_models` | 函数 | 两个模型各自生成，用 RM 打分对比 | 评估 |
| `__main__` | 脚本入口 | Stage 1 → Stage 2 → RM 评估 → Stage 3 → 对比 → KL 分析 | 三阶段流水线 |

数据流：`PREFERENCE_DATA` → `tokenize_for_reward` → `RewardModel.forward` → `bradley_terry_loss` → 更新 `reward_head`；随后 `sft_model` → `copy_model_weights` → `policy_model` / `reference_model` → `generate_response` → `RewardModel.forward` + `compute_kl_divergence` → 噪声更新 → `compare_models`。

---

## 3. 逐段精讲

### 3.1 导入与偏好数据

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "04-pre-training-mini-gpt", "code"))
from main import MiniGPT, LayerNorm, Embedding, TransformerBlock
```

- 与第 06 节相同的技巧：把第 04 节的 `code/` 放到搜索路径最前面。同样存在"两个 `main.py`"的陷阱：在别的脚本里 `import main` 加载本文件会触发循环导入错误，需要用 `importlib` 以别名加载（我们写验证脚本时就是这样做的）。导入的 4 个名字都有用：`MiniGPT` 用于 SFT / 策略 / 参考模型，`Embedding`、`TransformerBlock`、`LayerNorm` 用于拼装 `RewardModel`。

```python
PREFERENCE_DATA = [
    {
        "prompt": "What is the capital of France?",
        "preferred": "The capital of France is Paris.",
        "rejected": "France is a country in Europe. It has many cities. The capital is Paris. Paris is known for the Eiffel Tower.",
    },
    ...
]
```

- 每条是一个字典，三个键对应讲义中的 `(prompt, winner, loser)`。
- 各对 preferred / rejected 的字符数：31/109、71/68、18/116、29/105、27/123、126/109。**有 4 对 preferred 比 rejected 短得多**——这是一个长度混杂因素：RM 可能学到"越短越好"，而不是"更准确、更直接"。真实标注数据中常见的是反方向的长度偏差（偏好更长），本质相同（见测验 Q10、Q15）。

### 3.2 奖励模型

```python
class RewardModel:
    def __init__(self, vocab_size=256, embed_dim=128, num_heads=4, num_layers=4, max_seq_len=128, ff_dim=512):
        self.embedding = Embedding(vocab_size, embed_dim, max_seq_len)
        self.blocks = [TransformerBlock(embed_dim, num_heads, ff_dim) for _ in range(num_layers)]
        self.ln_f = LayerNorm(embed_dim)
        self.reward_head = np.random.randn(embed_dim) * 0.02

    def forward(self, token_ids):
        seq_len = token_ids.shape[-1]
        mask = np.triu(np.full((seq_len, seq_len), -1e9), k=1)

        x = self.embedding.forward(token_ids)
        for block in self.blocks:
            x = block.forward(x, mask)
        x = self.ln_f.forward(x)

        last_hidden = x[:, -1, :]
        reward = last_hidden @ self.reward_head
        return reward
```

形状追踪（B = 1，S ≤ 128，D = 128）：

| 步骤 | 形状 |
|------|------|
| `token_ids` | `(1, S)` |
| `embedding.forward` | `(1, S, 128)` |
| 4 个 block + `ln_f` | `(1, S, 128)` |
| `x[:, -1, :]` | `(1, 128)`：只取最后一个位置 |
| `@ reward_head`（形状 `(128,)`） | `(1,)`：每条序列一个标量 |

- 结构与 `MiniGPT.forward` 完全一样，只是最后一步从 `x @ token_embed.T`（得到 `(1, S, 256)` 的 logits）换成了 `x[:, -1] @ w`（得到一个标量）——这就是讲义说的"把 LM 头换成标量头"。
- **为什么取最后一个位置**：因果 mask 下只有最后一个位置看过全部 token。
- ⚠️ 讲义说 RM 应"Take the SFT model"初始化；这里是**独立随机初始化**，且后面只训练标量头，Transformer 主体相当于固定的随机特征提取器。
- ⚠️ `Embedding` 只有 128 行位置编码，输入超过 128 个 token 会报广播错误，所以调用方必须截断（见 3.3）。

### 3.3 RM 的输入格式与截断

```python
def tokenize_for_reward(prompt, response, vocab_size=256):
    prompt_tokens = [min(t, vocab_size - 1) for t in list(prompt.encode("utf-8"))]
    response_tokens = [min(t, vocab_size - 1) for t in list(response.encode("utf-8"))]
    return prompt_tokens + [0] + response_tokens
```

- 用字节 0（NUL）作 prompt 与 response 的分隔符；`min(t, 255)` 对字节值是空操作。
- 训练时 `preferred_tokens[:max_seq_len]` 截到 128。我们实测 12 条序列中有 **7 条**超长（134–155 个 token）：第 1、3、4、5 对的 rejected，以及第 6 对的两条。截断后最后一个 token 往往落在半个单词上，例如 `"...known for the E"`、`"...might be aro"`、`"...in the mid-1"`。RM 只看最后一个位置，等于在给"被腰斩的回复"打分。
- ⚠️ **训练 / 推理格式不一致**：`ppo_training` 和 `compare_models` 把 `prompt_tokens + 生成的 token` 直接送进 RM，**没有中间的分隔符 0**，属于 RM 从未见过的输入格式。

### 3.4 sigmoid 与 Bradley-Terry 损失

```python
def sigmoid(x):
    return np.where(
        x >= 0, 1.0 / (1.0 + np.exp(-x)), np.exp(x) / (1.0 + np.exp(x))
    )

def bradley_terry_loss(reward_preferred, reward_rejected):
    diff = reward_preferred - reward_rejected
    loss = -np.log(sigmoid(diff) + 1e-8)
    return loss
```

- **两支写法**：x ≥ 0 时用 `1/(1+e^{−x})`，x < 0 时用 `e^x/(1+e^x)`，两者数学上相等，但各自只对"不会溢出"的那一侧求指数。
- ⚠️ `np.where` 会**先把两支都算出来**再挑选，所以对很大的 |x| 仍会触发 `RuntimeWarning: overflow encountered in exp`（我们用 `x = −1000` 实测出现了警告），只是被选中的那一支结果正确。真正无警告的写法是用布尔索引分别计算，或直接用 `scipy.special.expit`。
- `+ 1e-8` 防止 `log(0)`；更稳定的写法是 `np.logaddexp(0, -diff)`（即 softplus(−Δ)），在 Δ 很负时也不会损失精度。
- 数值：Δ = 0 → loss = ln 2 ≈ 0.6931；Δ = 1 → 0.3133；Δ = −1 → 1.3133；Δ = 2 → 0.1269。

### 3.5 RM 训练循环（⚠️ 梯度错误）

```python
            r_preferred = rm.forward(preferred_ids)[0]
            r_rejected = rm.forward(rejected_ids)[0]
            loss = bradley_terry_loss(r_preferred, r_rejected)

            if r_preferred > r_rejected:
                epoch_correct += 1

            diff = r_preferred - r_rejected
            grad = sigmoid(diff) - 1.0

            rm.reward_head -= (
                lr * grad
                * rm.ln_f.forward(rm.embedding.forward(preferred_ids))[:, -1, :].flatten()
            )
```

- `grad = σ(Δ) − 1` 是 `d loss / dΔ`，这一步是对的，且恒为负（loss 总希望 Δ 变大）。
- 正确的标量头梯度是 `(σ(Δ) − 1) · (h_p − h_r)`，其中 `h` 是**经过全部 block 和 `ln_f`** 的最后位置隐藏状态。代码有两处错误：
  1. `rm.ln_f.forward(rm.embedding.forward(...))` **跳过了 4 个 Transformer block**，用的是"最后一个 token 的 embedding + 位置 embedding"再做 LayerNorm；
  2. **只用了 chosen 一侧**，漏了 `− h_r`。
- 后果：`w` 被不断推向"chosen 序列末尾 token 的 embedding 方向"。实测 10 个 epoch 后 `reward_head` 的变化范数只有 0.02（初始范数 0.25），准确率从 4/6 到 5/6；改用正确梯度（同样 lr = 1e-4）可以达到 6/6。
- 准确率是在**更新之前**统计的（先判断 `r_preferred > r_rejected`，再更新），所以每个 epoch 报告的是"该 epoch 开始时附近"的准确率。
- 训练集 = 评估集：`__main__` 的 "Reward Model Evaluation" 用的还是这 6 对数据，没有 held-out 集，83.3% 不代表泛化能力。讲义练习 2 要求加入 4 对新数据检验。

### 3.6 KL 散度

```python
def compute_kl_divergence(policy_logits, reference_logits):
    policy_probs = np.exp(policy_logits - policy_logits.max(axis=-1, keepdims=True))
    policy_probs = policy_probs / policy_probs.sum(axis=-1, keepdims=True)
    policy_probs = np.clip(policy_probs, 1e-10, 1.0)
    ... # ref_probs 同理
    kl = np.sum(policy_probs * np.log(policy_probs / ref_probs), axis=-1)
    return kl.mean()
```

- 对每个位置分别做 softmax，得到 `(1, S, 256)` 的两组分布；`np.sum(..., axis=-1)` 得到每个位置的 `KL(π ‖ π_ref)`，形状 `(1, S)`；`.mean()` 对所有位置平均。
- `np.clip(…, 1e-10, 1.0)` 防止 `log(0)`，但 clip 后分布不再严格归一化（影响极小）。
- 这是**精确 KL**（对整个词表求和），而 RLHF 实现中通常用采样 token 上的估计 `log π(y_t) − log π_ref(y_t)`，计算更省。
- ⚠️ 对 `response_ids` 的**所有位置**（包括 prompt 部分）求平均。RLHF 只关心策略在回复部分的行为，KL 应只在生成的 token 上计算，并按序列求和后加到奖励里。

### 3.7 生成与权重复制

```python
def copy_model_weights(source, target):
    target.embedding.token_embed = source.embedding.token_embed.copy()
    ...
    for s_block, t_block in zip(source.blocks, target.blocks):
        t_block.attn.W_q = s_block.attn.W_q.copy()
        ...
```

- 逐个数组 `.copy()`，保证策略、参考模型与 SFT 模型**不共享内存**：之后修改策略不会影响参考模型。如果写成 `target.x = source.x`（不 copy），三个模型会共用同一块数组，KL 将永远是 0。
- 手写逐字段复制很脆弱：新增参数（如注意力 bias）时容易漏掉。生产中用 `copy.deepcopy(model)` 或 `state_dict` 加载。
- `generate_response` 与第 06 节相同：每步对最多 128 个 token 的上下文完整前向一次，温度采样，固定生成 `max_new_tokens` 个 token，没有停止条件。

### 3.8 "PPO" 训练（⚠️ 只是随机噪声）

```python
        response_tokens = generate_response(policy_model, prompt_tokens, max_new_tokens=20, temperature=0.8, ...)
        response_ids = np.array(response_tokens[:max_seq_len]).reshape(1, -1)
        reward = reward_model.forward(response_ids)[0]

        policy_logits = policy_model.forward(response_ids)
        ref_logits = reference_model.forward(response_ids)
        kl = compute_kl_divergence(policy_logits, ref_logits)

        total_reward = reward - kl_coeff * kl

        for block in policy_model.blocks:
            update_scale = lr * total_reward
            block.ffn.W1 += update_scale * np.random.randn(*block.ffn.W1.shape) * 0.01
            block.ffn.W2 += update_scale * np.random.randn(*block.ffn.W2.shape) * 0.01
```

- 前 4 步（采样、打分、算 KL、`reward − β·KL`）与讲义描述的流程一致。
- ⚠️ 第 5 步完全不是 PPO：
  - 没有生成 token 的 log 概率，算不出 `ratio = π_new / π_old`；
  - 没有 baseline / 优势，也没有价值模型；
  - 没有裁剪；
  - 更新方向 `N(0, I)` 与奖励、与模型输出无关，**期望为 0**——奖励只决定噪声的幅度。
- 量级：`1.5e-5 × 约 0.3 × 0.01 ≈ 5e-8`。我们把同量级噪声叠加 20 次后算 KL，约 2.4e-10，所以输出里 KL 一直是 `0.0000`。
- 讲义称"The KL penalty grows as the policy diverges from the reference, automatically preventing reward hacking"——在这份代码里，KL 既没有变化，也没有通过梯度影响策略，这句话不成立。
- `episode % len(prompts)` 让 6 个 prompt 轮流使用。

### 3.9 对比与 KL 分析

```python
        sft_response = generate_response(sft_model, prompt_tokens, max_new_tokens=20, temperature=0.6, ...)
        rlhf_response = generate_response(rlhf_model, prompt_tokens, max_new_tokens=20, temperature=0.6, ...)
        sft_reward = reward_model.forward(sft_ids)[0]
        rlhf_reward = reward_model.forward(rlhf_ids)[0]
```

- 两个模型各采样一次、各打一次分，每个 prompt 只有一个样本。
- ⚠️ 统计上毫无说服力：我们让**同一个** SFT 模型和自己比三次，平均奖励差分别为 +0.09、+0.14、−0.16，比运行结果中 RLHF 的"提升" +0.063 还大。可靠的对比应对每个 prompt 采样多次求均值，并报告方差，或者用贪心解码。
- KL 分析部分打印首个、最后一个和最大的 KL，与阈值 0.1 比较。
- ⚠️ `sft_model` 本身也是随机初始化的 `MiniGPT`，并不是第 06 节训练出来的 SFT 模型（Stage 1 只是打印了参数量）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| RM 复用 MiniGPT 主体 + 标量头 | 体现"RM 就是换了头的 LM" | 应从 SFT 检查点初始化并全量微调 |
| 只训练 `reward_head` 且梯度近似 | 避免手写整个 Transformer 反传 | 梯度方向错误、漏掉 rejected；用 autograd 计算 `(σ(Δ)−1)(h_p−h_r)` 并反传到主体 |
| 取最后一个位置打分 | 因果注意力下信息最全 | 必须保证最后一个 token 有意义（不截断回复、末尾加 EOS）；练习 1 对比 mean pooling |
| 用字节 0 作分隔符 | 简单 | 训练 / 推理格式必须一致；生产用统一的 chat template |
| 截断到 128 | 位置 embedding 只有 128 行 | 7/12 条序列被截断；应从左侧截 prompt 或增大上下文 |
| 精确 KL、所有位置平均 | 公式直观 | 生产按回复 token 用 log 概率差估计，序列求和，逐 token 加到奖励上 |
| 随机噪声代替 PPO 更新 | 回避实现策略梯度 | 完全不学习；应实现 log 概率、优势、裁剪、价值模型（或至少 REINFORCE + baseline） |
| 单样本对比 | 输出简短 | 采样噪声大于"提升"；多样本、多 prompt、报告方差 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多行默认参数 | `def __init__(self, vocab_size=256, embed_dim=128, ...)` | 参数列表可分行书写，末尾逗号合法 |
| 列表推导式创建对象 | `[TransformerBlock(embed_dim, num_heads, ff_dim) for _ in range(num_layers)]` | 每次迭代新建一个独立 block |
| 切片取最后一位 | `x[:, -1, :]` | 第 1 维取最后一个元素，结果降一维 |
| 一维向量点乘 | `last_hidden @ self.reward_head` | `(1, 128) @ (128,)` → `(1,)` |
| 列表拼接 | `prompt_tokens + [0] + response_tokens` | 生成新列表 |
| `np.where(条件, a, b)` | `np.where(x >= 0, 1/(1+np.exp(-x)), np.exp(x)/(1+np.exp(x)))` | 逐元素三元选择；注意两支都会被计算 |
| 比较 NumPy 标量 | `if r_preferred > r_rejected:` | 0 维数组 / NumPy 标量可直接用于 `if` |
| 增强赋值 | `rm.reward_head -= ...`、`block.ffn.W1 += ...` | 原地修改数组 |
| 括号续行 | `rm.reward_head -= (lr * grad * ...)` | 括号内可跨行 |
| `zip` 并行遍历 | `for s_block, t_block in zip(source.blocks, target.blocks)` | 同时遍历两个列表 |
| `.copy()` | `source.embedding.token_embed.copy()` | 复制数组数据，避免共享内存 |
| 取模循环 | `prompts[episode % len(prompts)]` | 轮流取 prompt |
| `float()` 转换 | `rewards_history.append(float(reward))` | 把 NumPy 标量转成 Python 浮点数，便于存储与打印 |
| 条件表达式 | `np.mean(rewards_history[-5:]) if rewards_history else 0` | 列表为空时给默认值 |
| 负索引切片 | `rewards_history[-5:]` | 最近 5 个元素 |
| 字符串切片 + 条件 | `prompt[:33] + ".." if len(prompt) > 35 else prompt` | 超长时截断并加省略号 |
| f-string 对齐 | `{'Prompt':<35}`、`{sft_reward:>10.4f}`、`{r_pref:+.4f}`、`{epoch + 1:3d}`、`{accuracy:.1%}` | 左 / 右对齐、带符号、宽度、百分比 |
| f-string 内嵌表达式 | `{'Correct' if r_pref > r_rejected else 'Wrong'}` | 花括号内可写任意表达式 |
| `"\n"` 换行 | `f"\n  Accuracy: ..."` | 字符串内换行 |
| 元组返回与解包 | `rm, rm_losses, rm_accuracies = train_reward_model(...)` | 一次返回多个值 |

---

## 6. 运行结果解读

实际运行（Python 3 + NumPy，`np.random.seed(42)`，耗时约 4.6 秒）：

```text
STAGE 1: SFT Model (from Lesson 06)
  Parameters: 840,448                         ← 随机初始化的 MiniGPT，并非真正的 SFT 模型

STAGE 2: Train Reward Model
  Epoch   1 | Loss: 0.6474 | Accuracy: 66.7%   ← ≈ ln 2 = 0.693：几乎分不出好坏
  Epoch   3 | Loss: 0.6451 | Accuracy: 66.7%
  Epoch   5 | Loss: 0.6423 | Accuracy: 66.7%
  Epoch   7 | Loss: 0.6397 | Accuracy: 83.3%
  Epoch   9 | Loss: 0.6370 | Accuracy: 83.3%   ← loss 只降了 0.01

Reward Model Evaluation:
  Preferred: -0.2235 | Rejected: -0.2483 | Correct
  Preferred: -0.1623 | Rejected: -0.3874 | Correct
  Preferred: -0.2351 | Rejected: -0.5965 | Correct
  Preferred: -0.1898 | Rejected: -0.2926 | Correct
  Preferred: -0.2953 | Rejected: -0.2643 | Wrong     ← 第 5 对（WWII）
  Preferred: -0.2330 | Rejected: -0.2949 | Correct
  Accuracy: 5/6 = 83.3%                       ← 训练集上的准确率，无 held-out

STAGE 3: PPO Training
  Episode   0 | Reward: -0.3380 | KL: 0.0000 | Avg Reward: -0.3380
  Episode   5 | Reward: -0.1792 | KL: 0.0000 | Avg Reward: -0.4078
  Episode  10 | Reward: -0.3835 | KL: 0.0000 | Avg Reward: -0.3946
  Episode  15 | Reward: -0.4863 | KL: 0.0000 | Avg Reward: -0.1448   ← 奖励随机波动，无上升趋势

  Prompt                                     SFT       RLHF
  What is the capital of France?         -0.3825    -0.6187
  Explain gravity.                       -0.2732    -0.3354
  Name three programming languages.      -0.6351    -0.1481
  Average                                -0.4303    -0.3674   ← 差异来自采样噪声

  Initial KL: 0.0000
  Final KL:   0.0000
  Max KL:     0.0000
  KL > 0.1: No (model stayed close to reference)   ← 因为策略根本没动
```

逐项解读：

- **RM 的 loss 接近 ln 2**：奖励差都在 ±0.4 以内，`σ(Δ)` 接近 0.5。错误的梯度 + 很小的学习率，让 RM 几乎没有学到东西。
- **准确率 66.7% → 83.3%**：只是一对数据的排序翻转。初始（训练前）准确率已经是 4/6，说明随机 RM 本身就有偶然的排序倾向。
- **所有奖励都是负数**：`reward_head` 与随机特征的点积恰好偏负，绝对值没有意义；BT 模型只关心差值，奖励整体平移不改变偏好概率。这也是 PPO 需要 baseline / 奖励归一化的原因。
- **Episode 的 "Avg Reward"**：取最近 5 个 episode 的平均，例如第 15 个 episode 时的 −0.1448 是第 11–15 个 episode 的平均，单个 episode 的奖励在 −0.18 到 −0.49 之间随机跳动。
- **KL 全为 0**：见 3.8，约 1e-10 量级。
- **对比表**：三个 prompt 中 RLHF 赢一个、输两个，平均值的"提升"小于同模型重复采样的波动。

---

## 7. 动手改一改

1. **修正 RM 梯度**：写一个 `hidden_last(rm, ids)` 返回经过全部 block 和 `ln_f` 的最后位置隐藏状态，把更新改为 `rm.reward_head -= lr * (sigmoid(diff) - 1) * (h_p - h_r)`。比较 lr = 1e-4、1e-1 时的准确率与 margin（我们实测正确梯度 lr = 1e-4 即可 6/6）。
2. **统一 RM 的输入格式并避免截断**：PPO 与 `compare_models` 中用 `tokenize_for_reward(prompt, 生成文本)` 构造 RM 输入；把截断改为"保留完整回复、从左侧截 prompt"，统计截断前后 RM 准确率的变化。
3. **讲义练习 1：mean pooling**：把 `x[:, -1, :]` 改为 `x.mean(axis=1)`，在修正梯度的前提下比较两种池化方式的准确率。
4. **讲义练习 2：校准与泛化**：自己再写 4 对偏好数据（注意让 preferred 不总是更短），检查 margin 是否在新数据上保持；同时计算 preferred / rejected 长度与 RM 分数的相关系数，看 RM 是否学到了长度捷径。
5. **讲义练习 3：模拟 reward hacking**：用 `reward = len(response) / 100` 作为"有缺陷的 RM"，实现一个真正的 REINFORCE 更新（至少更新输出头：`∇ log π(y_t)` 对 `token_embed` 的梯度），观察回复是否越来越长；再加 β = 0.1 的 KL 惩罚对比。
6. **讲义练习 5：β 扫描**：在第 5 题的基础上，用 β = 0.001 / 0.02 / 0.5 各训练一次，画出奖励曲线与 KL 曲线。

---

## 8. 常见坑

- **以为流程跑通就是算法正确**：本文件每一步都"有输出"，但 RM 梯度错误、PPO 没有梯度。检查训练是否有效的最低标准：参数是否真的变了、loss / 奖励是否有趋势、与随机基线相比是否显著。
- **RM 训练与使用时的输入格式不一致**：分隔符、模板、截断方式不一致都会让 RM 打分失真，进而被策略利用。
- **截断导致最后一个 token 无意义**：取最后位置打分的 RM 对截断极其敏感；回复末尾最好有 EOS。
- **数据中的长度混杂**：preferred 普遍更短或更长，RM 都可能学到长度捷径。
- **KL 算在 prompt 上**：稀释信号；应只在回复 token 上计算。
- **`np.where` 版 sigmoid 仍会报溢出警告**：两支都会被计算；需要完全无警告时改用掩码分别计算。
- **单样本比较模型**：采样随机性会淹没真实差异。
- **参考模型与策略共享数组**：复制权重时忘了 `.copy()`，KL 恒为 0，KL 惩罚形同虚设。
- **讲义事实需留意口径**：讲义写"评估者在 85% 的情况下更喜欢 InstructGPT，尽管它小 135 倍（1.3B vs 175B）"。据 InstructGPT 论文摘要，85% 左右的偏好率对应的是 **175B** InstructGPT 对 175B GPT-3；1.3B InstructGPT 的结论是"比 175B GPT-3 更受偏好"，论文表述为参数少约 100 倍。引用时注意不要把两个结论混在一起。
- **"RLHF 需要三个模型"是简化说法**：标准 PPO 实现中同时存在策略、参考、奖励、价值 4 个模型（见测验 Q13）。
- **`outputs/` 提示词中的一处笔误**：其 "Red Flags" 表把"奖励剧烈震荡"的对策写成"increase clip ratio"；增大 ε 会允许更大的更新、加剧震荡，通常应**减小** ε（或降低学习率）。
