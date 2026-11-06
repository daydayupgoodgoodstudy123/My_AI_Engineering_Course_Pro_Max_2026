# 测验 · 数据管理（Data Management）

> **阶段 00 · 环境搭建与工具 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/data_utils.py](../code/data_utils.py) ｜ 代码讲解：[code/data_utils.讲解.md](../code/data_utils.讲解.md)
>
> **用法**：学完讲义、`pip install datasets huggingface_hub` 并跑过 `python code/data_utils.py`（需要联网）后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | HF `datasets` 加载与缓存 | `load_dataset("stanfordnlp/imdb")` 首次下载，之后从 `~/.cache/huggingface/datasets/` 读缓存 |
| 2 | 流式加载（streaming） | `streaming=True` 返回 `IterableDataset`，边下边处理、不落完整数据，内存占用与数据集大小无关；代价是不能随机索引 |
| 3 | Arrow：内存里的格式 | `datasets` 底层用 Apache Arrow 列式格式，并对磁盘上的 Arrow 文件做内存映射，可以处理比内存大的数据集 |
| 4 | 四种格式的分工 | Parquet 适合存储（列式 + 压缩，小且快）；Arrow 适合内存处理；CSV / JSON 适合交换和人读 |
| 5 | train / val / test 三分 | 训练集学参数、验证集调超参和看训练进度、测试集只在最后评估一次；常见 80/10/10 |
| 6 | 固定种子可复现 | 同样的数据 + 同样的 `seed` → 同样的切分；数据本身变了，种子也救不了 |
| 7 | 两段式切分的比例换算 | 先切出"val+test"，再按 `val/(val+test)` 二次切分；比例算错就得到错误的划分 |
| 8 | 模型文件下载 | `hf_hub_download` 下单个文件、`snapshot_download` 下整个仓库，缓存在 `~/.cache/huggingface/hub/` |
| 9 | 大文件不进 git | `.gitignore`（最简单）→ Git LFS（git 里存指针）→ DVC（`.dvc` 指针文件 + S3/GCS 远程存储，面向可复现实验） |
| 10 | 数据指纹 | 对数据内容做哈希，快速判断"这次实验用的数据和上次是不是同一份" |

### 核心技能（能动手做到）

- [ ] 用 `load_dataset` 加载一个数据集，打印 `column_names`、`features` 和第一行，并说出 `label` 是什么类型
- [ ] 用 `streaming=True` 只取前 N 行，并解释为什么 `ds[0]` 在流式模式下不可用
- [ ] 把同一份数据导出为 CSV / JSON / Parquet，比较文件大小，再从 Parquet 读回来
- [ ] 写出一个 70/15/15、`seed` 固定的三分切分，打印每份大小并验证重复运行结果一致
- [ ] 分别用 `hf_hub_download` 和 `snapshot_download` 下载模型文件，并在缓存目录里找到它们
- [ ] 为一个项目写好 `.gitignore`，并能说清 `git lfs track` / `dvc add` 之后真正提交进 git 的是什么文件
- [ ] 读懂 `data_utils.py` 的 `make_splits`，能指出浮点比例导致的边界问题

---

## 二、基础自测（选择题）

**Q1.** `load_dataset(..., split="train", streaming=True)` 返回的对象：

- A. 是一个普通 `Dataset`，只是下载速度更快
- B. 是 `IterableDataset`，需要边迭代边取数据，不支持 `ds[0]` 这样的随机访问
- C. 会先把完整数据下载到磁盘，再逐行读出来
- D. 只能用于 Hugging Face 官方组织下的数据集

**Q2.** 为什么讲义说"对 AI 工作来说，Parquet 是最好的存储格式"？

- A. Parquet 是纯文本，可以直接在编辑器里修改
- B. Parquet 是列式、带压缩的二进制格式，文件更小，而且可以只读需要的列
- C. Parquet 只能被 `datasets` 库读取，因此更安全
- D. Parquet 天然支持嵌套 JSON，CSV 不支持任何数据类型

**Q3.** 讲义 Step 5 的切分代码作用在 IMDB 的 `train`（25,000 行）上：

