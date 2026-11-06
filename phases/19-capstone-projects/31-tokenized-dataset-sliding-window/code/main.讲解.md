# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 31 节 使用滑动窗口构建分词后的数据集 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）或 `cd code && python3 main.py`；测试：`python3 -m pytest code/tests/ -v` ｜ **依赖**：标准库（`re`、`collections`、`dataclasses`、`typing`）+ 第三方 `torch`（CPU 即可，本次运行使用 torch 2.14.1）

---

## 1. 这份代码在考察什么

这份代码搭建了 GPT 预训练的"传送带"：把原始文本变成一个个 `(B, T)` 的输入 / 目标张量。

1. **一次性分词**：用内联的 `MiniBPE`（第 30 课 tokenizer 的精简版）在语料上训练并编码，得到一条扁平的 id 流。
2. **滑动窗口**：按上下文长度 `T` 与步长 `S` 切出长度为 `T+1` 的窗口，样本数由公式 `1 + (N − (T+1)) // S` 给出。
3. **PyTorch Dataset**：`__len__` 与 `__getitem__`，惰性计算窗口起点，在 `__getitem__` 中完成"左移一位"。
4. **确定性 DataLoader**：每个 epoch 用 `base_seed + epoch` 播种的 `torch.Generator`，同种子同顺序、换 epoch 换顺序。
5. **stride 取舍**：stride 4/8/16 时样本数 1224/612/306。

> 一句话：**训练循环只需要一个稳定的契约——"给我一个 `(B, T)` 的输入和左移一位的 `(B, T)` 目标"；本文件把这个契约从文本一路实现到 DataLoader**。同时注意：讲义说的"文档间插入 `<|endoftext|>`"在代码里并没有实现，讲义建议"把 T 从 16 改到 32 观察样本数下降"在 stride 固定为 8 时几乎看不到变化（612 → 610）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MiniBPE` | dataclass | 字节 + special 的词表布局，存 merges | 第 30 课 tokenizer |
| `_pretokenize` / `_count_pairs` / `_apply_merge_to_corpus` | 函数 | 预分词、pair 计数、全语料合并 | BPE 训练 |
| `train_bpe` | 函数 | 训练到目标词表（含参数检查） | BPE 训练 |
| `encode_text` | 函数 | 按 rank 应用合并，输出 id 列表（无 special 支持、无 decode） | 编码 |
| `SlidingWindowDataset` | `torch.utils.data.Dataset` 子类 | 保存 id 张量；`count_windows`、`__len__`、`__getitem__` | 滑动窗口 + 左移一位 |
| `make_dataloader` | 函数 | 构造带种子 generator 的 DataLoader | 确定性 shuffle |
| `_encode_corpus_to_ids` | 函数 | 训练 tokenizer 并编码整个语料 | 一次性分词 |
| `DEMO_CORPUS` / `main` | 常量 / 函数 | 18 行 × 8 的语料；演示与断言 | 演示 |

数据流：`DEMO_CORPUS`（7408 字符）→ `_encode_corpus_to_ids`（`train_bpe` → `encode_text`）→ 4912 个 id → `SlidingWindowDataset(T=16, S=8)`（612 个窗口）→ `make_dataloader(B=4, seed=7+epoch)` → `(4, 16)` 输入与 `(4, 16)` 目标。

---

## 3. 逐段精讲

### 3.1 内联的 `MiniBPE`：与第 30 课的差异

文件开头约 150 行是第 30 课 BPE 的精简复制版（文档字符串："same contract as lesson 30"），目的是让本课不依赖其他目录。算法相同（`\S+|\s+` 预分词、按块频次加权计数、平局按 pair 排序、最高频不足 2 次停止、按 rank 编码），值得注意的差异：

| 项目 | 第 30 课 `BPETokenizer` | 本课 `MiniBPE` |
|------|------------------------|---------------|
| 新 token 的 id | `_add_token` 按字节去重，可能返回已有 id（甚至 special id） | 总是 `len(vocab)`，不去重，因此不会与 special 撞 id |
| 参数检查 | 无 | `target_vocab_size < 258` 时抛 `ValueError` |
| 编码 rank 表 | 每个块重建一次 | 每次 `encode_text` 调用只建一次（更高效） |
| special token 编码 | `encode(..., allow_special=True)` | **不支持**，字面量 `<\|endoftext\|>` 被当作普通文本 |
| 解码 / 保存 / 加载 | 有 | 都没有 |
| 演示语料 | 18 行 × 6，含逗号 | 18 行 × 8，去掉了 "write," 的逗号 |

```python
def train_bpe(tokenizer: MiniBPE, corpus: str, target_vocab_size: int) -> None:
    min_vocab_size = BYTE_ALPHABET_SIZE + len(DEFAULT_SPECIALS)
    if target_vocab_size < min_vocab_size:
        raise ValueError(f"target_vocab_size must be >= {min_vocab_size}, got {target_vocab_size}")
    ...
        new_id = len(tokenizer.vocab)
        merged_bytes = tokenizer.vocab[best[0]] + tokenizer.vocab[best[1]]
        tokenizer.vocab[new_id] = merged_bytes
        tokenizer.inv_vocab[merged_bytes] = new_id
        tokenizer.merges[best] = new_id
