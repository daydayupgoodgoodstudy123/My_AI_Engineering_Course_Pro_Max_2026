# 代码讲解 · jax_intro.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 12 节 JAX 简介 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python jax_intro.py`（无命令行参数；会通过 `sklearn.datasets.fetch_openml` 联网下载 MNIST） ｜ **依赖**：`jax`（含 `jaxlib`）、`optax`、`scikit-learn`（仅 `get_mnist_data` 内部导入）；GPU/TPU 可选

---

## 1. 这份代码在考察什么

同样是 784→256→128→10 的 MNIST MLP，上一节用 PyTorch 的面向对象写法，这一节换成 JAX 的**纯函数**写法。代码短（180 行），但每一行都在体现一种不同的思维方式：

1. **模型 = 纯函数 + 参数 pytree**：没有 `nn.Module`、没有 `self`，参数是一个嵌套 dict，显式地传进传出。
2. **梯度是函数的变换**：`jax.grad(f)` 返回一个新函数；`jax.value_and_grad` 一次拿到 loss 和梯度；嵌套 `grad` 得到高阶导数。
3. **jit 编译**：整个训练步（前向 + 反向 + Adam 更新）被编译成一个 XLA 程序，第一次调用慢，之后很快。
4. **vmap 自动批处理**：只写处理单个样本的函数，`vmap` 把它变成批处理版本。
5. **显式随机数**：没有全局种子，每次随机操作都需要一个 key，用 `split` 派生。
6. **Optax 的函数式优化器**：优化器状态 `opt_state` 也是一个显式传递的 pytree。

> 一句话：**PyTorch 里藏在对象和 `.grad` 里的状态，在 JAX 里全部摆到函数签名上**——这让编译器可以把整个训练步当成一个数学函数来优化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------------|
| `get_mnist_data` | 函数 | 用 `fetch_openml` 下载 MNIST，归一化，按 60000/10000 切分 | 数据准备（NumPy 数组） |
| `init_params(key)` | 函数 | 用 He 初始化生成三层参数，返回嵌套 dict | pytree、显式 PRNG |
| `forward(params, x)` | 纯函数 | 三层 MLP 前向，输出 logits | 函数式模型 |
| `loss_fn(params, x, y)` | 纯函数 | `log_softmax` + one-hot 手写交叉熵 | 标量损失 |
| `optimizer` | 模块级对象 | `optax.adam(1e-3)` | Optax 梯度变换 |
| `train_step` | `@jax.jit` 函数 | `value_and_grad` → `optimizer.update` → `apply_updates` | 编译后的训练步 |
| `accuracy` | `@jax.jit` 函数 | argmax 后与标签比较取平均 | 评估 |
| `train()` | 函数 | 10 个 epoch 的训练循环：split key、打乱、切批、记录 | 训练循环 |
| `demo_grad` | 演示 | `x³` 的一阶、二阶导数 | 可组合的 `grad` |
| `demo_vmap` | 演示 | 单样本线性预测 → 5 个样本批量预测 | `vmap` 与 `in_axes` |
| `demo_jit` | 演示 | 同一函数 eager 与 jit 的计时对比 | jit、异步派发 |

调用关系：入口依次运行 `demo_grad` → `demo_vmap` → `demo_jit` → `train()`。`train()` 内部：`get_mnist_data` → `init_params` → `optimizer.init` → 每个 batch 调用 `train_step`（内部调用 `loss_fn` → `forward`）→ 每个 epoch 末调用 `accuracy`（内部调用 `forward`）。

---

## 3. 逐段精讲

### 3.1 数据：NumPy 数组 → JAX 数组

```python
def get_mnist_data():
    from sklearn.datasets import fetch_openml
    mnist = fetch_openml('mnist_784', version=1, as_frame=False, parser='auto')
    X = mnist.data.astype('float32') / 255.0
    y = mnist.target.astype('int')
    X_train, X_test = X[:60000], X[60000:]
    y_train, y_test = y[:60000], y[60000:]
    return X_train, y_train, X_test, y_test
```

