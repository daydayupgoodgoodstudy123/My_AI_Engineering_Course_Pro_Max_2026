# 测验 · 使用滑动窗口构建分词后的数据集（Tokenized Dataset with Sliding Window）

> **阶段 19 · 综合项目 · 第 31 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 形状契约 | 因果 LM 每个 batch 是 `(B, T)` 的输入与 `(B, T)` 的目标，目标是输入左移一位；所以每个样本要覆盖 `T+1` 个原始 id |
| 2 | 一次性分词 | 整个语料只调用一次 tokenizer，得到一条扁平的 id 流，之后的切片都在 id 上做 |
| 3 | 滑动窗口 | 第 i 个窗口是 `ids[i*S : i*S + T + 1]`；`S = T` 不重叠，`S = T/2` 重叠一半、样本数约翻倍，`S = 1` 样本数约为 `T` 倍 |
| 4 | 窗口计数公式 | `max(0, 1 + (N − (T+1)) // S)`；凑不满 `T+1` 的尾部直接丢弃 |
| 5 | Dataset 惰性切片 | 只存一份 id 张量，`__getitem__` 按 index 现算起点，内存与 stride 无关 |
| 6 | 左移一位在 `__getitem__` 内完成 | `input = window[:-1]`、`target = window[1:]`，都是 `torch.long` |
| 7 | 确定性 shuffle | 每个 epoch 新建 DataLoader，`torch.Generator().manual_seed(base_seed + epoch)`；同种子同顺序，换 epoch 换顺序 |
| 8 | DataLoader 细节 | 默认随机采样是无放回的排列；`drop_last=True` 丢掉不满的最后一个 batch；`num_workers=0` |
| 9 | stride 的代价与收益 | 小 stride 增加边界多样性，但每个 epoch 计算量成倍增加，且同一 token 被重复当作目标；大语料预训练通常 `S = T` |
| 10 | 本节不做的事 | 不从磁盘流式读取、不处理多文档边界（讲义说应在文档间插 `<\|endoftext\|>`，但代码中的 `encode_text` 并不支持 special token） |

### 核心技能（能动手做到）

- [ ] 给定 `N`、`T`、`S` 手算窗口数、每 epoch 的 batch 数、尾部被丢弃的 id 数
- [ ] 实现一个 PyTorch `Dataset`（`__len__` / `__getitem__`，支持负索引与越界检查），返回左移一位的 `(input, target)`
- [ ] 用 `torch.Generator` 做到"同种子可复现、不同 epoch 不同顺序"，并解释复用同一个 DataLoader 时为什么顺序会变
- [ ] 分析 stride 对样本数、重复梯度、数据覆盖率的影响，识别 `S > T+1` 时的数据遗漏
- [ ] 为多文档语料插入 `<|endoftext|>`，为尾部窗口做 padding + `ignore_index` 屏蔽
- [ ] 估算 id 张量的内存，并选择合适的整数类型

---

## 二、基础自测（选择题）

**Q1.** demo 中语料编码后共 `N = 4912` 个 id，`T = 16`，`S = 8`。窗口数是：

- A. 613
- B. 306
- C. 612
- D. 611

**Q2.** 对第 i 个窗口 `window = ids[start : start + T + 1]`，`__getitem__` 返回 `(window[:-1], window[1:])`。下列关系恒成立的是：

- A. `target[t] == input[t + 1]`（对 `t = 0 … T−2`），且 `target[T−1] == ids[start + T]`
- B. `target[t] == input[t − 1]`
- C. `target == input`，左移发生在 loss 计算时
- D. `target[0] == ids[start]`

**Q3.** 讲义最后建议："change the context length from 16 to 32 and watch how the number of examples per epoch falls." 保持 demo 的 `stride = 8` 不变，实际窗口数从 612 变为：

- A. 306，减半
- B. 153，变为四分之一
- C. 1224，翻倍
- D. 610，几乎不变——窗口数主要由 stride 决定，`T` 只影响 `N − (T+1)` 这一小项；只有令 `S = T` 时才会降到 153