```python
split = dataset.train_test_split(test_size=0.2, seed=42)
train_val = split["train"].train_test_split(test_size=0.125, seed=42)
```

最终 `Train / Val / Test` 的行数是：

- A. 20000 / 2500 / 2500
- B. 17500 / 2500 / 5000
- C. 20000 / 2000 / 3000
- D. 17500 / 3750 / 3750

**Q4.** 你上个月用 `seed=42` 切分了数据集，今天重新运行同一段代码，发现测试集里的样本变了。最可能的原因是：

- A. 随机种子每天会自动过期
- B. 换了一台机器，CPU 型号不同
- C. 上游数据集更新了（行数或行的顺序变了），而你加载时没有固定数据版本
- D. 变量名从 `test_ds` 改成了 `test_set`

**Q5.** 关于 `huggingface_hub` 的两个下载函数，正确的是：

- A. `hf_hub_download` 下载整个模型仓库，`snapshot_download` 只下载一个文件
- B. `hf_hub_download` 下载仓库中的单个文件（如 `config.json`），`snapshot_download` 下载整个仓库快照；两者都使用本地缓存
- C. 两者每次调用都会重新下载
- D. 两者都只能下载数据集，不能下载模型

**Q6.** 用 DVC 执行 `dvc add data/training_set.parquet` 后，讲义让你 `git add` 的是：

- A. `data/training_set.parquet` 本身
- B. `data/training_set.parquet.dvc` 和 `data/.gitignore`
- C. 整个 `~/.cache/huggingface/` 目录
- D. 什么都不用提交，DVC 会自动 push 到 GitHub

**Q7.** 一台 16 GB 内存、500 GB 空闲磁盘的机器，要用一个下载后约 50 GB 的 Arrow 数据集训练。下列说法最准确的是：

- A. 必须用 `streaming=True`，否则一定内存溢出
- B. 可以正常（非流式）加载：Arrow 文件被内存映射，按需读入，不需要一次性装进内存
- C. 只能先转成 CSV 才能读
- D. 必须换一台 64 GB 内存以上的机器

**Q8.** 下面哪种做法会造成**数据泄漏**（data leakage）？

- A. 用训练集计算均值和标准差，再用它们标准化验证集和测试集
- B. 先用**全部数据**计算均值和标准差做标准化，再切分 train/val/test
- C. 切分时固定随机种子
- D. 用验证集选择学习率

---

## 三、动手 / 代码题

**Q9.** 阅读 `data_utils.py` 中的 `make_splits`：

```python
def make_splits(ds, train_ratio: float = 0.8, val_ratio: float = 0.1, seed: int = 42):
    test_ratio = 1.0 - train_ratio - val_ratio
    assert test_ratio > 0, "train_ratio + val_ratio must be less than 1.0"

    test_size = val_ratio + test_ratio
    split1 = ds.train_test_split(test_size=test_size, seed=seed)
    train_ds = split1["train"]

    val_fraction = val_ratio / test_size
    split2 = split1["test"].train_test_split(test_size=(1.0 - val_fraction), seed=seed)
    val_ds = split2["train"]
    test_ds = split2["test"]
```

1. 主程序里用 500 行的 `small_ds` 调用 `make_splits(small_ds, train_ratio=0.8, val_ratio=0.1, seed=42)`，三份各有多少行？为什么第二次切分要用 `1.0 - val_fraction`，而且取 `split2["train"]` 作为验证集？
2. 如果调用 `make_splits(ds, train_ratio=0.7, val_ratio=0.3)`（500 行），作者的本意是让 `assert` 报错。实际会怎样？
3. 改写这个函数，让它对任意比例都给出精确、可预期的行数。

**Q10.** 下面两个函数各有一个边界情况会出错，找出来并修复：

```python
def load_and_inspect(dataset_name: str, config: str = None, split: str = "train"):
    kwargs = {"path": dataset_name}
    if config:
        kwargs["name"] = config
    if split:
        kwargs["split"] = split

    ds = load_dataset(**kwargs)
    print(f"Dataset: {dataset_name}")
    print(f"  Split: {split}")
    print(f"  Rows: {len(ds)}")
    print(f"  Columns: {ds.column_names}")
    print(f"  Features: {ds.features}")
    print(f"  First row: {ds[0]}")
    return ds
```

