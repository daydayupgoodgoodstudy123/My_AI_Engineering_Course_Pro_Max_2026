# 测验 · JAX 简介（Introduction to JAX）

> **阶段 03 · 深度学习核心 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/jax_intro.py](../code/jax_intro.py) ｜ 代码讲解：[code/jax_intro.讲解.md](../code/jax_intro.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 函数式哲学 | 模型就是纯函数 `f(params, x) -> y`，参数显式传入传出，没有对象内部的可变状态 |
| 2 | `jax.numpy` 与不可变数组 | API 与 NumPy 几乎一致，但数组不可原地修改：`a[0] = 5` 不行，要写 `a = a.at[0].set(5)` |
| 3 | `jax.grad` | 输入一个（标量输出的）函数，返回它的梯度函数；默认对第一个参数求导；可以嵌套得到高阶导数 |
| 4 | `jax.value_and_grad` | 一次前向+反向同时返回 loss 值和梯度，训练步的标准写法 |
| 5 | `jax.jit` 与 XLA | 第一次调用时用抽象值**追踪（tracing）**函数，交给 XLA 编译（算子融合、去掉多余拷贝），之后同形状输入直接运行编译结果；依赖数值的 Python 控制流不能用 |
| 6 | `jax.vmap` | 把"处理单个样本"的函数自动变成"处理一批"；`in_axes` 指定每个参数沿哪一维批处理；`vmap(grad(...))` 一行得到逐样本梯度 |
| 7 | `pmap` 与多设备 | 把函数复制到多个设备、切分 batch，内部用 `jax.lax.pmean/psum` 同步梯度 |
| 8 | Pytree | 嵌套的 list/tuple/dict + 数组；`grad/jit/vmap` 都能遍历它，`jax.tree.map` 对所有叶子做同一操作 |
| 9 | 显式 PRNG key | 没有全局随机状态；每次随机操作都要一个 key，用 `random.split` 派生新 key，同一个 key 永远产生同样的随机数 |
| 10 | Optax 与生态 | 优化器 = `init` + `update`（梯度变换）+ `apply_updates`，状态 `opt_state` 由调用者持有；`optax.chain` 组合裁剪、Adam、调度；Flax/Equinox 提供层抽象 |

### 核心技能（能动手做到）

- [ ] 用纯函数写出 MLP 的 `init_params / forward / loss_fn`，参数是嵌套 dict，用 `random.split` 为每层分配独立的 key
- [ ] 写出 `@jax.jit` 的 `train_step`：`value_and_grad` → `optimizer.update` → `optax.apply_updates`，并返回新的 `params` 和 `opt_state`
- [ ] 用 `jax.grad` 嵌套求 `x³` 在 2.0 处的一阶、二阶导数并与手算结果核对
- [ ] 用 `jax.vmap(..., in_axes=(None, 0))` 把单样本预测函数变成批量预测，并说出输出形状
- [ ] 用 `jax.vmap(jax.grad(...), in_axes=(None, 0, 0))` 计算一个 batch 中每个样本的梯度范数
- [ ] 正确地给 JAX 代码计时：先预热（排除编译时间），并对每次结果调用 `block_until_ready()`
- [ ] 能逐行说明 PyTorch 训练循环中的 `zero_grad / backward / step` 在 JAX 中分别对应什么、为什么 JAX 不需要它们

---

## 二、基础自测（选择题）

**Q1.** 本节代码 `demo_grad()` 中：`f(x) = x ** 3`，`df = jax.grad(f)`，`d2f = jax.grad(df)`。`df(2.0)` 和 `d2f(2.0)` 分别是：

- A. 12.0 和 12.0
- B. 12.0 和 6.0
- C. 8.0 和 12.0
- D. 6.0 和 12.0

**Q2.** 下面的函数调用时会怎样？

```python
@jax.jit
def f(x):
    if x > 0:
        return x
    return -x

f(jnp.array(1.0))
```

- A. 正常返回 1.0
- B. 报错：追踪时 `x` 是抽象的 tracer，没有具体数值，Python 的 `if` 无法判断真假
- C. 返回 -1.0
- D. 自动为两个分支各编译一个版本

**Q3.** `jax.vmap(predict_single, in_axes=(None, 0))` 中 `in_axes=(None, 0)` 的含义是：

- A. 第一个参数沿第 0 维批处理，第二个参数不批处理
- B. 第一个参数（params）在所有样本间共享、不批处理；第二个参数（x）沿第 0 维批处理
- C. 两个参数都不批处理
- D. 输出沿第 0 维拼接，输入不变

**Q4.** 关于 JAX 数组 `a = jnp.array([1.0, 2.0, 3.0])`，正确的是：

- A. `a[0] = 5.0` 可以正常执行
- B. 应该写 `a = a.at[0].set(5.0)`，它返回一个新数组，原数组不变
- C. `a.at[0].set(5.0)` 会原地修改 `a`
- D. JAX 数组不支持任何形式的元素修改

**Q5.** 在 JAX 中下面两行执行后，`x1` 和 `x2` 的关系是：

```python
key = random.PRNGKey(0)
x1 = random.normal(key, (3,))
x2 = random.normal(key, (3,))
```

- A. 不同，因为每次调用都会推进全局随机状态
- B. 完全相同；要得到不同的随机数，必须先 `random.split(key)` 派生新 key
- C. 报错，同一个 key 不能用两次
- D. 不确定，取决于是否在 jit 内

**Q6.** 在 `@jax.jit` 装饰的函数里写了一句 `print(x)`，然后用不同数值、相同形状的输入调用这个函数 3 次。会看到：

- A. 打印 3 次，每次都是具体数值
- B. 只在第一次调用（追踪时）打印 1 次，打印的是一个 tracer（只有形状和 dtype，没有数值）；要在每次执行时打印数值应使用 `jax.debug.print`
- C. 一次都不打印
- D. 报错，jit 函数中不允许 print

**Q7.** `train()` 中 `n_batches = len(X_train) // batch_size`，即 `60000 // 128 = 468`，每个 epoch 丢掉最后 96 个样本。在 JAX 中这样做的一个**额外**好处是：

- A. 节省内存
- B. 所有 batch 形状相同，`train_step` 只需编译一次；如果最后来一个 96 样本的 batch，jit 会因为形状变化再编译一次
- C. 提升准确率
- D. 让随机打乱更均匀

**Q8.** 关于 Optax 的 `updates, opt_state = optimizer.update(grads, opt_state, params)`，正确的是：

- A. `optimizer.update` 会原地修改 `params`
- B. 优化器对象本身不保存状态，Adam 的一阶/二阶矩存放在 `opt_state` 里，由调用者显式传入、接收新值；`updates` 还需要 `optax.apply_updates(params, updates)` 才会作用到参数上
- C. `updates` 就是原始梯度
- D. 每次调用前必须先调用 `optimizer.zero_grad()`

---

## 三、动手 / 代码题

**Q9.** 下面是 `demo_jit()` 的计时部分。它想比较"逐算子执行（eager）"和"jit 编译后执行"的速度，但计时方法对两边并不公平。请指出至少两个问题，并给出修正后的计时代码。

```python
    fast_fn = jax.jit(slow_fn)
    _ = fast_fn(x)

    start = time.perf_counter()
    for _ in range(10):
        _ = slow_fn(x)
    eager_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(10):
        _ = fast_fn(x).block_until_ready()
    jit_time = time.perf_counter() - start
```

**Q10.** 讲义练习 2：用 `jax.vmap` 计算一个 batch（32 张 MNIST 图）中**每个样本**的梯度范数。注意本节的 `loss_fn(params, x, y)` 期望 `x` 是 `[B, 784]`、`y` 是 `[B]` 的批数据。请写出 `per_example_grad_norms(params, xb, yb)`，返回形状为 `[32]` 的数组。

**Q11.** 讲义练习 3：写一个通用的 `mlp_forward(params, x)`，对 `init_params` 产生的 `{'layer1': ..., 'layer2': ..., 'layer3': ...}` 这种结构，层数任意时都能正确前向（隐藏层用 ReLU，最后一层不加激活）。并说明在 `@jax.jit` 内使用 Python `for` 循环遍历层是否可以。

---

## 四、面试高频题

**Q12.**（基础必考）PyTorch 和 JAX 在设计理念上最大的区别是什么？什么情况下你会选择 JAX？

**Q13.**（原理深挖）`jax.jit` 是怎么工作的？什么情况下会触发重新编译？为什么 jit 要求纯函数？列举几个常见的"jit 陷阱"。

**Q14.**（原理深挖）什么是逐样本梯度（per-example gradients）？为什么普通的反向传播拿不到它？它在哪些场景下必不可少？

**Q15.**（工程实践）为什么 JAX 坚持用显式的 PRNG key，而不是像 PyTorch 那样用全局随机种子？在 JAX 里实现 Dropout 要怎么处理 key？

**Q16.**（场景设计）你要把本节的单卡训练扩展到 8 张卡做数据并行。用 JAX 你会怎么做？梯度同步发生在哪里？和 PyTorch DDP 相比有什么不同？

---

## 五、参考答案与解析

### Q1 — 答案：A

`f'(x) = 3x²`，`f'(2) = 12`；`f''(x) = 6x`，`f''(2) = 12`。巧合的是两者相等，所以运行时会看到 `f'(2.0)  = 12.0` 和 `f''(2.0) = 12.0`，而 `f(2.0) = 8.0`。这道题的重点是 `jax.grad(jax.grad(f))`：梯度函数本身也是普通函数，可以再求导——"JAX 把梯度挂在函数上，而不是挂在张量上"。

### Q2 — 答案：B

jit 追踪时传入的不是具体数值，而是只带形状和 dtype 的抽象值（tracer）。`if x > 0` 需要把 tracer 转成 Python 的 `bool`，这是做不到的，于是抛出 `TracerBoolConversionError`（属于 `ConcretizationTypeError` 一类）。正确写法是 `jnp.where(x > 0, x, -x)` 或 `jax.lax.cond(x > 0, lambda v: v, lambda v: -v, x)`。D 错：JAX 不会自动为分支编译多个版本。

### Q3 — 答案：B

`in_axes` 与函数参数一一对应：`None` 表示"这个参数不批处理，所有样本共用"，`0` 表示"沿第 0 维切开，每个样本取一片"。在 `demo_vmap` 中，`params` 共享，`batch_x` 的形状 `(5, 3)` 被切成 5 个 `(3,)`，输出形状为 `(5,)`。

### Q4 — 答案：B

JAX 数组不可变（immutable），`a[0] = 5.0` 会抛出 `TypeError`。`a.at[0].set(5.0)` 返回一个**新**数组（在 jit 内部，XLA 往往能把它优化成原地更新，但语义上仍是"返回新值"）。D 错：可以"修改"，只是以函数式的方式。不可变性正是 `grad/jit/vmap` 能够自由组合的前提。

### Q5 — 答案：B

JAX 的随机函数是纯函数：相同的 key + 相同的形状 → 相同的输出。所以 `x1` 与 `x2` 完全相同。正确做法：`key, subkey = random.split(key)`，用 `subkey` 生成随机数，留下 `key` 供以后继续 split。本节 `init_params` 用 `random.split(key, 3)` 为三层各分配一个 key，`train()` 每个 epoch 用 `key, subkey = random.split(key)` 生成新的打乱顺序，都是这个模式。

### Q6 — 答案：B

`print` 是 Python 的副作用，只在**追踪**时执行一次，此时 `x` 是 tracer，打印出来类似 `Traced<ShapedArray(float32[...])>`。之后两次调用形状相同，命中编译缓存，Python 函数体根本不再执行，所以不再打印。讲义："`jax.debug.print()` works inside JIT. Regular `print()` does not."

### Q7 — 答案：B

jit 的编译结果按输入的**形状和 dtype** 缓存。468 个 batch 都是 `[128, 784]`，只编译一次。如果保留最后 96 个样本的 batch，就会遇到新形状 `[96, 784]`，触发第二次编译（之后会缓存，但也是额外开销）。PyTorch 中对应的选项是 `DataLoader(..., drop_last=True)`。同理，`accuracy` 在代码中被用于 5000 和 10000 两种形状，会各编译一次。

### Q8 — 答案：B

这就是 JAX 的"显式状态"：`optax.adam(...)` 返回的是一对纯函数（`init`、`update`）；`opt_state = optimizer.init(params)` 创建初始状态（m、v、步数等）；每步 `update` 返回**变换后的更新量**和**新状态**。`updates` 已经包含了学习率和负号，所以 `apply_updates` 实际做的是 `params + updates`。JAX 没有 `.grad` 累加，所以也不需要 `zero_grad`（D 错）。

### Q9 — 参考答案

问题：
1. **eager 循环没有 `block_until_ready()`**：JAX 默认**异步派发**——函数返回时计算可能还没完成。jit 那边每次都等待结果，eager 那边不等，计时只测到了派发时间，对 eager 有利，结果不可信。
2. **eager 没有预热**：jit 版用 `_ = fast_fn(x)` 预热、排除了编译时间；但 eager 模式下每个算子第一次执行也要编译并缓存，这部分被算进了 `eager_time`，对 eager 不利。
3. （次要）预热调用 `_ = fast_fn(x)` 没有等待完成，它的执行可能与后面 eager 的计时重叠。
4. （次要）只测 10 次、没有重复取中位数，结果噪声较大。

修正：

```python
    fast_fn = jax.jit(slow_fn)
    fast_fn(x).block_until_ready()        # 预热 jit：编译 + 等待完成
    slow_fn(x).block_until_ready()        # 预热 eager：各算子的首次编译

    start = time.perf_counter()
    for _ in range(10):
        slow_fn(x).block_until_ready()
    eager_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(10):
        fast_fn(x).block_until_ready()
    jit_time = time.perf_counter() - start
```

补充：这里 jit 的收益主要来自把 10 次 `dot` + `norm` + 除法融合进一个 XLA 程序，省掉了逐算子的 Python 派发开销和中间结果的内存往返。在 1000×1000 矩阵乘法这种**计算密集**的负载下，大部分时间花在 matmul 本身，加速比往往不会特别夸张；算子小而多时，jit 的优势更明显。

### Q10 — 参考答案

```python
def per_example_grad_norms(params, xb, yb):
    def single_loss(params, x, y):
        # 把单个样本包装成大小为 1 的 batch，复用原来的 loss_fn
        return loss_fn(params, x[None, :], y[None])

    # params 共享（None），x 和 y 沿第 0 维逐样本（0）
    per_example_grads = jax.vmap(jax.grad(single_loss), in_axes=(None, 0, 0))(params, xb, yb)
    # per_example_grads 与 params 结构相同，但每个叶子多了一个长度为 32 的前导维

    def sq_norm(g):
        return jnp.sum(g.reshape(g.shape[0], -1) ** 2, axis=1)   # 每个样本的平方和，[32]

    leaves = jax.tree.leaves(per_example_grads)
    return jnp.sqrt(sum(sq_norm(g) for g in leaves))             # [32]


norms = jax.jit(per_example_grad_norms)(params, X_train[:32], y_train[:32])
```

要点：
- `jax.grad(single_loss)` 只处理**一个**样本，`vmap` 把它提升到 32 个样本，并且输出与 `params` 同结构的 pytree，每个叶子形状变为 `(32, *原形状)`，如 `layer1.w` 为 `(32, 784, 256)`。
- 梯度范数是**所有参数**的整体 L2 范数，所以要把每个叶子的平方和加起来再开方。
- 梯度最大的样本通常是**模型预测错误或很不自信**的样本（loss 大），也可能是标注错误或书写潦草的数字。这正是讲义练习 2 问"为什么"的答案。
- ⚠️ 显存：逐样本梯度是参数量的 32 倍（约 32 × 23.5 万个浮点数），batch 大或模型大时需要分块。

### Q11 — 参考答案

```python
def mlp_forward(params, x):
    names = sorted(params, key=lambda k: int(k[len("layer"):]))   # layer1, layer2, ..., layer10
    for name in names[:-1]:
        x = jax.nn.relu(jnp.dot(x, params[name]['w']) + params[name]['b'])
    last = params[names[-1]]
    return jnp.dot(x, last['w']) + last['b']
```

- 层数也可以用讲义提示的 `len(jax.tree.leaves(params)) // 2` 得到（每层 `w`、`b` 两个叶子）。注意 `jax.tree.leaves` 对 dict 按**键排序**展开，`'layer10'` 会排在 `'layer2'` 前面，所以按数字排序更稳妥；更简单的设计是把参数存成列表 `[{'w':..., 'b':...}, ...]`，天然有序。
- **在 jit 内用 Python `for` 遍历层是可以的**：循环次数由 pytree 的**结构**决定（追踪时已知、是静态的），JAX 会把循环"展开"成一串算子，本节 `demo_jit` 中的 `slow_fn` 也是这样。被禁止的是**依赖数组数值**的控制流（如 Q2）。讲义说"用 `jax.lax.scan` 替代 `for`"，指的是循环次数很大（展开会让编译变慢）或需要依赖数值的情形。
- 用 `assert jnp.allclose(mlp_forward(params, x), forward(params, x))` 验证与原 `forward` 一致。

### Q12 — 参考回答要点

- **核心区别**：PyTorch 是**面向对象 + 即时执行 + 可变状态**：参数存在 `nn.Module` 里，`.grad` 挂在张量上，优化器原地更新。JAX 是**函数式 + 编译**：模型是纯函数，参数是不可变的 pytree，显式传入传出；`grad/jit/vmap/pmap` 是对函数的**变换**，可以任意组合。
- **带来的差异**：JAX 可以把整个训练步编译成一个 XLA 程序（融合、跨设备切分），在大规模训练上效率很高；代价是调试更难（追踪 + 编译）、控制流受限、需要自己管理状态和随机数。
- **何时选 JAX**（讲义）：有 TPU；需要逐样本梯度、高阶导数等函数变换；超大规模多设备训练；团队已在 JAX 生态（Flax、Optax、Orbax）。否则默认 PyTorch——生态更大、调试更容易、招人更容易。
- **加分点**：PyTorch 也在向这个方向靠拢（`torch.compile`、`torch.func.grad/vmap`），JAX 也有 Flax/Equinox 提供类 Module 的体验，两者的差距在缩小。

### Q13 — 参考回答要点

- **原理**：第一次调用时，JAX 用抽象值（只有形状、dtype，没有数值）执行一遍 Python 函数，记录下所有 JAX 原语，得到中间表示（jaxpr），再交给 XLA 编译成针对该设备的优化代码。编译结果按"输入的形状、dtype、静态参数的值"缓存。
- **触发重新编译**：输入形状或 dtype 变化（如最后一个 batch 变小、变长序列）；标记为 `static_argnums` 的参数取值变化；函数对象本身变化（例如每次都在循环里新建 `jax.jit(lambda ...)`）。
- **为什么要纯函数**：Python 函数体只在追踪时执行一次，之后直接运行编译产物。副作用（print、修改全局变量、往列表 append、读取外部可变状态）只会在追踪时发生一次，之后"消失"；读取的全局变量会被当作**常量**固化进编译结果，之后修改它不会生效。
- **常见陷阱**：①依赖数值的 `if/while`（用 `jnp.where`、`lax.cond`、`lax.while_loop`）；②计时不调用 `block_until_ready()`；③形状不固定导致反复编译；④Python 循环次数极大时展开导致编译很慢（改用 `lax.scan/fori_loop`）；⑤在 jit 内 `print` 看不到数值（用 `jax.debug.print`）。
- **加分点**：本节 `train_step` 读取了全局的 `optimizer`——它在追踪时被固化，之后如果重新给 `optimizer` 赋值，已编译的 `train_step` 不会感知到。

### Q14 — 参考回答要点

- **定义**：一个 batch 里每个样本各自的梯度 `∇θ L(xᵢ, yᵢ)`，而不是它们的平均。
- **为什么普通反向拿不到**：标准反向传播在 batch 维上对梯度**求和/平均**后才得到参数梯度（如 `∂L/∂W = Σᵢ gᵢ xᵢᵀ`），逐样本的信息在求和时就丢了。朴素做法是 batch size = 1 跑 B 次，非常慢。
- **JAX 方案**：`jax.vmap(jax.grad(loss_single), in_axes=(None, 0, 0))`，一行、向量化、可 jit（讲义："Per-example gradients. One line."）。PyTorch 现在也有 `torch.func.vmap(torch.func.grad(...))`，讲义说的"PyTorch 中几乎不可能"已经不完全准确。
- **必不可少的场景**：
  - **差分隐私训练 DP-SGD**：必须先把每个样本的梯度裁剪到阈值 C，再求和加噪声；
  - 数据质量分析：梯度范数大的样本往往是难例或标注错误；
  - 影响函数、数据价值评估、主动学习中的不确定性估计。
- **代价**：显存是普通梯度的 B 倍。

### Q15 — 参考回答要点

- **为什么显式 key**：①纯函数要求同样的输入得到同样的输出，全局随机状态是隐藏的副作用，与 jit/vmap 冲突；②可复现：给定 key，结果在不同设备、不同编译、不同并行方式下都确定（讲义：PyTorch 的 `torch.manual_seed` 在多 GPU 场景下无法保证这一点）；③可并行：`split` 能派生出统计上独立的子 key，各设备、各层各用各的，不需要共享一个顺序状态。
- **规则**：一个 key 只用一次；需要新的随机数就 `split`；不要把同一个 key 传给两个不同的随机操作。
- **Dropout 的实现**（讲义练习 1）：前向函数增加 `key` 参数和 `training` 标志；每个 dropout 层用 `split` 得到的独立子 key 生成 `random.bernoulli(subkey, 1-p, x.shape)` 掩码，`x * mask / (1-p)`；`train_step` 每步接收新的 key（训练循环中 `key, subkey = random.split(key)`），评估时直接返回 x。Flax 中对应 `model.apply(..., rngs={'dropout': key})`。
- **常见误区**：在训练循环里反复使用同一个 key，结果每一步的 dropout 掩码完全一样，等于没有随机性。

### Q16 — 参考回答要点

- **JAX 写法（讲义的 pmap 方案）**：
  1. 把参数和优化器状态**复制**到 8 个设备（例如用 `jax.device_put_replicated`，或把每个叶子堆叠出一个大小为 8 的前导维）；
  2. 把全局 batch reshape 成 `[8, B/8, ...]`；
  3. `train_step` 中算出本地梯度后，用 `grads = jax.lax.pmean(grads, axis_name='devices')` 在所有设备间求平均，再各自做相同的 optax 更新——因为初值相同、梯度相同，各设备参数始终保持一致；
  4. `jax.pmap(train_step, axis_name='devices')` 编译并在 8 个设备上并行执行。
- **梯度同步位置**：就在 `pmean` 那一行，是一次 all-reduce，由 XLA 编进同一个程序里。
- **与 PyTorch DDP 的对比**：DDP 在 `loss.backward()` 过程中通过 hook 自动按桶（bucket）做 all-reduce，通信与反向计算重叠，用户代码几乎不变；JAX 中同步是函数里**显式**的一行集合通信，语义清晰，也更容易改成其他并行策略。
- **加分点**：新版 JAX 更推荐用 `jax.jit` + sharding（`Mesh`、`NamedSharding`）或 `shard_map` 来表达数据并行/模型并行，`pmap` 正在被它们取代（讲义也提到 `shard_map` 是其后继）。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：本节处处与 PyTorch 对照。
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：面向对象的 Module 设计，正好是 JAX 函数式设计的反面。
- [阶段 01 · 05 链式法则与自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：`jax.grad` 的数学基础。
- [阶段 03 · 06 Optimizers](../../06-optimizers/docs/zh.md)、[08 Weight 初始化](../../08-weight-initialization/docs/zh.md)：Adam 与 He 初始化在本节以纯函数形式重现。

### 本节被哪些后续内容用到
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：梯度范数、loss 曲线等诊断手段，JAX 中同样适用。
- [阶段 01 · 12 张量运算](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：`jnp` 的广播与形状规则。
- [阶段 10 · 05 扩展与分布式训练](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：数据并行、模型并行，对应 `pmap` / sharding。
- [阶段 19 · 77 数据并行 DDP](../../../19-capstone-projects/77-data-parallel-ddp/docs/zh.md)：Q16 中 PyTorch 一侧的实现。
- [阶段 18 · 22 LLM 的差分隐私](../../../18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/zh.md)：DP-SGD 依赖逐样本梯度裁剪，正是 `vmap(grad)` 的典型应用。

### 延伸关键词
`XLA` · `jaxpr / tracing` · `static_argnums` · `block_until_ready` · `jax.lax.scan / cond` · `pytree` · `jax.tree.map` · `PRNGKey / split` · `Optax chain` · `Flax / Equinox / Orbax` · `shard_map / NamedSharding` · `per-example gradients` · `DP-SGD`