**Q4.** demo 配置 `T = 16`、`S = 8`。对 id 流中间的某个位置，它在一个 epoch 中被当作**预测目标**多少次？

- A. 1 次
- B. 2 次（实测 4888 个位置各 2 次，只有首尾各 8 个位置是 1 次）
- C. 8 次
- D. 16 次

**Q5.** 某同学只创建一次 `loader = make_dataloader(ds, 4, base_seed=7, epoch=0)`，然后每个 epoch 都 `for batch in loader:`。结果是：

- A. 每个 epoch 的顺序都不同，但整个运行仍然可复现；因为 generator 的状态在每次 `iter(loader)` 时向前推进（实测两次 `next(iter(loader))` 得到不同 batch）。缺点是无法直接"从第 k 个 epoch 的顺序"恢复
- B. 每个 epoch 的顺序完全相同
- C. 第二个 epoch 抛出异常，因为 generator 只能用一次
- D. 每个 epoch 的顺序不可复现，因为 DataLoader 内部改用了全局随机数

**Q6.** `SlidingWindowDataset(list(range(100)), context_length=4, stride=10)` 会怎样？

- A. 构造时抛出 `ValueError`，因为 stride 大于 context_length
- B. 自动把 stride 截断为 `T + 1 = 5`
- C. 10 个窗口覆盖全部 100 个 id
- D. 正常构造出 10 个窗口，但每个窗口只用 5 个 id，实测只覆盖 50 / 100 个 id——一半数据永远不会被训练到，代码没有任何警告

**Q7.** demo 中 `batch_size = 4`、`drop_last = True`、612 个窗口。一个 epoch 的 step 数和每个 batch 的张量形状分别是：

- A. 153 步；`inputs` 为 `(4, 17)`、`targets` 为 `(4, 17)`
- B. 612 步；`(16,)`
- C. 153 步；`inputs` 与 `targets` 都是 `(4, 16)`、`dtype=torch.long`
- D. 154 步；最后一步是 `(0, 16)`

**Q8.** 若语料很短，例如 `SlidingWindowDataset([1, 2, 3], context_length=8)`，再调用 `make_dataloader(ds, 2)`（默认 `shuffle=True`），结果是：

- A. 数据集构造时就抛 `ValueError`
- B. 数据集构造成功、`len(ds) == 0`，但 `make_dataloader` 在构造 DataLoader 时抛 `ValueError: num_samples should be a positive integer value, but got num_samples=0`
- C. DataLoader 正常返回，迭代时得到 0 个 batch
- D. 自动用 `<|pad|>` 补齐到 `T + 1`

---

## 三、动手 / 代码题

**Q9.** 讲义说："The next-document boundary is encoded by inserting `<|endoftext|>` ids when the corpus is built from multiple documents." 但本节的 `encode_text` 没有 special token 支持——`encode_text(tok, "a<|endoftext|>b")` 实测得到 `[97, 60, 124, 271, 276, 102, 116, 101, 120, 116, 124, 62, 98]`，这一串全是普通字节/合并 token，里面没有 EOT id 256。

1. 写 `build_ids_from_documents(tokenizer, docs) -> list[int]`，在每个文档后追加 EOT id。
2. 用 `docs = ["the quick brown fox", "the lazy dog sleeps", "focus is saying no"]`，id 流长度是多少？EOT 出现在哪些位置？
3. 滑动窗口会跨越文档边界，这有什么影响？有哪些处理方式？

**Q10.** `self.ids = torch.tensor(ids, dtype=torch.long)` 每个 id 占 8 字节。

1. demo 的 id 张量占多少字节？对一个 100 亿（1e10）token 的语料，按 `int64` 与 `uint16` 存储各需多少内存？本节词表 320、GPT-2 词表 50,257，用 `uint16` 是否安全？
2. 修改 Dataset：底层用紧凑类型存储，在 `__getitem__` 中再转成 `torch.long`。为什么输出必须是 `long`？

**Q11.** 本节"凑不满 `T+1` 就丢弃尾部"。

