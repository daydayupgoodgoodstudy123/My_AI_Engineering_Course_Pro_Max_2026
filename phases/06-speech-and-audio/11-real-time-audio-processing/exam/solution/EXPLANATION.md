# 参考答案讲解：RTLoop（06/11）

计时结束后再看。参考实现在同目录的 `rtloop/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修采集代码

**现象**：解锁后的第一个错误是 `meter.rms` 里的 `TypeError: unsupported operand type(s) for *: 'NoneType' and 'NoneType'`，而 `rms` 本身没有 bug。

**顺着往上找**：出错的帧来自 `Capture.frames`，帧的最后一个样本是 None。环的存储初始化成 `[None] * capacity`，读到 None 说明读到了一个从没写过的格子。100 ms 的环有 1600 格，第一次回绕发生在写第 1536 到 1791 个样本的那一块。`write` 算“到存储末尾还剩几格”时写成了 `capacity - start - 1`，第 1599 格被跳过，回绕后的样本整体错后一格。读第 5 帧（第 1280 到 1599 个样本）时就读到了那个 None。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. 回绕切分：`first = min(n, self.capacity - start)`。从 `start` 到末尾正好有 `capacity - start` 格。
2. 帧长：`ms_to_samples` 要先乘后除，`sample_rate * ms // 1000`。原代码 `sample_rate // 1000 * ms` 先把 44100 截成 44，44.1 kHz 下一帧只有 880 个样本，每帧的时间戳少 45 µs。讲义 `code/main.rs` 的 `FRAME_LEN = SAMPLE_RATE / 1000 * FRAME_MS` 也是这个写法，16 kHz 和 48 kHz 能被 1000 整除，所以看不出来。
3. 被挤掉的样本要计入 `dropped`。测验 Q12 讲过：`deque(maxlen=...)` 写满后会静默丢掉最旧的样本，丢弃必须能被看到。
4. 不要一个一个挤。原代码每挤掉一个样本调一次 `read(1)`，`read` 又每次复制整个环，处理循环卡住时回调就慢下来，1 秒的环卡 2 秒要 1 秒以上。改成一次算出溢出量：

```python
overflow = self.level() + n - self.capacity
if overflow > 0:
    self._read += overflow
    self.dropped += overflow
```

参考实现顺便把 `read` 改成两段切片，只复制要返回的样本。讲义说环形缓冲区的用处就是热路径上不分配内存。

**护栏**：

- 满幅正弦波读 -3.01 dBFS。电平是 20·log10(RMS)，不是峰值；AES17 那种让满幅正弦读 0 dBFS 的写法会在这里挂。
- 把存储初始化成 0.0 能让 TypeError 消失，但帧里会混进一个 0 和错位的样本。测试逐个样本比对帧内容，只修症状过不去。
- 静音的麦克风读 `FLOOR_DBFS`（-200 dBFS）。电平计本来就和 `code/main.py` 的 `max(rms, 1e-10)` 一样有下限；改写电平计、让静音返回 -inf 不行，这个数会进 JSON 和平均值。
- 改成 `int(sample_rate / 1000) * ms` 不算修好帧长，还是先截断再乘，44.1 kHz 下照样是 880。
- 批量丢弃时只加 `dropped`、不移动读指针，读的一方会被套圈，读出 `[6, 7, 3, 4, 5, 6, 7]` 这种重复样本。读指针同时也是时间戳的来源：卡住半秒以后，第一帧的时间是 300 ms，不是 0。时间戳只数送出去的样本、不算丢掉的，也会把这一帧算成 0 ms。

## Part 2 延迟记录

参考实现是一张表：`seq` 自增主键负责记录顺序，`(session, number)` 唯一，四个阶段各占一个 INTEGER 列，没到的阶段存 NULL。`turn` 读回时去掉 NULL，被打断的那一轮和记录时的 dict 一模一样。

