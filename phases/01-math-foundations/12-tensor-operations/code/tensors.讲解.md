# 代码讲解 · tensors.py

> **所属小节**：阶段 01 · 数学基础 · 第 12 节 Tensor 操作 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python tensors.py`（无命令行参数，依次运行 10 个演示） ｜ **依赖**：`numpy`；标准库 `functools.reduce`、`itertools.product`

---

## 1. 这份代码在考察什么

文件约 26KB，前半部分是一个从零实现的 `Tensor` 类，后半部分是 10 个演示函数（多数直接用 NumPy）。它要训练的是"形状直觉"：

1. **张量 = 扁平数据 + 形状元数据**：数据永远存在一维列表里，shape 和 strides 决定怎么把多维下标映射到一维位置。
2. **形状变换的语义**：reshape / squeeze / unsqueeze / flatten 只改"怎么看"，transpose / permute 改"轴的顺序"——二者不能互相替代。
3. **广播规则**：从右对齐、相等或为 1，用 NumPy 演示偏置相加、按通道缩放、外积、两两距离。
4. **内存布局**：strides、行优先 vs 列优先、转置与切片产生的非连续视图。
5. **einsum**：用一套字母标注写出点积、矩阵乘、迹、批量矩阵乘，以及完整的多头注意力。
6. **AI 中的真实形状和显存**：图像、token embedding、注意力分数、各种权重的形状与参数量。

> 一句话：**先自己把"扁平数组 + strides"写一遍，再用 NumPy 把深度学习里最常见的形状操作走一遍**——以后看到 `mat1 and mat2 shapes cannot be multiplied` 时，你能立刻定位是哪一维出了问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Tensor.__init__` / `_flatten_nested` | 构造 | 把嵌套列表 / ndarray / 标量展平成一维数据并推断 shape | 张量存储 |
| `_compute_strides` / `_flat_index` | 静态方法 / 方法 | 行优先 strides；多维下标 → 扁平下标 | 内存布局 |
| `shape` / `rank` / `size` / `strides` | 属性 | 只读元数据 | 张量基本属性 |
| `__getitem__` / `__setitem__` | 魔术方法 | `t[i, j, k]` 读写单个元素 | 索引 |
| `reshape` / `squeeze` / `unsqueeze` / `flatten` | 方法 | 改变形状但不改变元素顺序 | 变形 |
| `transpose` / `permute` | 方法 | 重排轴的顺序 | 转置 |
| `_elementwise_op` 及 `+ - *` | 方法 | 同形状逐元素运算或与标量运算 | 逐元素运算 |
| `sum(axis)` | 方法 | 沿某轴求和 | 归约 |
| `to_list` / `__repr__` / `to_numpy` | 方法 | 还原为嵌套列表 / 打印 / 转 NumPy | 调试与互操作 |
| `demo_custom_tensor_class` / `demo_basic_tensor` / `demo_reshape_operations` | 演示 | 演示自写 Tensor 的各项功能 | — |
| `demo_broadcasting_numpy` | 演示 | 4 种广播用法 + 规则检查 | 广播 |
| `demo_memory_layout` | 演示 | strides、连续性、C/F 顺序、切片视图 | 内存布局 |
| `demo_einsum` / `demo_einsum_gallery` | 演示 | 常见 einsum 模式对照 | einsum |
| `demo_attention_einsum` | 演示 | 用 einsum 实现多头注意力 | 形状追踪 |
| `demo_ai_tensor_shapes` / `demo_reduction_operations` | 演示 | 真实模型的形状、参数量、显存；池化 | AI 中的张量 |

数据流：自写 `Tensor` 只在前三个演示中使用；其余演示都用 NumPy，把"原理"和"真实工具"对照起来。`Tensor` 内部所有变形操作最终都通过 `reshape`，或像 `permute`、`sum` 那样用 `itertools.product` 遍历全部多维下标。

---

## 3. 逐段精讲

### 3.1 构造：一切先展平

```python
class Tensor:
    def __init__(self, data, shape=None):
        if isinstance(data, (list, tuple)):
            self._data, self._shape = self._flatten_nested(data)
        elif isinstance(data, np.ndarray):
            self._data = data.flatten().tolist()
            self._shape = tuple(data.shape)
        else:
            self._data = [data]
            self._shape = ()

        if shape is not None:
            total = reduce(lambda a, b: a * b, shape, 1)
            if total != len(self._data):
                raise ValueError(
                    f"Cannot reshape {len(self._data)} elements into shape {shape}"
                )
            self._shape = tuple(shape)

        self._strides = self._compute_strides(self._shape)
```