1. 对 `N = 4912`、`T = 16`，分别计算 `S = 8` 与 `S = 16` 时被丢弃的尾部 id 数。
2. 实现一个 `PaddedTailDataset`：最后一个窗口不足时，输入用 `<|pad|>`（id 257）补齐，目标用 `-100` 补齐，使 `F.cross_entropy(..., ignore_index=-100)` 自动忽略这些位置。给出 `count_windows` 的新公式，并用 `list(range(30))`、`T = 8`、`S = 8` 验证。

**Q12.** 你需要从同一条 id 流中划出验证集。同事的做法是：先用 `S = 8`、`T = 16` 构造全部窗口，再随机抽 10% 的窗口作为验证集。

1. 这种做法有什么问题？
2. 给出正确的切分方法与代码要点。

---

## 四、面试高频题

**Q13.**（基础必考）描述一个因果语言模型预训练数据管道从原始文本到 `(B, T)` 训练张量的完整过程。为什么目标是输入左移一位？为什么每个样本需要 `T+1` 个 id？

**Q14.**（原理深挖）stride 应该怎么选？`S = 1`、`S = T/2`、`S = T` 各有什么利弊？为什么大规模预训练通常用 `S = T`？

**Q15.**（工程实践）如何保证数据顺序可复现，并支持训练中断后从第 k 个 epoch 的第 m 步精确恢复？多卡、多 worker 时要注意什么？

**Q16.**（场景设计）语料是 2TB 文本，你会如何把本节的内存版 Dataset 改造成生产级数据管道？

**Q17.**（追问型）把多个文档用 `<|endoftext|>` 拼接后切窗口，模型会在一个窗口里看到上一个文档的结尾。这会造成什么问题？"按文档 padding"、"拼接 + EOT"、"拼接 + 文档内注意力 mask" 三种方案怎么取舍？

---

## 五、参考答案与解析

### Q1 — 答案：C

`1 + (4912 − 17) // 8 = 1 + 4895 // 8 = 1 + 611 = 612`，与 demo 输出 `num windows : 612` 一致。A 是把 `T+1` 误写成 `T` 的结果（`1 + (4912 − 16) // 8 = 613`），忘了目标需要多 1 个 id；B 是 `S = 16` 的结果；D 忘了 `1 +`（起点为 0 的那个窗口）。

### Q2 — 答案：A

`input = window[0:T]`，`target = window[1:T+1]`，所以 `target[t] = window[t+1] = input[t+1]`（`t ≤ T−2`），最后一个目标 `target[T−1] = window[T] = ids[start + T]` 是输入里没有的那个 id——这正是需要 `T+1` 个 id 的原因。demo 的断言 `torch.equal(input_ids[1:], target_ids[:-1])` 检查的就是这个关系；实测第一行 `input` 以 `..., 32, 269]` 结尾，`target` 以 `..., 269, 262]` 结尾。B 方向反了；C 错，左移在 `__getitem__` 内完成；D 错，`target[0] = ids[start + 1]`。

### Q3 — 答案：D

`1 + (4912 − 33) // 8 = 1 + 609 = 610`（已实测）。窗口数 ≈ `N / S`，几乎只由 stride 决定；改 `T` 只是让每个窗口更长、相邻窗口重叠更多。讲义的说法只在 `S = T`（不重叠）时成立：`T = 16, S = 16` 为 306，`T = 32, S = 32` 为 153。所以把"每 epoch 步数"理解为由 `N / S / B` 决定更准确。A、B、C 都与公式不符。

### Q4 — 答案：B

每个窗口覆盖 16 个目标位置，相邻窗口错开 8，于是中间的每个位置恰好落在 2 个窗口中。实测：4888 个位置各被当作目标 2 次，只有开头 8 个和结尾 8 个位置是 1 次（尾部还有 7 个 id 根本没被覆盖，见 Q11）。这意味着 `S = T/2` 时每个 epoch 对同一段数据算两次梯度——相当于数据重复了一遍。A 是 `S = T` 的情况；C、D 不对。

### Q5 — 答案：A