```python
def stream_dataset(dataset_name: str, config: str = None, max_rows: int = 5):
    kwargs = {"path": dataset_name, "split": "train", "streaming": True}
    if config:
        kwargs["name"] = config

    ds = load_dataset(**kwargs)
    rows = []
    for i, example in enumerate(ds):
        rows.append(example)
        if i >= max_rows - 1:
            break
```

（提示：分别考虑 `split=None` 和 `max_rows=0`。另外，两个函数的类型注解 `config: str = None` 有什么问题？）

**Q11.** `data_utils.py` 的指纹函数如下：

```python
def fingerprint(ds, num_rows: int = 100):
    sample = ds.select(range(min(num_rows, len(ds))))
    content = json.dumps([row for row in sample], default=str).encode()
    digest = hashlib.sha256(content).hexdigest()[:16]
    print(f"Dataset fingerprint (first {num_rows} rows): {digest}")
    return digest
```

1. 有人把数据集第 5000 行的标签改错了，这个指纹能发现吗？有人把整个数据集重新打乱了顺序呢？
2. 写一个改进版 `full_fingerprint(ds, batch_size=1000)`：覆盖**全部**行、内存占用不随数据量增长、对字典键顺序不敏感，并把列名也纳入哈希。

---

## 四、面试高频题

**Q12.**（基础必考）为什么要把数据分成 train / validation / test 三份？只有 train / test 两份会有什么问题？举出至少三种常见的数据泄漏。

**Q13.**（原理深挖）CSV、JSON、Parquet、Arrow 的本质区别是什么？为什么列式存储特别适合分析和 ML？Hugging Face `datasets` 为什么能"加载比内存还大的数据集"？

**Q14.**（工程实践）你的团队经常出现"上周的实验复现不出来"。从数据的角度，你会建立哪些机制保证实验可复现？`.gitignore`、Git LFS、DVC 各适合什么场景？

**Q15.**（场景设计）要在一个约 1 TB 的文本语料上做训练，但训练机只有 200 GB 本地磁盘。请设计数据加载管线，并说明如何处理打乱（shuffle）、多机多卡的数据划分和断点续训。

**Q16.**（追问型）"用固定种子随机切分"总是对的吗？哪些场景下随机切分会让验证结果虚高？应该怎么切？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Streaming gives you an `IterableDataset`. You process rows as they arrive. Memory usage stays constant regardless of dataset size." 流式模式按需拉取数据，不会先完整下载（C 错），因此只能顺序迭代（`for` 循环、`next(iter(ds))`、`ds.take(n)`），不能 `ds[0]` 随机访问。任何 Hub 上的数据集都可以尝试流式加载（D 错）。

### Q2 — 答案：B

Parquet 按**列**存储，同一列数据类型一致、取值相似，压缩效果好；读取时可以只读需要的列（列裁剪），跳过其他列，所以讲义的对比表里它是"Small / Fast"。A 错：Parquet 是二进制，不能用文本编辑器改；C 错：pandas、Spark、DuckDB、Polars 等都能读；D 错：CSV 能存数字和字符串，只是没有类型信息。

### Q3 — 答案：B

第一次：`test = ceil(0.2 × 25000) = 5000`，剩 20000；第二次：在 20000 里切 `0.125`，得到 `2500` 作验证集，剩 `17500` 作训练集。所以比例是 **70 / 10 / 20**，而不是讲义上一段写的"典型 80 / 10 / 10"——这是讲义示例与说明不一致的地方。想要 80/10/10，应该先 `test_size=0.2` 切出 20%，再把这 20% 对半分（`test_size=0.5`），这正是 `data_utils.py` 里 `make_splits` 的做法。

### Q4 — 答案：C

种子决定的是"对**同一个输入**做同样的打乱"。如果输入变了——上游数据集加了行、删了行、换了顺序——同样的种子也会给出不同的切分。A、B、D 都不影响 `train_test_split(seed=42)` 的结果。解决办法：加载时固定数据版本（例如给 `load_dataset` 指定 `revision`），或者把切分结果本身存成 Parquet 并做版本管理（DVC），再配合指纹校验。