- 三种输入：嵌套列表/元组（递归展平）、NumPy 数组（`flatten().tolist()`）、其他视为标量（shape 为空元组 `()`，rank 0）。
- 可选的 `shape` 参数允许"给一串数，再指定形状"，如 `Tensor(list(range(12)), shape=(2, 6))`。`reduce(lambda a, b: a * b, shape, 1)` 计算各维乘积，初始值 1 保证空形状 `()` 的乘积为 1（标量有 1 个元素）。
- 设计思路与 NumPy / PyTorch 一致：**数据只有一份一维存储，形状只是元数据**。

```python
    def _flatten_nested(self, data):
        if not isinstance(data, (list, tuple)):
            return [data], ()
        if len(data) == 0:
            return [], (0,)

        sub_results = [self._flatten_nested(item) for item in data]
        sub_shape = sub_results[0][1]
        for i, (_, s) in enumerate(sub_results):
            if s != sub_shape:
                raise ValueError(
                    f"Inconsistent shapes at index {i}: {s} vs {sub_shape}"
                )

        flat = []
        for sub_data, _ in sub_results:
            flat.extend(sub_data)

        return flat, (len(data),) + sub_shape
```

- **递归**：标量是递归终点（shape `()`）；一个列表的 shape = `(元素个数,) + 子元素的 shape`。例如 `[[1,2,3],[4,5,6]]`：子元素 shape 都是 `(3,)`，于是整体为 `(2,) + (3,) = (2, 3)`。
- 检查每个子元素形状一致，拒绝 `[[1, 2], [3]]` 这种"参差数组"（ragged array）——张量必须是规整的长方体。

### 3.2 strides：多维下标 → 一维位置

```python
    @staticmethod
    def _compute_strides(shape):
        if len(shape) == 0:
            return ()
        strides = [1] * len(shape)
        for i in range(len(shape) - 2, -1, -1):
            strides[i] = strides[i + 1] * shape[i + 1]
        return tuple(strides)

    def _flat_index(self, indices):
        # ...
        idx = 0
        for i, (ind, stride) in enumerate(zip(indices, self._strides)):
            if ind < 0 or ind >= self._shape[i]:
                raise IndexError(
                    f"Index {ind} out of range for axis {i} with size {self._shape[i]}"
                )
            idx += ind * stride
        return idx
```

- 行优先（C order）：最后一维 stride 为 1，从倒数第二维往前，每一维的 stride = 右边一维的 stride × 右边一维的大小。`range(len(shape) - 2, -1, -1)` 就是"从倒数第二个下标倒着走到 0"。
- 例子：shape `(2, 3)` → strides `(3, 1)`；shape `(2, 2, 2)` → `(4, 2, 1)`（运行输出可见）。
- 扁平下标公式 `Σ indexᵢ × strideᵢ`：`tensor_3d[1, 0, 1]` = `1×4 + 0×2 + 1×1 = 5`，第 5 个元素正是 6。
- `@staticmethod` 表示这个方法不依赖 `self`，只是放在类里的普通函数；`reshape`、`permute` 等方法都通过 `self._compute_strides(...)` 复用它。
- ⚠️ 这里的 strides 以**元素个数**为单位；NumPy 的 `.strides` 以**字节**为单位（`demo_memory_layout` 用 `s // a.itemsize` 换算）。
- ⚠️ 不支持负下标（`t[-1, 0]` 会报 `IndexError`），也不支持切片和部分索引（`__getitem__` 里明确抛出 "Partial indexing not supported"）。

### 3.3 reshape：唯一的"变形引擎"

```python
    def reshape(self, new_shape):
        new_shape = list(new_shape)
        neg_idx = -1
        known_product = 1
        for i, s in enumerate(new_shape):
            if s == -1:
                if neg_idx != -1:
                    raise ValueError("Only one dimension can be -1")
                neg_idx = i
            else:
                known_product *= s

        if neg_idx != -1:
            new_shape[neg_idx] = self.size // known_product

        total = reduce(lambda a, b: a * b, new_shape, 1)
        if total != self.size:
            raise ValueError(
                f"Cannot reshape {self.size} elements into shape {tuple(new_shape)}"
            )

        result = Tensor.__new__(Tensor)
        result._data = self._data[:]
        result._shape = tuple(new_shape)
        result._strides = self._compute_strides(result._shape)
        return result
```