`make_dataloader` 只在构造时 `manual_seed` 一次；每次 `iter(loader)` 都会从同一个 generator 抽取新的随机排列，状态随之前进，所以第二次迭代的顺序与第一次不同（实测 `torch.equal(a, b)` 为 False）。整个运行仍然可复现（同一个起始种子 → 同一串 epoch 顺序），但要从第 k 个 epoch 恢复时，必须把前 k 个 epoch 的随机数全部"重放"一遍。本节"每个 epoch 用 `base_seed + epoch` 新建 DataLoader"的设计让第 k 个 epoch 的顺序只依赖 `(base_seed, k)`，恢复时可以直接构造。B、C、D 都与实际行为不符。

### Q6 — 答案：D

构造函数只检查 `stride >= 1`，没有检查 `stride <= T + 1`。窗口起点为 0、10、20…90，每个窗口取 5 个 id（0–4、10–14…），实测 10 个窗口只覆盖 50 / 100 个 id。A、B 是"应该有的保护"但代码没有；C 错。

### Q7 — 答案：C

`612 // 4 = 153` 步（`drop_last=True`，612 恰好整除，不会丢 batch；`len(loader)` 实测为 153）。每个样本是 `(16,)`，`default_collate` 把 4 个样本堆叠成 `(4, 16)`；demo 有断言 `inputs.shape == (batch_size, context_length)`。A 的 17 是窗口长度 `T+1`，切分后是 16；B 是样本形状而非 batch 形状；D 错。

### Q8 — 答案：B

`count_windows(3, 8, 8)`：`usable = 3 − 9 < 0` → 0，所以 `len(ds) == 0`，构造不报错（只有 `ids` 为空时才报错）。但 `shuffle=True` 时 DataLoader 会创建 `RandomSampler`，它在构造时检查样本数，实测抛出 `ValueError: num_samples should be a positive integer value, but got num_samples=0`。这个错误信息与"语料太短"相距甚远，容易让人困惑；更好的做法是在 Dataset 构造时就检查 `len(self) > 0` 并给出明确提示。A、C、D 都不是实际行为。

### Q9 — 参考答案

1. 实现（已运行验证）：

```python
def build_ids_from_documents(tokenizer: MiniBPE, docs: list[str]) -> list[int]:
    eot = tokenizer.special_to_id["<|endoftext|>"]     # 256
    ids: list[int] = []
    for doc in docs:
        ids.extend(encode_text(tokenizer, doc))       # 普通文本走 BPE
        ids.append(eot)                                # 边界直接追加保留 id，不经过 encode
    return ids
```

   关键是 EOT 由**代码**直接追加，而不是在文本里写字面量再编码——本节的 `encode_text` 会把字面量当普通字节处理（题干的实测结果），而且即使 tokenizer 支持 `allow_special`，也不应该对外部文本打开它。

2. 用 demo 的 tokenizer（目标 320）实测：id 流长度为 **40**，EOT（256）出现在下标 **11、25、39**（三个文档分别编码为 11、13、13 个 id）。
3. 跨文档的影响与处理：
   - 一个窗口可能包含"文档 A 的结尾 + EOT + 文档 B 的开头"，模型在预测 B 的开头时能注意到 A 的内容，学到虚假的跨文档依赖；
   - 讲义的观点是"模型学会围绕边界做预测"，即看到 EOT 就知道后面是新文档——这是 GPT 系列的常见做法，开销最小；
   - 更严格的做法：①在注意力中加入文档级 mask（document masking），让 token 只能看到同一文档内的前文；②按文档打包（packing）并重置位置编码；③短文档单独成样本并 padding（浪费算力）。详见 Q17。

### Q10 — 参考答案

1. demo：`4912 × 8 = 39,296` 字节（实测）。1e10 token：`int64` 需 **80 GB**，`uint16` 需 **20 GB**。`uint16` 的范围是 0–65,535：本节词表 320、GPT-2 词表 50,257 都能装下；但 Llama 3 的 128K 词表就装不下，需用 `int32`（40 GB）。
2. 修改要点：