```

- 若两个不同 pair 合出相同字节，`vocab` 中会出现重复的字节串，`inv_vocab` 被后者覆盖；本课不用 `inv_vocab` 做编码，所以不影响结果。
- ⚠️ 由于 `encode_text` 没有 special 支持，讲义所说"多文档时插入 `<|endoftext|>` id"必须由调用方在 id 层面手动追加（`tokenizer.special_to_id["<|endoftext|>"]`），在文本里写字面量是无效的：实测 `encode_text(tok, "a<|endoftext|>b")` 得到 13 个普通 id，不含 256。参考实现见测验 Q9。
- `_encode_corpus_to_ids` 在同一份语料上**训练并编码**。对演示足够；生产中 tokenizer 通常在一个采样子集上训练一次，然后冻结，用于编码全部语料。

### 3.2 `SlidingWindowDataset.__init__`：参数校验与存储

```python
class SlidingWindowDataset(Dataset):
    def __init__(self, ids: list[int], context_length: int, stride: int | None = None) -> None:
        if context_length < 1:
            raise ValueError(f"context_length must be >= 1, got {context_length}")
        if not ids:
            raise ValueError("ids must be non-empty")
        if stride is None:
            stride = context_length
        if stride < 1:
            raise ValueError(f"stride must be >= 1, got {stride}")
        self.ids = torch.tensor(ids, dtype=torch.long)
        self.context_length = context_length
        self.stride = stride
```

- 继承 `torch.utils.data.Dataset`，只需实现 `__len__` 与 `__getitem__`（"map-style" 数据集）。
- `stride=None` 时默认等于 `context_length`，即不重叠窗口——讲义所说的大规模预训练常用设置。
- id 流一次性转成 `torch.long`（int64）张量，之后所有窗口都是它的切片，**内存只有一份**，与 stride 无关（讲义："the memory cost is one copy of the id stream regardless of how many examples the stride produces"）。demo 的 4912 个 id 占 39,296 字节。
- ⚠️ 缺少的检查：
  - `stride > context_length + 1` 时窗口之间有空隙，部分数据永远不会被使用（实测 `range(100)`、`T=4`、`S=10` 只覆盖 50 个 id）；
  - id 流短于 `T + 1` 时 `len == 0`，构造不报错，但交给 `shuffle=True` 的 DataLoader 时才抛出令人困惑的 `num_samples=0` 错误。
- `int64` 对词表 320 而言很浪费，`uint16` 就够（4 倍压缩），见测验 Q10。

### 3.3 `count_windows`：窗口计数公式

```python
    @staticmethod
    def count_windows(num_ids: int, context_length: int, stride: int) -> int:
        usable = num_ids - (context_length + 1)
        if usable < 0:
            return 0
        return 1 + usable // stride
```

- 第一个窗口占用 `T + 1` 个 id；剩下的 `usable` 个 id 每多出 `S` 个就能多一个窗口：`1 + usable // S`。与讲义公式 `max(0, 1 + (N − (T + 1)) // S)` 等价。
- `@staticmethod`：不依赖实例，训练器可以在构造 Dataset 之前就算出每个 epoch 的步数（讲义："so the trainer can compute total steps per epoch without iterating"）。
- 本次语料的实际数值（N = 4912，实测）：