- 与上一节手工解析 IDX 文件不同，这里借用 scikit-learn 从 OpenML 下载。`mnist_784` 共 70000 张图，前 60000 张是标准训练集、后 10000 张是测试集，与官方划分一致。
- `as_frame=False`：返回 NumPy 数组而不是 pandas DataFrame。
- `mnist.target` 在 OpenML 中是**字符串**（`'5'`、`'0'`…），所以要 `.astype('int')`。
- `import` 写在函数内部：只有真正下载数据时才需要 sklearn，`demo_*` 部分不受影响（延迟导入）。
- 在 `train()` 里通过 `jnp.array(X_train)` 把 NumPy 数组转成 JAX 数组，放到默认设备（有 GPU 就是 GPU）上。整个训练集约 188 MB，一次性放进设备内存。

### 3.2 `init_params`：参数就是一个嵌套 dict

```python
def init_params(key):
    k1, k2, k3 = random.split(key, 3)
    scale1 = jnp.sqrt(2.0 / 784)
    # ...
    params = {
        'layer1': {
            'w': scale1 * random.normal(k1, (784, 256)),
            'b': jnp.zeros(256),
        },
        # layer2: (256, 128)，layer3: (128, 10)
    }
    return params
```

- **显式 PRNG**：`random.split(key, 3)` 从一个 key 派生出 3 个独立的子 key，每层用一个。如果三层都用同一个 key，`random.normal` 会生成"相关"的随机数（同 key 同形状时完全相同），初始化就不再独立。
- **He 初始化**：`scale = √(2/fan_in)`，与第 08 节和第 10 节的 `Linear` 一致，适配 ReLU。
- **pytree**：这个嵌套 dict 就是模型的全部状态。`grad`、`jit`、`tree.map`、Optax 都能自动遍历它的叶子（6 个数组）。讲义："The tree structure is the model."
- **权重布局**：这里 `w` 的形状是 `(fan_in, fan_out)`，前向写 `x @ w`；PyTorch `nn.Linear.weight` 是 `(out, in)`，前向是 `x @ Wᵀ`。在两个框架之间迁移权重时要转置。
- 参数总数与上一节相同：235,146。

### 3.3 `forward` 与 `loss_fn`：纯函数

```python
def forward(params, x):
    x = jnp.dot(x, params['layer1']['w']) + params['layer1']['b']
    x = jax.nn.relu(x)
    x = jnp.dot(x, params['layer2']['w']) + params['layer2']['b']
    x = jax.nn.relu(x)
    x = jnp.dot(x, params['layer3']['w']) + params['layer3']['b']
    return x


def loss_fn(params, x, y):
    logits = forward(params, x)
    one_hot = jax.nn.one_hot(y, 10)
    return -jnp.mean(jnp.sum(jax.nn.log_softmax(logits) * one_hot, axis=-1))
```

- **纯函数**：输出只依赖输入 `params` 和 `x`，不读写任何外部状态。这是 `grad` 和 `jit` 能工作的前提。
- `x` 的形状是 `[B, 784]`，`jnp.dot(x, w)` 得到 `[B, 256]`，再加 `b`（形状 `[256]`，自动广播到每一行）。
- **交叉熵手写**：`log_softmax(logits)` 得到 `[B, 10]` 的对数概率；乘以 one-hot 后每行只剩真实类别那一项；`sum(axis=-1)` 取出它；`-mean` 得到平均负对数似然。数学上等价于 PyTorch 的 `CrossEntropyLoss`。
- 用 `log_softmax` 而不是 `log(softmax(...))`：前者内部用 log-sum-exp 技巧，数值稳定。
- 和 PyTorch 一样，`forward` 输出 logits，不做 softmax。
- `loss_fn` 返回**标量**——`jax.grad` 要求被求导的函数输出标量。

### 3.4 `train_step`：一次编译，三步合一

```python
optimizer = optax.adam(learning_rate=1e-3)


@jax.jit
def train_step(params, opt_state, x, y):
    loss, grads = jax.value_and_grad(loss_fn)(params, x, y)
    updates, opt_state = optimizer.update(grads, opt_state, params)
    params = optax.apply_updates(params, updates)
    return params, opt_state, loss
```

逐行对照 PyTorch：

| JAX | 做了什么 | PyTorch 对应 |
|-----|---------|-------------|
| `jax.value_and_grad(loss_fn)(params, x, y)` | 构造"返回 (loss, 梯度)"的新函数并立即调用；默认对**第一个参数** `params` 求导，梯度与 `params` 同结构 | `loss = criterion(model(x), y)` + `loss.backward()` |
| `optimizer.update(grads, opt_state, params)` | Adam 把梯度变换成更新量（含学习率、负号、偏差修正），返回新的 `opt_state` | `optimizer.step()` 的前半部分 |
| `optax.apply_updates(params, updates)` | 对每个叶子做 `p + u`，返回**新的** params | `optimizer.step()` 的后半部分（原地 `p -= ...`） |
| （无） | 梯度不累加在任何地方，每次都是新算的 | `optimizer.zero_grad()` |