- **-1 推断**：最多一个 -1，其大小 = 总元素数 ÷ 其他维乘积。`(2, 6)` reshape 成 `(-1, 3)` → `12 // 3 = 4`，得到 `(4, 3)`。如果除不尽（如 12 个元素 reshape 成 `(-1, 5)`），整除得到 2，随后的总数检查 `10 != 12` 会报错——所以先整除、后校验的顺序是正确的。
- **元素顺序不变**：数据原样复制，只换 shape 和 strides。`(2, 6)` → `(3, 4)` 的结果是 `[[0,1,2,3],[4,5,6,7],[8,9,10,11]]`，即"按行读出再按行填入"。
- `Tensor.__new__(Tensor)`：只分配对象、**不调用 `__init__`**，然后手动填三个字段。这样可以绕开 `__init__` 中的类型分派和展平逻辑，直接构造结果。
- ⚠️ `self._data[:]` 会**复制**整份数据。真实框架里 reshape 在可能时返回共享内存的视图（PyTorch 的 `view`），不复制。这里为了简单，每次都复制，所以也不存在"改了视图影响原张量"的问题。

`squeeze`、`unsqueeze`、`flatten` 全部是"算出新 shape → 调 `reshape`"：

```python
    def unsqueeze(self, dim):
        if dim < 0:
            dim = len(self._shape) + 1 + dim
        new_shape = list(self._shape)
        new_shape.insert(dim, 1)
        return self.reshape(tuple(new_shape))
```

- `unsqueeze` 的负下标换算是 `len + 1 + dim`（插入后会多一维），所以对 `(3,)` 调 `unsqueeze(-1)` 得到 `(3, 1)`，与 `unsqueeze(1)` 相同——运行输出印证了这一点。
- `squeeze()` 删除所有大小为 1 的轴：`(1, 3, 1, 2)` → `(3, 2)`；`squeeze(dim=0)` 只删第 0 轴 → `(3, 1, 2)`；若指定轴大小不为 1，则原样返回（与 PyTorch 行为一致）。
- `flatten(start_dim=1)` 把从 `start_dim` 到 `end_dim` 的轴乘起来合成一维：`(2, 4, 4, 2)` → `(2, 32)`，这正是 CNN 卷积层接全连接层前的操作。

### 3.4 permute / transpose：重排轴

```python
    def transpose(self, dim0, dim1):
        perm = list(range(self.rank))
        perm[dim0], perm[dim1] = perm[dim1], perm[dim0]
        return self.permute(perm)

    def permute(self, dims):
        if sorted(dims) != list(range(self.rank)):
            raise ValueError(f"Invalid permutation {dims} for rank {self.rank}")

        new_shape = tuple(self._shape[d] for d in dims)
        result = Tensor.__new__(Tensor)
        result._shape = new_shape
        result._strides = self._compute_strides(new_shape)
        result._data = [0] * self.size

        old_strides = self._strides
        for old_indices in iterproduct(*(range(s) for s in self._shape)):
            new_indices = tuple(old_indices[d] for d in dims)
            old_flat = sum(i * s for i, s in zip(old_indices, old_strides))
            new_flat = sum(
                i * s for i, s in zip(new_indices, result._strides)
            )
            result._data[new_flat] = self._data[old_flat]

        return result
```

