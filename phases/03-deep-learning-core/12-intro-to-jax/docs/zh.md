<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="introduction-to-jax"></a>

# JAX简介

> PyTorch 突变 tensors。 TensorFlow 构建图表。 JAX 编译纯函数。最后一个改变了你对深度学习的看法。

**类型：** 构建
**语言：** Python
**先决条件：** 第 03 阶段课程 01-10，基础 NumPy
**时间：** ~90 分钟

<a id="learning-objectives"></a>

## 学习目标

- 使用JAX的函数式API编写纯函数神经网络代码（jax.numpy、jax.grad、jax.jit、 jax.vmap)
- 解释PyTorch的eagermutation和JAX的函数式编译模型之间的关键设计差异
- 与简单的 Python 相比，应用 jit 编译和 vmap 矢量化来加速训练循环
- 在 JAX 中训练一个简单的网络，并将显式状态管理与 PyTorch 的面向对象方法进行对比

<a id="the-problem"></a>

## 问题

您知道如何在 PyTorch 中构建神经网络。你定义一个`nn.Module`，调用`.backward()`，单步执行optimizer。有用。数百万人使用它。

但 PyTorch 的 DNA 中有一个约束：它在 Python 中急切地一次操作一个 traces。每个 `tensor + tensor` 都是一个单独的内核启动。每个训练步骤都会重新解释相同的 Python 代码。在您需要在 2,048 个 TPU 上训练 5400 亿个 parameter 模型之前，这种方法工作得很好。那么开销就会杀死你。

Google DeepMind 在 JAX 上训练 Gemini。 Anthropic 在 JAX 上训练 Claude。这些都不是小规模的操作——它们是地球上最大的神经网络训练运行。他们选择 JAX 是因为它将您的训练循环视为可编译程序，而不是一系列 Python 调用。

JAX是NumPy，具有自动微分、JIT编译为XLA、自动矢量化三大超能力。您编写一个处理一个示例的函数。 JAX 为您提供了一个处理批处理、计算 gradients、编译为机器代码并跨多个设备运行的函数。全部不改变原有功能。

<a id="the-concept"></a>

## 概念

<a id="the-jax-philosophy"></a>

### JAX理念

JAX是一个功能框架。没有类，没有可变状态，没有 `.backward()` 方法。相反：

| PyTorch | JAX |
|---------|-----|
| `nn.Module` 类带状态 | 纯函数：`f(params, x) -> y` |
| `loss.backward()` | `jax.grad(loss_fn)(params, x, y)` |
| 热切的执行力 | 通过 XLA 进行 JIT 编译 |
| `for x in batch:`手动回路 | `jax.vmap(f)` 自动矢量化 |
| `DataParallel` / `FSDP` | `jax.pmap(f)` 自动并行 |
| 可变 `model.parameters()` | 数组的不可变 pytree |

这不是风格偏好。这是一个编译器约束。 JIT 编译需要纯函数——相同的输入总是产生相同的输出，没有副作用。这一限制使得 100 倍的加速成为可能。

<a id="jaxnumpy-the-familiar-surface"></a>

### jax.numpy：熟悉的表面

JAX 在加速器上重新实现了 NumPy API：

```python
import jax.numpy as jnp

a = jnp.array([1.0, 2.0, 3.0])
b = jnp.array([4.0, 5.0, 6.0])
c = jnp.dot(a, b)
```

相同的函数名称。相同的广播规则。相同的切片语义。但数组位于 GPU/TPU 上，并且每个操作都可以由编译器跟踪。

一个关键区别：JAX 数组是不可变的。没有 `a[0] = 5`。相反：`a = a.at[0].set(5)`。这让我感觉很尴尬一周，然后就明白了——不变性使得 `grad`、`jit` 和 `vmap` 等转换可组合。

<a id="jaxgrad-functional-autodiff"></a>

### jax.grad：功能性Autodiff

PyTorch 将 gradients 连接到 tensors (`.grad`)。 JAX 将 gradients 附加到函数。

```python
import jax

def f(x):
    return x ** 2

df = jax.grad(f)
df(3.0)
```

`jax.grad` 接受一个函数并返回一个计算 gradient 的新函数。没有 `.backward()` 呼叫。 tensors上没有存储计算图。 gradient 只是您可以调用、编写或 JIT 编译的另一个函数。

任意组合：

```python
d2f = jax.grad(jax.grad(f))
d2f(3.0)
```