### Q5 — 答案：B

讲义 Step 6：`hf_hub_download(repo_id=..., filename="config.json")` 只下载指定文件并返回本地路径；`snapshot_download(repo_id)` 下载整个仓库并返回目录。两者都缓存在 `~/.cache/huggingface/hub/`，下次直接命中缓存（C 错）。它们可以下载 Hub 上的模型、数据集等仓库（D 错）。

### Q6 — 答案：B

DVC 把真实数据移入自己的缓存并在原位置保留，同时生成一个很小的 `.dvc` 指针文件（记录哈希等元数据），并在 `data/.gitignore` 里加上这个大文件，防止它被 git 跟踪。所以 git 里只提交 `.dvc` 文件和 `.gitignore`（A 错）；真实数据通过 `dvc push` 推到 S3/GCS 等远程存储，而不是 GitHub（D 错）。

### Q7 — 答案：B

`datasets` 把数据存成磁盘上的 Arrow 文件并做**内存映射**（memory-map）：操作系统按需把用到的页读入内存，不需要一次性装下 50 GB，所以内存小于数据集也能处理。限制条件是**磁盘**要放得下——磁盘不够时才必须用流式（A 说"一定内存溢出"不对）。讲义 Key Terms 里 Arrow 的"zero-copy reads"说的就是这一点。

### Q8 — 答案：B

用全部数据算统计量，测试集的信息（均值、方差）就"泄漏"进了训练流程，测试分数会偏乐观。正确做法是 A：只用训练集拟合预处理（标准化、词表、特征选择等），再应用到 val/test。D 是验证集的本职工作，不是泄漏；但如果反复用**测试集**调参，测试集就退化成了第二个验证集。

### Q9 — 参考答案

1. **400 / 50 / 50**（80.0% / 10.0% / 10.0%）。`test_size = 0.1 + 0.1 = 0.2`，第一次切出 100 行"val+test 池"。`val_fraction = 0.1 / 0.2 = 0.5`，即池子里一半做验证集。第二次调用 `train_test_split(test_size=1.0 - val_fraction)` 时，`train_test_split` 的输出只有 `"train"` 和 `"test"` 两个键，作者把"`train` 那一份"当验证集、把"`test` 那一份"当测试集，所以要把**测试集的占比** `1 - val_fraction` 传给 `test_size`。这个写法正确但容易绕晕，读代码时要盯住"哪一份对应哪个名字"。
2. **`assert` 不会触发**，因为浮点误差：`1.0 - 0.7 - 0.3 = 5.551115123125783e-17 > 0`。接着 `test_size ≈ 0.30000000000000004`，`val_fraction ≈ 0.9999999999999998`，第二次切分的 `test_size ≈ 2.2e-16`。`datasets` 对浮点 `test_size` 的测试行数做**向上取整**，`ceil(2.2e-16 × 151) = 1`，于是你得到一个**只有 1 行**的测试集，程序不报错、悄悄往下跑。（同理，70/15/15 的比例在 500 行上会因为 `0.30000000000000004 × 500` 向上取整，得到 349 / 75 / 76，而不是 350 / 75 / 75。以上数字按 `datasets` 的取整规则推算。）
3. 改用**整数行数**，避开浮点比例：

```python
def make_splits(ds, train_ratio: float = 0.8, val_ratio: float = 0.1, seed: int = 42):
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1):
        raise ValueError("ratios must be in (0, 1)")
    if train_ratio + val_ratio >= 1.0 - 1e-9:          # 带容差的检查
        raise ValueError("train_ratio + val_ratio must be less than 1.0")

    n = len(ds)
    n_train = round(n * train_ratio)
    n_val = round(n * val_ratio)
    n_test = n - n_train - n_val                       # 余数全给测试集，保证总数不丢
    if min(n_train, n_val, n_test) <= 0:
        raise ValueError(f"split too small: {n_train}/{n_val}/{n_test}")

    # train_test_split 的 test_size 传整数时表示"行数"
    split1 = ds.train_test_split(test_size=n_val + n_test, seed=seed)
    split2 = split1["test"].train_test_split(test_size=n_test, seed=seed)
    return {"train": split1["train"], "val": split2["train"], "test": split2["test"]}
```

   要点：①比例检查加容差，或干脆用 `raise` 而不是 `assert`（`python -O` 会跳过所有 `assert`）；②整数 `test_size` 让行数完全确定：500 行、70/15/15 → 350 / 75 / 75；③余数统一归到一份，避免三份加起来不等于总数。