| T | S | 窗口数 | 每 epoch batch 数（B=4，drop_last） | 未被使用的尾部 id |
|---|---|-------|-------------------------------|----------------|
| 16 | 16 | 306 | 76 | 15 |
| 16 | 8 | 612 | 153 | 7 |
| 16 | 4 | 1224 | 306 | 3 |
| 16 | 1 | 4896 | 1224 | 0 |
| 32 | 8 | 610 | 152 | 7 |
| 32 | 32 | 153 | 38 | 15 |

- 读表要点：窗口数 ≈ `N / S`，主要由 stride 决定；只有在 `S = T` 时改 `T` 才会让样本数成比例变化。尾部最多丢弃 `S − 1` 个 id。

### 3.4 `__len__` 与 `__getitem__`：惰性切片与左移一位

```python
    def __len__(self) -> int:
        return self.count_windows(self.ids.numel(), self.context_length, self.stride)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(f"window index {index} out of range")
        start = index * self.stride
        end = start + self.context_length + 1
        window = self.ids[start:end]
        return window[:-1].clone(), window[1:].clone()
```

- **负索引**：`index += len(self)` 模仿 Python 列表，`ds[-1]` 是最后一个窗口（测试 `test_negative_index_supported`）。
- **越界检查**：必须显式抛 `IndexError`。张量切片越界不会报错，只会返回更短的结果；没有这个检查，`ds[len(ds)]` 会悄悄返回长度不足 `T` 的样本，堆叠 batch 时才报形状错误。
- **左移一位**：`window` 长度 `T + 1`；`input = window[:-1]`（前 T 个）、`target = window[1:]`（后 T 个），满足 `target[t] == input[t+1]`。示例（`T = 4`）：

| 位置 | 0 | 1 | 2 | 3 | 4 |
|------|---|---|---|---|---|
| window | a | b | c | d | e |
| input | a | b | c | d | |
| target | b | c | d | e | |

- **为什么 `.clone()`**：张量切片是共享底层存储的**视图**。不 clone 的话，调用方如果原地修改样本（例如做 masking），会悄悄改坏 `self.ids`；clone 后返回的是独立副本（实测 `data_ptr` 不同）。代价是每个样本复制 2×T 个 int64，微不足道。
- `__getitem__` 是纯函数（同一 index 永远返回同一结果），因此在多 worker 场景下也无需处理随机状态。

### 3.5 `make_dataloader`：确定性 shuffle

```python
def make_dataloader(dataset, batch_size, shuffle=True, base_seed=0, epoch=0, drop_last=True) -> DataLoader:
    generator = torch.Generator()
    generator.manual_seed(base_seed + epoch)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=drop_last,
        generator=generator if shuffle else None,
        num_workers=0,
    )
```

- `shuffle=True` 时 DataLoader 内部创建 `RandomSampler`，用传入的 `generator` 生成一次**无放回**的随机排列；传入独立 generator 可以避免受全局随机状态（模型初始化、dropout 消耗的随机数）影响。
- 种子约定 `base_seed + epoch`：第 k 个 epoch 的顺序只依赖 `(base_seed, k)`，中断后可直接重建该 epoch 的顺序。
- ⚠️ 若只构造一次 DataLoader 并在多个 epoch 中复用，generator 状态会在每次 `iter()` 时前进，顺序每次都变（实测两次 `next(iter(loader))` 得到不同 batch）——仍然可复现，但无法单独重建第 k 个 epoch。本课的设计是"每个 epoch 新建一个 DataLoader"。
- ⚠️ `base_seed + epoch` 的小隐患：`(7, 1)` 与 `(8, 0)` 得到相同的顺序；用 `numpy.random.SeedSequence` 或哈希组合更稳妥。
- `drop_last=True`：最后一个不满 `B` 的 batch 被丢弃，保证每个 batch 形状一致（demo 中 612 恰好被 4 整除，不丢 batch）。
- `num_workers=0`：在主进程里取数据；本数据集的 `__getitem__` 只是内存切片，多进程反而增加开销（讲义："mostly a no-op"）。
- batch 的组装由默认的 `collate_fn` 完成：把 4 个 `(input, target)` 元组分别 `torch.stack` 成 `(4, 16)` 的两个张量。
- ⚠️ `len(dataset) == 0` 且 `shuffle=True` 时，DataLoader **构造**阶段就会抛 `ValueError: num_samples should be a positive integer value, but got num_samples=0`（实测）。