- `transpose` 是 `permute` 的特例：从恒等排列 `[0, 1, ..., rank-1]` 出发，交换两个位置。
- `sorted(dims) != list(range(self.rank))` 校验 dims 是一个合法排列（每个轴恰好出现一次）。
- `dims` 的语义："新第 k 轴 = 旧第 `dims[k]` 轴"，所以 `new_shape[k] = shape[dims[k]]`。`(1, 2, 3, 4)` 用 `(0, 2, 3, 1)` 重排得到 `(1, 3, 4, 2)`——这就是 NCHW → NHWC。
- `iterproduct(*(range(s) for s in self._shape))` 生成所有多维下标的笛卡尔积，例如 shape `(2, 3)` 依次产生 `(0,0), (0,1), …, (1,2)`；对每个旧下标算出新下标和两边的扁平位置，然后拷贝元素。
- ⚠️ **与讲义的重要差异**：讲义说"transpose 不移动数据，只交换 strides，结果是非连续的"。这里的实现却新建了一块连续缓冲区并逐个搬运元素，相当于 PyTorch 的 `x.permute(...).contiguous()`。逻辑结果正确，但时间是 O(N) 而不是 O(1)，也无法演示"非连续"状态——这一点要靠后面的 `demo_memory_layout`（NumPy）来补上。
- 对比 3D 例子：`[[[1,2],[3,4]],[[5,6],[7,8]]]` 用 `(2, 0, 1)` 重排后得到 `[[[1,3],[5,7]],[[2,4],[6,8]]]`——原来的最后一维（每对数中的第 1 个 / 第 2 个）变成了第一维。

### 3.5 逐元素运算与归约

```python
    def _elementwise_op(self, other, op):
        if isinstance(other, (int, float)):
            result_data = [op(x, other) for x in self._data]
            return Tensor(result_data, shape=self._shape)
        if not isinstance(other, Tensor):
            raise TypeError(f"Unsupported type {type(other)}")
        if self._shape != other._shape:
            raise ValueError(
                f"Shape mismatch: {self._shape} vs {other._shape}. "
                "Use broadcast() first."
            )
        result_data = [op(a, b) for a, b in zip(self._data, other._data)]
        return Tensor(result_data, shape=self._shape)

    def __add__(self, other):
        return self._elementwise_op(other, lambda a, b: a + b)
```

- **一个通用函数 + 不同的 lambda**：`+ - *` 共用 `_elementwise_op`，只是传入的运算不同，避免重复三遍相同的循环（策略模式的雏形）。
- 因为两个张量都是行优先连续存储、形状相同，逐元素运算就是把两个扁平列表 `zip` 起来——这就是"连续内存"带来的便利。
- ⚠️ 不支持广播：形状不同直接报错。报错信息提示 "Use broadcast() first."，但**类中并没有 `broadcast()` 方法**——讲义练习 2 正是让你补上 `broadcast_to`。
- ⚠️ 只支持"张量 op 标量"，`2 * a` 会报错（没有 `__rmul__`）；标量类型只认 Python 的 `int/float`，`np.int64(2)` 会触发 `TypeError`（`np.float64` 恰好是 `float` 的子类，可以通过）。

```python
    def sum(self, axis=None):
        if axis is None:
            return sum(self._data)
        # ...
        new_shape = list(self._shape)
        axis_size = new_shape.pop(axis)

        result_size = reduce(lambda a, b: a * b, new_shape, 1)
        result_data = [0.0] * result_size
        result_strides = self._compute_strides(tuple(new_shape))

        for indices in iterproduct(*(range(s) for s in self._shape)):
            old_flat = sum(i * s for i, s in zip(indices, self._strides))
            new_indices = indices[:axis] + indices[axis + 1:]
            # ...
            result_data[new_flat] += self._data[old_flat]
```

- 归约的本质：**把下标中的第 `axis` 个分量删掉**（`indices[:axis] + indices[axis + 1:]`），所有删掉后相同的下标累加到同一个位置。所以被求和的那一轴从 shape 中消失。
- `axis_size` 变量算出来后没有被使用，属于无害的冗余。
- ⚠️ 类型不一致：`a.sum()` 直接用 Python 内置 `sum`，返回整数 `10`；`a.sum(axis=0)` 的累加器初始化为 `0.0`，返回 `[4.0, 6.0]`。运行输出里一个是 `10`、一个是 `4.0`，原因就在这里。
- ⚠️ 不支持 `keepdims`，也不支持一次对多个轴求和；NumPy 的 `x.sum(axis=(1, 2))` 可以。

### 3.6 `demo_broadcasting_numpy`：四种广播套路

```python
    images = np.random.randn(2, 3, 4, 4)
    scale = np.array([0.5, 1.0, 1.5]).reshape(1, 3, 1, 1)
    result = images * scale
    # ...
    points_a = np.random.randn(5, 2)
    points_b = np.random.randn(3, 2)
    diff = points_a[:, np.newaxis, :] - points_b[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff ** 2, axis=-1))
```