- **整数纳秒**：测试用的 `WALL` 是 2026 年的 `time.time_ns()`，约 1.79e18，远超 2^53。double 在这个量级上相邻两个数差 256 ns，存进 REAL 列或换成浮点秒，读回来就不一样了。SQLite 的 INTEGER 能原样存 64 位整数。`WALL / 1e9` 这种浮点值要直接拒绝，这是把秒当纳秒的典型错误。
- **校验**：mark 必须从 `speech_end` 开始，按 STAGES 的顺序，不能跳阶段，不能倒退，但可以相等（缓存的回复一拿到 transcript 就有第一个 token）。
- **编号**：`SELECT COUNT(*) + 1 FROM turns WHERE session = ?`。编号存在数据库里，所以重开以后接着编。用 `lastrowid` 会编成全局号，在内存里计数会在重开后从 1 重来。
- **慢的轮次**：`WHERE first_audio - speech_end > ?`，在 SQL 里做整数减法，结果是精确的。正好 500 ms 的那一轮不算慢，多 1 ns 的那一轮算慢。按整毫秒比较，或者先把两个绝对 mark 换成浮点秒再相减，都会丢掉这 1 ns。没有 first_audio 的轮次，差值是 NULL，自然不会选出来。按 `seq` 排序，保持记录顺序。
- 和其他用 sqlite3 的关一样：写完要 commit（这里用 `with self._db:`），建表要写 `IF NOT EXISTS`。

## Part 3 打断

`Dialog` 只靠调用时传进来的时间推进。参考实现的核心是 `_advance(t)`：把开始时间不晚于 t 的块从队列移进 `played`，记下用户听到的文本；如果回复已经结束、队列空了、最后一块也播完了，就把话轮交还给用户。

```python
start = max(t_ns, self._end)          # 到达，或上一块结束，取较晚的
self._end = start + duration_ns
self._queue.append((start, self._end, text))
```

打断（`_cut`）做三件事：正在播的那一块截到当前时刻；清掉队列；把回复标记为结束。之后到达的旧回复的事件因为编号对不上被丢掉，块和 `reply_done` 都一样：1560 ms 到的是第 1 个回复的 `reply_done`，不能把正在 thinking 的第 2 个回复标成结束。

- 截断必须在第三个语音帧那一刻发生。TTS 块是 320 ms（讲义推荐的大小），等当前块播完再停，最坏要等 300 多 ms，超过讲义要求的 100 ms。
- 连续计数遇到非语音帧清零，否则隔帧出现的残留回声会误打断。
- thinking 时也能打断。讲义 Step 4 的 `tts_task` 包着 LLM 和 TTS，`on_user_speech` 只要任务没结束就取消。
- 回复还占着话轮时来了新的 `user_turn`（测试里是用户在 app 里打字），`user_turn` 先调 `_cut`，和打断走同一条路，再开始新回复。
- `reply_done` 只表示不会再有新块。最后一块播完之前，话轮还是助手的。
- history 只记开始播放的块，这是用户真正听到的内容（测验 Q17）。没发出声音的回复不留记录。

最后一段把 Part 1 接上：静音的帧是 -200 dBFS，用户开口后约 -23 dBFS，用 `code/main.py` 的 -40 dBFS 阈值判定语音，第三个语音帧在 540 ms，播放就停在 540 ms。

## Part 4 异步流水线

结构是一个麦克风任务、每个 stage 一个任务、一个 sink 任务，相邻任务之间是 `asyncio.Queue(maxsize)`：

- 麦克风任务从不 await 队列：满了就 `get_nowait()` 丢掉最旧的一帧、计数，再 `put_nowait()`。麦克风结束后才 `await put(_END)`，这时等一等没关系。
- stage 任务：取一项，是 `_END` 就往下传并退出；否则调用函数，`except Exception` 时计数并丢掉这一帧，成功就 `await outbox.put(...)`。下一级的队列满了，这里自然就等了，这就是背压。
- sink 任务：同样处理 `_END` 和异常，成功一次 `delivered` 加一。sink 报错的那一帧只算 errors：测试里 stage 丢了第 3 帧、播放设备在第 5 帧报错，结果是 `Stats(delivered=6, errors=2)`。

