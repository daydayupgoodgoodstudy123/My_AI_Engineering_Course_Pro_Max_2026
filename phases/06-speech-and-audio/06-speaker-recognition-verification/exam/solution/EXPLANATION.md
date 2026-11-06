# 参考答案讲解：SpeakerID（06/06）

计时结束后再看。参考实现在同目录的 `speakerid/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 EER 代码

**现象**：解锁后的第一个失败是 `eer` 对测验 Q9 的例子返回 `(1.0, 0.0)`。

**依次修四处**：

1. 初始差距。`eer` 是讲义 Step 3 的原版，`best = (1.0, 1.0, 0.0)` 的差距是 0，任何真实的差距都不会小于 0，所以 `best` 从来不更新。改成单独记一个 `best_gap = float("inf")`，这是 `code/main.py` 的修法。
2. 修好以后，trial 列表那一段报 ZeroDivisionError，位置在 `eer` 的 `/ len(nontarget)`。`eer` 本身没错，是它收到的 non-target 列表是空的。往上找：`score_trials` 按 `trial.target` 分组，而 `parse_trials` 用的是 `bool(label)`。非空字符串都为真，`bool("0")` 也是 True，于是每个 trial 都成了 target。改成 `label == "1"`。这一关想练的是：报错的位置往往不是出 bug 的位置，给 `eer` 加一个判空只会把错误藏起来。
3. 再跑，trial 列表的 EER 是 0.5，阈值是 25。分数比 1 还大，说明 `cosine` 算的不是余弦：它是讲义代码里的点积，只有输入都是单位向量时才等于余弦。先把两边归一化再点积。用 `l2_normalize` 还顺带处理了静音片段的零向量，结果是 0.0。
4. 最后是计时。原代码对每个候选阈值都把全部分数数一遍，12,000 个分数要 1.1 到 1.8 秒。把两组分数各排一次序，一次扫描就能得到每个阈值下的计数。

参考实现的扫描：

```python
tg, nt = sorted(target), sorted(nontarget)
i = j = 0  # 阈值 t 处：tg[:i] 被拒，nt[j:] 被接受
while i < s or j < d:
    t = tg[i] if j == d or (i < s and tg[i] <= nt[j]) else nt[j]   # 下一个最小的分数
    gap = abs((d - j) * s - i * d)                                  # |FAR - FRR| 乘以 s * d
    ...记下 gap 最小的那个阈值...
    while i < s and tg[i] == t:   # 等于 t 的分数一起挪到阈值下面
        i += 1
    while j < d and nt[j] == t:
        j += 1