| 场景 | 形状 | 关键点 |
|------|------|--------|
| 偏置相加 | `(4, 3) + (3,)` | `(3,)` 自动在左边补 1 → `(1, 3)`，**不需要手动 unsqueeze** |
| 按通道缩放 | `(2, 3, 4, 4) * (1, 3, 1, 1)` | 通道在第 1 轴，不在最右边，所以**必须**显式 reshape 成 `(1, 3, 1, 1)`（或 `(3, 1, 1)`） |
| 外积 | `(3, 1) * (1, 4)` | 一个"竖着"一个"横着"，广播出 `(3, 4)` |
| 两两距离 | `(5, 1, 2) - (1, 3, 2)` | `np.newaxis` 插入新轴，得到 `(5, 3, 2)`，再在最后一轴求平方和开方，得到 `(5, 3)` 距离矩阵 |

- 最后的"规则检查"循环用 `try/except ValueError` 包住 `a + b`，展示广播失败时 NumPy 抛出的是 `ValueError`（本例 4 组都合法）。
- 这两行对比值得记住：偏置 `(D,)` 加到 `(B, T, D)` 上能自动对齐（因为 D 在最右边）；而按通道的 `(C,)` 要乘到 `(B, C, H, W)` 上就必须手动扩维（因为 C 不在最右边，直接乘会拿 C 去对 W）。

### 3.7 `demo_memory_layout`：视图、strides 与连续性

```python
    a = np.array([[1, 2, 3], [4, 5, 6]])
    print(f"Strides (bytes): {a.strides}")
    print(f"Strides (elements): {tuple(s // a.itemsize for s in a.strides)}")
    # ...
    b = a.T
    # ...
    c = np.ascontiguousarray(b)
    # ...
    sliced = x[:, ::2]
```

- `a` 是 int64，每个元素 8 字节：strides `(24, 8)` 字节 = `(3, 1)` 元素。
- `a.T` 的 strides 变为 `(8, 24)`，`C-contiguous: False`、`F-contiguous: True`——转置后的行优先数组，恰好就是原数据的列优先解读。**数据一个字节都没动**。
- `np.ascontiguousarray(b)` 复制出一块真正行优先的内存，strides 变为 `(16, 8)`（shape `(3, 2)`）。这对应 PyTorch 的 `.contiguous()`。
- 用 `order='F'` 创建的数组，`ravel(order='K')` 按内存顺序读出是 `[1 4 2 5 3 6]`。
- `x[:, ::2]`（每隔一列取一次）也是视图：列方向的 stride 从 8 变成 16 字节，同样不连续。

### 3.8 einsum 与多头注意力

```python
    B, H, T, D = 2, 4, 8, 16
    E = H * D
    # ...
    Q = np.einsum("bte,ek->btk", X, W_q)
    # ...
    Q = Q.reshape(B, T, H, D).transpose(0, 2, 1, 3)
    # ...
    scores = np.einsum("bhtd,bhsd->bhts", Q, K) / np.sqrt(D)

    def softmax(x, axis=-1):
        e = np.exp(x - np.max(x, axis=axis, keepdims=True))
        return e / np.sum(e, axis=axis, keepdims=True)

    weights = softmax(scores, axis=-1)
    # ...
    attn_output = np.einsum("bhts,bhsd->bhtd", weights, V)
    # ...
    concat = attn_output.transpose(0, 2, 1, 3).reshape(B, T, E)
    # ...
    output = np.einsum("bte,ek->btk", concat, W_o)
```

形状追踪（与运行输出完全一致）：

| 步骤 | 代码 | 形状 | 被求和的字母 |
|------|------|------|-------------|
| 输入 | `X` | `(2, 8, 64)` | — |
| 投影 | `bte,ek->btk` | `(2, 8, 64)` | e |
| 拆头 | `reshape(B,T,H,D).transpose(0,2,1,3)` | `(2, 4, 8, 16)` | — |
| 分数 | `bhtd,bhsd->bhts` | `(2, 4, 8, 8)` | d |
| softmax | 沿最后一轴 | `(2, 4, 8, 8)` | — |
| 加权求和 | `bhts,bhsd->bhtd` | `(2, 4, 8, 16)` | s |
| 合并头 | `transpose(0,2,1,3).reshape(B,T,E)` | `(2, 8, 64)` | — |
| 输出投影 | `bte,ek->btk` | `(2, 8, 64)` | e |

