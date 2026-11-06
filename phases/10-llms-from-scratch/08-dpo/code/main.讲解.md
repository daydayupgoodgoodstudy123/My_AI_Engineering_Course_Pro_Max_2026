# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 08 节 DPO：直接偏好优化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；依赖仓库目录结构，从 `../../04-pre-training-mini-gpt/code/main.py` 导入 `MiniGPT`） ｜ **依赖**：`numpy`（第三方）；`sys`、`os`（标准库）；无需 GPU、无需网络。

---

## 1. 这份代码在考察什么

这份代码演示 DPO 的完整计算链路：

1. **偏好数据**：与第 07 节相同的 6 组 `(prompt, preferred, rejected)`。
2. **序列 log 概率**：对 `prompt + response` 前向一次，只把**回复 token** 的 log 概率加起来——DPO 的"主力函数"。
3. **DPO 损失**：`−log σ(β·[(log π_w − log π_ref,w) − (log π_l − log π_ref,l)])`，并导出隐式奖励与 margin。
4. **训练循环**：每对样本 4 次前向（策略 / 参考 × chosen / rejected），没有奖励模型、没有采样、没有 PPO。
5. **评估**：隐式奖励准确率、逐对的隐式奖励表、loss 与 margin 曲线、β 敏感性分析。

> 一句话：**DPO 把"训练奖励模型 + 强化学习"折叠成一个分类式损失，奖励就藏在 `log π − log π_ref` 里**。代码中 log 概率与损失的计算是正确的，但与第 06、07 节一样，参数更新是随机噪声——所以所有训练与评估输出都停留在初始状态附近。理解"为什么数字是 0.6931 和 0.0000"，是读懂这份代码的关键。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `from main import MiniGPT, ...` | 导入 | 复用第 04 节的模型 | 策略 / 参考模型 |
| `PREFERENCE_DATA` | 常量 | 6 组偏好三元组 | 偏好数据 |
| `tokenize_sequence` | 函数 | 文本 → 字节 token 列表 | 字节级 tokenizer |
| `compute_sequence_log_prob` | 函数 | 前向 → log-softmax → 回复 token 的 log 概率求和 | 序列 log 概率 `log π(y|x)` |
| `sigmoid` | 函数 | 数值稳定的两支 sigmoid | σ 函数 |
| `dpo_loss` | 函数 | 两个 log 比率 → logit → loss，并返回隐式奖励等指标 | DPO 损失 / 隐式奖励 |
| `copy_model_weights` | 函数 | 逐数组复制权重 | 冻结参考模型 |
| `dpo_train` | 函数 | 每对 4 次前向 → `dpo_loss` → （伪）更新 | DPO 训练循环 |
| `evaluate_preference_accuracy` | 函数 | 隐式奖励 chosen > rejected 的比例 | 偏好准确率 |
| `analyze_implicit_rewards` | 函数 | 打印每对的隐式奖励与 margin | 隐式奖励分析 |
| `beta_sensitivity_analysis` | 函数 | 对多个 β 从同一 SFT 权重重新训练并评估 | β 扫描 |
| `__main__` | 脚本入口 | 初始化 → 训练 → 评估 → 曲线 → β 扫描 → 打印 DPO vs RLHF 对比 | — |

数据流：`PREFERENCE_DATA` → `tokenize_sequence` → `compute_sequence_log_prob`（策略、参考各两次）→ `dpo_loss` → 噪声更新 → `evaluate_preference_accuracy` / `analyze_implicit_rewards` → `beta_sensitivity_analysis`。

---

## 3. 逐段精讲

### 3.1 导入与数据

- 与第 06、07 节相同：`sys.path.insert(0, ...)` 指向第 04 节的 `code/`，`from main import MiniGPT, LayerNorm, Embedding, TransformerBlock`。本文件实际只用到 `MiniGPT`；同样存在"两个 `main.py`"的循环导入陷阱（在别处 `import main` 加载本文件会失败）。
- `PREFERENCE_DATA` 与第 07 节完全相同，同样有"4 对 preferred 明显更短"的长度混杂。

### 3.2 序列 log 概率：DPO 的主力函数

