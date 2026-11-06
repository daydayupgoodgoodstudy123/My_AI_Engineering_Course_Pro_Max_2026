# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 05 节 深Q网络（DQN） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，纯 Python 实现，约 15–20 秒） ｜ **依赖**：仅 Python 标准库（`random`；文件还 `import math` 但没有用到），不需要 NumPy / PyTorch

---

## 1. 这份代码在考察什么

讲义说 DQN = Q-learning + 让函数近似稳定的几个技巧。这份代码用**纯 Python 手写**了一个最小但完整的 DQN，所有部件都看得见：

1. **神经网络代替 Q 表**：16 维 one-hot 状态 → 32 个 ReLU 隐藏单元 → 4 个 Q 值。前向传播、反向传播全部手写。
2. **DQN 损失与半梯度**：对 `½(Q(s,a;θ) − y)²` 求梯度，目标 `y` 当作常数。
3. **经验回放**：用列表实现容量 2000 的缓冲区，每步随机抽 32 条训练。
4. **目标网络**：每 200 个环境步把在线网络深拷贝一份作为目标网络。
5. **ε 线性衰减**：从 1.0 线性降到 0.05，前期充分探索。
6. **验证**：训练后把 `Q(0,0, ·)` 与解析的 `Q*` 对照，打印贪心策略。

> 一句话：**与 Atari DQN 算法完全相同，只是把 CNN 换成了一个小 MLP、把像素换成了 one-hot**——规模小到每个梯度都能用 for 循环算出来。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`…`step` | 常量 / 函数 | 与前几节相同的确定性 4×4 GridWorld | 环境 |
| `state_features(state)` | 函数 | 把 `(r, c)` 编码成 16 维 one-hot 列表 | 状态表示 / 网络输入 |
| `init_net(n_in, n_hidden, n_out, rng)` | 函数 | 用字典存 `W1, b1, W2, b2`，高斯初始化 | Q 网络参数 θ |
| `forward(net, x)` | 函数 | 线性 → ReLU → 线性，返回 Q 值与隐藏激活 | 前向传播 |
| `clone(net)` | 函数 | 深拷贝网络参数 | 目标网络 θ⁻ |
| `epsilon_greedy(net, state, rng, epsilon)` | 函数 | 返回动作**下标** | 行为策略 |
| `train_step(online, target, batch, gamma, lr)` | 函数 | 计算 TD 目标、手写反向传播、SGD 更新 | DQN 损失与优化 |
| `main()` | 函数 | 交互、存回放、采样训练、同步目标网络、打印结果 | DQN 外层循环 |

数据流：`main` 每步 → `epsilon_greedy`（在线网络前向）→ `step` → 转移存入 `buffer` → 随机抽 32 条 → `train_step`（在线网络算预测、目标网络算目标、反向传播更新在线网络）→ 每 200 步 `clone` 一次。

---

## 3. 逐段精讲

### 3.1 状态编码：one-hot

```python
def state_features(state):
    feat = [0.0] * (GRID * GRID)
    r, c = state
    feat[r * GRID + c] = 1.0
    return feat
```

- `r * GRID + c` 把二维坐标展平成 0–15 的下标（行优先），对应位置置 1。
- 网络输入必须是数值向量，one-hot 是最直接的离散状态编码。
- ⚠️ 讲义 Build It 开头说代码用的是 "tiny continuous GridWorld"，但实际是 16 维 one-hot 的离散网格（讲义后文也写了 "16-dim one-hot state"）。one-hot 意味着状态之间几乎不共享输入权重，网络近似一个"带共享输出层的查表"——这让训练很稳定，也解释了为什么在这里去掉目标网络/回放依然能收敛（见测验 Q11）。

### 3.2 网络：用字典存参数

```python
def init_net(n_in, n_hidden, n_out, rng):
    return {
        "W1": [[rng.gauss(0, 0.2) for _ in range(n_in)] for _ in range(n_hidden)],
        "b1": [0.0] * n_hidden,
        "W2": [[rng.gauss(0, 0.2) for _ in range(n_hidden)] for _ in range(n_out)],
        "b2": [0.0] * n_out,
    }