### Q10 — 参考答案

**`load_and_inspect` 在 `split=None`（或空字符串）时出错。** 此时 `kwargs` 里没有 `split`，`load_dataset` 返回的是 `DatasetDict`（键为 `"train"`、`"test"` 等），不是 `Dataset`：`len(ds)` 打印的是 split 个数而不是行数，`ds.column_names` 变成按 split 分组的字典，最晚到 `ds[0]` 一定崩溃（`DatasetDict` 按 split 名索引，`0` 不是合法的键）。修复：要么禁止 `split=None`，要么分情况处理：

```python
from datasets import DatasetDict

def load_and_inspect(dataset_name: str, config: str | None = None, split: str | None = "train"):
    kwargs = {"path": dataset_name}
    if config:
        kwargs["name"] = config
    if split:
        kwargs["split"] = split
    ds = load_dataset(**kwargs)

    if isinstance(ds, DatasetDict):                  # 没指定 split：逐个 split 打摘要
        for name, part in ds.items():
            print(f"{dataset_name}[{name}]: {len(part)} rows, columns={part.column_names}")
        return ds

    print(f"Dataset: {dataset_name}")
    print(f"  Rows: {len(ds)}")
    print(f"  Columns: {ds.column_names}")
    print(f"  First row: {ds[0] if len(ds) else None}")
    return ds
```

**`stream_dataset` 在 `max_rows=0` 时仍返回 1 行。** 循环先 `append` 再判断，`i=0` 时 `0 >= -1` 成立才 `break`，此时已经放进去 1 行。用 `itertools.islice` 最简洁，也不会有差一错误：

```python
from itertools import islice

def stream_dataset(dataset_name: str, config: str | None = None, max_rows: int = 5,
                   split: str = "train"):
    if max_rows <= 0:
        return []
    kwargs = {"path": dataset_name, "split": split, "streaming": True}
    if config:
        kwargs["name"] = config
    ds = load_dataset(**kwargs)
    rows = list(islice(ds, max_rows))
    print(f"Streamed {len(rows)} rows from {dataset_name}")
    return rows
```

**类型注解问题**：`config: str = None` 声明类型是 `str`，默认值却是 `None`，类型自相矛盾。应写成 `config: str | None = None`（Python 3.10+）或 `Optional[str] = None`。上一节开启 Pylance 类型检查后，这类写法通常会被标出来。

### Q11 — 参考答案

1. **第 5000 行改错：发现不了**——指纹只看前 100 行。**整体打乱顺序：能发现**——前 100 行的内容变了，哈希就变了；但这也说明它对"内容相同、顺序不同"过于敏感。所以它是一个"便宜的快速抽检"，不是完整的数据版本标识。
2. 改进版：

```python
import hashlib
import json

def full_fingerprint(ds, batch_size: int = 1000) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(sorted(ds.column_names)).encode())      # 列名纳入哈希
    for start in range(0, len(ds), batch_size):                  # 分批，内存恒定
        batch = ds.select(range(start, min(start + batch_size, len(ds))))
        for row in batch:
            line = json.dumps(row, sort_keys=True, default=str, ensure_ascii=False)
            h.update(line.encode("utf-8"))
            h.update(b"\n")                                      # 行分隔，防止拼接歧义
    digest = h.hexdigest()[:16]
    print(f"Dataset fingerprint (all {len(ds)} rows): {digest}")
    return digest
```

   要点：①`hashlib` 的 `update` 支持增量喂数据，不需要先把全部内容拼成一个大字符串；②`sort_keys=True` 让字典键顺序不影响结果；③每行后加分隔符，避免 `["ab","c"]` 和 `["a","bc"]` 这类拼接后相同的歧义；④如果希望"顺序无关"，可以对每行单独求哈希、排序后再汇总。另外，`datasets` 内部也会为每个 `Dataset` 维护一个基于"变换历史"的指纹，用于缓存命中，但它反映的是处理步骤而不是内容本身。