### 3.6 `main`：演示与断言

```python
    target_vocab = 320
    context_length = 16
    stride = 8
    batch_size = 4
    base_seed = 7
```

`main` 依次验证了讲义承诺的所有契约，每一项都有 `assert`：

| 段落 | 断言 / 检查 | 验证的性质 |
|------|-----------|-----------|
| Corpus and tokenizer | `len(dataset) == count_windows(...)` | 长度公式 |
| Inspect one example | 形状相同；`input_ids[1:] == target_ids[:-1]` | 左移一位 |
| Pull a batch | `inputs.shape == (4, 16)`、`targets.shape == (4, 16)` | batch 形状契约 |
| Shuffle is seeded | 同种子、同 epoch 的两个 loader 第一个 batch 相同 | 可复现 |
| | `epoch=1` 的第一个 batch 与 `epoch=0` 不同 | 换 epoch 换顺序 |
| Stride trade-off | 打印 stride 4/8/16 的窗口数 | 取舍 |

- 关于"换 epoch 必然不同"的断言：两个随机排列的第一个 batch 恰好相同的概率极小（612 个窗口中前 4 个完全一致），但理论上不是 0；固定种子下结果是确定的，所以这个断言不会随机失败。
- `raise SystemExit(main())`：以 `main()` 的返回值作为进程退出码。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 内联 `MiniBPE` | 本课独立运行，不跨目录 import | 两份实现会漂移（已与第 30 课有 5 处差异）；生产中 tokenizer 是独立的、冻结的组件 |
| 同一语料上训练 tokenizer 并编码 | 演示简单 | 生产中 tokenizer 训练一次后冻结，离线批量编码 |
| 整个 id 流放进一个 `int64` 张量 | 实现最简单，切片零开销 | 内存 8 字节/id；生产用 `uint16`/`int32` + `np.memmap` 或 HDF5（第 43 课） |
| 惰性计算窗口 | 内存与 stride 无关 | 无 |
| 尾部不足就丢弃 | 不需要 loss mask | 最多丢 `S − 1` 个 id；可选 padding + `ignore_index`（测验 Q11） |
| 左移在 `__getitem__` 中完成 | 训练循环拿到的就是 `(input, target)`，契约清晰 | 无 |
| `.clone()` 返回样本 | 防止调用方原地修改污染 id 流 | 少量复制 |
| 每个 epoch 新建 DataLoader + `base_seed + epoch` | 任一 epoch 的顺序可单独重建 | 种子组合可能撞车；多卡需 `DistributedSampler.set_epoch` |
| `drop_last=True` | 每个 batch 形状一致，便于编译/静态形状 | 可能丢弃最多 `B − 1` 个样本 |
| `num_workers=0` | 简单、可调试 | 数据需要解码/读盘时应开多个 worker |
| 多文档用 EOT 分隔（讲义） | 零 padding 浪费 | 代码未实现；存在跨文档注意力（测验 Q17） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 继承第三方基类 | `class SlidingWindowDataset(Dataset):` | 只需实现 `__len__`、`__getitem__` 即可被 DataLoader 使用 |
| 魔术方法 `__len__` / `__getitem__` | `len(dataset)`、`dataset[0]` | 让对象支持 `len()` 与下标访问 |
| `@staticmethod` | `count_windows(num_ids, context_length, stride)` | 不需要 `self`，可用类名直接调用 |
| 可选参数与 `None` 默认 | `stride: int \| None = None` → `if stride is None: stride = context_length` | 用 `None` 表示"使用默认规则" |
| 主动抛异常 | `raise ValueError(...)`、`raise IndexError(...)` | 参数非法 / 越界时立即失败并给出信息 |
| 负索引换算 | `if index < 0: index += len(self)` | 模仿 Python 序列语义 |
| 张量切片 | `self.ids[start:end]`、`window[:-1]`、`window[1:]` | 与列表切片同语法，返回共享存储的视图 |
| `.clone()` | `window[:-1].clone()` | 复制出独立张量 |
| `torch.tensor(..., dtype=torch.long)` | `self.ids = torch.tensor(ids, dtype=torch.long)` | 列表转 int64 张量 |
| `.numel()` / `.shape` / `.tolist()` | `self.ids.numel()`、`tuple(input_ids.shape)`、`inputs[0].tolist()` | 元素个数、形状、转回 Python 列表 |
| `torch.equal` | `torch.equal(input_ids[1:], target_ids[:-1])` | 形状与元素都相同才为 True |
| `torch.Generator().manual_seed(...)` | `make_dataloader` | 独立的随机数生成器 |
| `next(iter(loader))` | `inputs, targets = next(iter(loader))` | 取 DataLoader 的第一个 batch |
| 条件表达式作参数 | `generator=generator if shuffle else None` | 只有 shuffle 时才传 generator |
| `@dataclass` + `field(default_factory=dict)` | `class MiniBPE` | 每个实例独立的字典字段 |
| `Iterable[str]` 注解 | `specials: Iterable[str] = DEFAULT_SPECIALS` | 接受任何可迭代对象 |
| 元组作字典键 | `units[symbols] = units.get(symbols, 0) + 1` | 统计不同字节序列 |
| f-string 对齐 | `f"  stride {s:>2}: {len(ds):>4} windows"` | 右对齐宽度 2、4 |
| `assert 条件, 信息` | `assert inputs.shape == (batch_size, context_length)` | 演示中的契约检查 |
| `raise SystemExit(main())` | 文件末尾 | 以返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + torch 2.14.1 CPU，`cd code && python3 main.py`，退出码 0，约 1.8 秒；结果确定）：