def forward(net, x):
    h = []
    for row, b in zip(net["W1"], net["b1"]):
        z = b + sum(w * xi for w, xi in zip(row, x))
        h.append(max(0.0, z))
    q = []
    for row, b in zip(net["W2"], net["b2"]):
        z = b + sum(w * hi for w, hi in zip(row, h))
        q.append(z)
    return q, h
```

- 形状约定：`W1` 是 `n_hidden × n_in`（32×16），每一行是一个隐藏单元的输入权重；`W2` 是 `n_out × n_hidden`（4×32），每一行对应一个动作。参数共 676 个。
- `rng.gauss(0, 0.2)`：小标准差的高斯初始化，偏置为 0。讲义示例用的是 0.3 并且写成 `QNet` 类，代码改成了字典 + 函数，算法相同。
- `forward` 是"线性 → ReLU → 线性"：`h = ReLU(W1·x + b1)`，`q = W2·h + b2`。输出层**没有激活函数**，因为 Q 值可以是任意实数（这里都是负数）。
- 同时返回 `h`：反向传播需要隐藏层激活，算一次复用，避免重复前向。
- **一次前向输出所有动作的 Q 值**，这是 DQN 的标准结构——选 `argmax` 或算 `max` 只需一次前向。

### 3.3 `clone`：目标网络就是一份深拷贝

```python
def clone(net):
    return {
        "W1": [row[:] for row in net["W1"]],
        "b1": net["b1"][:],
        "W2": [row[:] for row in net["W2"]],
        "b2": net["b2"][:],
    }
```

- 必须**逐行复制**：`row[:]` 复制每一行列表。如果只写 `dict(net)` 或 `net["W1"][:]`，内层列表仍然是共享的，在线网络一更新，"目标网络"也跟着变，就等于没有目标网络。
- 这是 `copy.deepcopy(net)` 的手写版本，速度更快、意图更明确。
- 每 `sync_every` 步整体替换，叫**硬更新**；讲义提到 DDPG、SAC 用的软更新 `θ⁻ ← τθ + (1−τ)θ⁻` 是更平滑的变体。

### 3.4 `epsilon_greedy`：动作用下标表示

```python
def epsilon_greedy(net, state, rng, epsilon):
    if rng.random() < epsilon:
        return rng.randrange(len(ACTIONS))
    q, _ = forward(net, state_features(state))
    return max(range(len(ACTIONS)), key=lambda i: q[i])
```

- 与前几节不同，这里返回动作的**整数下标** 0–3，因为网络输出是列表，按下标取 Q 值最方便；执行时再用 `ACTIONS[a]` 转回字符串。
- `max(range(4), key=lambda i: q[i])` 就是 argmax，平局取较小的下标。
- 探索分支不做前向传播，省一次计算。

### 3.5 `train_step`：目标、损失、手写反向传播

```python
    for s, a, r, s_next, done in batch:
        x = state_features(s)
        q, h = forward(online, x)
        if done:
            y = r
        else:
            q_next, _ = forward(target, state_features(s_next))
            y = r + gamma * max(q_next)
        td_error = q[a] - y
        total_loss += 0.5 * td_error * td_error
```

- **目标**：`done` 时 `y = r`（终止后没有回报）；否则 `y = r + γ max_a' Q(s', a'; θ⁻)`——用的是**目标网络**。这就是讲义的损失 `L(θ) = E[(r + γ max Q(s',a';θ⁻) − Q(s,a;θ))²]`。
- **半梯度**：`y` 只是一个数，后面不会对它求导。PyTorch 中对应 `with torch.no_grad()` 或 `.detach()`。
- `td_error = q[a] − y` 是损失 `½(q[a] − y)²` 对 `q[a]` 的导数（符号与第 04 节的 `δ = target − Q` 相反）。

```python
        db2[a] += td_error
        for j in range(n_hidden):
            dW2[a][j] += td_error * h[j]

        grad_h = [0.0] * n_hidden
        for j in range(n_hidden):
            if h[j] > 0:
                grad_h[j] = td_error * online["W2"][a][j]

        for j in range(n_hidden):
            db1[j] += grad_h[j]
            for k in range(n_in):
                dW1[j][k] += grad_h[j] * x[k]
```

