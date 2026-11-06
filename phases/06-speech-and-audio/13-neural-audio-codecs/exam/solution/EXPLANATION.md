# 参考答案讲解：RVQCodec（06/13）

计时结束后再看。参考实现在同目录的 `rvqcodec/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修量化器

**现象**：解锁后的第一个错误是 `rvq_encode` 里查码本时的 IndexError，而那一行本身没有 bug。

**顺着往上找**：越界的下标是 `assign` 返回的。测试有 7 帧、码本有 4 个码字，`assign` 却返回了 4 个数，而且有 4 和 5。原因是 `scores` 是 T×K 的表（每帧一行），`for row in zip(*scores)` 先把它转置成 K×T，于是 argmin 取在帧这一维上，得到的是“离每个码字最近的帧”。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `assign`：对每一行（每一帧）取 argmin，`for row in scores`。
2. `rvq_encode`：把 `residual` 交给 `assign`。原来每一级都在量化原始帧，算好的残差没有用上，第 1、2 级的码全错。这正是 RVQ 名字里的 residual。
3. `rvq_decode`：`[[0.0] * dim] * n` 的 n 行是同一个列表，所有帧的码字都加到同一行上，解出来每一帧都一样。改成 `[[0.0] * dim for _ in codes[0]]`。
4. `assign`：`energies(codebook)` 在推导式里对每一对（帧，码字）都调用一次，每次又要算 K 个点积，总共 O(T·K²·D)。提到循环外只算一次，1024 个码字、8 帧从 1.6 秒以上降到 2 毫秒左右，测试的限值是 0.1 秒。

**护栏**：||f||² 对所有码字都一样，可以省掉；||c||² 不行。只按点积排序，等于假设所有码字一样长（DAC 的 L2 归一化码本就是这种情况）。训练出来的残差码本通常有一个接近零的码字，也有长短不一的码字，只按点积排序会选中方向相近里最长的那个，加一级误差反而变大。正确的最近码字搜索加上码本里的零码字，可以保证每加一级，每一帧的误差都不会变大，所以测试检查的是这个单调性。

## Part 2 码流

`Packet` 的三个属性都来自课里的算术：

- `frame_rate = sample_rate / hop`。EnCodec 24 kHz、hop 320 是 75 Hz；Mimi 24 kHz、hop 1920 是 12.5 Hz。用整除会把 12.5 变成 12。
- `bits_per_code = (K - 1).bit_length()`，也就是 ceil(log2 K)。K = 1024 是 10 位，K = 1000 也是 10 位，K = 2048 是 11 位。
- `bitrate = frame_rate × n_q × bits_per_code`：EnCodec 75 × 8 × 10 = 6000，正是课里 Step 1 的 6 kbps；Mimi 12.5 × 8 × 11 = 1100。课里写的 Mimi 4.4 kbps 和这个公式对不上，测验 Q9 有说明。K = 1000 时每个码也占 10 位，50 Hz、3 个码本是 1500，不是按 log2(1000) ≈ 9.97 算出的 1495。

打包用 Python 的大整数最简单：

```python
value = 0
for t in range(n_frames):          # 逐帧
    for row in packet.codes:       # 每帧里先写 codebook 0
        value = (value << bits) | row[t]