```

对每个阈值用 `bisect_left` 二分计数也可以，同样是 O(n log n)。参考实现比较的是整数 `|accepted·S − rejected·D|`，而不是两个浮点比例的差，差距相等时不会因为舍入选错阈值。

**三个护栏**：

- 并列分数：逐个把分数挪过阈值的扫描，会停在 0.6 这一组的中间，把一部分 0.6 算成被拒，得到一个其实不存在的阈值，结果是 0.25 和 0.6，正确是 0.375 和 0.7。归并两个有序列表时只挪当前这一类的并列分数，也会停在中间，得到 0.625 和 0.6。分数相同的一组，不管属于哪一类，要么都被接受，要么都被拒。
- 分数全相同：只有一个候选阈值，FAR = 1、FRR = 0，EER 是 0.5。把初值设成这个角点、再用严格小于比较，`best` 永远不更新，返回的阈值是初值里的 0.0。
- 零向量：`dot / (|a|·|b|)` 遇到静音片段会除零。讲义 Step 2 的写法是零向量返回 0.0。

## Part 2 注册库

参考实现只有一张表 `enrollments`：`seq` 自增主键记录注册顺序，`enrollment_id` 是 UUID，原始 embedding 存成 JSON 文本。模板不缓存，每次从存着的原始 embedding 重新算：

```python
units = [l2_normalize(e.embedding) for e in self.enrollments(speaker)]
return l2_normalize([math.fsum(column) / len(units) for column in zip(*units)])
```

容易漏的几点：

- **先归一化再平均**：这样每条注册对模板的影响一样大，一条模长大的注册不会主导模板。最后再归一化一次，模板是单位向量（测验 Q12）。用 (模板 + 新注册) / 2 滚动更新是均值的均值，越晚加入的注册权重越大。
- **精确恢复**：给每个说话人缓存 (和, 数量)、删除时减回去，看起来是 O(1)，可浮点加法不能精确撤销，`(s + x) - x` 一般不等于 `s`。测试里删掉 noisy 注册以后，16 维模板会有好几维差几个 ulp。重新计算只取决于当前这些注册，所以一位都不差。要缓存也可以，但注册集合变化时要整体重算，或者用 `fractions.Fraction` 精确累加。
- **原样往返**：存的是调用方给的原始向量，JSON 对 Python 的 float 能精确往返。存归一化以后的向量会丢掉模长，存成 float32 会丢掉精度，读回成 tuple 和 list 比较不相等，往返断言都会挂。
- **commit**：sqlite3 在 INSERT 和 DELETE 之前自动开启事务，不 commit 的话，`close()` 后数据就没了。参考实现用 `with self._db:` 提交。
- **校验在 Python 里做**：零向量没有方向，维度和库里已有的不一致，都报 ValueError。维度要和整个库比，不只和同一个说话人比，所以 dave 的第一条 3 维注册也要拒。删除时看 `rowcount`，是 0 就报 KeyError。
- **说话人列表**：`speakers()` 直接 `SELECT DISTINCT speaker ... ORDER BY speaker`，按名字排序，注册删光的人自然就不在了。另外维护说话人表或名字集合的话，删掉最后一条注册时要一起删。

`math.fsum` 是正确舍入的求和，结果只取决于注册集合本身，与插入顺序无关。测试没有考顺序，因为 Python 3.12 起内置的 `sum()` 对浮点数做补偿求和，顺序几乎不影响结果，在 3.10 和 3.11 上就会影响。

## Part 3 S-norm 和阈值

一次声明 (speaker, embedding) 的原始分数，是模板和测试 embedding 的余弦。S-norm 用 cohort 对它做两次 z 归一化，再取平均：

```python
def _normalize(self, raw, side):
    scores = [cosine(side, member) for member in self.cohort]
    if self.top_k is not None:
        scores = sorted(scores, reverse=True)[: self.top_k]   # AS-norm：这一侧自己的 top_k
    return (raw - statistics.fmean(scores)) / statistics.pstdev(scores)

score = 0.5 * (self._normalize(raw, template) + self._normalize(raw, embedding))
```

测试的 cohort 是按余弦值构造的。模板一侧是 0.36、0.12、0.04、−0.20，均值 0.08，标准差 0.2，z = 2.6；测试一侧是 0.05、−0.25、0.45、0.15，均值 0.1，标准差 0.25，z = 2.0；S-norm 是 2.3。AS-norm 每侧只留最高的两个：模板一侧 0.36、0.12，z = 3.0；测试一侧 0.45、0.15，z = 2.0；结果是 2.5。两侧留下的 cohort 成员不同，adaptive 指的就是这个。

`threshold_at_far` 从低到高试每个开发集分数，返回第一个 FAR 不超过目标的。FAR 只看 non-target：分数大于等于阈值的 non-target 占多少。候选里要包括 target 分数，因为满足 FAR 的最低阈值常常就是某个 target 分数，阈值越低，被拒的真用户越少。

`calibrate` 用 `self.score` 给开发集打分，阈值和 `verify` 比较的分数在同一个尺度上。这组开发集说明了为什么要做 S-norm：

| 片段 | 原始余弦 | S-norm |
|---|---|---|
| alice 本人 | 0.60 | 2.30 |
| lookalike（冒认者） | 0.71 | 1.63 |
| stranger（冒认者） | 0.00 | −0.69 |

按原始余弦，冒认者 lookalike 比 alice 本人分数还高，想做到 0% FAR 只能把所有人都拒掉，`threshold_at_far` 报 ValueError。lookalike 和 cohort 里的每个人都很像，S-norm 把它压到 alice 下面。阈值定在 2.3，alice 正好通过，因为分数等于阈值算接受。

## Part 4 在线 diarization

```python
async for segment in segments:
    unit = l2_normalize(segment.embedding)
    # 找质心和它最相似的说话人；相似度低于阈值就新建 spkN
    # 把 unit 加进这个说话人的单位向量之和（方向就是均值的方向）
    # 同一个说话人：延长当前 turn；换了人：先 yield 上一个 turn 的 RTTM 行