- `bhtd,bhsd->bhts`：K 的时间轴用了不同的字母 `s`，表示"query 的位置 t"和"key 的位置 s"是两个独立的轴；d 只出现在输入里，被求和——这就是 `Q @ Kᵀ`，但不用手动转置 K。
- **拆头必须"先 reshape 再 transpose"，合并必须"先 transpose 再 reshape"**：reshape 只能在"内存上相邻"的维度之间拆 / 合。直接 `reshape(B, H, T, D)` 会把不同 token 的特征混进同一个头里，形状正确但内容错误。
- `softmax` 是嵌套在函数内部的局部函数；`x - max` 防止 `exp` 溢出；`keepdims=True` 让 `(2,4,8,8)` 归约成 `(2,4,8,1)` 而不是 `(2,4,8)`，这样才能按行正确广播。输出 `weights sum per query: 1.000000` 验证了每个 query 的权重和为 1。
- ⚠️ 权重用 `randn * 0.02` 随机初始化，没有偏置、没有 mask、没有 dropout——这是"形状演示"，不是可训练的注意力层。

`demo_einsum_gallery` 把 13 种单 / 双操作数模式和一个三操作数的双线性型 `i,ij,j->`（即 `xᵀWy`）列成一张表，适合当作速查表背下来。

### 3.9 `demo_ai_tensor_shapes` 与 `demo_reduction_operations`

```python
    attn_scores = np.random.randn(B, H, T, T).astype(np.float32)
    print(f"Attention scores: {attn_scores.shape}")
    print(f"  Memory: {attn_scores.nbytes / 1024 / 1024:.1f} MB")
    # ...
    hidden_states = np.random.randn(4, 128, 768)
    mask = np.ones((4, 128, 1))
    mask[:, 100:, :] = 0
    pooled = (hidden_states * mask).sum(axis=1) / mask.sum(axis=1)
```