- **为什么没有 `zero_grad`**：JAX 的梯度是函数的返回值，不存在"挂在张量上、默认累加"的 `.grad`，自然不需要清零。
- **为什么返回新的 `params` 和 `opt_state`**：数组不可变，只能"用旧状态算出新状态"。调用方写 `params, opt_state, loss = train_step(params, opt_state, xb, yb)`，把新状态接回来。
- **`@jax.jit` 的效果**：第一次调用时追踪整个函数（前向、反向、Adam），交给 XLA 编译成一个程序；之后每次调用直接运行编译产物，没有逐算子的 Python 开销。这也是讲义所说"第一个 epoch 慢、之后快"的原因。
- ⚠️ `optimizer` 是**模块级全局变量**，`train_step` 在追踪时读取它，Adam 的超参数随即被"烧"进编译结果。如果之后重新给 `optimizer` 赋值（比如换学习率），已编译的 `train_step` 不会感知到，因为相同形状的输入会命中缓存。更稳妥的写法是把优化器作为闭包参数，或用 `functools.partial` 生成 `train_step`。

### 3.5 `accuracy`：评估也可以 jit

```python
@jax.jit
def accuracy(params, x, y):
    logits = forward(params, x)
    preds = jnp.argmax(logits, axis=-1)
    return jnp.mean(preds == y)
```

- 布尔数组取 `mean` 得到正确率（True 当 1，False 当 0）。
- JAX 没有"训练/评估模式"的概念——这个模型没有 Dropout/BN，`forward` 在训练和评估中完全相同。如果加 Dropout（讲义练习 1），就需要给 `forward` 增加 `key` 和 `training` 参数。
- jit 按输入形状缓存编译结果：本文件用 `X_train[:5000]`（5000 行）和 `X_test`（10000 行）调用，会各编译一次。

### 3.6 `train()`：显式 key + 固定形状的 batch

```python
    key = random.PRNGKey(0)
    params = init_params(key)
    opt_state = optimizer.init(params)

    batch_size = 128
    n_epochs = 10

    for epoch in range(n_epochs):
        key, subkey = random.split(key)
        perm = random.permutation(subkey, len(X_train))
        X_shuffled = X_train[perm]
        y_shuffled = y_train[perm]

        epoch_loss = 0.0
        n_batches = len(X_train) // batch_size
        for i in range(n_batches):
            start = i * batch_size
            xb = X_shuffled[start:start + batch_size]
            yb = y_shuffled[start:start + batch_size]
            params, opt_state, loss = train_step(params, opt_state, xb, yb)
            epoch_loss += loss

        train_acc = accuracy(params, X_train[:5000], y_train[:5000])
        test_acc = accuracy(params, X_test, y_test)
```

- `optimizer.init(params)`：根据参数的结构创建 Adam 的状态（与参数同形状的 m、v，以及步数计数）。
- **每个 epoch 一个新 key**：`key, subkey = random.split(key)`，用 `subkey` 生成打乱顺序，留下 `key` 给下一个 epoch。如果每次都用同一个 key，每个 epoch 的打乱顺序将完全相同。
- ⚠️ 一个小细节：`init_params(key)` 和第一个 epoch 的 `random.split(key)` 消费的是**同一个** `key`，违反了"一个 key 只用一次"的规则。`init_params` 内部做 `split(key, 3)`，这里做 `split(key)`（分成 2 份）。在较新版本的 JAX 中，`split` 默认采用"逐下标派生"的方案（`jax_threefry_partitionable` 配置），第 i 个子 key 与总份数无关，于是第一个 epoch 的 `subkey` 可能正好等于第二层初始化用的 `k2`。对训练效果影响很小，但这是典型的 key 复用。规范写法：先 `key, init_key = random.split(key)`，再 `params = init_params(init_key)`。
- `X_train[perm]`：用下标数组做"花式索引"，在设备上生成打乱后的**新数组**（原数组不变）。
- **丢弃余数**：`60000 // 128 = 468` 个 batch，每个 epoch 丢掉最后 96 个样本。好处不只是简单：所有 batch 形状都是 `[128, 784]`，`train_step` 只编译一次；否则最后一个 `[96, 784]` 的 batch 会触发一次额外编译。
- `epoch_loss += loss`：`loss` 是设备上的 JAX 数组，这里的加法也在设备上进行、不强制同步，所以 Python 循环可以持续地往设备派发工作（JAX 的**异步派发**）。对比上一节 PyTorch 中的 `loss.item()`，那会每步都等 GPU 算完。
- 训练准确率只在前 5000 个训练样本上算，是为了省时间的抽样估计。
- 讲义的预期：10 个 epoch 后测试准确率约 97%。