# 流结束时，把还开着的 turn 写出去
```

- 质心存成单位向量之和。余弦只看方向，不用除以个数。每段先归一化，模长 10 的第一段才不会把质心钉住。
- 相似度要用 `embed.cosine`，不能直接点积。单位向量的和或平均都不是单位向量：前三段的平均模长只有 0.91，第 6 段（−17°）离 spk0 的质心 47°，余弦 0.68 过了阈值，拿平均值点积只有 0.62，会被错拆成新的说话人。
- 要跟质心比，不跟第一段或最近一段比。测试里的说话人在慢慢转：0°、30°、60°，质心跟着走到 30°。第 4 段的 85° 离质心 55°，是新的说话人；跟第一段比，60° 那段就已经被拆出去；跟最近一段比，85° 那段离 60° 只有 25°，两个人被串成一个。用“旧质心加新段再归一化”滚动更新也不行，越晚的段权重越大，质心偏到 37.5°，85° 那段离它只有 47.5°，同样被串进来。
- 要选最相似的说话人，不是第一个过阈值的。第 5 段（75°）离 spk0 的质心 45°、离 spk1 的质心 10°，两个都过了阈值，应该归 spk1。
- 换人的时候才知道上一个 turn 结束了，所以第一行在拉取第 4 段之后出来。流结束时最后一个 turn 还开着，要单独写出；空流没有 turn，什么都不写。
- RTTM 的第 5 个字段是时长，参考实现写的是 `f"{start:.3f} {end - start:.3f}"`。测试用 `"".join(...)`、`splitlines()`、`split()` 解析，所以每行结尾正好一个换行，正好 10 个字段。

## Part 5 聚类树切分

参考实现用显式栈做后序遍历。每棵子树处理完留下一个结果：整棵是一个簇时是 `(True, 它的段)`，被切开时是 `(False, 它的簇)`。合并节点 `(left, right, sim)` 只有在两边都是整簇、并且 `sim >= threshold` 时才合成一个簇，否则把两边的簇并列起来。这和“子树里每一次合并都不低于阈值”是同一个条件，也是 scipy 的 `fcluster` 按子树内最大距离判断的做法。

- **倒挂**：centroid linkage 合并之后，新簇的质心可能离第三个点更近。测试里 0 和 1 以 0.50 合并，2 再以 0.55 并进来。只看节点自己的相似度，阈值 0.52 会把三段并成一簇。三个说话人的那棵树里也有一处小倒挂：(3, 7) 在 0.986 合并，5 在 0.988 并进来。
- **深度**：3000 层的链用递归会报 RecursionError，显式栈只受内存限制。
- **重复下标**：用一个贯穿整棵树的 `seen` 集合检查，出现两次就报 ValueError，和阈值无关。阈值 0.95 时两份 1 落在不同的簇里，只在簇内查重复是查不出来的。
- **排序**：簇内升序，簇之间按第一个下标排序。几个互不相交的升序列表，直接 `sorted` 就是这个顺序。不按簇的大小排：阈值 0.92 时结果是 [[0], [1], [2, 5], [3], [4]]。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 EER 和余弦打分，建一个删除后能精确恢复的注册库，实现 S-norm 和按目标 FAR 定阈值，写在线聚类的流式生成器，以及在很深的合并树上做非递归的切分。它不涉及 ECAPA-TDNN、WavLM 这类 embedding 模型和 AAM-softmax 的训练，也不涉及 PLDA、真实音频的 VAD 和分段、DER 的计算和反欺骗。讲义 Step 4 和 Step 5 的 SpeechBrain、pyannote 需要另外动手跑。