- `.nbytes` = 元素数 × 每元素字节数。`(16, 12, 512, 512)` 个 float32 = 192 MB，而且随 T **平方**增长——长上下文的显存瓶颈就在这里。
- 权重形状遵循 PyTorch 约定：`Linear(768 → 3072)` 的权重是 `(3072, 768)`，即 `(out, in)`；参数量用 `reduce` 连乘得到，例如 GPT-2 词表 `50257 × 768 = 38,597,376`。
- NCHW ↔ NHWC 用 `np.transpose(nchw, (0, 2, 3, 1))` 和 `(0, 3, 1, 2)` 互转，round-trip 为 True。
- 带 mask 的平均池化：mask 形状 `(4, 128, 1)`，最后一维的 1 让它能广播到 `(4, 128, 768)`；分母 `mask.sum(axis=1)` 是每条序列的有效长度 `(4, 1)`。
- 全局平均池化 `feature_map.mean(axis=(2, 3))`：`(2, 64, 7, 7)` → `(2, 64)`。
- ⚠️ `np.random.randn(...)` 先生成 float64，再 `.astype(np.float32)` 复制一份，峰值内存是目标的 3 倍左右（注意力分数这一项就要临时占用约 384 MB 的 float64 数组）。只关心形状时，用 `np.empty(shape, dtype=np.float32)`，或 `np.random.default_rng().standard_normal(shape, dtype=np.float32)` 直接生成 float32 更省内存。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 数据存为一维 Python 列表 + shape/strides | 与真实框架的存储模型一致，直观 | 纯 Python 慢；真实框架用连续的 C 内存块 |
| 所有变形都走 `reshape`，且每次复制数据 | 实现简单，不会出现视图别名问题 | 无法体现"视图共享内存"；真实框架 reshape/view 是 O(1) 的 |
| `permute` 搬运数据成连续布局 | 只需维护行优先 strides，其他方法都能假设数据连续 | 与讲义"只交换 strides"的描述不同；真实框架只改 strides，必要时再 `.contiguous()` |
| 逐元素运算要求形状完全相同 | 先把规则讲清楚，广播留作练习 | 实际几乎所有运算都要支持广播 |
| 用 `itertools.product` 遍历所有下标 | 对任意 rank 都成立，代码短 | O(N) 的 Python 循环，大张量极慢 |
| 演示部分改用 NumPy | 原理（自写类）与工具（NumPy）对照 | — |
| 注意力用 einsum 写 | 每一步的轴语义写在字符串里，可读性强 | 实际实现常用 `@` / `matmul` 或融合内核（如 FlashAttention） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `isinstance` 配元组 | `isinstance(data, (list, tuple))` | 同时判断多种类型 |
| 单元素元组与元组拼接 | `(len(data),) + sub_shape`、`()` | 单元素元组必须带逗号；`+` 拼接元组 |
| 元组切片拼接 | `indices[:axis] + indices[axis + 1:]` | 删掉第 axis 个分量 |
| `list.pop` / `list.insert` | `new_shape.pop(axis)`、`new_shape.insert(dim, 1)` | 删除 / 插入指定位置的元素 |
| 交换赋值 | `perm[dim0], perm[dim1] = perm[dim1], perm[dim0]` | 元组解包，无需临时变量 |
| `range` 倒序 | `range(len(shape) - 2, -1, -1)` | 从倒数第二个下标倒着走到 0 |
| 递归 | `_flatten_nested`、`_build_nested` | 函数调用自身处理嵌套结构 |
| `lambda` | `lambda a, b: a + b` | 匿名小函数，作为参数传给 `_elementwise_op` |
| `functools.reduce` | `reduce(lambda a, b: a * b, shape, 1)` | 把序列"折叠"成一个值，这里是连乘（Python 3.8+ 也可用 `math.prod`） |
| `itertools.product` + `*` 解包 | `iterproduct(*(range(s) for s in self._shape))` | 多个可迭代对象的笛卡尔积；`*` 把生成器展开成多个参数 |
| 生成器表达式 | `sum(i * s for i, s in zip(indices, strides))` | 不建中间列表 |
| `@property` | `def shape(self): return self._shape` | 把方法变成只读属性，调用时写 `t.shape` 不加括号 |
| `@staticmethod` | `_compute_strides(shape)` | 不需要 `self` 的方法 |
| `__getitem__` / `__setitem__` | `t[1, 2]` 实际传入元组 `(1, 2)` | 方括号取值 / 赋值的魔术方法 |
| `__repr__` | `Tensor(shape=(2, 3), data=[...])` | 决定 `print` / f-string 中的显示 |
| `Tensor.__new__(Tensor)` | `reshape`、`permute` 中构造结果 | 创建实例但不执行 `__init__` |
| `raise` 自定义信息 | `raise ValueError(f"Cannot reshape ...")` | 抛出带上下文的异常 |
| `try / except ValueError as e` | 广播规则检查 | 捕获异常并打印信息 |
| 嵌套函数 | `demo_attention_einsum` 里的 `def softmax(...)` | 局部函数，只在外层函数内可见 |
| `*` 解包实参 | `np.random.randn(*shape_a)` | 把元组 `(3, 4)` 展开为 `randn(3, 4)` |
| `hasattr` | `hasattr(result, 'shape')` | 判断对象是否有某属性 |
| `dict.items()` | `for name, shape in shapes.items():` | 同时遍历键和值 |
| f-string 格式符 | `{name:30s}`、`{images.size:,}`、`{x:.1f}`、`{v:.6f}` | 左对齐占 30 格；千分位；保留小数 |
| NumPy 索引技巧 | `np.newaxis`、`x[:, ::2]`、`mask[:, 100:, :] = 0` | 插入新轴；步长切片；切片赋值 |
| `keepdims=True` | `np.max(x, axis=axis, keepdims=True)` | 归约后保留长度为 1 的轴，便于广播 |

---

## 6. 运行结果解读

已在临时副本中实际运行（`python3 tensors.py`，NumPy 2.5.3，数秒内完成；本机测得进程峰值内存约 820 MB，主要来自 `demo_ai_tensor_shapes` 里的大数组）。关键输出：