```python
def tokenize_sequence(text, vocab_size=256):
    return [min(t, vocab_size - 1) for t in list(text.encode("utf-8"))]

def compute_sequence_log_prob(model, prompt_tokens, response_tokens, max_seq_len=128):
    full_sequence = prompt_tokens + response_tokens
    if len(full_sequence) > max_seq_len:
        full_sequence = full_sequence[:max_seq_len]

    if len(full_sequence) < 2:
        return 0.0

    input_ids = np.array(full_sequence[:-1]).reshape(1, -1)
    target_ids = np.array(full_sequence[1:])

    logits = model.forward(input_ids)
    logits = logits[0]

    max_logits = logits.max(axis=-1, keepdims=True)
    log_probs = logits - max_logits - np.log(
        np.exp(logits - max_logits).sum(axis=-1, keepdims=True)
    )

    prompt_len = len(prompt_tokens)
    response_start = max(0, prompt_len - 1)
    response_end = len(target_ids)
    if response_start >= response_end:
        return 0.0

    response_log_probs = log_probs[response_start:response_end, :]
    response_targets = target_ids[response_start:response_end]

    total_log_prob = 0.0
    for i, target in enumerate(response_targets):
        total_log_prob += response_log_probs[i, target]
    return total_log_prob
```

以 `prompt = "What is 15 times 7?"`（19）+ `preferred = "15 times 7 is 105."`（18）为例：

| 量 | 值 / 形状 |
|----|----------|
| `full_sequence` | 37 个 token |
| `input_ids` | `(1, 36)` |
| `target_ids` | `(36,)` |
| `logits[0]`、`log_probs` | `(36, 256)` |
| `response_start` / `response_end` | 18 / 36 |
| 累加项数 | 18（正好是回复长度） |

- **为什么从 `prompt_len − 1` 开始**：位置 i 的输出预测 `full_sequence[i+1]`，回复第一个 token 是 `full_sequence[19]`，由位置 18 预测。这一错位处理是**正确的**。
- **求和而不是平均**：DPO 的 `log π(y|x) = Σ_t log π(y_t | x, y_<t)`，是整条回复的联合概率。随机初始化时每个 token 约 −5.65，31 个 token 的 chosen 为 −175.28，98 个 token 的 rejected 为 −553.32（实测）。总 log 概率强烈依赖长度，但 DPO 用的是与参考模型的**差值**，长度效应在初始时被抵消。
- `log_probs` 用 log-sum-exp 技巧计算，数值稳定。
- 最后的 `for` 循环可以用花式索引一行完成：`response_log_probs[np.arange(len(response_targets)), response_targets].sum()`。
- ⚠️ **截断**：长度超过 128 时只保留前 128 个 token，被截掉的总是回复尾部。实测 12 条序列中有 6 条被截断（第 1、3、4、5 对的 rejected，第 6 对两条），例如 "World War II" 的 rejected 只计入了 123 个回复 token 中的 97 个。截断集中在较长的 rejected 上，与偏好方向混在一起。
- ⚠️ **没有分隔符 / 模板**：prompt 与回复直接拼接（"...times 7?15 times 7 is 105."），与 SFT 和推理时的格式都不一致。生产中 log 概率必须在同一个 chat template 下计算。
- 边界保护：序列不足 2 个 token、或 prompt 已占满整个窗口（`response_start >= response_end`）时返回 0.0。注意后者会让这对样本的 log 比率恒为 0，默默失去训练信号。

### 3.3 DPO 损失与隐式奖励

```python
def dpo_loss(policy_logprob_preferred, policy_logprob_rejected,
             ref_logprob_preferred, ref_logprob_rejected, beta=0.1):
    preferred_ratio = policy_logprob_preferred - ref_logprob_preferred
    rejected_ratio = policy_logprob_rejected - ref_logprob_rejected

    logit = beta * (preferred_ratio - rejected_ratio)
    loss = -np.log(sigmoid(logit) + 1e-8)

    preferred_reward = beta * preferred_ratio
    rejected_reward = beta * rejected_ratio
    return loss, {
        "preferred_ratio": float(preferred_ratio),
        "rejected_ratio": float(rejected_ratio),
        "logit": float(logit),
        "implicit_preferred_reward": float(preferred_reward),
        "implicit_rejected_reward": float(rejected_reward),
        "reward_margin": float(preferred_reward - rejected_reward),
    }
```

