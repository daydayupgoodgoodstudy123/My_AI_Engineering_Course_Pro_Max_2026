# 参考答案讲解：Duplex（06/15）

计时结束后再看。参考实现在同目录的 `duplex/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修全双工循环

**现象**：解锁后的第一个错误是 `split_frames` 里的 `TypeError: 'float' object cannot be interpreted as an integer`，而那个函数本身没写错。

**顺着往上找**：`range(count)` 拿到的是 4.0，因为 `len(pcm) // SAMPLES_PER_FRAME` 里的除数是 1920.0。这个常量写成了 `SAMPLE_RATE / FRAME_RATE`，Python 3 的 `/` 总是得到 float；12.5 本身是 float，所以换成 `//` 也一样。改成 `SAMPLE_RATE * FRAME_MS // 1000`，和课里 `main.py` 的 `int(SAMPLE_RATE * FRAME_MS / 1000)` 是同一个数。

**依次修四处**：

1. 帧长常量，见上。
2. `DuplexSession.hear` 遍历的是 `encode` 的返回值，而 `encode` 按 docstring 返回 codebook-major 的 `codes[k][t]`，和 Mimi 的 `(n_q, T)` 张量一样。遍历它得到的是 8 个码本，每个 4 帧，于是 `step` 报 `a user frame carries 8 codes, got 4`。报错在 `step`，根因在上一层的 `hear`，改成 `frames_of(encode(pcm))`。
3. `step` 原来先预测，最后才把用户帧、文本、音频一起 append。这样第 t 步的上下文只有第 0..t-1 帧，模型永远晚一帧听到用户。重放循环还把用户第 s 帧和模型第 s 步自己的输出配成一对，而 `ToyMoshi.advance` 要的是第 s - 1 步的输出（第 0 步用 `TEXT_START` 和 `AUDIO_START`）。这正是课里 Step 3 的下标：预测第 t 帧时，输入是 `user_mimi[0..t]`、`moshi_mimi[0..t-1]`、`moshi_text[0..t-1]`。测试用一个记录调用的 Probe 模型把这一点直接量出来。只在上下文前面补一帧起始 token，计数也能对上，但第 t 步折叠进去的还是用户第 t - 1 帧，模型照样晚一帧。Probe 记录了每一步最后折叠进去的用户帧和模型音频，所以这种修法过不了。
4. `_context()` 每一步都从头重放整段会话，是 O(T²)。1500 帧大约 1.6 到 2 秒，越到后面每一步越慢，迟早超过每帧 80 ms 的预算。参考实现把上下文存在 `self._state` 里，每步只折叠一帧，相当于 KV cache：

```python
said = self.text[-1] if self.text else TEXT_START
spoken = self.audio[-1] if self.audio else [AUDIO_START] * CODEBOOKS
self._state = self.model.advance(self._state, list(user), said, spoken)
```

**护栏**：两种常见的错误修法都会被抓住。一是把 `encode` 改成逐帧输出，或者把帧率写成 12 让 `//` 得到整数，第一行断言就挂，因为 `encode` 的布局和每帧 1920 个样本都是别的代码依赖的约定。二是为了提速只重放最近几帧：计时能过，但 Probe 跑满 100 步后，上下文里已经没有第 0 帧了。

## Part 2 会话记录

参考实现用一张表，主键是 `(session, frame)`，用户侧和模型侧各占一列，码用 JSON 文本存。两侧由不同的任务分开写入，所以每次写入都是“有这一行就只更新自己这一侧，没有就插入”：

```sql
INSERT INTO frames (session, frame, user) VALUES (?, ?, ?)
ON CONFLICT (session, frame) DO UPDATE SET user = excluded.user
```

容易漏的几点：

- **合并而不是替换**：`INSERT OR REPLACE` 会删掉整行再插入，先写进去的那一侧变成 NULL。测试里第 1 帧的模型侧比用户侧先到，正好撞上。
- **commit 和重开**：用 `with self._db:` 自动提交；建表写 `IF NOT EXISTS`。
- **只返回完整的帧**：读的时候加 `user IS NOT NULL AND model IS NOT NULL`，按 `frame` 排序。只写了一侧的帧，`frame()` 报 KeyError，补齐之后才出现。两个方向都算：测试在第 1 帧只有模型侧时就查了一次 `frames()`。判断一侧写没写要看 NULL，不能看真假值，PAD 是 0。
- **半帧马上落库**：不要把一侧留在内存里等另一侧，服务重启之后那一半就没了。测试在重开之后才补上第 2 帧的模型侧。
- **校验在 Python 里做**：每侧恰好 8 个 0..1023 的整数，用户侧和模型侧都不能写第二次，否则报 ValueError。主键冲突抛的是 IntegrityError，而 upsert 会静默覆盖，两者都不对。
- **原样读回**：码 0、码 1023、PAD 都是普通整数，JSON 能原样还原。一个码一个字节存不下 1023；读回成 tuple 和 list 比较不相等。

## Part 3 inner monologue 对齐

做法是一遍扫描，记住第一个空闲帧 `free`：

