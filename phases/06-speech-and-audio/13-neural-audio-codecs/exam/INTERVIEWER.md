# 面试官手册：RVQCodec（06/13）

候选人计时期间不要看。候选人手里只有 README、`rvqcodec/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 可以不用展开式，直接算距离吗？ | "Sure. Same codes, same tie rule." |
| 1 | 两个码字一样近时选哪个？ | "The lower index. It's in the docstring." |
| 2 | 头里为什么没有帧数？ | "The header keeps the clip length in samples. The frame count follows from it and the hop." |
| 2 | 码超出码本范围怎么办？ | "ValueError. Never mask or clip a code." |
| 2 | 字节序和比特顺序？ | "Big-endian, as HEADER says. Within the payload, most significant bit first." |
| 2 | 包里的码本数和 codec 不一样怎么办？ | "Fewer is fine: decode with the stages you got. More is a ValueError." |
| 3 | 码本要不要像课里的代码那样排序？ | "No. A code is an index into the codebook. Keep the seeding order." |
| 3 | 不同的向量比码字还少怎么办？ | "The spare codewords copy the first one and never get used. That's fine." |
| 3 | Lloyd 跑几轮？ | "Until no codeword moves, or until iterations runs out." |
| 4 | 流结束时剩下不够一帧的样本怎么办？ | "Zero-pad them into a last frame, like Codec.encode does, and say how many samples are real." |
| 4 | 流正好在帧边界结束呢？ | "Then there is no partial frame. Don't send an empty one." |
| 4 | 帧在路上会丢码吗？ | "The network may drop trailing acoustic codes. Codebook 0 always comes through; a frame without it is an error." |
| 5 | tree_search 要找到真正最近的叶子吗？ | "No. Greedy descent. full_search is the exact one." |
| 5 | 比较次数怎么数？ | "Every distance you compute, at every level." |

## 每关：要看什么、提示、追问

### Part 1 修量化器（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏：

1. `assign` 用 `for row in zip(*scores)` 取 argmin，把 T×K 的分数表转置了：argmin 取在帧这一维上，返回的是“离每个码字最近的帧”。错误不在 `assign` 报出来，而是在 `rvq_encode` 拿这些下标查码本时报 IndexError。
2. `rvq_encode` 每一级都把原始帧交给 `assign`，算好的残差没有用上。第 0 级的码是对的，后面几级全错。
3. `rvq_decode` 用 `[[0.0] * dim] * n` 建输出，n 行其实是同一个列表，所有帧的码字都加到了一起。课的代码讲解在“常见坑”里专门提过 `[[]] * size`。
4. `assign` 在列表推导式里对每一对（帧，码字）都重新调用 `energies(codebook)`，是 O(T·K²·D)。1024 个码字、8 帧要 1.6 到 2 秒，测试的限值是 0.1 秒。
5. 护栏：常见的提速写法是把 ||c||² 也当成常数去掉，只按点积排序。码字长短不一时，这会选中方向相近里最长的那个码字，加一级反而更差。测试用带零码字、长短不一的码本检查“多一级不会更差”。

看什么：是不是先读 traceback，再追到产生越界下标的函数；是不是先 `print` 出 `assign` 的返回值看形状；每改一处就重跑。

提示：
- H1："Which function produced the index that is out of range?"
- H2："What shape is scores, and what does zip(*scores) iterate over?"
- H3：直接指出 `zip(*scores)`。

追问：
- "DAC L2-normalizes its codebooks. What does that change about nearest-codeword search?"（码字一样长时，最小距离等价于最大点积，这时只按点积排序才成立）
- "When is the expanded form ||c||² − 2f·c less accurate than computing the distance directly?"（f 和 c 都很大而差很小时，两项相减会抵消有效位）
- "Why can the first stage alone still be decoded?"（解码是逐级相加，少用几级就是低码率版本；EnCodec 一个模型支持 1.5 到 24 kbps，训练时随机丢掉后几级）

### Part 2 码流（目标 12 分钟）

坑：
- 每个码的比特数是 ceil(log2 K)，可以写成 `(K - 1).bit_length()`。`K.bit_length()` 在 K = 1024 时得到 11；`int(log2(K))` 在 K = 1000 时只有 9 位，999 放不下。
- 码率也按这个位数算：K = 1000 时每个码占 10 位，测试里 50 Hz × 3 × 10 = 1500。用 log2(1000) ≈ 9.97 算出来的不是这个码流的码率。
- 帧率是 `sample_rate / hop`。Mimi 是 24000 / 1920 = 12.5 Hz，用整除会变成 12，码率从 1100 变成 1056。
- 顺序：逐帧写，每帧里先写 codebook 0（语义码），每个码从高位写起。测试用两个字节的小例子把这一点定死了：按码本一行一行写，或者低位在前，字节都不对。
- 头里存的是样本数，不是帧数。帧数要向上取整：1000 个样本、hop 320 是 4 帧，最后一帧补零。末尾补齐的零比特不能读成多余的帧（K = 4 的那个包）。
- 越界的码、行长度不对（一帧的 clip 给了两个码）、截断的数据、末尾多出来的字节、错误的 magic 都要报 ValueError。数据比头还短时 struct 报的是 struct.error，测试不认。
- `decompress` 要拒绝另一种帧率下编出来的包，也要拒绝码本数比本 codec 多的包：`rvq_decode` 里的 `zip` 会悄悄丢掉多出来的几级。课里说帧率不一致是“fails silently”：码本一样时解码不会报错，只会放出错的声音。
- 测试只拿采样率不同的包试了帧率这一项，所以只比帧率、或者只比采样率也能过。docstring 要求采样率、hop、码本大小逐项比较，用第一个追问问出来。

追问：
- "Two codecs both run at 75 Hz: 24 kHz with hop 320, and 48 kHz with hop 640. Can one play the other's packets?"（不能：一帧代表的样本数和码字长度都不一样，所以要比采样率和 hop，只比帧率不够）
- "EnCodec runs 1.5 to 24 kbps with one model. What changes in the packet?"（n_q 变；同一套码本只取前几级）
- "How would you go below log2(K) bits per code?"（熵编码；EnCodec 用一个小语言模型加算术编码）
- "Frame by frame, or codebook by codebook: when would you pick the other layout?"（逐帧适合流式，收到一帧就能解；按码本存，截掉后几级就是更低的码率）

### Part 3 学码本（目标 13 分钟）

坑：
- k-means++：第一个码字均匀抽，后面每个按 D(x)² 加权抽。课里的代码在数据范围里均匀撒点；D(x) 不平方，或者从数据里随机挑 k 个（Forgy），种子都对不上。
- D(x) 是到目前所有码字里最近那个的距离，每加一个码字都要和旧值取 min，不能只看最新的码字。
- 所有向量都已经落在码字上时，D(x)² 全是 0：`random.choices` 会报 “Total of weights must be greater than zero”。docstring 规定剩下的码字复制第一个。
- 空簇：没分到向量的码字留在原位。直接除以个数会 ZeroDivisionError。
- 种子码字要复制一份（`list(v)`）。直接引用输入向量，Lloyd 再原地改码字，改掉的是调用方的数据，第二轮起分配就乱了。
- Lloyd 要一直迭代到码字不再移动，或者用完 iterations。测试里直线上的 5 个点要移动三轮才停：只跑一轮得到 [7.5, 0] 和 [1, 0]，最后是 [11, 0] 和 [3, 0]。`return` 缩进到循环里面，就只跑了一轮。
- 码字保持种子顺序，不要像课里的一维代码那样排序：码就是码本下标。
- 每一级在前面几级留下的残差上训练。每级都在原始帧上训练的话，加一级误差反而变大。
- 误差在另一段信号（seed=1）上评估，不是训练用的那段。课的代码讲解提醒过：在同一段信号上学码本再评估，是在测过拟合。
- 把空簇的码字重置成随机向量（生产里处理死码字的办法）、多出来的码字复制最后一个而不是第一个、Lloyd 里平局分给编号大的码字、每一级都用同一个种子，测试都能过，但和 docstring 不一致。遇到时问候选人为什么这样写，再接到死码字的追问。

追问：
- "Real codecs get dead codes all the time. What do they do about it?"（EMA 更新码本，把很久没被用到的码字重置成当前 batch 里的随机向量，EnCodec 就这样做；DAC 在低维投影里做 L2 归一化来提高码本利用率）
- "Each stage cuts the error by 4 to 5 times here. What sets that number?"（高码率近似下，D 维里 K 个码字让误差按 K^(2/D) 下降，2 维、8 个码字是 8 倍。实测只有 4 到 5 倍，在训练信号上也是这样：每一级的残差来自上一级形状各不相同的区域，叠在一起之后一个码本没法同时贴合；K = 8 也离高码率很远）
- "One 64-entry codebook or two stages of 8: both are 6 bits. Which reconstructs better, and why do codecs still pick RVQ?"（同比特下单个大码本通常更准；但 RVQ 存储和搜索的是 n_q·K 个码字，不是 K^n_q 个。课的测验 Q11 有实测）

### Part 4 流式编解码（目标 13 分钟）

坑：
- 帧对齐：缓冲区要跨块拼接，空块和只有 1 个样本的块都会出现。每块单独分帧，结果就和整段编码不一样。
- 结尾：不足一帧的样本补零（和 `Codec.encode` 一样），并带上真实长度 length；解码只输出 length 个样本。和 06/03 打标签的窗口不同，codec 不能把结尾丢掉，也不能把补的零放出来。流正好在帧边界结束时没有不完整的帧，不能再发一个全零的空帧（测试用前 20 个样本检查）。
- 延迟：每一帧的最后一个样本一到，就要编码、解码、输出。测试记录每一块音频输出时已经拉取了多少个样本，必须正好是 4、8、12、16、20、23。先检查缓冲区再追加新块，会晚一块；解码器为了判断哪一帧是最后一帧而扣住一帧，会晚一帧。
- 丢码：网络可能丢掉一帧末尾的声学码，只剩 codebook 0，解码就用剩下的几级。按 `range(len(codebooks))` 逐级取码会 IndexError；用 0 号码把缺的几级补齐也不对，0 号码不一定是零向量（测试里第 1 级的零码字排在最后）。一个码都没有的帧是错误，报 ValueError。

追问：
- "What is the algorithmic latency of this codec at Mimi's 12.5 Hz?"（一帧，80 ms；真实编码器的卷积还有前瞻）
- "Real decoders use transposed convolutions. What state does a streaming decoder have to carry between frames?"（相邻帧的卷积核有重叠，上一帧的尾巴要留下来和下一帧叠加）
- "The network drops whole frames. What would you do?"（按帧序号发现缺帧；丢包补偿或前向纠错）

### Part 5 树结构码本（目标 12 分钟）

坑：
- 码就是叶子的编号：深度优先，子节点按列表顺序从左到右。按层（广度优先）编号，或者把路径当成二进制数，在这棵不平衡的树上都错。
- `"children": []` 也是叶子。只看有没有 `children` 这个键，会把它当成内部节点，叶子就少了一个。
- 贪心下降：每一层只比较当前节点的子节点，选最近的往下走。搜全部叶子会得到更近的答案，但测试要的是贪心的结果和比较次数：查询 [0.5, 0] 时贪心是 (3, 3)，全搜是 (2, 7)。
- 比较次数数的是算了多少次距离：每经过一个内部节点，加上它的子节点个数。每层只算一次是错的。
- 平局选靠前的子节点；全搜的平局选编号小的叶子（查询 [-5, 0] 时 [-5, 1] 和 [-5, -1] 一样近）。向量长度和质心不同要报 ValueError，`zip` 会悄悄截断；只在根节点检查一次长度也可以。

追问：
- "RVQ and tree-structured VQ both make a large codebook searchable. What does each cost?"（树：要存全部 K 个叶子和内部节点，搜索约 b·log_b K 次距离，结果不一定最近；RVQ：存 n_q·K 个码字，搜索 n_q·K 次，等效码本有 K^n_q 个）
- "How would you build this tree from data?"（从根开始递归做 2-means 分裂，每个节点的质心是它下面所有向量的均值）
- "Your search adds up the leaf counts of the earlier siblings on every call. What does that cost on a big tree, and how do you avoid it?"（每次都要遍历左边的子树；预先给每个节点记下它第一个叶子的编号）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出码率、帧率一致、死码字、延迟、丢包 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