二阶导数。三阶导数。 Jacobians。 Hessians。全部由 `grad` 组成。 PyTorch 也可以做到这一点（`torch.autograd.functional.hessian`），但它是用螺栓固定的。在JAX中，它是基础。

约束：`grad` 仅适用于纯函数。内部没有打印语句（它们在跟踪期间运行，而不是执行期间运行）。外部状态没有突变。如果没有明确的密钥管理，则不会生成随机数。

<a id="jit-compile-to-xla"></a>

### jit：编译为 XLA

```python
@jax.jit
def train_step(params, x, y):
    loss = loss_fn(params, x, y)
    return loss

fast_step = jax.jit(train_step)
```

第一次调用时，JAX traces 函数——它记录发生了哪些操作，但不执行它们。然后它将 trace 交给 XLA（加速线性代数），Google 的 TPU 编译器和 GPUs。 XLA 融合操作、消除冗余内存副本并生成优化的机器代码。

后续调用完全跳过 Python。编译后的代码以 C++ 速度在加速器上运行。

当 JIT 有帮助时：
- 训练步骤（相同的计算重复数千次）
- Inference（相同型号，不同输入）
- 任何使用类似形状的输入多次调用的函数

当 JIT 受到伤害时：
- 具有 Python 的函数控制取决于值的流（`if x > 0`，其中 x 是跟踪数组）
- 一次性计算（编译开销超过运行时间）
- 调试（跟踪隐藏实际执行）

控制流限制是真实的。 `jax.lax.cond` 替换 `if/else`。 `jax.lax.scan` 替换 `for` 循环。这些不是可选的——它们是编译的代价。

<a id="vmap-automatic-vectorization"></a>

### vmap：自动矢量化

您编写一个函数来处理一个示例：

```python
def predict(params, x):
    return jnp.dot(params['w'], x) + params['b']
```

`vmap` 举起处理一批：

```python
batch_predict = jax.vmap(predict, in_axes=(None, 0))
```

`in_axes=(None, 0)`表示：不要对`params`（共享）进行批处理，对`x`的0轴进行批处理。无手动 `for` 循环。没有重塑。无批量尺寸螺纹。 JAX 计算出批量维度并对整个计算进行向量化。

这不是语法糖。 `vmap` 生成融合矢量化代码，其运行速度比 Python 循环快 10-100 倍。由`jit`和`grad`组成：

```python
per_example_grads = jax.vmap(jax.grad(loss_fn), in_axes=(None, 0, 0))
```

每个示例 gradients。一行。如果没有黑客攻击，这在 PyTorch 中几乎是不可能的。

<a id="pmap-data-parallelism-across-devices"></a>

### pmap：跨设备的数据并行性

```python
parallel_step = jax.pmap(train_step, axis_name='devices')
```

`pmap` 在所有可用设备 (GPUs/TPU) 上复制该功能并拆分批次。在函数内部，`jax.lax.pmean` 和 `jax.lax.psum` 跨设备同步 gradients。

Google 使用 `pmap`（及其后继产品 `shard_map`）在数千个 TPU v5e 芯片上训练 Gemini。编程模型：编写单机版本，用`pmap`包起来，完成。

<a id="pytrees-the-universal-data-structure"></a>

### Pytree：通用数据结构

JAX 在“pytree”上运行——列表、元组、字典和数组的嵌套组合。您的模型 parameters 是一个 pytree：

```python
params = {
    'layer1': {'w': jnp.zeros((784, 256)), 'b': jnp.zeros(256)},
    'layer2': {'w': jnp.zeros((256, 128)), 'b': jnp.zeros(128)},
    'layer3': {'w': jnp.zeros((128, 10)),  'b': jnp.zeros(10)},
}
```

每个 JAX 转换 - `grad`、`jit`、`vmap` - 都知道如何遍历 pytree。 `jax.tree.map(f, tree)` 将 `f` 应用于每片叶子。这是 optimizers 一次更新所有 parameters 的方法：

```python
params = jax.tree.map(lambda p, g: p - lr * g, params, grads)
```

无 `.parameters()` 方法。没有parameter注册。树结构就是模型。

<a id="functional-vs-object-oriented"></a>

### 函数式与面向对象

PyTorch 将状态存储在对象内部：

```python
class Model(nn.Module):
    def __init__(self):
        self.linear = nn.Linear(784, 10)

    def forward(self, x):
        return self.linear(x)
```

JAX 使用具有显式状态的纯函数：