链式法则逐层展开：

| 梯度 | 公式 | 说明 |
|------|------|------|
| `∂L/∂b2[a]` | `td_error` | 只有被执行的动作 a 有梯度 |
| `∂L/∂W2[a][j]` | `td_error · h[j]` | 输出层第 a 行 |
| `∂L/∂h[j]` | `td_error · W2[a][j]` | 误差沿第 a 行传回隐藏层 |
| `∂L/∂z[j]` | 上式 × ReLU'(z) | `h[j] > 0` 时导数为 1，否则为 0 |
| `∂L/∂W1[j][k]` | `grad_h[j] · x[k]` | one-hot 输入下只有 `x[k]=1` 的那一列非零 |

- 梯度先在整个 batch 上**累加**，最后统一更新——这保证了反向传播时用的 `online["W2"]` 是更新前的值。
- ⚠️ 内层 `for k in range(n_in)` 对 one-hot 输入来说有 15/16 是乘以 0 的无用功；真实实现用矩阵运算（NumPy/PyTorch），或对稀疏输入只更新非零列。

```python
    scale = lr / len(batch)
    for j in range(n_hidden):
        online["b1"][j] -= scale * db1[j]
        for k in range(n_in):
            online["W1"][j][k] -= scale * dW1[j][k]
    # ... W2、b2 同理
    return total_loss / len(batch)
```

- `lr / len(batch)` 等价于"对 batch 求平均梯度再乘学习率"。
- 普通 SGD，**原地修改** `online` 的参数（函数没有返回新网络）。
- 返回平均损失，但 `main` 没有使用它——可以拿来画损失曲线。
- ⚠️ 没有 Huber 损失、没有梯度裁剪：奖励恒为 -1、Q 值量级很小，所以 MSE 足够稳定；Atari 级别的训练通常需要两者（讲义 skill 第 5 条）。

### 3.6 `main`：DQN 外层循环

```python
    buffer = []
    capacity = 2000
    batch = 32
    gamma = 0.99
    lr = 0.05
    sync_every = 200
    episodes = 400
    # ...
    for ep in range(episodes):
        s = reset()
        total = 0.0
        epsilon = max(0.05, 1.0 - ep / 200)
        for _ in range(50):
            a = epsilon_greedy(online, s, rng, epsilon)
            s_next, r, done = step(s, ACTIONS[a])
            total += r
            buffer.append((s, a, r, s_next, done))
            if len(buffer) > capacity:
                buffer.pop(0)
            if len(buffer) >= batch:
                mb = rng.sample(buffer, batch)
                train_step(online, target, mb, gamma, lr)
            step_count += 1
            if step_count % sync_every == 0:
                target = clone(online)
            if done:
                break
            s = s_next
```

- **回放缓冲区**：列表 + `pop(0)` 实现 FIFO。⚠️ `pop(0)` 是 O(n)（要移动后面所有元素），容量 2000 时无所谓；大容量应使用 `collections.deque(maxlen=capacity)` 或预分配数组 + 环形下标。讲义提到 Atari 用约 10⁶ 条。
- **预热**：缓冲区满 32 条就开始训练。讲义 Pitfalls 建议真实任务预热几千条，避免一开始在极少样本上过拟合。
- **`rng.sample(buffer, batch)`**：无放回均匀抽样——这就是"打破时间相关性"的地方。
- **每个环境步训练一次**（replay ratio = 1）；Atari DQN 是每 4 步训练一次。
- **目标网络同步**：按**环境步数**而不是回合数计数，每 200 步一次。讲义经验：约为训练总步数的 1/100。
- **ε 计划**：前 190 个回合从 1.0 线性降到 0.05，之后保持。讲义："ε must decay, typically from 1.0 to 0.01 over the first ~10% of training." 这里衰减期占了近一半回合，因为总训练量很小。
- **50 步上限**：超时结束的回合，最后一条转移 `done=False`，训练时仍会自举——正确地把截断当作非终止。
- 存入缓冲区的是原始状态元组，训练时再 `state_features`——节省内存，代价是重复编码。