### 3.7 `demo_grad`：梯度是可以再求导的函数

```python
    def f(x):
        return x ** 3

    df = jax.grad(f)
    d2f = jax.grad(df)
    print(f"f(2.0)   = {f(2.0)}")
    print(f"f'(2.0)  = {df(2.0)}")
    print(f"f''(2.0) = {d2f(2.0)}")
```

- `jax.grad(f)` 返回一个新函数 `df`，`df(x) = 3x²`；对 `df` 再 `grad` 得到 `d2f(x) = 6x`。
- 在 x = 2：`f = 8`、`f' = 12`、`f'' = 12`（一阶和二阶导恰好相等）。
- `f(2.0)` 是普通 Python 运算，结果是 Python float `8.0`；`df(2.0)` 返回的是 0 维 JAX 数组，打印出来也是 `12.0`。
- ⚠️ `jax.grad` 要求输入是**浮点数**：`df(2)`（整数）会报错，必须写 `df(2.0)`。

### 3.8 `demo_vmap`：只写单样本版本

```python
    params = {'w': random.normal(k1, (3,)), 'b': 0.0}

    def predict_single(params, x):
        return jnp.dot(params['w'], x) + params['b']

    batch_x = random.normal(k2, (5, 3))
    batch_predict = jax.vmap(predict_single, in_axes=(None, 0))
    results = batch_predict(params, batch_x)
```

- `predict_single` 只处理一个 3 维向量 `x`，输出标量。
- `in_axes=(None, 0)`：`params` 不批处理（所有样本共用），`batch_x` 沿第 0 维切开。结果形状 `(5,)`。
- `vmap` 不是在 Python 里循环 5 次，而是**改写函数的计算**，让它直接对 `[5, 3]` 的输入做一次向量化运算——等价于手写的 `batch_x @ params['w'] + params['b']`。
- 价值在于：你只需要写"单个样本"这种最自然、最不容易出错的版本，批维度交给 `vmap` 处理。配合 `grad` 就能得到逐样本梯度：`jax.vmap(jax.grad(loss_fn), in_axes=(None, 0, 0))`。
- `'b': 0.0` 是 Python float，也是 pytree 的合法叶子。

### 3.9 `demo_jit`：编译的威力与计时陷阱