- 与讲义公式逐项对应：`preferred_ratio = log π(y_w) − log π_ref(y_w)`（"log 比率"），`logit = β × (比率差)`，`loss = −log σ(logit)`。
- **隐式奖励** `β·(log π − log π_ref)` 就是推导中的 `R(x,y)` 去掉 `β log Z(x)`；`reward_margin` 恰好等于 `logit`。
- 数值示例（已运行验证，β = 0.1）：
  - 策略 = 参考：logit 0 → loss 0.6931；
  - 策略 −9 / −13，参考 −10 / −12：logit 0.2 → loss 0.5981，隐式奖励 +0.1 / −0.1；
  - 方向相反：logit −0.2 → loss 0.7981。
- 返回"loss + 指标字典"是训练代码的常见写法，便于日志记录（TRL 的 `DPOTrainer` 也会记录 `rewards/chosen`、`rewards/rejected`、`rewards/margins`、`rewards/accuracies` 等同类指标）。
- 更稳定的写法：`loss = np.logaddexp(0, -logit)`，避免 `+ 1e-8` 在 logit 很负时截断 loss（`−log(1e-8) ≈ 18.4` 是上限）。

### 3.4 训练循环（⚠️ 随机噪声更新）

```python
        indices = np.random.permutation(len(preference_data))
        for idx in indices:
            ...
            pi_logprob_w = compute_sequence_log_prob(policy_model, prompt_tokens, preferred_tokens, max_seq_len)
            pi_logprob_l = compute_sequence_log_prob(policy_model, prompt_tokens, rejected_tokens, max_seq_len)
            ref_logprob_w = compute_sequence_log_prob(reference_model, prompt_tokens, preferred_tokens, max_seq_len)
            ref_logprob_l = compute_sequence_log_prob(reference_model, prompt_tokens, rejected_tokens, max_seq_len)

            loss, metrics = dpo_loss(pi_logprob_w, pi_logprob_l, ref_logprob_w, ref_logprob_l, beta)

            update_direction = 1.0 if metrics["logit"] < 0 else -0.1
            for block in policy_model.blocks:
                block.ffn.W1 += lr * update_direction * np.random.randn(*block.ffn.W1.shape) * 0.01
                block.ffn.W2 += lr * update_direction * np.random.randn(*block.ffn.W2.shape) * 0.01
```

- **4 次前向**：讲义"For each preference pair, it runs four times"。参考模型冻结，它的两个 log 概率在整个训练中不变，生产中通常预先算好缓存，省掉一半前向。
- ⚠️ **更新与损失无关**：`N(0, I)` 关于 0 对称，乘以 +1.0 或 −0.1 后分布仍然对称，期望更新为 0。`update_direction` 只决定噪声的幅度。实测 5 个 epoch 后策略 `W1` 最大变化约 7e-7，训练中 `|margin|` 最大约 1e-5。
- 正确的做法是对 log 概率求梯度（见测验 Q10）：

  ```text
  ∂L/∂log π(y_w) = −β·σ(−logit)，  ∂L/∂log π(y_l) = +β·σ(−logit)
  ∂log π(y)/∂z_t = onehot(y_t) − softmax(z_t)   （仅回复位置）
  ```

  我们只对输出头（`token_embed`）实现了这一梯度（lr = 0.05、β = 0.1、15 个 epoch），loss 从 0.354 降到 0.0035，训练集准确率 6/6；同时观察到 chosen 的 log 比率也降到 −24.2（rejected 为 −87.0），这就是 DPO 常见的"chosen 似然下降"现象。
- `epoch_loss += loss` 累加的是 NumPy 标量；`losses.append(float(loss))` 转为 Python 浮点数以便后续 `sum`。

### 3.5 评估函数

```python
        preferred_reward = beta * (pi_w - ref_w)
        rejected_reward = beta * (pi_l - ref_l)
        if preferred_reward > rejected_reward:
            correct += 1
```

