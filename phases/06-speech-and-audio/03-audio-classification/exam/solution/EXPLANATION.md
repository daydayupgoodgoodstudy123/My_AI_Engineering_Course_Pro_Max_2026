# 参考答案讲解：ClipTag（06/03）

计时结束后再看。参考实现在同目录的 `cliptag/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修特征代码

**现象**：解锁后的第一个错误是 `apply_filterbank` 里的 IndexError，而那里本身没有 bug。

**顺着往上找**：`apply_filterbank` 要取第 0 到 64 个频率 bin，但传进来的频谱只有 31 个 bin。频谱短，是因为传给 `dft_mag` 的帧只有 60 个样本。帧短，是因为 `frame_signal` 的 `1 + max(0, ...)` 在信号比一帧还短时仍然切出一帧，而 `stft_mag` 里的 `zip` 又把多出来的窗函数系数静默截掉了。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `frame_signal`：信号短于 `frame_len` 时返回 `[]`。
2. `summarize`：没有帧时报 `ValueError`，不要让 `frames[0]` 抛 IndexError。
3. 方差改成除以 `t`，与 docstring 和课里的公式一致。原来的 `t - 1` 还会让单帧 clip 除零。
4. 均值只算一次。原代码在方差的循环里每次都重新求一遍均值，是 O(T²·n)，3000 帧大约要 2 秒。

**护栏**：常见的提速写法是一遍算出 E[x²]−E[x]²。特征带着 1e8 这种大偏移时，两个 1e16 量级的数相减，有效位几乎全部抵消，1.25 会被算成 2 左右。两遍算法（先求均值，再求偏差平方）或 Welford 算法都没有这个问题。

## Part 2 特征库

参考实现只有一张表：`seq` 自增主键负责插入顺序，`clip_id` 是唯一的 UUID 字符串，特征用 JSON 文本存。Python 的 float 经过 `json.dumps` 和 `json.loads` 能原样还原，包括 `0.1 + 0.2` 和次正规数。

容易漏的四点：

- **commit**：sqlite3 在执行 INSERT 时会自动开启事务，不 commit 的话，`close()` 后数据就没了。参考实现用 `with self._db:` 自动提交。
- **重开**：建表要写 `IF NOT EXISTS`，否则第二次打开同一个文件就报错。
- **校验在 Python 里做**：非法 split、特征长度不同、采样率不同，都要抛 `ValueError`。CHECK 约束抛的是 IntegrityError，测试不认。
- **返回类型**：特征要读回成 list，tuple 和 list 比较不相等。

## Part 3 分类和评估

`classify` 只取 train，按 (−相似度, 插入顺序) 排序后取前 k 个。投票时记下每个标签的票数和相似度之和，最后按 (−票数, −相似度和, 标签名) 取最小的那个。课里的 `Counter.most_common` 遇到平票时会选先出现的标签，测试里的 2:2 平票专门让它选错。

`evaluate` 对 eval 里出现的每一类都算召回和 F1。某一类一次都没被预测出来时，它的精确率是 0/0，按 0 处理，F1 也是 0，但这一类照样计入 macro 平均。这组数据的 accuracy 是 0.8，看起来不错，可 siren 的召回是 0，macro F1 只有 0.44。课里说重度不平衡时看每类召回和 macro F1，原因就在这里。

最后的端到端检查把 Part 1–3 串起来：150 Hz 和 600 Hz 的带噪正弦波，经过特征提取、写入特征库，再用 k-NN 分类，必须分对。

## Part 4 流式打标

用一个缓冲区，外加一个记录缓冲区起点在整条流中样本下标的整数：

```python
async for chunk in chunks:
    buffer.extend(chunk)
    while len(buffer) >= window:
        yield json.dumps({...}) + "\n"
        del buffer[:hop]
        start += hop
```

- 跨块的窗口由缓冲区自然拼好，所以无论怎么切块，结果都一样。
- 窗口一凑齐就 `yield`，所以第一个事件出来时只拉取了 5 块。
- 时间戳用整数下标除以采样率，不用浮点秒数累加，不会漂移。
- 结尾不足一个窗口的样本留在缓冲区里，直接丢掉。
- 格式由测试的 `"".join(...)` 加 `splitlines()` 再逐行 `json.loads` 决定：每个事件后面恰好一个 `\n`。

## Part 5 标签树汇总

先写一个 `_children(node)`，把三种写法统一成 `(名字, 子节点)` 对：dict、只含名字的 list、list 里混着的 dict。然后递归 `visit(name, children, path)`：

- 当前类的分数取它自己的分数和所有子类返回值中的最大值，有分数才写进结果。
- 同一个名字出现在多个位置时，结果里保留最大的那个，祖先各自从自己那条路径拿到分数。
- `path` 记录从根到当前节点经过的类名，遇到重名就报错，这样能查出“自己包含自己”。
- 遍历完后，`scores` 里还有没访问到的名字，就是未知标签，报 ValueError。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试、建表、实现 k-NN 和不平衡评估、写流式生成器，以及处理嵌套结构。它不涉及 CNN、AST、BEATs 的训练，也不涉及真实音频解码和部署。课里 Step 4 和 Step 5 的内容需要另外动手跑。