```python
    def slow_fn(x):
        for _ in range(10):
            x = jnp.dot(x, x)
            x = x / jnp.linalg.norm(x)
        return x

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

- `jax.jit(slow_fn)` 是装饰器的**函数调用写法**，与 `@jax.jit` 等价，好处是同时保留了未编译的 `slow_fn`，便于对比。
- `slow_fn` 中有一个 Python `for` 循环：循环次数 10 是固定的，追踪时会被**展开**成 10 组 `dot + norm + 除法`，在 jit 中完全合法。jit 禁止的是**依赖数组数值**的控制流。
- `_ = fast_fn(x)` 是**预热**：第一次调用触发追踪和编译，把编译时间排除在计时之外。
- `.block_until_ready()`：JAX 默认异步派发，函数返回时计算可能还在进行，计时必须等结果就绪。
- ⚠️ **计时不公平**：eager 循环里没有 `block_until_ready()`，测到的可能只是派发时间，对 eager 有利；同时 eager 没有预热，各算子首次执行时的编译开销被算进了 `eager_time`，又对 eager 不利。正确做法是两边都预热、都 `block_until_ready()`（参见测验 Q9）。因此打印的 `Speedup` 只能作为粗略参考。
- 为什么 jit 会更快：XLA 把整个循环当成一个程序，能融合算子、减少中间结果的内存读写、消除每个算子的 Python 派发开销。对于 1000×1000 矩阵乘法这种计算密集型任务，大部分时间花在 matmul 本身，加速比可能不太大；对很多小算子组成的函数，加速会明显得多。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 参数用嵌套 dict（pytree） | 最直接地体现"模型 = 数据 + 纯函数"，所有变换都能遍历 | 层多了手写 dict 很繁琐；生产中用 Flax/Equinox 自动生成 |
| 手写 `forward`，层数固定 | 每一步都看得见 | 不通用；讲义练习 3 要求写任意层数的版本 |
| 手写交叉熵（`log_softmax` + one-hot） | 展示交叉熵的定义 | 生产中用 `optax.softmax_cross_entropy_with_integer_labels`，省掉 one-hot |
| `optimizer` 放在模块级 | `train_step` 签名简洁 | 被 jit 固化为常量；需要切换优化器时应改为参数或闭包 |
| 整个训练步 `@jax.jit` | 前向 + 反向 + 更新融合成一个 XLA 程序，速度最快 | 第一次调用有编译开销；调试时看不到中间值 |
| 丢弃最后不足一批的样本 | 形状固定，只编译一次 | 每个 epoch 少用 96 个样本；也可以把最后一批 pad 到 128 再用掩码 |
| 每个 epoch `split` 出新 key 打乱 | 可复现、每个 epoch 顺序不同 | 需要手动管理 key 的传递；本文件初始化与第一次打乱复用了同一个 `key`，应先 split 出 `init_key` |
| 数据整体放进设备内存，用花式索引取 batch | 简单，MNIST 放得下 | 大数据集需要 `tf.data` / Grain 之类的流式数据管线 |
| 训练准确率只用前 5000 个样本 | 节省评估时间 | 是抽样估计，不是全量训练准确率 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as` / `from ... import` | `import jax.numpy as jnp`；`from jax import random` | 起别名、直接导入子模块 |
| 函数内导入 | `get_mnist_data` 中的 `from sklearn.datasets import fetch_openml`；`demo_jit` 中的 `import time` | 延迟导入：只有执行到这里才需要该依赖 |
| 嵌套 dict 字面量 | `params = {'layer1': {'w': ..., 'b': ...}, ...}` | JAX 的 pytree 最常见的形式 |
| 多重下标 | `params['layer1']['w']` | 逐层取出嵌套字典中的值 |
| 元组解包 | `k1, k2, k3 = random.split(key, 3)`；`key, subkey = random.split(key)` | `split` 返回的数组可以直接按行解包 |
| 多返回值 | `return params, opt_state, loss` 与 `params, opt_state, loss = train_step(...)` | 函数式风格：新状态通过返回值传出 |
| 函数是一等公民 | `df = jax.grad(f)`；`d2f = jax.grad(df)`；`fast_fn = jax.jit(slow_fn)` | 函数可以作为参数传入、作为返回值返回 |
| 立即调用返回的函数 | `jax.value_and_grad(loss_fn)(params, x, y)` | 第一对括号构造新函数，第二对括号调用它 |
| 装饰器 | `@jax.jit` | 等价于 `train_step = jax.jit(train_step)` |
| 嵌套函数定义 | `demo_grad` 内的 `def f(x)`；`demo_vmap` 内的 `def predict_single` | 定义只在外层函数内可见的局部函数 |
| 切片 | `X[:60000]`、`X[60000:]`、`X_shuffled[start:start + batch_size]` | 左闭右开区间 |
| 花式索引 | `X_train[perm]` | 用下标数组一次取出多行，得到新数组 |
| 整除 `//` | `len(X_train) // batch_size` | 向下取整，自然丢掉余数 |
| `_` 占位变量 | `for _ in range(10)`；`_ = fast_fn(x)` | 表示"不关心这个值" |
| 方法链 | `fast_fn(x).block_until_ready()` | 在返回值上继续调用方法 |
| `time.perf_counter()` | `demo_jit` | 高精度计时器，适合测短时间间隔 |
| f-string 与格式符 | `f"{epoch + 1:2d}"`、`f"{epoch_loss / n_batches:.4f}"`、`f"{eager_time / jit_time:.1f}x"` | 花括号内可写表达式；JAX 的 0 维数组也支持 `:.4f` 格式化 |
| 相邻字符串自动拼接 | `print(f"Epoch ..." f"Train Acc: ...")` | 括号内跨行的字符串字面量会自动连接 |
| `if __name__ == '__main__':` | 文件末尾 | 直接运行才执行演示与训练 |