```python
def predict(params, x):
    return jnp.dot(x, params['w']) + params['b']
```

参数已传入。不存储任何内容。一切都没有变异。这使得每个函数都可测试、可组合和可编译。这也意味着您可以自己管理参数——或者使用 Flax 或 Equinox 等库。

<a id="the-jax-ecosystem"></a>

### JAX生态系统

JAX 为您提供原语。图书馆为您提供人体工程学：

| 图书馆 | 角色 | 风格 |
|---------|------|-------|
| **Flax**（谷歌） | 神经网络层 | `nn.Module` 具有显式状态 |
| **Equinox**（帕特里克·基杰） | 神经网络层 | 基于 Pytree，Pythonic |
| **Optax**（DeepMind） | Optimizers+LR时间表 | 可组合 gradient 变换 |
| **Orbax**（谷歌） | 检查点 | 保存/恢复pytree |
| **CLU**（谷歌） | 指标+日志记录 | 训练循环实用程序 |

Optax 是标准 optimizer 库。它将 gradient 转换（Adam、SGD、剪辑）与 parameter 更新分开，使得编写起来很简单：

```python
optimizer = optax.chain(
    optax.clip_by_global_norm(1.0),
    optax.adam(learning_rate=1e-3),
)
```

<a id="when-to-use-jax-vs-pytorch"></a>

### 何时使用 JAX 与 PyTorch

| 因素 | JAX | PyTorch |
|--------|-----|---------|
| TPU支持 | 一流（Google 均打造） | 社区维护（torch_xla） |
| GPU 支持 | 好（CUDA，来自 XLA） | 同类最佳（原生 CUDA） |
| 调试 | Hard（追踪+编译） | 简单（渴望，逐行） |
| 生态系统 | 以研究为重点（Flax、Equinox） | 海量（HuggingFace、torchvision 等） |
| 招聘 | 利基 (Google/DeepMind/Anthropic) | 主流（无处不在） |
| 大规模培训 | 高级（XLA、pmap、网格） | 良好（FSDP、DeepSpeed） |
| 原型制作速度 | 较慢（功能开销） | 更快（变异并继续） |
| 生产 inference | TensorFlow 服务，顶点人工智能 | 火炬服务，Triton，ONNX |
| 谁使用它 | DeepMind (Gemini)、Anthropic (Claude) | Meta (Llama)、OpenAI (GPT)、稳定性 AI |

诚实的答案：使用 PyTorch 除非您有特定原因使用 JAX。这些原因是——TPU 访问、需要每个示例 gradients、大规模多设备培训，或者在 Google/DeepMind/Anthropic 工作。

<a id="random-numbers-in-jax"></a>

### JAX中的随机数

JAX 没有全局随机状态。每个随机操作都需要一个显式的 PRNG 密钥：

```python
key = jax.random.PRNGKey(42)
key1, key2 = jax.random.split(key)
w = jax.random.normal(key1, shape=(784, 256))
```

一开始这很烦人。但它保证了跨设备和编译的可重复性——PyTorch 的 `torch.manual_seed` 在多 GPU 设置中无法保证这一属性。

```figure
batchnorm-effect
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-setup-and-data"></a>

### 第 1 步：设置和数据

我们将使用 JAX 和 Optax 在 MNIST 上训练 3 层 MLP。 784 个输入，两个包含 256 和 128 个神经元的隐藏层，10 个输出类。

```python
import jax
import jax.numpy as jnp
from jax import random
import optax

def get_mnist_data():
    from sklearn.datasets import fetch_openml
    mnist = fetch_openml('mnist_784', version=1, as_frame=False, parser='auto')
    X = mnist.data.astype('float32') / 255.0
    y = mnist.target.astype('int')
    X_train, X_test = X[:60000], X[60000:]
    y_train, y_test = y[:60000], y[60000:]
    return X_train, y_train, X_test, y_test
```

<a id="step-2-initialize-parameters"></a>

### 第二步：初始化Parameters

没有课。只是一个返回 pytree 的函数：

```python
def init_params(key):
    k1, k2, k3 = random.split(key, 3)
    scale1 = jnp.sqrt(2.0 / 784)
    scale2 = jnp.sqrt(2.0 / 256)
    scale3 = jnp.sqrt(2.0 / 128)
    params = {
        'layer1': {
            'w': scale1 * random.normal(k1, (784, 256)),
            'b': jnp.zeros(256),
        },
        'layer2': {
            'w': scale2 * random.normal(k2, (256, 128)),
            'b': jnp.zeros(128),
        },
        'layer3': {
            'w': scale3 * random.normal(k3, (128, 10)),
            'b': jnp.zeros(10),
        },
    }
    return params