### 3.7 结果打印

```python
    q0, _ = forward(online, state_features((0, 0)))
    for a, v in zip(ACTIONS, q0):
        print(f"  {a:<6} = {v:6.2f}")
```

- `{a:<6}` 左对齐、宽度 6，让动作名对齐。
- 贪心策略图对每个非终止格子做一次前向、取 argmax。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 手写 MLP | 每个梯度都看得见，无需安装框架 | 慢（约 17 秒）；生产用 PyTorch/JAX，自动求导 + GPU |
| one-hot 状态 | 最简单的离散编码 | 几乎没有泛化，体现不出函数近似的威力与风险 |
| 一次前向输出所有动作的 Q | 选动作、取 max 只需一次前向 | 只适用于离散动作；连续动作要用 actor-critic（SAC/TD3） |
| 列表 + `pop(0)` 做回放 | 代码直观 | O(n) 删除；用 `deque(maxlen=...)` 或环形数组 |
| 硬同步，每 200 步 | 实现简单，与 Nature DQN 一致 | 软更新更平滑 |
| MSE 损失、无梯度裁剪 | 奖励恒定、Q 值小，足够稳定 | 生产中常用 Huber 损失 + 梯度裁剪 |
| 标准 DQN 目标（非 Double） | 与讲义主线一致 | 讲义建议生产中默认用 Double DQN |
| 预热 32 条就训练 | 玩具环境步数少 | 真实任务预热几千条 |
| ε 线性衰减到 0.05 | 前期探索、后期利用 | 训练回报仍含约 3.75% 的非贪心动作 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表乘法初始化 | `[0.0] * (GRID * GRID)`、`[0.0] * n_hidden` | 创建定长、元素相同的列表（元素是不可变的 float，安全） |
| 嵌套列表推导式 | `[[rng.gauss(0, 0.2) for _ in range(n_in)] for _ in range(n_hidden)]` | 二维"矩阵"；注意**不能**写成 `[[0.0] * n] * m`，那样所有行是同一个列表 |
| 字典存多种参数 | `{"W1": ..., "b1": ..., ...}` | 用键名访问各层参数，类似 PyTorch 的 `state_dict` |
| 切片复制 | `row[:]`、`net["b1"][:]` | 浅拷贝一层列表；二维要逐行复制才算深拷贝 |
| `zip` 并行遍历 | `for row, b in zip(net["W1"], net["b1"])` | 同时取第 j 行权重和第 j 个偏置 |
| 生成器表达式求点积 | `sum(w * xi for w, xi in zip(row, x))` | 手写的向量点积 |
| `max(0.0, z)` | ReLU | 内置 `max` 实现激活函数 |
| 函数返回多个值 | `return q, h`；`q, _ = forward(...)` | 返回元组，用 `_` 丢弃不需要的部分 |
| `rng.randrange(n)` | `rng.randrange(len(ACTIONS))` | 随机整数 `[0, n)` |
| `rng.sample(population, k)` | `rng.sample(buffer, batch)` | 无放回随机抽 k 个 |
| `rng.gauss(mu, sigma)` | `rng.gauss(0, 0.2)` | 高斯随机数 |
| `list.pop(0)` | `buffer.pop(0)` | 删除并返回第一个元素（O(n)） |
| 原地修改可变参数 | `online["b1"][j] -= ...` | 函数修改传入的字典/列表，调用者可见（没有 return 也生效） |
| 取模判断周期 | `if step_count % sync_every == 0` | 每 N 步执行一次 |
| f-string 对齐 | `f"{a:<6}"`、`f"{i:3d}"`、`f"{v:6.2f}"` | `<` 左对齐、`3d` 宽度 3 的整数 |
| 未使用的 import | `import math` | 文件导入了 `math` 但没用到，可以删除 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 17 秒）的输出：