```python
import numpy as np
from torch.utils.data import Dataset

class CompactSlidingWindowDataset(Dataset):
    def __init__(self, ids, context_length, stride=None):
        if context_length < 1 or not ids:
            raise ValueError("context_length must be >= 1 and ids non-empty")
        stride = context_length if stride is None else stride
        if stride < 1:
            raise ValueError("stride must be >= 1")
        dtype = np.uint16 if max(ids) < 2**16 else np.int32
        self.ids_np = np.asarray(ids, dtype=dtype)        # 紧凑存储（也可以换成 np.memmap）
        self.context_length, self.stride = context_length, stride

    def __len__(self):
        return SlidingWindowDataset.count_windows(len(self.ids_np), self.context_length, self.stride)

    def __getitem__(self, index):
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        start = index * self.stride
        window = torch.from_numpy(self.ids_np[start:start + self.context_length + 1].astype(np.int64))
        return window[:-1], window[1:]                    # astype 已经复制，无需再 clone
```

   已验证：在 demo 的 4912 个 id 上，612 个窗口与原实现逐一相等，底层数组只占 9,824 字节（原来 39,296），取出的张量 dtype 为 `torch.int64`。

   输出必须是 `long`（int64）：`nn.Embedding` 的索引与 `F.cross_entropy` 的目标都要求整数索引类型，`cross_entropy` 的类别目标必须是 `long`；而且 PyTorch 对 `uint16` 张量的运算支持很有限，所以通常在 NumPy 侧紧凑存储、取出时再转。这也是第 43 课用 HDF5 存分词语料的出发点。

### Q11 — 参考答案

1. 最后一个窗口的结束位置 = `(n − 1) × S + T + 1`：
   - `S = 8`：n = 612，结束于 `611 × 8 + 17 = 4905`，丢弃 `4912 − 4905 = 7` 个；
   - `S = 16`：n = 306，结束于 `305 × 16 + 17 = 4897`，丢弃 **15** 个（实测一致）。
   最多丢弃 `S − 1` 个；对大语料可忽略，对小语料或"每个文档单独切窗口"时损失明显。
2. 实现（已运行验证）：

```python
class PaddedTailDataset(SlidingWindowDataset):
    def __init__(self, ids, context_length, stride=None, pad_id=257, ignore_index=-100):
        super().__init__(ids, context_length, stride)
        self.pad_id, self.ignore_index = pad_id, ignore_index

    @staticmethod
    def count_windows(num_ids, context_length, stride):
        if num_ids < 2:
            return 0
        # 向上取整：只要还有剩余 id 就多开一个窗口
        return 1 + max(0, -(-(num_ids - (context_length + 1)) // stride))

    def __getitem__(self, index):
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        start = index * self.stride
        window = self.ids[start:start + self.context_length + 1]
        x, y = window[:-1].clone(), window[1:].clone()
        pad = self.context_length - x.numel()
        if pad > 0:
            x = torch.cat([x, torch.full((pad,), self.pad_id, dtype=torch.long)])
            y = torch.cat([y, torch.full((pad,), self.ignore_index, dtype=torch.long)])
        return x, y
```

   `list(range(30))`、`T = 8`、`S = 8`：原实现 3 个窗口，新实现 4 个；最后一个为 `x = [24, 25, 26, 27, 28, 257, 257, 257]`、`y = [25, 26, 27, 28, 29, -100, -100, -100]`，id 29 也被用作目标了。`F.cross_entropy(logits, y, ignore_index=-100)` 正常返回有限值。要点：
   - 目标用 `-100` 而不是 pad id，否则模型会学着预测 padding（讲义："The loss mask hides it during training"）；
   - 因果注意力下，padding 在序列末尾不会影响前面位置的计算，所以输入侧不需要额外 attention mask；
   - 讲义说"Padding the tail ... complicates the loss mask"，代价就是需要这套 `ignore_index` 约定。

### Q12 — 参考答案