### Q12 — 参考回答要点

- **三份的分工**：train 用来拟合参数；validation 用来选超参数、做 early stopping、比较模型；test 只在最后用一次，估计模型在新数据上的真实表现。
- **只有两份的问题**：如果用 test 来调参，等于把 test 的信息"学进"了模型选择过程，最终报告的分数偏乐观——test 不再是"没见过的数据"。数据少时可以用 k 折交叉验证代替单独的验证集，但测试集仍要留出。
- **常见泄漏**：
  1. 用全量数据拟合预处理（标准化、TF-IDF 词表、特征选择），再切分；
  2. 重复或近重复样本同时出现在 train 和 test（网页语料、数据增强后的图片非常常见）；
  3. 时间序列用随机切分，模型"看到了未来"；
  4. 同一用户 / 患者 / 文档的多条样本被分到不同集合；
  5. 特征里包含了标签的"代理"（比如由标签派生出来的字段）；
  6. LLM 场景：评测集出现在预训练语料里（benchmark 污染）。
- **加分点**：提到 `train_test_split` 的分层切分（按标签比例切，`stratify_by_column`），以及"先切分、再做一切数据相关的拟合"这一原则。

### Q13 — 参考回答要点

- **CSV**：纯文本、按行存储、无类型信息，体积大、解析慢，但通用、人可读。**JSON / JSONL**：文本、支持嵌套结构，适合 API 和半结构化数据，同样体积大、解析慢。**Parquet**：列式、二进制、自带 schema、按列压缩和编码，适合**落盘存储**。**Arrow**：列式的**内存格式**标准，强调零拷贝和跨语言共享（pandas / Polars / DuckDB / Spark 都能直接读写），适合**内存中处理**。
- **列式为什么适合分析和 ML**：①训练常常只用几列（如 `text`、`label`），列式可以只读这几列；②同列数据类型一致、取值相近，压缩率高；③按列连续存放，便于向量化计算（SIMD）。
- **为什么能加载比内存大的数据集**：`datasets` 把数据写成磁盘上的 Arrow 文件并**内存映射**，读取时由操作系统按页加载、按需换出；`map`、`filter` 等变换的结果也写成新的 Arrow 缓存文件，而不是常驻内存。真正的限制是磁盘空间，磁盘也放不下时再用 streaming。
- **常见误区**：把 Parquet 说成"压缩版 CSV"（讲义"What people say"一栏正是这个说法），忽略了列式存储和 schema 才是本质。

### Q14 — 参考回答要点

- **复现需要锁定的东西**：代码版本（git commit）、数据版本、预处理与切分（种子、比例、切分结果）、环境（依赖锁文件 / Docker 镜像）、超参数配置。
- **数据侧机制**：
  - 数据集版本化：DVC 跟踪数据文件并推到 S3/GCS；或者对 HF 数据集固定 `revision`；
  - 把**切分结果本身**存下来（各 split 存成 Parquet），而不是每次在线重新切；
  - 每次实验记录数据指纹（内容哈希）、行数、种子，写进实验追踪系统；
  - 原始数据只读，所有清洗步骤脚本化，形成可重跑的管线。
- **三种工具的选择**（讲义表格）：`.gitignore` 适合个人项目、可以重新下载的数据；Git LFS 适合团队通过 git 共享模型权重等少量大文件；DVC 适合可复现实验、大数据集、团队协作，配合远程存储。
- **加分点**：提到数据卡 / 数据集说明（来源、许可、处理流程），以及"同一个 git commit 必须能找回当时那份数据"这一可审计要求。

### Q15 — 参考回答要点