```text
=== DQN on 4x4 GridWorld (400 episodes, batch=32, target sync every 200 steps) ===

learning curve (mean return per block of 50 episodes):
  episodes   0- 49: mean = -28.06
  episodes  50- 99: mean = -14.70
  episodes 100-149: mean = -10.42
  episodes 150-199: mean =  -6.84
  episodes 200-249: mean =  -6.28
  episodes 250-299: mean =  -6.32
  episodes 300-349: mean =  -6.20
  episodes 350-399: mean =  -6.34

Q(0,0) per action:
  up     =  -6.79
  down   =  -5.88
  left   =  -6.74
  right  =  -5.87

greedy policy from trained net:
   > v v v
   v v v v
   v v v v
   > > > .
```

逐项解读：

- **学习曲线**：前 50 回合 ε 接近 1，几乎随机游走（50 步上限内常走不到终点），平均 -28；随着 ε 下降，回报快速提升；第 150–199 回合后稳定在 -6.2 ~ -6.3。讲义练习 1 问"滑动平均何时超过 -10"——按 50 回合分块，第 150–199 块（-6.84）首次超过 -10，前一块是 -10.42。
- **为什么不是 -6.0**：ε 最低是 0.05，每步仍有 3.75% 概率选非贪心动作。
- **Q(0,0) 与解析值对照**：γ=0.99 下 `Q*((0,0), down) = Q*((0,0), right) = -(1 − 0.99⁶)/(1 − 0.99) ≈ -5.85`；`Q*((0,0), up) = Q*((0,0), left) = -1 + 0.99 × (-5.85) ≈ -6.79`（撞墙浪费一步）。学到的 `-5.88 / -5.87 / -6.79 / -6.74` 与之非常接近，网络确实学到了 `Q*`。
- **贪心策略**：所有箭头都只向下或向右，全是最短路径，最优。`(0,0)` 选 `>` 是因为 right（-5.87）比 down（-5.88）略大——两者真值相等，差别来自近似误差。
- **运行时间 17 秒**：纯 Python 三重循环做矩阵运算的代价；同样的计算用 NumPy 会快两个数量级。

---

## 7. 动手改一改

1. 讲义练习 1：把每回合回报存下来，计算 20 回合滑动平均，找出首次超过 -10 的回合编号。
2. 用 `collections.deque(maxlen=capacity)` 替换列表回放，删掉 `pop(0)` 那两行（`random.sample` 可以直接作用于 deque）。
3. 讲义练习 2：把 `sync_every` 改为 1（≈ 没有目标网络），或每步只用最新一条转移训练（没有回放），比较学习曲线（参考测验 Q11：在这个玩具环境中两者都仍能收敛，思考为什么）。
4. 讲义练习 3：按测验 Q10 改成 Double DQN，并给奖励加上 `rng.gauss(0, 5)` 噪声，比较训练后 `max Q(0,0)` 与 `V*(0,0) ≈ -5.85` 的偏差。
5. 把 one-hot 换成两维连续特征 `[r / 3, c / 3]`，观察网络是否还能学好、是否更容易不稳定。
6. 把 MSE 换成 Huber 损失：当 `|td_error| > 1` 时梯度用 `sign(td_error)` 代替 `td_error`。

---

## 8. 常见坑

- **浅拷贝当深拷贝**：`target = online` 或 `dict(online)` 不会复制内层列表，目标网络会跟着在线网络一起变。
- **`[[0.0] * n] * m` 陷阱**：外层乘法复制的是同一个内层列表的引用，改一行等于改所有行；代码用的是推导式，正确。
- **对目标求梯度**：在 PyTorch 中忘记 `detach()` 或 `no_grad()`，目标也会被"优化"，训练行为完全改变。
- **只更新被选动作的输出**：如果误把损失写成对所有 4 个输出求和（例如把目标复制给所有动作），会把未执行动作的 Q 值也拉向错误目标。
- **done 与截断混淆**：50 步超时不是终止，不能把 `done` 设为 True。
- **回放预热太短 / ε 衰减太快**：真实任务中会在极少样本上过拟合、过早陷入局部最优。
- **把"玩具环境里消融无影响"推广到真实任务**：one-hot 小网格几乎是表格问题，目标网络和回放的价值要在高维、强泛化的场景中才显现。