```text
Corpus and tokenizer
--------------------
corpus chars      : 7408          ← 18 行 × 8 次
vocab size        : 320           ← 256 + 2 + 62 个合并
total ids         : 4912          ← 约 1.51 字符/id
context length    : 16
stride            : 8
num windows       : 612           ← 1 + (4912 − 17) // 8

Inspect one example
-------------------
input shape       : (16,)
target shape      : (16,)

Pull a batch from the DataLoader
--------------------------------
inputs            : (4, 16)
targets           : (4, 16)
first input row   : [32, 310, 284, 121, 32, 292, 270, 115, 32, 294, 318, 265, 110, 100, 32, 269]
first target row  : [310, 284, 121, 32, 292, 270, 115, 32, 294, 318, 265, 110, 100, 32, 269, 262]

Shuffle is seeded
-----------------
same seed -> same first batch: OK
different epoch -> different order: OK

Stride trade-off
----------------
  stride  4: 1224 windows
  stride  8:  612 windows
  stride 16:  306 windows

Demo OK.
```

逐项解读：

- **4912 个 id**：语料 7408 个字符，压缩比约 0.66 id/字符；其中大量 id 是单独成块的空格（32），与第 30 课相同的预分词特点。
- **第一行输入与目标**：目标就是输入左移一位，最后多出的 `262` 是窗口的第 17 个 id；第一行以 `32`（空格）开头，说明窗口起点是任意的 id 位置，不对齐单词或句子——这正是讲义说的"边界多样性"问题。
- **数据集第 0 个窗口**解码为 `'the quick brown fox jumps'`（16 个 id），而 DataLoader 的第一行来自打乱后的某个窗口。
- **stride 取舍**：stride 减半样本数翻倍；`S = 8` 时中间每个 id 被当作目标 2 次（实测 4888 个位置 2 次、首尾 16 个位置 1 次），等于每个 epoch 把数据看两遍。
- **讲义练习**：把 `context_length` 改成 32 而 stride 仍为 8，窗口数是 610，几乎不变；要看到"样本数下降"，需要同时令 `stride = context_length`（306 → 153）。

---

## 7. 动手改一改