```python
ms = round(word.start * 1000)
first = max(ms // FRAME_MS, free + 1)
stream[first - 1] = EPAD
stream[first:end] = word.tokens
free = end
```

- **帧边界用整数算**：时间戳是毫秒精度，先四舍五入到毫秒，再整除 80。直接用浮点数会出错：`2.32 / 0.08` 和 `2.32 * 12.5` 都是 28.999999999999996，取整得到第 28 帧；`int(16.08 * 1000)` 是 16079，也会差一帧。
- **向下取整**：第 t 帧覆盖 [80t, 80t + 80) ms，0.62 s 在第 7 帧，`round` 会给 8。
- **`free + 1`**：多出来的 1 是留给 EPAD 的帧。它同时处理了两种情况：说得快时撞上前一个词，以及 0 s 开始的词前面没有帧可放 EPAD。不留这一帧时，`stream[first - 1]` 在 first 为 0 时写到的是 `stream[-1]`，Python 不会报错。
- **显式检查长度**：切片赋值越过结尾时列表会变长，不会报 IndexError，所以要先判断 `end > n_frames`。词正好写到最后一帧是合法的，所以是 `>` 而不是 `>=`。

最后一段是端到端检查：两段正弦波经过 Part 1 的 `encode` 和 `frames_of`，与对齐好的文本一起写进 Part 2 的会话记录，再用给好的 `transcript()` 从文本流里读回每个词和它所在的帧。这就是课里说的 inner monologue 的附带好处：转写是白送的。

## Part 4 会话监控

每个方向包一层 `_Side`：一个待用的包队列，加上“这一侧结束了没有”。对第 t 帧，每一侧只在队列为空时才去拉下一个 burst：

- 队首正好是第 t 帧，就取走它的 voiced；
- 队首是更晚的帧，或者这一侧已经结束，第 t 帧就是丢了，记 null；
- 两侧都没有第 t 帧，而且都已经结束、队列也空了，就停下。

这样做有几个效果：

- 按帧号配对，丢帧不会让后面的帧错位。
- 同一方向的包按顺序到，所以“还没到”和“丢了”能分开：只有这一侧送来了更晚的帧或者结束了，才算丢。空的 burst 不影响判断。
- 丢包记 null，静音是 false，两者不混：模型在听的时候照样每帧发包。
- 两侧都丢了的帧照样输出一行，两边都是 null。停下的条件是两侧都结束、队列也空了，不是“两侧都没有第 t 帧”。
- 只在需要时才拉取，第一行输出时每一侧只拉了一个 burst。
- `barge_in` 用上一帧用户是否在说话来判断，这个状态放在循环变量里，跨 burst 保留。丢了的帧按没在说话算，所以每一帧都更新这个状态，不沿用更早一帧的值。
- 帧号在拉取时检查，上一个帧号跨 burst 记着；重复和倒退都报 ValueError。
- 格式由测试的 `"".join(...)` 加 `splitlines()` 再逐行 `json.loads` 决定：每行后面恰好一个 `\n`。

## Part 5 声学延迟

延迟和帧是同一个嵌套形状，所以三个函数都沿着 delays 递归，用一条路径（键和码本下标）定位到每个位置：

- `delay`：先按 delays 的形状校验每一帧，缺码本、多码本、多一路流、不是合法 token 都报 ValueError。然后第 s 步在路径 p 上的值，取第 s - d(p) 帧在 p 上的值；越界就是 UNSET。一共 len(frames) + 最大延迟 步。
- `undelay`：第 t 帧在路径 p 上的值，取第 t + d(p) 步在 p 上的值。还原之后再 `delay` 一次，和输入比较，不一致就报 ValueError。这一步顺带查出了步数不对、该是 UNSET 的地方有码、该有码的地方是 UNSET。最后一种靠的是 `delay` 对帧的校验：还原出来的帧里有 UNSET，就不是合法的帧。
- `ready_ms`：第 t 帧在第 t + 最大延迟 步才完整，第 s 步要等用户第 s 帧完整到达，也就是 (s + 1) × 80 ms。第 0 帧是 160 ms，正好是课里的 80 ms 帧长加 80 ms 声学延迟。这里取的是整个布局里的最大延迟，和 docstring 一致。Moshi 的用户流和模型流延迟相同，结果和只看模型音频一样；如果用户流的延迟更大，模型什么时候能出声其实只取决于它自己的码本，面试官手册的追问里讨论了这种情况。

每一步都要新建 dict 和 list。写成 `[template] * n` 再往里填，所有步骤会共享同一个对象，最后全都一样。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试时间换算、数据布局和自回归的下标，能设计两侧分开写入的会话存储，能把带时间戳的词对齐到 12.5 Hz 的帧上，能按帧号合并两路异步流，也能处理嵌套结构的可逆变换。它不涉及真正的 Mimi 编解码、Temporal / Depth Transformer 的训练和推理、WebSocket 和音频设备，也不涉及 GPU 上的实时性能和容量规划。课里 Exercise 2 和 3 要求的真实延迟测量需要另外动手跑。