pad = -n_bits % 8
payload = (value << pad).to_bytes((n_bits + pad) // 8, "big")
```

解包反过来：`int.from_bytes` 后右移掉补齐的零比特，再从高位起每次取 `bits` 位，按 `flat[q::n_q]` 分回各个码本。

容易漏的几点：

- **逐帧、语义码在前**：这就是课里 `frame_t → [semantic_token_t, acoustic_token_0_t, …]` 的顺序。收到一帧就能解一帧，适合流式。
- **帧数向上取整**：头里存的是样本数，帧数是 ceil(n_samples / hop)。不能从负载长度反推帧数，K = 4 的那个包只有 2 位码和 6 位补齐，反推会多出 3 帧。
- **报错要报 ValueError**：越界的码不能截断成合法的码；每一行的码数必须正好是帧数；数据比头还短时要先检查，否则 `struct` 报的是 struct.error；magic 不对、负载少了或多了字节也都是 ValueError。
- **帧率不一致要拒绝**：`decompress` 检查包的采样率、hop、码本大小和本 codec 一致，码本数也不能比本 codec 多（`rvq_decode` 里的 `zip` 会悄悄丢掉多出来的几级）。课里 Pitfalls 说帧率不一致会“fails silently”：码本相同时，100 Hz 的 codec 照样能解 50 Hz 的包，只是放出来的声音是错的。只比帧率不够：24 kHz、hop 320 和 48 kHz、hop 640 都是 75 Hz，一帧代表的样本数却不同。

## Part 3 学码本

k-means++ 播种：

```python
codebook = [list(vectors[rng.randrange(len(vectors))])]
d2 = [sq_dist(v, codebook[0]) for v in vectors]
while len(codebook) < size:
    total = sum(d2)
    if total == 0:                       # 每个向量都已经落在码字上
        codebook.append(list(codebook[0]))
        continue
    r = rng.random() * total             # 第一个累计和超过 r 的向量
    ...
    d2 = [min(w, sq_dist(v, codebook[-1])) for w, v in zip(d2, vectors)]
```

用 `rng.choices(range(n), weights=d2)` 也行，它内部同样是 `random() * total` 加二分查找，结果和上面一致，但全零权重时会报错，要先单独处理。

然后是 Lloyd：用 Part 1 的 `assign` 分配，每个码字移到它那一簇的均值；没分到向量的码字留在原位；码字不再移动就提前结束，否则跑满 iterations 轮。测试里直线上的 5 个点要移动三轮：[7.5, 0] 和 [1, 0]，[9, 0] 和 [2, 0]，最后是 [11, 0] 和 [3, 0]，只跑一轮的写法会停在第一步。码字保持种子顺序，因为码就是码本下标。

`train_rvq` 就是课里 `rvq_encode` 的训练部分：第 q 级在前 q 级留下的残差上学码本（种子 seed + q），再用它量化残差，得到下一级的输入。

测试里的数字说明了课里的两条 Pitfalls：

- 在另一段信号（seed=1）上评估，每加一级误差降到 1/4 到 1/5，但码率是线性增加的，收益递减。
- 去掉 codebook 0 再解码，误差是去掉最后一级的 270 倍左右。“Assuming all codebooks equal” 是错的：前几级承载了信号的主体。Mimi 更进一步，把 codebook 0 专门训练成语义码本，丢了它就听不懂说的是什么。

## Part 4 流式编解码

编码端用一个缓冲区，凑够 hop 个样本就编一帧：

```python
async for chunk in chunks:
    buffer.extend(chunk)
    while len(buffer) >= codec.hop:
        yield encode_frame(buffer[: codec.hop], length=codec.hop)
        del buffer[: codec.hop]
if buffer:                                # 结尾：补零，带上真实长度
    yield encode_frame(buffer + [0.0] * (codec.hop - len(buffer)), length=len(buffer))
```

解码端收到一帧就解一帧，只输出 `frame.length` 个样本：`rvq_decode([[c] for c in frame.codes], codec.codebooks)`。`zip` 会自动只用这一帧还在的几级，所以丢了声学码的帧照样能解，只是更粗。缺的几级不能用 0 号码补上：0 号码不一定是零向量，测试里第 1 级的零码字就排在最后。

- 帧边界由缓冲区跨块对齐，所以无论怎么切块，码都和 `Codec.encode` 一样，解出来的样本也逐个相同。
- 结尾补零的方式必须和 `Codec.encode` 一致，否则最后一帧的码不同。长度字段让解码端不用等下一帧，也能知道最后一帧该放多少样本。流正好在帧边界结束时缓冲区是空的，不再发帧，所以 `if buffer:` 不能省。
- 延迟固定为一帧：每一帧的最后一个样本到达时，这一帧就被编码、解码、输出。测试用逐个样本到达的麦克风检查，每块音频输出时已拉取的样本数正好是 4、8、…、20、23。在 Mimi 的 12.5 Hz 下，一帧就是 80 ms。
- 没有任何码的帧报 ValueError：codebook 0 承载内容，不能丢。

## Part 5 树结构码本

叶子就是码本，编号按深度优先、从左到右：

```python
def leaf_codebook(node):
    children = node.get("children") or []
    if not children:
        return [node["centroid"]]
    return [c for child in children for c in leaf_codebook(child)]
```

`tree_search` 从根往下走：每个内部节点算一遍到所有子节点质心的距离（计数加上子节点个数），走向最近的那个，平局选靠前的；走到叶子时，它的编号等于路上每一层左边兄弟子树的叶子数之和。`full_search` 对全部叶子各算一次距离，平局选编号小的。

- 这棵不平衡的树里有 3 叉节点、深度 1 的叶子和 `"children": []` 的叶子，按层编号或者把路径当二进制数都会错。
- 贪心不保证最近：查询 [0.5, 0] 在根上离 [3, 0] 最近，于是走进那片叶子，得到 (3, 3)；全搜找到的是 [-1, 0]，得到 (2, 7)。
- 64 个叶子的平衡二叉树上，贪心每次算 12 次距离，全搜算 64 次。叶子数是 K 时，贪心的代价约为 2·log2 K，这就是树结构的好处。

和 RVQ 对比：两者都是为了“不用一个巨大的平坦码本”。树结构码本省的是搜索，仍然要存全部叶子；RVQ 用 n_q 个小码本相加，存储和搜索都是 n_q·K，等效码本却有 K^n_q 个组合。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 RVQ，做按位打包并算对码率，实现 k-means++ 和逐级残差训练，写不改变结果的流式编解码，以及处理树结构码本的递归搜索。它不涉及神经网络编码器和解码器、端到端训练（straight-through 估计、commitment loss、EMA 码本更新），也不涉及真实的 EnCodec、Mimi 模型和 PESQ、ViSQOL 这类感知指标。课里 Build It 的 Step 1 到 Step 3 和 Hard 练习（替换 Mimi 的 codebook 0）需要另外装库动手跑。