- 隐式奖励准确率：chosen 的隐式奖励是否严格高于 rejected。
- ⚠️ **平局记为错误**：`__main__` 中的 "pre-DPO" 用 `sft_model` 对比与之完全相同的 `reference_model`，所有奖励都是 0，于是 6 对全错，打印 0.0%。合理的基线是"全部平局"或 50%。
- ⚠️ **训练集即评估集**，且只有 6 对：一对翻转就改变 16.7 个百分点。
- `analyze_implicit_rewards` 逐对打印隐式奖励与 margin。由于 margin 在 ±1e-5 量级，`{:.4f}` 格式下显示为 `0.0000` 或 `-0.0000`（负号说明它是一个极小的负数，而不是精确的 0）。

### 3.6 β 敏感性分析

```python
    for beta in betas:
        policy = MiniGPT(...)
        reference = MiniGPT(...)
        copy_model_weights(sft_model, policy)
        copy_model_weights(sft_model, reference)
        policy, train_losses, margins_list = dpo_train(policy, reference, preference_data, num_epochs=3, lr=5e-6, beta=beta, ...)
        accuracy = evaluate_preference_accuracy(policy, reference, preference_data, beta, max_seq_len)
```

- 设计是对的：每个 β 都从同一份 SFT 权重重新开始，避免实验之间相互污染；用 `copy_model_weights` 而不是直接赋值，保证参考模型独立。
- 每次新建 `MiniGPT` 都会消耗随机数并生成一套随机权重，随后又被 `copy_model_weights` 覆盖——浪费但无害。
- ⚠️ 由于更新是噪声，四个 β 的 loss 都是 0.6931，准确率 66.7% / 33.3% / 100% / 83.3% 只是噪声符号的结果；**β = 0.3 的 100% 不说明任何问题**。讲义"0.1–0.3 是最佳区间"的经验结论需要在修好训练后自己验证（我们在修正版中看到：β = 0.5 时 chosen 的 log 比率只降到约 −4.5，β = 0.1 时降到约 −24.2，体现了"β 大 → 更贴近参考"）。

### 3.7 `__main__` 中的 DPO vs RLHF 小结

最后一段只是 `print` 讲义中的对比要点（训练循环数、显存中的模型数、在线学习能力等），没有计算。注意其中 "1 training loop (vs 3 for RLHF)" 只算了 DPO 本身；完整流水线仍需要先做 SFT（讲义表格中写为 "2 (SFT, DPO)"）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 序列 log 概率 = 回复 token 求和 | 与 DPO 推导中的 `log π(y|x)` 一致 | 长回复的绝对值更负；有参考模型时初始抵消，但训练后可能出现长度利用 |
| 每对 4 次前向 | 公式直观 | 参考模型 log 概率可预计算缓存；chosen 与 rejected 可拼成一个 batch |
| 前 128 个 token 截断 | 位置 embedding 只有 128 行 | 截掉回复尾部且集中在 rejected 上；应截 prompt、丢弃超长样本或扩大上下文 |
| prompt 与回复直接拼接 | 代码简单 | 与 SFT / 推理模板不一致；应使用统一的 chat template |
| `dpo_loss` 返回指标字典 | 便于观察隐式奖励 | 生产中同样记录 chosen / rejected 奖励、margin、准确率 |
| 随机噪声更新 | 避免手写反向传播 | 完全没有学习；应使用 autograd + AdamW（或至少实现输出头梯度） |
| 准确率用严格 `>` | 简单 | 平局被记为错；应单独统计平局，并使用 held-out 集 |
| β 扫描从同一 SFT 权重重启 | 公平比较 | 训练无效时扫描结果只是噪声；需多个随机种子 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 + `min` | `[min(t, vocab_size - 1) for t in list(text.encode("utf-8"))]` | 逐元素截断 |
| 列表拼接与切片 | `full_sequence = prompt_tokens + response_tokens`、`full_sequence[:max_seq_len]` | 拼接后截取前 N 个 |
| 错位切片 | `full_sequence[:-1]`、`full_sequence[1:]` | 输入去掉最后一个，目标去掉第一个 |
| 提前返回 | `if len(full_sequence) < 2: return 0.0` | 边界情况直接退出 |
| `max(0, ...)` | `response_start = max(0, prompt_len - 1)` | 防止出现负下标 |
| 二维切片 | `log_probs[response_start:response_end, :]` | 取行区间、保留所有列 |
| `enumerate` 遍历 | `for i, target in enumerate(response_targets)` | 同时拿到下标与值 |
| 多返回值（元组） | `return loss, {...}`、`loss, metrics = dpo_loss(...)` | 返回损失与指标字典 |
| 字典字面量 | `{"preferred_ratio": float(preferred_ratio), ...}` | 结构化地返回多个指标 |
| `float()` | `float(preferred_ratio)` | NumPy 标量 → Python `float`，便于序列化与打印 |
| 关键字参数调用 | `dpo_train(..., num_epochs=5, lr=5e-6, beta=0.1)` | 显式指定参数，提高可读性 |
| 条件表达式 | `update_direction = 1.0 if metrics["logit"] < 0 else -0.1` | 一行 if-else |
| 星号解包 | `np.random.randn(*block.ffn.W1.shape)` | 把形状元组展开为位置参数 |
| 字符串截断 + 条件 | `pair["prompt"][:28] + ".." if len(pair["prompt"]) > 30 else pair["prompt"]` | 超长时截断 |
| 列表内追加字典 | `results.append({"beta": beta, ...})` | 收集实验结果 |
| 负索引 | `train_losses[-1]` | 取最后一个元素 |
| `max(1, ...)` 防除零 | `window = max(1, len(losses) // 5)` | 至少为 1 |
| f-string 格式符 | `{beta:>8.3f}`、`{accuracy:>10.1%}`、`{margin:>10.4f}`、`{i:3d}` | 宽度、小数位、百分比、右对齐 |
| `np.where` 版 sigmoid | `np.where(x >= 0, 1/(1+np.exp(-x)), np.exp(x)/(1+np.exp(x)))` | 两支都会计算，极端值仍可能报溢出警告 |

