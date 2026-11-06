# 面试官手册：Provenance（06/16）

候选人计时期间不要看。候选人手里只有 README、`provenance/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 可以把 DFT 换成 FFT 吗？ | "Sure, if you have the time. The test only needs an eight-frame clip to score quickly." |
| 1 | 静音和完全没有高频的 clip 怎么打分？ | "Both score the floor, minus 100 dB. Neither is suspicious." |
| 2 | AASIST 的分数是越高越像真人。这个日志里的分数是什么方向？ | "Every model here logs a spoof score: higher means more likely fake. Convert before you log." |
| 2 | 时间存成 UTC，还是保留原来的时区？ | "UTC. Give it back in UTC. The caller's offset doesn't matter to an auditor." |
| 2 | 同一个 clip 可以记两次吗？ | "Yes. Every decision is a new entry. The log never updates or deletes." |
| 2 | 分数是无穷大呢？ | "Your call. NaN must be rejected; the tests don't cover infinities." |
| 3 | 概率正好等于阈值的样本算不算？ | "No. Above means strictly above." |
| 3 | 先连间隙，还是先去掉短段？ | "Bridge the gaps first, then drop the short segments." |
| 4 | 冷却期里平滑还要继续算吗？ | "Yes. The cooldown only blocks new alarms. Smoothing never stops." |
| 4 | 通话结束时告警还开着怎么办？ | "Clear it at the time of the last score." |
| 4 | 时间戳相同或者倒退呢？ | "ValueError. The scores come from one call, in order." |
| 5 | ingredient 没有 manifest 字段怎么办？ | "It came without content credentials. Skip it. That alone is not a problem." |
| 5 | 哈希对不上的 ingredient 还往下走吗？ | "No. Report it and stop there. Nothing behind it can be trusted." |
| 5 | 同一个 manifest 被引用两次呢？ | "That's fine, it's a DAG. Check it once." |

## 每关：要看什么、提示、追问

### Part 1 修检测器（目标 12 分钟）

一个测试里叠了 5 个缺陷和 4 条护栏：

1. `frame_starts` 用的是课里 `range(0, len(audio) - n_fft, n_fft)` 的写法，最后一个完整帧永远不会开始（测验 Q11a）。正好一帧长的 clip 一帧都没有。错误不在 `frame_starts` 报出来，而是在上一层 `average_spectrum` 除以帧数时报 ZeroDivisionError。
2. `power_spectrum` 的 docstring 写的是 |X|²，代码照课里写成了 `math.sqrt(...)`，返回的是幅度。“能量占比”于是成了幅度占比：先 1 kHz（幅度 0.2）后 6 kHz（幅度 0.1）的 clip 应该是 1/5，即 −6.99 dB，算出来是 1/3，即 −4.77 dB。
3. `high_band` 把 `len(spec)` 当成 FFT 点数。256 点 FFT 的单边谱有 129 个 bin，bin k 的频率是 k·sr/n_fft，其中 n_fft = 2·(len − 1)。用 129 换算时 bin 间隔成了 124 Hz，“4 kHz 以上”实际从 2 kHz 左右开始，3 kHz 的音被算成全在高频（0 dB）。
4. `toy_detector_score` 为了躲开 log(0)，在高频能量和总能量上各加了 1e-12。静音时两个能量都是 0，占比成了 1e-12/1e-12 = 1，也就是 0 dB，成了最可疑的分数。docstring 要求静音是 FLOOR_DB（−100 dB）。要直接用两个能量相除，占比为 0 时返回 FLOOR_DB，其余照常截断在 FLOOR_DB。
5. `average_spectrum` 的推导式按 bin 循环，每个 bin 都把每一帧的 DFT 重算一遍，重复 129 倍。8 帧的 clip 要 1 秒左右，每帧只算一次以后大约 8 毫秒。

护栏：

- 音量不改变分数：同一个 clip 小 80 dB，分数要一样。只把静音单独处理、留着那个 1e-12 的话，常数在安静的 clip 上占了比重，会在这里挂（−6.98969 对 −6.98970）。
- 分数在下限处截断：去掉 max、改成给占比加 1e-10 再取对数，1 kHz 纯音得 −99.49 而不是 −100。
- 结尾不足一帧的样本丢掉：把差一错误“修”成 `range(0, n_samples, n_fft)`，会把 200 个样本的残帧也算进来。
- 4 kHz 正好在截止频率上，要算进高频：FFT 点数写成 `2 * len(spec)`（258）时，bin 64 落在 3969 Hz，被漏掉。

看什么：是不是先读 traceback，发现报错的位置和根因不在一处；有没有打印 `list(frame_starts(256, 256))`、`len(spec)`、静音时的 `share` 这样的中间量；能不能逐个函数对照 docstring，说出代码哪里和它不一致；每改一处就重跑。

提示：

- H1："The error is in average_spectrum. How many frames did it get for this clip?"
- H2："Read each docstring against its code. What does power_spectrum promise, and what does high_band assume about the spectrum it is given?"
- H3：直接指出出问题的那一行。

追问：

- "The lesson's toy_detector_score sums magnitudes. Why does it matter whether you sum |X| or |X|²?"（能量是功率。幅度会抬高弱的 bin，算出来的不再是能量占比，阈值的含义也跟着变了）
- "Why report the score in dB with a floor, instead of the raw share?"（检测器的分数通常在对数域，便于在本域数据上校准阈值；下限让静音也有一个有限、能写进日志的分数）
- "Where can a small epsilon go, if anywhere?"（加在占比上、比下限小得多的常数可以，比如 `log10(share + 1e-12)` 再截断；加在两个能量上不行，静音会变成 0 dB，安静的 clip 也会换分数）
- "An attacker low-passes the TTS output at 4 kHz. What does this detector say?"（分数直接掉到下限。手工特征很容易绕过，所以生产里用 AASIST 这类学出来的检测器，再加上水印和来源清单）
- "How would you score an hour of calls?"（用 FFT，比如 `numpy.fft.rfft`；每帧的谱只算一次，相邻窗口复用；按课里说的，只抽一部分来电检测）

### Part 2 审计日志（目标 12 分钟）

坑：

- sqlite3 默认开着隐式事务，不 commit 的话，关闭连接就丢数据。建表要写 `IF NOT EXISTS`，否则重开报 `table decisions already exists`。
- NaN：SQLite 会把 NaN 存成 NULL。有 NOT NULL 约束时报的是 IntegrityError，没有约束时就存进去一个 NULL。NaN 和任何阈值比较都是 False，检测器坏掉吐出 NaN 时，clip 会被当成真人放行。要在 Python 里检查，报 ValueError。
- 精确存取：阈值是 0.1 + 0.2 = 0.30000000000000004，校准扫出来的数；第一个 clip 的分数是 0.3，差一点点没到阈值，判 bonafide。存成 float32、round 到 6 位、用 `f"{x:.6f}"` 存成文本，这两个数都会变成一样，重新判定时就翻了。REAL 列和 `repr` 文本都能存准。
- 分数等于阈值算 spoof（`>=`）。
- 时间：naive 报 ValueError；存的时候转成 UTC，读回来 `isoformat()` 以 `+00:00` 结尾。Python 3.12 把 datetime 直接交给 sqlite3 时，用的是已经弃用的默认适配器，读回来是字符串。
- id 是 1、2、3，按记录顺序；`entries()` 按 entry_id 排序。
- `flips` 用同一个 `>=` 规则，拿存下来的分数和新阈值重新判一遍，只看这个模型的记录，不改日志。改到 0.3 时，分数正好 0.3 的那一条从 bonafide 翻成 spoof。

追问：

- "Why store the threshold with every decision instead of looking up the model's current one?"（阈值会随校准变化，每条判定都要能用当时的阈值解释。另建一张带生效时间的校准表也可以，每条记录各存一份最简单）
- "Why UTC here, when the consent registry in 06/08 keeps the signer's offset?"（审计记录要跨地区比较、排序；同意书的签字日期是签字人所在时区的法律事实）
- "The skill file says seven-year retention, EU data stays in the EU. What changes?"（只存 clip 的哈希，不存音频；按地区分库；保留期满的删除任务；有法律保全时暂停删除）
- "Two detector workers write to the same log?"（SQLite 同一时间只允许一个写者，可以开 WAL；量大时换服务端数据库，或者先写消息队列）
- 候选人把时间存成 float 的 Unix 时间戳时问："Is that exact?"（2026 年前后秒数的 float 间隔大约 0.24 微秒，微秒能原样还原，测试也能过；但精度随日期变化，ISO 文本在任何日期都精确，审计员也能直接读）

### Part 3 水印定位（目标 10 分钟）

坑：

- 严格大于阈值：概率正好是 0.5 表示检测器拿不准（logit 为 0），不算有水印。用 `>=` 会把 [100, 500) 连成一段。
- 一直持续到结尾的那一段要收尾，否则 [750, 1000) 会丢。区间左闭右开。
- 先连起短间隙，再去掉短段。先去短段的话，90 个样本的 [260, 350) 先被删掉，后面就连不上了，结果成了 [100, 250)。
- 边界：间隙正好等于 max_gap_s 要连（`<=`），长度正好等于 min_s 的段要留（`>=`）。
- IoU 按样本数算，并集是 |P| + |T| − |P∩T|。拿“最早开始到最晚结束”的跨度当并集，100/300 会算成 100/350。两个列表都为空时是 1.0，不能除零。
- 交集是两两相交的长度之和，一段可能和对面好几段相交。按位置 zip 配对，或者每段只取最大的那个重叠，[0, 300) 对 [0, 100)、[200, 300) 都会算成 0.25，正确是 2/3。
- 时长用传进来的 `sample_rate` 换算。按每秒 1000 个样本算的话，前两条 1000 Hz 的断言照样能过，到 16 kHz 的端到端才挂：200 个样本的掉点超过 20，连不上。
- 最后一段是端到端检查：拼接 clip 里只有中间三分之一是生成的，按整段平均或者按“超过 0.5 的样本比例”判断，结论都是没有水印，定位要找到 8000 到 16000。真人语音里 40 个样本的误报要去掉，生成语音里 200 个样本的掉点要连上（不超过 320）。同一个 clip 还经过 Part 1 的检测器打分，写进 Part 2 的审计日志。

追问：

- "AudioSeal's detect_watermark gives one number per clip. Why localize at all?"（拼接攻击：整段的比例只有 0.33，看起来像没有水印，里面却有一整句是生成的）
- "The generated part was pitch-shifted. What do you see, and what do you do?"（那一段检测不到水印了，AudioMarkBench 里变调后所有水印的比特准确率都低于 0.6；对那一段退回到伪造检测器，课里说两样都要就是这个原因）
- "How would you choose min_s and max_gap_s?"（在干净音频上统计误报的长度，再在带标注的拼接数据上按定位 IoU 调）
- 候选人用 `int(min_s * sample_rate)` 时问："Why round and not int?"（`0.29 * 100` 是 28.999999999999996，int 得 28；这套测试里的乘积恰好都是整数，int 也能过）

### Part 4 实时告警（目标 14 分钟）

坑：

- 输出格式由测试的解析代码决定：Server-Sent Events，每个事件一行 `event:`、一行 `data:`（JSON），后面跟一个空行。
- 平滑值从第一个分数开始，不从 0 开始。从 0 开始的话，一开始就是伪造的通话要晚一个分数才告警，测试里只有两个分数的那条流干脆不告警。
- 按流时间平滑：8.0 秒之前隔了 2 秒没有分数，平滑系数是 1 − 0.5⁴ = 0.9375，8.0 秒就告警。每个分数固定用 0.5 的话，要到 8.5 秒才告警。
- 迟滞：2.5 秒时 s = 0.5625，在 0.5 和 0.75 之间，告警保持。只用一个阈值的话 2.5 秒就解除了。
- 两个边界：s 正好到 0.75 就告警（1.5 秒那一刻），正好等于 0.5 不算跌破（三个分数那条流的 1.0 秒）。写成 `>` 或 `<=` 都会挂。
- 告警里的 `score` 和 `peak` 都是平滑值 s，不是这一刻的原始分数；peak 要随告警期间的 s 更新。
- 冷却期从解除时刻算，到 3.0 + 2.0 = 5.0 秒正好可以再告警（`>=`）。从告警开始时刻算的话，4.0 秒就又告警了。
- 冷却期内平滑照常更新：5.0 秒告警时 s 是 0.837890625。冷却期内跳过分数的话，报出来的是 0.962890625。
- 通话结束时还开着的告警，在最后一个分数的时刻解除。已经解除的告警不能在结尾再发一次 clear。
- 分块随意，包括空块：状态要跨块保留。每块重新开始平滑的话，一个一个送进来时结果就不一样了；把空块当成通话结束，[2, 0, 3] 那种分块就只剩开头两个分数。
- 告警一判定就要发出去，测试会数被拉取了多少块。时间重复或倒退都要报 ValueError。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要能看出这里需要 async generator。

追问：

- "Why smooth in stream time instead of per window?"（窗口会因为静音、VAD 或丢包被跳过；按半衰期平滑，平滑的含义不随窗口间隔变化）
- "Why a cooldown at all?"（同一通电话反复告警会把分析员的队列刷屏；一通电话一个事件更好处理）
- "What goes into the audit log when an alarm fires?"（模型版本、当时的阈值、分数、时间、通话 id，也就是 Part 2 的一条记录）
- "One worker watches 500 calls at once?"（每通电话一份状态，各自一个 asyncio 任务；上游跟不上时要有背压，不能无限排队）

### Part 5 manifest 链（目标 12 分钟）

坑：

- 只有 active manifest 绑定的是手里这份音频。每个 ingredient 绑定的是它自己的音频，拿手里的音频去校验 ingredient 的 data hash，会报出一串误报。
- AI 参与要沿两种关系找：TTS 那一句是 edit 和 mix 的 componentOf，只沿 parentOf 走就找不到。
- active manifest 自己的 action 也算：直接查 TTS 那一句，结果就是 AI 生成。没走到的 manifest 不算：单独查 take 时，store 里虽然有 TTS 那一句，结果也是 False，扫整个 store 的写法会在这里挂。
- mix 里的 music bed 没有 `manifest` 字段，是没带内容凭证的素材：跳过，不算问题。直接取 `ingredient["manifest"]` 会报 KeyError，报成 missing 也不对。
- 菱形不是环：TTS 那一句被两个 manifest 引用。“见过就算环”的写法会在这里报 ValueError。判断环要看当前路径。
- 环要在校验哈希之前检查，docstring 写了 whatever its hash。带内容哈希的引用不可能真的绕回来，先校验哈希的写法只会报一个 mismatch，不会报 ValueError。
- 链接坏了就不往下走：换掉的 take 不能出现在 history 里。
- 找不到的 manifest 报 `ingredient.manifest.missing`，不能抛 KeyError。
- 有两个 parentOf 的 manifest 报 `manifest.multipleParents`，history 停在它这里，不能随便跟第一个。
- 去掉 TTS 的 manifest 之后，`ai_generated` 是 False。这就是课里 Pitfalls 说的 strip-and-rehost：C2PA 自己挡不住，要靠水印（Part 3）和检测器（Part 1）。
- problems 要排序、去重。mix 先列 TTS 那一句、再列 edit，深度优先时 mix 的问题先找到，不排序就是 mix 排在 edit 前面。两个 parent 那条里，edit 既是 two 的 parent，又是 mix 的 parent；不记查过哪些、用列表收集的话，edit 的问题会出现两次。

追问：

- "Real C2PA signs every claim with a certificate. What does a signature add to these hashes?"（哈希只说明被引用以后没改过；签名说明是谁做的声明，还要对照信任列表。没有签名，攻击者可以把整条链重新生成一遍）
- "Someone re-encodes the file and drops the manifest. What is left?"（水印和检测器。C2PA 的 soft binding 用水印或指纹去 manifest 仓库里找回丢掉的 manifest）
- "A chain five thousand edits deep?"（递归会超过 Python 的递归上限，改成显式栈）
- 候选人不记查过的 manifest、靠 set 去重时问："Your walk checks the edit twice. Does it matter?"（结果一样，但每多一层菱形，重复的工作就翻一倍；记一个 done 集合，每个 manifest 只查一次）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出校准、保留期、告警疲劳、元数据被剥离以后怎么办 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
