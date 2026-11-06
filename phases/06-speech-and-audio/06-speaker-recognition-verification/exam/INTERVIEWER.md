# 面试官手册：SpeakerID（06/06）

候选人计时期间不要看。候选人手里只有 README、`speakerid/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- Part 3、4、5 都用 `embed.cosine` 打分，Part 5 里现成的 `agglomerate` 也用它。候选人还没修好 `cosine` 就离开 Part 1 的话，先告诉他 `cosine` 要先归一化。不然后面的失败会指错地方：Part 3 的 S-norm 算成 8.3，Part 4 前六段都归给 spk0，Part 5 报的是 agglomerate then cut recovers the three speakers，而他写的 `cut` 并没有错。Part 2 不受影响。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | `eer` 收到空列表怎么办？ | "Both lists are non-empty in practice. A ValueError is fine. The tests don't cover it." |
| 1 | 两个阈值的 \|FAR − FRR\| 一样大，取哪个？ | "The lower threshold, as the docstring says. The tests don't hit that case." |
| 1 | trial 列表的标签只有 0 和 1 吗？ | "Yes. 1 is a target trial, 0 a non-target trial." |
| 2 | 存原始 embedding 还是归一化以后的？ | "The raw one, exactly as given. Normalize when you build the template." |
| 2 | 模板可以缓存吗？ | "Sure, as long as removing an enrollment gives back exactly the earlier template." |
| 2 | 不同说话人的 embedding 维度能不一样吗？ | "No. One registry, one dimension. Raise a ValueError." |
| 3 | 标准差用总体还是样本？ | "Population, as in the docstring." |
| 3 | cohort 里会有被验证的那个说话人吗？ | "No. The cohort is a fixed set of imposters, none of them enrolled." |
| 3 | 达不到目标 FAR 怎么办？ | "Raise a ValueError. Don't invent a threshold above every score." |
| 4 | 同一个人的两段之间隔了很久，还算一个 turn 吗？ | "Yes. Consecutive segments of one speaker are one turn, gap or not." |
| 4 | 段会乱序或者重叠吗？ | "No. They arrive in time order and don't overlap." |
| 4 | 已经写出去的 turn 以后能改吗？ | "No. Once a line is out, it stays out." |
| 5 | 合并相似度正好等于阈值，算不算？ | "It joins. At least the threshold." |
| 5 | 叶子一定是 int 吗？ | "Yes, segment indices." |

## 每关：要看什么、提示、追问

### Part 1 修 EER 代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 3 个护栏：

1. `eer` 是讲义 Step 3 的原版。初始 `best = (1.0, 1.0, 0.0)` 的差距是 0，`abs(fa - fr) < 0` 永远不成立，所以对任何输入都返回 `(1.0, 0.0)`。测验 Q10 讲的就是它。
2. `parse_trials` 用 `bool(label)` 解析标签，可 `bool("0")` 也是 True：所有 trial 都成了 target，non-target 列表是空的。错误不在 `parse_trials` 报出来，而是在 `eer` 里报 ZeroDivisionError。
3. `cosine` 是讲义代码里的点积，默认输入已经归一化。测试的 embedding 没有归一化，模长主导了分数：EER 从 0.25 变成 0.5，阈值变成 25。这是讲义 Pitfalls 的最后一条。
4. `eer` 对每个候选阈值重新数一遍全部分数，是 O(T·(S+D))，12,000 个分数要 1.1 到 1.8 秒（Python 3.10 到 3.14）。
5. 护栏：提速改成排序扫描时，等于阈值的分数要一起处理，两类的都算。一个一个挪过阈值，2:2 的并列会算成 0.25（阈值 0.6）；两个有序列表归并时只挪当前这一类的并列分数，会算成 0.625（阈值 0.6）。正确是 0.375（阈值 0.7）。
6. 护栏：分数全部相同时 EER 是 0.5。修第 1 个缺陷时把初值换成 FAR=1、FRR=0 的角点、却还用严格小于比较，在这里会返回阈值 0.0，而 0.0 根本不是观测到的分数。
7. 护栏：修 `cosine` 时直接除以两个模长，会在静音片段（零向量）上除零。讲义 Step 2 的写法是零向量返回 0。

看什么：是不是先读 traceback，再想 `eer` 收到的是什么；是不是 `print(repr(...))` 看 `score_trials` 的输出；有没有看到 ZeroDivisionError 就去给 `eer` 加判空，而不去找空列表从哪来。

提示：
- H1："Before you change eer, print what score_trials hands it."
- H2："How many non-target trials does parse_trials find?"
- H3：直接指出 `bool(label)`，问 `bool("0")` 的值。

追问：
- "EER is 25% here. Would you ship the EER threshold?"（不会。EER 只用来比较模型，上线阈值按目标 FAR 在目标领域的开发集上定，这就是 Part 3）
- "Why average FAR and FRR instead of finding where they cross?"（阈值是离散的，两者很少正好相等；严格做法是在 ROC/DET 曲线上插值求交点）
- "The two score sets are separable. Where does your threshold land?"（落在 target 分数的最小值，贴着正类边缘；取空隙中点或按目标 FAR 定阈值更稳，见测验 Q11）

### Part 2 注册库（目标 12 分钟）

坑：
- 模板是“每条注册先归一化，再平均，再归一化”。直接平均原始 embedding，模长大的那条会主导模板，这是讲义说的 one noisy enrollment poisons the anchor。测试里 carol 三条注册的模长分别是 2、5、0.5。平均完忘了再归一化，模板就不是单位向量（测验 Q12）。
- 用 (模板 + 新注册) / 2 滚动更新是均值的均值，越晚加入的注册权重越大。
- 精度陷阱：给每个说话人缓存 (和, 数量)，注册时加、删除时减。浮点数加上再减掉回不到原值，删掉 noisy 注册以后模板差几个 ulp，测试要求一位都不差。滚动的 Welford 均值倒着撤销也一样。要从存着的原始 embedding 重新算，或者用 Fraction 精确累加。直接缓存模板也可以，但删除时也要让缓存失效：只在注册时清缓存，删掉 noisy 以后拿到的还是带 noisy 的模板。
- 原始 embedding 要原样存，原样读回成 list。存归一化以后的向量、存成 float32、读回成 tuple，往返断言都会挂。JSON 能精确往返 Python 的 float。
- Python 的 sqlite3 不 commit 就关闭连接，数据就丢了；建表要写 `IF NOT EXISTS`。模板要能从库里重建：只在内存里留一份单位向量的话，重开以后 `template` 报 KeyError。
- 零向量报 ValueError，`if not embedding` 只查得出空列表。维度要和库里已有的任何一条比，不能只和同一个说话人比：dave 的第一条注册是 3 维，也要报 ValueError。删除未知 id 报 KeyError。
- `speakers()` 按名字排序，测试里 bob 先注册。一个说话人的注册删光以后，`speakers()` 里不能再有他，`template` 报 KeyError。另外维护一张说话人表或一个名字集合时，最容易漏掉这一步。

追问：
- "Two replicas hold the same enrollments in a different order. Bit-identical templates?"（`math.fsum` 是正确舍入，与顺序无关；Python 3.12 起 `sum()` 也做补偿求和；手写的 `+=` 循环与顺序有关）
- "Why keep the raw embedding instead of the normalized one?"（换打分后端、换模板配方、做审计时都要原始数据）
- "A customer asks you to delete their voiceprint."（删掉全部注册和所有缓存、备份里的模板；删除后不留残差，正是这里要求精确恢复的原因）
- "How would you spot the noisy enrollment?"（每条注册对其余注册组成的模板打分，分数偏低的就是；注册时按信噪比、时长做质量门控）

### Part 3 S-norm 和阈值（目标 12 分钟）

坑：
- S-norm 两边各做一次 z 归一化再取平均。只做模板一侧（z-norm）得 2.6，只做测试一侧（t-norm）得 2.0，测试要 2.3。
- 标准差是总体标准差。用 `statistics.stdev` 得 1.99。
- AS-norm 的 top_k 是两侧各自选最相似的 k 个 cohort。按模板一侧选出一组再给两侧共用，得 3.83，测试要 2.5；取成最低的 k 个，得 5.17。
- `threshold_at_far` 的候选阈值包括 target 分数。只在 non-target 分数里找会返回 0.9 而不是 0.5，拒掉更多真用户；只在 target 分数里找，第二个例子会返回 0.8 而不是 0.7。
- 分数等于阈值算接受，所以等于阈值的 non-target 算一次误接受（第二个例子）。FAR 等于目标值就算达标，写成严格小于，第一个例子会返回 0.95。
- FAR/FRR 弄反：FAR 算到 target 分数上，第一个例子就会报“达不到目标 FAR”。FAR 的分母只是 non-target 的个数，除以全部开发集 trial，第二个例子会返回 0.6。
- `calibrate` 必须和 `verify` 用同一种 S-norm 分数。用原始余弦校准时，lookalike（原始余弦 0.71）比 alice 本人（0.6）还高，0% FAR 根本达不到，`threshold_at_far` 报 ValueError。lookalike 和整个 cohort 都很像，S-norm 以后它只有 1.63，alice 是 2.3。这就是做分数归一化的理由。
- `verify` 用 `>=`。还没 calibrate 就调用 verify 要报 RuntimeError，不能拿 None 去比，也不能给阈值一个默认值 0.0。

追问：
- "Why does the lookalike score so high on raw cosine?"（hubness：有些 embedding 和谁都像；信道变化会把所有分数整体抬高。S-norm 衡量的是这个分数在两侧冒认者分布里的位置）
- "How big should the cohort be, and where does it come from?"（几百到几千条目标领域的冒认者 embedding；AS-norm 的 top_k 常取 100 到 300；每次打分都要对 cohort 算余弦，模板一侧可以缓存）
- "Target FAR is 0.1% and the dev set has 500 non-target trials. Problem?"（FAR 的分辨率只有 1/500 = 0.2%，至少要几千条 non-target trial，还要给出置信区间）
- "The bank wants FAR at most 0.1%. What happens to FRR?"（在 DET 曲线上读出来，通常远高于 EER；可以提 minDCF，见测验 Q15、Q16）

### Part 4 在线 diarization（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：每个 turn 一行 RTTM SPEAKER 记录，10 个字段，第 4 个字段是起点，第 5 个字段是时长（不是终点），三位小数，换行结尾。缺了换行，所有记录挤在一行里，40 个字段。
- 质心是各段归一化以后的 embedding 的平均。测试里的说话人在慢慢转：0°、30°、60°，质心跟着走到 30°。常见的几种错法，各自挂在一段上：
  - 只跟每个说话人的第一段比：第 3 段（60°）离第一段 60°，超过 50° 的阈值，被错拆成新的说话人。
  - 直接累加原始 embedding：第一段的模长是 10，质心被钉在 0° 附近，第 3 段同样被拆出去。
  - 只跟最近一段比：第 4 段（85°）离上一段只有 25°，两个人被串成一个。
  - 用“旧质心加新段再归一化”滚动更新：越晚的段权重越大，质心偏到 37.5°，第 4 段离它 47.5°，也被串进 spk0。
  - 遇到第一个过阈值的说话人就加入：第 5 段（75°）离 spk0 的质心 45°，也过了阈值，可离 spk1 只有 10°，要选最相似的 spk1。
  - 质心存成平均值，却拿点积当相似度：前三段的平均模长只有 0.91，第 6 段（−17°）离 spk0 的质心 47°，余弦 0.68 过了阈值，点积只有 0.62，被错拆成新的说话人。这就是讲义 Pitfalls 的最后一条。
- 只合并相邻的同一说话人：spk0、spk1、spk0 是三个 turn。同一个人的两段之间有空隙，也还是一个 turn（见澄清问题）。
- turn 一结束就要写出去：第 4 段一到，第一个 turn 就该出来，测试会数拉取了几段，多等一段也不行。流结束时还开着的 turn 要写出去；空流什么都不写，不能写出 None 或空字符串。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。
- 相似度正好等于阈值时加入，docstring 写的是 at least。测试里没有正好相等的段，写成 `>` 也能过，看到了提一句就行。

追问：
- "A turn is already written, and later segments show it was the wrong speaker. Now what?"（在线系统拿准确率换延迟；可以留一个前瞻窗口再输出，或者事后发更正版本）
- "Two people talk at the same time?"（一段一个标签的假设失效，要用能输出多标签的分割模型，pyannote 3.x 就是这样，见测验 Q17）
- "How do you measure this?"（拿参考 RTTM 算 DER = 漏检 + 虚警 + 说话人混淆，通常带 collar）
- "An eight-hour meeting with forty speakers. What grows?"（质心数量是说话人数乘以维度；可以合并收敛到一起的说话人，给不活跃的说话人设上限）

### Part 5 聚类树切分（目标 12 分钟）

坑：
- 合并树写成嵌套 tuple：叶子是段的下标，合并是 (left, right, similarity)。
- 一棵子树成为一个簇，要求里面每一次合并都不低于阈值，不能只看最上面那次。centroid linkage 会倒挂：先以 0.50 合并 0 和 1，再以 0.55 把 2 并进来。只看最上面一次，阈值 0.52 会把三段并成一簇，可 0 和 1 本身只有 0.50。pyannote 的聚类就用 centroid linkage；scipy 的 `fcluster` 用子树内最大距离来判断，原因相同。
- 正好等于阈值的合并算并进。树上记的是相似度，不是距离，照 scipy 的距离写法把比较方向弄反，第一个断言就挂。
- 同一个下标出现两次是坏树，报 ValueError，和阈值无关。阈值 0.95 时两份 1 落在不同的簇里，只在每个簇内部查重复会漏掉，要对整棵树查。
- 链状的树有 3000 层，递归会超过 Python 默认 1000 层的限制，报 RecursionError，要改成显式栈。调大 recursionlimit 也能过测试，追问时要能说出它的问题。
- 输出：簇内升序，簇之间按第一个下标排序，不按大小，也不按最后一个下标。阈值 0.92 时 [2, 5] 排在 [1] 和 [3] 之间。

追问：
- "Centroid linkage can invert. Why use it at all?"（合并时只要把和加起来，更新便宜；average linkage 不会倒挂，但要维护全部两两距离）
- "How would you choose the threshold?"（在开发集上按 DER 调；或者先估计说话人数，比如谱聚类的特征值间隔）
- "Why not sys.setrecursionlimit(10000)?"（树再深一些就会耗尽 C 栈，整个进程崩掉，而且上限随解释器版本不同；显式栈没有这个问题）
- "agglomerate here is O(n³). A two-hour meeting?"（几千段；用优先队列或最近邻链，或者先在窗口内聚类再合并）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出阈值选择、可复现性、cohort 规模、延迟、递归深度 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