---

## 6. 运行结果解读

> **未实际运行**（原因：当前环境未安装 `jax`、`optax`、`scikit-learn`，且训练部分需要联网下载 MNIST）。以下为根据代码与讲义推断的预期输出。

**可以精确推出的部分**：

```text
=== jax.grad demo ===
f(2.0)   = 8.0          ← 2³
f'(2.0)  = 12.0         ← 3·2²
f''(2.0) = 12.0         ← 6·2（与一阶导恰好相等）

=== jax.vmap demo ===
Input shape:  (5, 3)
Output shape: (5,)      ← 5 个样本各输出一个标量
Predictions:  [ ...5 个数... ]   ← 取决于 PRNGKey(42) 生成的随机数
```

**依赖硬件的部分**：

```text
=== jax.jit demo ===
Eager: x.xxxxs
JIT:   x.xxxxs
Speedup: x.xx
```

- 具体数值取决于 CPU/GPU。如 3.9 所述，eager 一侧计时既缺少 `block_until_ready()` 又没有预热，打印的加速比只是粗略参考。

**训练部分**（讲义给出的预期）：

```text
=== MNIST Training ===
Epoch  1 | Loss: ... | Train Acc: ... | Test Acc: ...
...
Epoch 10 | Loss: ... | Train Acc: ... | Test Acc: ~0.97
```

- **第 1 个 epoch 明显较慢**：`train_step` 和 `accuracy` 首次调用时要追踪和编译；从第 2 个 epoch 起直接运行编译产物。
- 由于 `PRNGKey(0)` 固定，在同一台机器、同一版本的 JAX 下，初始化和打乱顺序是可复现的。
- Loss 是 468 个 batch 的平均值，应随 epoch 稳步下降；Train Acc 是前 5000 个训练样本上的准确率，通常略高于 Test Acc。

---

## 7. 动手改一改

1. **修正计时**：按测验 Q9 的方法，给 eager 一侧也加上预热和 `block_until_ready()`，比较修正前后的 `Speedup`；再把矩阵改小到 100×100，看加速比怎么变化（讲义练习 4）。
2. **逐样本梯度（讲义练习 2）**：用 `jax.vmap(jax.grad(...), in_axes=(None, 0, 0))` 计算 32 张图的梯度范数，找出范数最大的几张图，看它们是否是被模型分错的样本。
3. **通用 MLP（讲义练习 3）**：把参数改成列表 `[{'w':..., 'b':...}, ...]`，写一个 `mlp_forward` 支持任意层数，并让 `init_params` 接收 `sizes=[784, 256, 128, 10]`。
4. **加 Dropout（讲义练习 1）**：给 `forward` 增加 `key` 和 `training` 参数，用 `random.bernoulli` 生成掩码；`train_step` 每步接收一个新的 subkey；比较测试准确率。
5. **梯度裁剪（讲义练习 5）**：把优化器换成 `optax.chain(optax.clip_by_global_norm(1.0), optax.adam(1e-3))`，并用 `optax.global_norm(grads)` 记录每步的梯度范数。
6. **观察重编译**：去掉 `// batch_size` 的丢弃逻辑，让最后一个 batch 只有 96 个样本，在 `train_step` 里加一句 Python `print("tracing")`，看它在什么时候被打印。

---

## 8. 常见坑

- **用 `print` 调试 jit 函数**：只在追踪时打印一次 tracer；看数值要用 `jax.debug.print`，或者先去掉 `@jax.jit` 调试。
- **在 jit 内写依赖数值的 `if`**：会报 `TracerBoolConversionError`，改用 `jnp.where` 或 `jax.lax.cond`。
- **重复使用同一个 PRNG key**：同 key 同形状产生完全相同的随机数，打乱顺序、dropout 掩码都会"不随机"。
- **忘记把新状态接回来**：写成 `train_step(params, opt_state, xb, yb)` 而不赋值，参数永远不会更新——JAX 不会原地修改任何东西。
- **计时不加 `block_until_ready()`**：异步派发让计时严重失真。
- **输入形状不断变化**：每种新形状都会触发一次编译，变长序列、不完整 batch 都可能让训练"莫名其妙地慢"。
- **`jax.grad` 传入整数**：`df(2)` 会报错，要写 `df(2.0)`。