---

## 6. 运行结果解读

实际运行（Python 3 + NumPy，`np.random.seed(42)`，耗时约 7.6 秒）：

```text
STEP 1: Initialize SFT Model (from Lesson 06)
  Parameters: 840,448                      ← 随机初始化的 MiniGPT，并非真正的 SFT 模型

DPO Training: 6 pairs, 5 epochs, lr=5e-06, beta=0.1
  Epoch 1/5 | Loss: 0.6931 | Avg Margin: 0.0000
  ...
  Epoch 5/5 | Loss: 0.6931 | Avg Margin: 0.0000   ← = ln 2，策略始终 ≈ 参考

  Preference accuracy (pre-DPO):  0.0%     ← 策略 = 参考，平局全部记为错
  Preference accuracy (post-DPO): 33.3%    ← margin 约 ±1e-5，噪声决定符号

Implicit Reward Analysis:
  Prompt                          Pref Reward   Rej Reward     Margin
  What is the capital of France?       0.0000       0.0000    -0.0000
  ...                                                           ← "-0.0000" 是极小的负数

  Loss curve:          Steps 0-5 ... 24-29: loss = 0.6931
  Reward margin curve: Steps 0-5 ... 24-29: margin = 0.0000

Beta Sensitivity Analysis
      Beta   Final Loss   Final Margin   Accuracy
     0.010       0.6931        -0.0000      66.7%
     0.100       0.6931        -0.0000      33.3%
     0.300       0.6931         0.0000     100.0%   ← 纯属噪声
     1.000       0.6931         0.0000      83.3%
```

逐项解读：

- **loss = 0.6931 = ln 2**：DPO 的初始 loss 恒为 ln 2（与模型、数据无关），因为策略与参考相同、logit = 0。一直保持 ln 2，说明策略从未离开参考。
- **margin = 0.0000**：隐式奖励差在 1e-5 量级，四位小数下为 0。
- **pre-DPO 0.0%**：不是"模型很差"，而是"平局被判错"。
- **post-DPO 33.3% 与 β 扫描的四个准确率**：每对样本的 margin 只是噪声，6 对中有几对恰好为正就是几个"正确"。β = 0.3 的 100% 只是 6 次"抛硬币"恰好全部朝上。
- **耗时约 7.6 秒**：主要花在 β 扫描上（4 个 β × 3 epoch × 6 对 × 4 次前向，再加评估），全部是对 ≤ 128 token 序列的完整前向。
- 修正训练后的参照（我们只训练输出头，β = 0.1，lr = 0.05，15 epoch）：loss 0.354 → 0.0035、准确率 6/6，chosen / rejected 的平均 log 比率分别为 −24.2 / −87.0。