- **整体思路**：200 GB 放不下 1 TB，所以要么**流式读取**，要么**分片按需下载 + 用完即删**。
- **存储格式**：语料以多个 Parquet 分片存放在对象存储（S3/GCS）或 HF Hub，单个分片几百 MB 到 1 GB 左右，便于并行和断点定位。
- **流式加载**：`load_dataset(..., streaming=True)` 得到 `IterableDataset`，边读边分词（`map` 在流上是惰性的）、边打包成固定长度的序列。
- **打乱**：流式无法全局打乱，用两级打乱近似——①先打乱分片顺序；②再用固定大小的缓冲区打乱（`IterableDataset.shuffle(seed=..., buffer_size=...)`），缓冲区越大越接近全局随机，但内存占用越大。
- **多机多卡**：按 rank 划分分片（每个进程读不同的分片），避免多个进程读到重复数据；分片数应是总进程数的倍数，以免负载不均。
- **断点续训**：checkpoint 不仅保存模型和优化器，还要保存数据位置（当前 epoch、读到哪个分片、分片内的偏移、随机数状态），否则恢复后会重复或跳过数据。
- **另一种方案**：如果会多次训练，可以离线一次性分词并写成 token 分片（如二进制数组），训练时直接按块读取，省掉重复分词的 CPU 开销。
- **加分点**：监控数据吞吐，确保 GPU 不在等数据（数据加载线程数、预取）。

### Q16 — 参考回答要点

- **不总是对的。** 随机切分隐含假设"样本独立同分布"，以下场景会违背：
  1. **时间序列 / 有时间顺序的数据**（销量、日志、用户行为）：随机切分让模型用未来预测过去。应该**按时间切**：早期做 train，较晚做 val，最晚做 test。
  2. **分组数据**（同一用户、同一患者、同一文档切出的多个 chunk）：同组样本高度相关，分到不同集合会让模型"记住个体"。应该**按组切分**（group split）。
  3. **近重复样本**（网页爬取、数据增强）：先去重或按"相似簇"切分，否则测试集等于训练集的影子。
  4. **类别极不平衡**：随机切分可能让少数类在 val/test 里几乎没有样本，应**分层切分**（stratified split）。
  5. **分布外泛化**：如果实际部署面对的是新领域、新用户，测试集也应该按领域/用户切出来，才能反映真实效果。
- **原则**：测试集的构造方式要模拟"模型上线后会遇到的数据"。
- **常见误区**：以为固定种子就等于"切分合理"——种子只保证可复现，不保证没有泄漏。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：能 `pip install datasets huggingface_hub` 并运行脚本。
- [阶段 00 · 02 Git & 协作](../../02-git-and-collaboration/docs/zh.md)：`.gitignore`、提交流程，是理解 Git LFS / DVC 的基础。
- [阶段 00 · 06 Python 环境](../../06-python-environments/docs/zh.md)：依赖锁定，与数据版本一起构成"可复现"的两半。

### 本节被哪些后续内容用到
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：train/val/test、交叉验证的系统讲解。
- [阶段 02 · 13 ML 管道](../../../02-ml-fundamentals/13-ml-pipelines/docs/zh.md)：先切分再拟合预处理，防止泄漏（对应 Q8）。
- [阶段 02 · 15 时间序列](../../../02-ml-fundamentals/15-time-series/docs/zh.md)：按时间切分（对应 Q16）。
- [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：分层切分与重采样。
- [阶段 10 · 03 数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：大规模语料的清洗、分词、打包（对应 Q15）。
- [阶段 19 · 42 大型语料下载器](../../../19-capstone-projects/42-large-corpus-downloader/docs/zh.md) 与 [阶段 19 · 43 HDF5 分词语料](../../../19-capstone-projects/43-hdf5-tokenized-corpus/docs/zh.md)：把本节的下载、缓存、格式转换做成工程组件。
- [阶段 18 · 27 数据溯源与训练治理](../../../18-ethics-safety-alignment/27-data-provenance-training-governance/docs/zh.md)：数据版本、来源与合规。

### 延伸关键词
`Apache Arrow / memory-map` · `Parquet row group / 列裁剪` · `IterableDataset.shuffle(buffer_size)` · `stratified / group / temporal split` · `dataset revision` · `DVC remote` · `Git LFS 指针文件` · `HF_HOME / HF_DATASETS_CACHE` · `benchmark contamination`