```

He-初始化，手动完成。三个 PRNG 密钥从一个种子中分离出来。每个 weight 都是嵌套字典中的不可变数组。

<a id="step-3-forward-pass"></a>

### 步骤3：Forward Pass

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

纯函数。参数输入，预测输出。没有`self`，没有存储状态。 `loss_fn` 从头开始​​计算 cross-entropy -- softmax，对数，负平均值。

<a id="step-4-jit-compiled-training-step"></a>

### 第 4 步：JIT 编译的训练步骤

```python
@jax.jit
def train_step(params, opt_state, x, y):
    loss, grads = jax.value_and_grad(loss_fn)(params, x, y)
    updates, opt_state = optimizer.update(grads, opt_state, params)
    params = optax.apply_updates(params, updates)
    return params, opt_state, loss

@jax.jit
def accuracy(params, x, y):
    logits = forward(params, x)
    preds = jnp.argmax(logits, axis=-1)
    return jnp.mean(preds == y)
```

`jax.value_and_grad` 一次性返回损失值和 gradients。 `@jax.jit` 装饰器将这两个函数编译为 XLA。第一次调用后，每个训练步骤都会在不接触 Python 的情况下运行。

<a id="step-5-training-loop"></a>

### 第 5 步：训练循环

```python
optimizer = optax.adam(learning_rate=1e-3)

X_train, y_train, X_test, y_test = get_mnist_data()
X_train, X_test = jnp.array(X_train), jnp.array(X_test)
y_train, y_test = jnp.array(y_train), jnp.array(y_test)

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
    print(f"Epoch {epoch + 1:2d} | Loss: {epoch_loss / n_batches:.4f} | "
          f"Train Acc: {train_acc:.4f} | Test Acc: {test_acc:.4f}")
```

10 个epoch。 ~97% 测试准确度。第一个epoch很慢（JIT编译）。 2-10 epoch很快。

注意缺少的内容：没有 `.zero_grad()`，没有 `.backward()`，没有 `.step()`。整个更新是一个组合函数调用。 Gradients 由 Adam 计算、转换，并应用于 parameters——全部在 `train_step` 内。

<a id="use-it"></a>

## 实际应用

<a id="flax-the-google-standard"></a>

### Flax：Google 标准

Flax是最常见的JAX神经网络库。它添加了 `nn.Module` 回来，但具有明确的状态管理：

```python
import flax.linen as nn

class MLP(nn.Module):
    @nn.compact
    def __call__(self, x):
        x = nn.Dense(256)(x)
        x = nn.relu(x)
        x = nn.Dense(128)(x)
        x = nn.relu(x)
        x = nn.Dense(10)(x)
        return x

model = MLP()
params = model.init(jax.random.PRNGKey(0), jnp.ones((1, 784)))
logits = model.apply(params, x_batch)
```

与PyTorch结构相同，但`params`与模型分离。 `model.init()` 创建参数。 `model.apply(params, x)` 运行 forward pass。模型对象没有状态。

<a id="equinox-the-pythonic-alternative"></a>

### Equinox：Python 风格的替代方案

Equinox（由 Patrick Kidger 设计）将模型表示为 pytree：

```python
import equinox as eqx

model = eqx.nn.MLP(
    in_size=784, out_size=10, width_size=256, depth=2,
    activation=jax.nn.relu, key=jax.random.PRNGKey(0)
)
logits = model(x)
```

该模型本身是一个 pytree。 不`.apply()`需要。 Parameters只是模型的叶子。 这更接近于如何JAX认为。

<a id="optax-composable-optimizers"></a>

### Optax：可组合 Optimizers

Optax 将 gradient 转换与更新解耦：

```python
schedule = optax.warmup_cosine_decay_schedule(
    init_value=0.0, peak_value=1e-3,
    warmup_steps=1000, decay_steps=50000
)