```text
Created: Tensor(shape=(2, 3), data=[[1, 2, 3], [4, 5, 6]])
Strides: (3, 1)                                   ← 行优先：跨一行跳 3 个元素
Transpose: Tensor(shape=(3, 2), data=[[1, 4], [2, 5], [3, 6]])
Sum all: 10                                       ← Python 内置 sum，整数
Sum axis 0: [4.0, 6.0]                            ← 累加器初始为 0.0，变成浮点
3D tensor (2, 2, 2) permuted (2,0,1): (2, 2, 2)
  [[[1, 3], [5, 7]], [[2, 4], [6, 8]]]            ← 原最后一维变成第一维

Strides for shape (2, 2, 2): (4, 2, 1)
Reshaped to (-1, 3): shape=(4, 3), ...            ← -1 推断为 12 // 3 = 4
After squeeze():  shape=(3, 2)
After squeeze(0): shape=(3, 1, 2)
unsqueeze(-1): (3, 1)                             ← 负下标按 len+1+dim 换算

  (8, 1, 6, 1) + (7, 1, 5) -> (8, 7, 6, 5)        ← 广播规则
distances: (5, 3)                                 ← (5,1,2) - (1,3,2) → (5,3,2) → 求和 → (5,3)

Strides (bytes): (24, 8)   →  转置后 (8, 24)       ← 只交换 strides，数据不动
C-contiguous: False / F-contiguous: True
Sliced strides: (32, 16)                          ← 隔列切片也是视图

  Tensor contraction   ijk,jkl->il   (2, 3, 4) x (3, 4, 5) -> (2, 5)
  x^T W y = einsum: 14.0, manual: 14.0            ← 1·1 + 2·2 + 3·3 = 14

Attention scores: (2, 4, 8, 8)
  weights sum per query (should be 1.0): 1.000000
Final output: (2, 8, 64)

Embedding table (GPT-2): (50257, 768)  Memory: 147.2 MB
Attention scores: (16, 12, 512, 512)   Memory: 192.0 MB   ← 随 T² 增长
  Linear (768 -> 3072): (3072, 768) -> 2,359,296 params   ← (out, in) 约定
Round-trip match: True                            ← NCHW↔NHWC、拆头↔合头都可逆
  Pooled:        (4, 768)                         ← 带 mask 的平均池化
```

---

## 7. 动手改一改

1. **补上 `broadcast_to`**：先写 `broadcast_shape(sa, sb)` 计算结果形状，再给 `Tensor` 加 `broadcast_to(shape)`，并让 `_elementwise_op` 自动广播。用 `(3, 1)` 与 `(1, 4)` 测试得到 `(3, 4)`（讲义练习 2）。
2. **支持负下标和 `__rmul__`**：在 `_flat_index` 中把负下标换算成 `ind + shape[i]`；加上 `__rmul__ = __mul__`，并把标量类型判断改为 `numbers.Number`，让 `2 * t`、`t * np.int64(2)` 都能工作。
3. **`sum` 加 `keepdims` 并统一返回类型**：`keepdims=True` 时把被归约的轴保留为 1；`axis=None` 时也返回浮点数。
4. **把 permute 改成真正的视图**：给 Tensor 增加 `_offset` 字段，`permute` 只重排 `_shape` 和 `_strides`、共享 `_data`；再实现 `is_contiguous()` 和 `contiguous()`，并让 `reshape` 在非连续时先 `contiguous()`。
5. **从零实现双操作数 einsum**：解析 `"ij,jk->ik"`，找出被收缩的字母，用 `itertools.product` 遍历所有字母的取值并累加，与 `np.einsum` 对比（讲义练习 3）。
6. **形状追踪器**：写 `trace_attention_shapes(batch, seq_len, embed_dim, num_heads)`，打印多头注意力每一步的形状和注意力分数的显存，并对 `embed_dim % num_heads != 0` 给出清晰报错（讲义练习 4）。

---

## 8. 常见坑

- **用 reshape 代替 transpose**：`(B, T, D)` 直接 `reshape(B, H, T, D_head)` 形状对、内容错，不会报错。拆头 = 先 reshape 再 transpose；合头 = 先 transpose 再 reshape。
- **`(N,)` 和 `(N, 1)` 混用**：广播从右对齐，`(B, 1) - (B,)` 会得到 `(B, B)`；`(5, 3) + (5,)` 则直接报错。
- **归约忘了 `keepdims`**：`x - x.max(axis=-1)` 在方阵上会静默地按错误方向广播。
- **对非连续张量 `view`**：PyTorch 中 transpose / permute 之后 `view` 可能报错，用 `.contiguous().view(...)` 或 `reshape`。
- **字节 strides vs 元素 strides**：NumPy 的 `.strides` 是字节数，要除以 `itemsize` 才是元素数。
- **低估显存**：注意力分数随 T² 增长；`randn(...).astype(np.float32)` 还会先占用 float64 两倍的临时内存。