1. 问题：窗口之间有重叠（`S = 8 < T + 1 = 17`），一个验证窗口的大部分 id 同时出现在相邻的训练窗口中。随机抽取窗口相当于把验证数据的内容泄漏进训练集，验证 loss 会被严重低估，无法反映泛化能力。即便 `S = T`，相邻窗口也共享 1 个 id，且同一文档被拆到两边仍有信息泄漏。
2. 正确做法：**先切 id 流（最好按文档切），再分别构造窗口**，并在切分点留出至少 `T` 个 id 的间隔：

```python
def split_ids(ids, val_fraction=0.1, gap=None, context_length=16):
    gap = context_length if gap is None else gap
    cut = int(len(ids) * (1 - val_fraction))
    train_ids = ids[:cut]
    val_ids = ids[cut + gap:]                       # 留出间隔，避免边界附近共享上下文
    return train_ids, val_ids

train_ds = SlidingWindowDataset(train_ids, 16, stride=8)
val_ds = SlidingWindowDataset(val_ids, 16, stride=16)   # 验证集用不重叠窗口即可
```

   多文档语料中更好的方式是按文档（或按来源）划分，保证同一文档不会同时出现在两边；验证集用 `S = T` 既省算力，又让每个 token 只被评估一次。

### Q13 — 参考回答要点

- **流程**：原始文本 →（清洗、去重）→ tokenizer 一次性编码为 id（文档间插 EOT）→ 拼成一条扁平 id 流 → 按 `T+1` 长度、步长 `S` 切窗口 → 每个窗口拆成 `input = w[:-1]`、`target = w[1:]` → DataLoader 按种子打乱、组 batch → `(B, T)` 的 `long` 张量送入模型。
- **为什么左移一位**：因果 LM 的目标是 next-token prediction，位置 t 的输出要预测 t+1 的 token；配合因果 mask，一个长度 T 的序列一次前向就能同时得到 T 个训练信号。
- **为什么 T+1**：T 个输入位置各需要一个"下一个 token"作为目标，最后一个输入位置的目标在输入之外，所以窗口要多取 1 个 id。
- 加分点：说明 tokenizer 只在构建时调用一次（讲义的时序图："tokenizer.encode runs once at build time"），训练循环里只做张量切片，数据加载不会成为瓶颈。

### Q14 — 参考回答要点

- **`S = T`**：不重叠、每个 token 每 epoch 只当一次目标，计算量最小；缺点是窗口边界固定，靠近窗口开头的 token 上下文很短，且每个 epoch 都在相同位置截断。
- **`S = T/2`**：样本数约翻倍，边界更多样；代价是每 epoch 计算量翻倍，且每个 token 被当作目标两次（Q4），相当于数据重复。
- **`S = 1`**：样本数约为 `T` 倍，边界多样性最大，但冗余极高，基本只适合很小的数据集。
- **`S > T+1`**：会跳过数据，通常是 bug（Q6）。
- **大规模预训练选 `S = T`**：讲义："the corpus is already much larger than the model can finish in one epoch, so the boundary diversity argument is weaker." 数据量远超训练预算时，与其重复看同一段数据的不同切法，不如看新数据；边界多样性也可以通过每个 epoch 随机偏移起点（random offset）低成本获得。
- 加分点：小数据集（如领域微调）上可以用较小 stride 或多 epoch，但要警惕过拟合。

### Q15 — 参考回答要点

- **可复现**：所有随机源都要定种子——模型初始化、dropout、数据顺序；数据顺序用独立的 `torch.Generator`，按 `base_seed + epoch` 派生，使每个 epoch 的顺序可以单独重建。
- **精确恢复**：checkpoint 中保存 `epoch`、epoch 内已完成的 step 数（或已消费的样本数）、`base_seed`；恢复时用 `base_seed + epoch` 重建该 epoch 的排列，跳过前 `m × B` 个样本（可以只跳过索引而不真正加载数据）。第 47 课会专门讲 checkpoint 保存与恢复。
- **多卡**：用 `DistributedSampler`，每个 epoch 调用 `sampler.set_epoch(epoch)`，保证各 rank 使用相同种子的排列并各取互不重叠的子集；否则各卡数据重复或不一致。
- **多 worker**：worker 进程有自己的随机状态，若 `__getitem__` 中有随机操作（如随机偏移），需要用 `worker_init_fn` 或基于 index 的确定性随机；本节的 `__getitem__` 是纯函数，没有这个问题。
- **种子派生的小坑**：`base_seed + epoch` 会让 `(base_seed=7, epoch=1)` 与 `(base_seed=8, epoch=0)` 得到同一顺序；更稳妥的是用哈希组合，如 `hash((base_seed, epoch))` 或 `numpy.random.SeedSequence`。