optimizer = optax.chain(
    optax.clip_by_global_norm(1.0),
    optax.adamw(learning_rate=schedule, weight_decay=0.01),
)
```

Gradient clipping、learning rate warmup、weight decay ——全部组成一个变换链。每个转换都会看到 gradients，修改它们，然后将它们传递给下一个转换。无单片 optimizer 类。

<a id="ship-it"></a>

## 交付成果

**安装：**

```bash
pip install jax jaxlib optax flax
```

对于 GPU 支持：

```bash
pip install jax[cuda12]
```

对于 TPU（谷歌云）：

```bash
pip install jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html
```

**性能陷阱：**

- 第一次 JIT 调用很慢（编译）。基准测试前热身。
- 避免 Python 在 JIT 内的 JAX 数组上循环。使用 `jax.lax.scan` 或 `jax.lax.fori_loop`。
- `jax.debug.print()` 在 JIT 内部工作。常规`print()`则没有。
- 使用 `jax.profiler` 或 TensorBoard 进行配置。 XLA 编译可以隐藏瓶颈。
- JAX 默认预分配 GPU 内存的 75%。将 `XLA_PYTHON_CLIENT_PREALLOCATE=false` 设置为禁用。

**检查点：**

```python
import orbax.checkpoint as ocp
checkpointer = ocp.PyTreeCheckpointer()
checkpointer.save('/tmp/model', params)
restored = checkpointer.restore('/tmp/model')
```

**本课产出：**
- `outputs/prompt-jax-optimizer.md` -- 用于选择正确的 JAX optimizer 配置的 prompt
- `outputs/skill-jax-patterns.md` -- 涵盖 JAX 中功能模式的技能

<a id="exercises"></a>

## 练习

1. 将 dropout 添加到 MLP。在 JAX 中，dropout 需要一个 PRNG 密钥——将密钥穿过 forward pass 并将其拆分为每个 dropout 层。比较有和没有的测试精度。

2. 使用 `jax.vmap` 计算一批 32 个 MNIST 图像的每个示例 gradients。计算每个示例的 gradient 范数。哪些示例具有最大的 gradients，为什么？

3. 将手动转发功能替换为适用于任意层数的通用 `mlp_forward(params, x)`。使用`jax.tree.leaves`自动确定深度。

4. 对使用和不使用 `@jax.jit` 的训练步骤进行基准测试。每步计时 100 步。您的硬件加速有多大？第一次调用的编译开销是多少？

5. 通过编写`optax.chain(optax.clip_by_global_norm(1.0), optax.adam(1e-3))`来实现gradient clipping。有和没有剪辑的训练。绘制训练后的 gradient 范数以查看效果。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| XLA | “让 JAX 变得快速的东西” | 加速线性代数——融合运算并从计算图生成优化的 GPU/TPU 内核的编译器 |
| 准时生产 | 《及时编译》 | JAX traces 首次调用时的函数，编译为 XLA，然后在后续调用时运行编译后的版本 |
| 纯函数 | “无副作用” | 输出仅取决于输入的函数——没有全局状态，没有突变，没有显式键的随机性 |
| 虚拟映射 | “自动批处理” | 将处理一个示例的函数转换为处理一批的函数，无需重写 |
| 映射图 | “自动并行” | 跨多个设备复制函数并拆分输入批次 |
| pytree | “数组的嵌套字典” | JAX 可以遍历和转换的任何列表、元组、字典和数组的嵌套结构 |
| 追踪 | “记录计算” | JAX 使用抽象值执行函数来构建计算图，而不计算真实结果 |
| 功能autodiff | “函数的梯度” | 通过转换函数来计算导数，而不是通过将 gradient 存储附加到 tensors |
| 光税 | “JAX 的 optimizer 库” | gradient 转换的可组合库 - Adam、SGD、剪辑、调度 - 链接在一起 |
| 亚麻 | “JAX的nn.Module” | Google 的 JAX 神经网络库，在保持状态明确的同时添加层抽象 |

<a id="further-reading"></a>

## 进一步阅读

- JAX 文档：https://jax.readthedocs.io/ -- 官方文档，有关于 grad、jit 和 vmap 的优秀教程
- “JAX：Python+NumPy 程序的可组合转换”（Bradbury 等人，2018）——解释设计理念的原始论文
- Flax 文档：https://flax.readthedocs.io/ -- Google 的 JAX 神经网络库
- Patrick Kidger，“Equinox：通过可调用 PyTree 和过滤转换实现 JAX 中的神经网络”（2021 年）——Flax 的 Python 替代品
- DeepMind，“Optax：可组合 gradient 转换和优化”——标准 optimizer 库
- “You Don't Know JAX”（Colin Raffel，2020）——来自 T5 作者之一的 JAX 陷阱和模式的实用指南