1. **验证公式**：对 `T ∈ {8, 16, 32}`、`S ∈ {1, T/2, T}` 打印窗口数、每 epoch 步数和尾部丢弃的 id 数，与第 3.3 节的表对照。
2. **补上 stride 检查**：当 `stride > context_length + 1` 时发出 `warnings.warn` 或抛 `ValueError`；当 `len(self) == 0` 时在构造阶段给出"语料太短"的明确错误。
3. **多文档**：实现测验 Q9 的 `build_ids_from_documents`，在文档之间追加 EOT id，统计有多少窗口跨越了文档边界。
4. **尾部 padding**：实现测验 Q11 的 `PaddedTailDataset`，用 `F.cross_entropy(..., ignore_index=-100)` 验证 padding 位置不贡献 loss。
5. **紧凑存储**：底层改用 `np.uint16`（或 `np.memmap` 打开磁盘文件），`__getitem__` 中转 `torch.long`；对比内存（demo 中 39,296 → 9,824 字节）。
6. **进阶**：加一个"每个 epoch 随机起点偏移"选项——`offset = rng.integers(0, S)`，窗口起点变为 `offset + i*S`；用它在 `S = T` 时也获得边界多样性，并保证同一 `(base_seed, epoch)` 下可复现。

---

## 8. 常见坑

- **忘了 `T + 1`**：只取 `T` 个 id 再左移，会得到 `T − 1` 长度的样本，或者最后一个目标越界。
- **以为改 `T` 会显著改变样本数**：样本数主要由 stride 决定。
- **stride 大于窗口长度**：静默跳过数据。
- **越界不报错**：张量切片越界会返回更短的结果，必须在 `__getitem__` 里显式检查。
- **返回视图而不 clone**：调用方原地修改会污染底层 id 流。
- **复用同一个 DataLoader 却以为顺序固定**：generator 状态会前进。
- **在文本中写 `<|endoftext|>` 字面量当作文档分隔**：本课的 `encode_text` 会把它编码成普通 token，必须在 id 层面追加保留 id。
- **随机抽窗口划分验证集**：重叠窗口导致数据泄漏，应先切 id 流再分别构造窗口（测验 Q12）。
- **padding 目标用 pad id 而不是 `-100`**：模型会学着预测 padding。
- **int64 存储大语料**：内存是 `uint16` 的 4 倍。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m pytest -q tests`。实际结果：**17 passed in 1.44s**。测试语料是 3 句话 × 30，用 `target_vocab=300` 训练 tokenizer。

| 测试 | 验证的性质 |
|------|-----------|
| `TestCountWindows.test_count_with_stride_equal_to_context` | `count_windows(33, 8, 8) == 1 + (33 − 9) // 8 = 4` |
| `test_count_with_half_stride_doubles` | 同样 200 个 id、`T = 16`，`S = 8` 的窗口数多于 `S = 16`（名字说"翻倍"，实际只断言"更多"：12 vs 23） |
| `test_count_zero_when_corpus_too_short` | 4 个 id、`T = 16` → 0 个窗口 |
| `test_count_one_when_exact_fit` | 恰好 `T + 1 = 9` 个 id → 1 个窗口（边界条件） |
| `TestDatasetShape.test_len_matches_count_windows` | `len(dataset)` 与静态公式一致 |
| `test_getitem_returns_long_tensors_of_T` | 输入、目标都是 `torch.long`，形状 `(T,)` |
| `test_target_is_input_shifted_by_one` | 第 3 个窗口满足 `inputs[1:] == targets[:-1]` |
| `test_window_endpoints_match_id_stream` | 第 2 个窗口的输入恰好等于 `ids[2S : 2S + T]`，验证起点计算 |
| `test_negative_index_supported` | `ds[-1]` 与 `ds[len(ds) − 1]` 相同 |
| `test_out_of_range_raises` | `ds[len(ds)]` 抛 `IndexError` |
| `TestDatasetGuards`（3 个） | `context_length=0`、`stride=0`、空 `ids` 都抛 `ValueError` |
| `TestDataLoaderDeterminism.test_same_seed_same_first_batch` | 同种子同 epoch → 第一个 batch 相同 |
| `test_different_epoch_changes_order` | 不同 epoch → 第一个 batch 不同 |
| `test_no_shuffle_preserves_index_order` | `shuffle=False` 时第一个样本就是 `ds[0]` |
| `TestBatchShape.test_batch_shape_matches_contract` | `T = S = 16`、`B = 3`：batch 形状 `(3, 16)`，且在 batch 维度上也满足左移一位 |

测试没有覆盖：`stride > T + 1` 的数据遗漏、空数据集交给 DataLoader 时的报错、多文档 EOT 插入、复用 DataLoader 时的顺序变化、尾部丢弃的 id 数。