---

## 7. 动手改一改

1. **修好训练（必做）**：写一个 `seq_logprob_and_grad(model, prompt, response)`，返回回复 log 概率和它对 `token_embed` 的梯度（`Σ_t (onehot − softmax)ᵀ h_t`，`h_t` 为 `ln_f` 后的隐藏状态）；按 `coef = −β·σ(−logit)` 组合 chosen / rejected 两份梯度更新 `token_embed`。观察 loss、margin、chosen 与 rejected 各自 log 比率的变化。进阶：用 PyTorch 重写并用 AdamW。
2. **修正评估**：单独统计平局；把 6 对数据按 4 / 2 划分训练与验证；每个 β 跑 3 个随机种子取平均。
3. **讲义练习 2：长度归一化 DPO**：把 `total_log_prob` 改为除以回复 token 数，比较 margin 与回复长度的相关性；再实现 SimPO 损失 `−log σ(β/|y_w|·log π_w − β/|y_l|·log π_l − γ)`（测验 Q12）。
4. **讲义练习 1：KTO**：把 chosen 当作"好"、rejected 当作"坏"独立训练：好样本 `−log σ(β·log 比率)`，坏样本 `1.5 × (−log(1 − σ(β·log 比率)))`，与 DPO 比较准确率。
5. **讲义练习 3：ORPO 式组合损失**：`L = L_sft(chosen) + α·L_dpo`，α ∈ {0.1, 0.5, 1.0}，观察 SFT 项能否阻止 chosen 似然下降。
6. **统一模板与截断**：在 prompt 与回复之间加入与第 06 节相同的角色标记，并改为"优先截断 prompt"，比较修改前后的 margin。

---

## 8. 常见坑

- **以为 loss = 0.6931 是"正常的平稳"**：DPO 初始 loss 恒为 ln 2，一直不变说明没有在学习。
- **错位一位**：回复 log 概率要从 `prompt_len − 1` 位置开始取；从 `prompt_len` 开始会漏掉第一个回复 token。
- **截断吃掉回复**：截断应优先作用于 prompt，并对 chosen 与 rejected 一视同仁；否则偏好信号会被长度扭曲。
- **模板不一致**：DPO 的 log 概率必须在与 SFT、推理相同的 chat template 下计算。
- **平局判错**：严格 `>` 让"完全没区分"显示成 0% 准确率。
- **只看 margin 不看 chosen 似然**：margin 变大时 chosen 的绝对概率可能也在下降，需要分别监控。
- **把隐式奖励当通用打分器**：`β·log(π/π_ref)` 只在训练分布附近有意义，跨 prompt 比较时还隐含了 `β log Z(x)` 的差异。
- **讲义事实需核对**：讲义称 Zephyr-7B 的 MT-Bench 为 6.47、"距 Llama 2 Chat 70B（6.86）6% 以内"。据 Zephyr 论文与模型卡，zephyr-7b-β 的 MT-Bench 为 7.34，**高于** Llama 2 Chat 70B 的 6.86；引用时以原论文为准。讲义称 Llama 3 "在初始 RLHF 阶段之后使用了 DPO"，据 Llama 3 技术报告，其后训练是多轮"奖励模型 + 拒绝采样 + SFT + DPO"，并没有使用 PPO（报告给出的理由大意是 DPO 对大模型所需计算更少、效果也更好），与"先 RLHF 再 DPO"的说法不完全一致。
- **`outputs/` 提示词中的一处术语错误**：它把 SimPO 的 γ 称为"长度归一化指数"；在 SimPO 中 γ 是目标奖励 margin，长度归一化是除以 `|y|`。