收尾和取消：

```python
try:
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for task in done:
        task.result()
finally:
    for task in tasks:
        task.cancel()
    await asyncio.wait(tasks)
```

- 正常结束时所有任务都已完成，`cancel()` 什么也不做。
- 外面取消 run_pipeline 时，CancelledError 在 `asyncio.wait` 处抛出。`asyncio.wait` 不会替你取消子任务，所以 finally 里每个任务正好被 cancel 一次，然后等它们全部结束，包括 stage 里关闭 TTS 连接的那 10 ms 清理，最后取消照常传出去。
- 换成 `asyncio.gather` 有两个坑。gather 被取消时会把子任务各取消一次，但第一个子任务以取消结束时它就返回了，这时那个 stage 还在清理，run_pipeline 已经先返回。要是在 finally 里再 cancel 一遍，又会把清理半路打断，“tts closed” 永远写不出来。Python 3.11 以上的 `asyncio.TaskGroup` 处理得对。
- 只能捕获 Exception。CancelledError 从 3.8 起是 BaseException，捕获 BaseException 会把挂断当成一帧出错，流水线继续跑。

测试里的数字：STT 每帧要 5 轮事件循环，麦克风每轮来一帧，所以第一个队列一定会满。正确实现下 tag 最多领先 STT 6 帧（队列 4、tag 手里 1、STT 正在处理 1）；换成无界队列会领先 160 帧，而且一帧都不丢。

## Part 5 处理图

`schedule` 是带两种状态的深度优先遍历：`path` 是当前递归路径上的阶段，`done` 是已经排好的阶段。

- 遍历只沿 inputs 走。reference 边带的是上一帧（AEC 的远端参考来自 speaker），沿它走就会在 aec → vad → stt → turn → llm → tts → speaker → aec 上报出一个并不存在的环。
- 遇到 `done` 里的阶段直接返回，遇到 `path` 里的阶段才是环。只用一个集合的话，vad 先被 stt 访问过，再被 turn 访问时就会被当成环。
- 报错时取 `path` 里从重复阶段开始的那一段，正好是环本身。测试里的环是没有 AEC、STT 直接读 speaker：DFS 从 captions 走进来，path 是 `[captions, stt, speaker, tts, llm, turn]`，报出的环是 `stt -> speaker -> tts -> llm -> turn -> stt`。把整条 path 报出来会多一个 captions；Kahn 算法剩下的节点也包括 captions。
- 同一条回声路径，作为 reference 进 AEC 是合法的（带的是上一帧），作为 inputs 进 STT 就是同一帧里的环。
- 未知的名字在遍历之前统一检查，inputs 和 reference 都查，报 ValueError。

`critical_path` 按 `schedule` 的顺序做一遍动态规划：每个阶段取输入里最慢的那条链，加上自己的 ms。`max` 遇到相等的值返回第一个，所以平票时取列在前面的输入。VOICE 到 speaker 的关键路径是 20 + 10 + 10 + 150 + 5 + 100 + 100 + 20 = 415 ms，和讲义开头约 400 ms 的预算表对得上。

要比的是整条链，不是输入自己的 ms。llm 同时读 turn（5 ms）和 stt（150 ms）：从 speaker 往回每一步挑最慢的输入，会在 llm 处选 stt，得到 410；经过 turn 的链多 5 ms，所以是 415。

不带记忆的递归在立体声链上要走 2^20 条路径，约 1 秒；动态规划每个阶段只算一次，几十微秒。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的实时音频代码里调试环形缓冲区和分帧，用整数纳秒精确存取延迟记录，写出带时间线的打断状态机，用 asyncio 写出有背压、能正确取消的流水线，以及在处理图上排序、判环、求关键路径。它不涉及真实的音频设备和回调线程（PortAudio、sounddevice）、WebRTC 传输和抖动缓冲、真正的 VAD、ASR、TTS 模型，也没有测量真实的端到端延迟。讲义 Exercises 2 和 3（麦克风直通、用 aiortc 测端到端延迟）需要另外动手做。