### Q16 — 参考回答要点

- **离线分词**：用多进程/集群把语料分片编码成 id，存成紧凑的二进制分片（`uint16`/`int32` 的 `.bin`、`.npy` 或 HDF5，见第 43 课），每个分片附带元数据（token 数、文档边界）。
- **随机访问**：用 `np.memmap` 打开分片，Dataset 只保存"全局窗口编号 → (分片, 偏移)"的映射，`__getitem__` 直接从 memmap 切片，内存占用与语料大小无关。
- **流式方案**：用 `IterableDataset` 顺序读取分片，配合"分片级打乱 + 内存 shuffle buffer"，适合远程对象存储。
- **并行**：`num_workers > 0` 与 `pin_memory=True`，预取若干 batch；多机时按 rank 分配分片。
- **质量与配比**：在分词前完成清洗、去重（第 42 课的语料下载器）、按来源配比采样。
- **可恢复**：记录每个 rank 已消费的分片与偏移。
- 加分点：讲义也指出"Disk streaming ... plugs in by replacing the storage but keeps the Dataset contract"——接口不变，只换存储层。

### Q17 — 参考回答要点

- **问题**：拼接后，一个窗口里文档 B 的 token 可以注意到文档 A 的内容；这些跨文档注意力是无意义的噪声，长上下文训练中可能削弱模型对"什么是相关上下文"的判断。EOT 至少告诉模型"这里换文档了"，模型通常能学会在 EOT 之后不依赖前文。
- **三种方案**：
  - **按文档 padding**：每个样本只含一个文档，不足补 pad 并用 `ignore_index` 屏蔽。干净但浪费算力（短文档多时 padding 比例很高）。
  - **拼接 + EOT**（本节讲义的方案）：零浪费、实现最简单，GPT-2/GPT-3 式预训练的常见做法；代价是存在跨文档注意力。
  - **拼接 + 文档内注意力 mask**（document masking / packing with block-diagonal mask）：零浪费且无跨文档注意力；需要在 attention 中支持变长块对角 mask（如基于序列长度累计偏移的变长注意力 kernel），位置编码也可按文档重置。实现最复杂。
- 取舍：短文档多、长上下文训练时更值得做文档 mask；常规预训练"拼接 + EOT"通常足够。
- 加分点：微调（SFT）阶段多用 padding 或带 mask 的 packing，因为样本是独立的对话，跨样本注意力的危害更大。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../30-bpe-tokenizer-from-scratch/docs/zh.md)：本节内联的 `MiniBPE` 来自上一课。
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：预训练数据的打包与加载。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：左移一位的 next-token 目标与因果 mask。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：词表大小决定 id 的取值范围与存储类型。

### 本节被哪些后续内容用到
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：消费本节产出的 `(B, T)` id 张量。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)、[阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：用本节的 DataLoader 训练与验证。
- [阶段 19 · 43 HDF5 格式的分词语料](../../43-hdf5-tokenized-corpus/docs/zh.md)：把内存版 id 流换成磁盘存储。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)、[阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)、[阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：有效 batch、数据位置恢复与分布式采样。

### 延伸关键词
`next-token prediction` · `context length` · `stride / overlap` · `torch.utils.data.Dataset` · `DataLoader` · `torch.Generator` · `DistributedSampler.set_epoch` · `drop_last` · `ignore_index=-100` · `sequence packing` · `document masking` · `np.memmap` · `IterableDataset`
