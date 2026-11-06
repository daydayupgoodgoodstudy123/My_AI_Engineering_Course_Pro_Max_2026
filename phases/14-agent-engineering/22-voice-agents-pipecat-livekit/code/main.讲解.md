# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 22 节 语音 Agents：Pipecat 与 LiveKit ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；不处理真实音频，不需要麦克风、API key 或网络

---

## 1. 这份代码在考察什么

这是一个"形状像 Pipecat"的玩具语音管道。真实的音频、语音识别、大模型和语音合成全部用字符串代替，只保留讲义要讲的**结构**：

1. **Frame**：管道里流动的、带类型的数据单元（音频块、转写、文本、TTS 音频、控制帧）。
2. **Processor 链**：每个阶段只实现 `process(frame)`，认识的帧就处理，不认识的就原样转发。
3. **两个方向**：DOWNSTREAM（VAD → STT → LLM → TTS → transport，音频进、语音出）与 UPSTREAM（transport → … → VAD，取消/控制）。
4. **Barge-in**（用户插话打断）：从传输层发出一个 UPSTREAM `cancel` 帧，传回 TTS 和 LLM。

> 一句话：**把语音 agent 拆成"帧 + 处理器 + 双向链表"**。但要特别注意：这份代码的 barge-in 演示**并没有真正截断任何音频**——同步、整句处理的管道里，取消信号永远来得太晚。看懂这一点，就看懂了为什么真实框架必须流式、异步。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Frame` | dataclass | `kind`（帧类型）、`payload`（内容）、`direction`（方向，默认 downstream） | Pipecat `Frame` |
| `Processor` | 基类 | 持有 `next` / `prev` 指针和 `trace`；默认行为是记录并按方向转发 | `FrameProcessor` |
| `VAD` | 子类 | `audio_chunk` → 判断是否有语音 → 发 `vad_speech` | 语音活动检测 |
| `STT` | 子类 | `vad_speech` → 发 `transcript` | 语音识别 |
| `LLM` | 子类 | `transcript` → 查表得回复 → 发 `text`；记录 `cancel` | 大模型 |
| `TTS` | 子类 | `text` → 按空格拆词 → 发 `tts_audio`；收到 `cancel` 置标志 | 语音合成 |
| `Transport` | 子类 | 收到 `tts_audio` 存入 `delivered`（终点） | WebRTC / SIP 传输 |
| `link` | 函数 | 把处理器串成双向链表 | 管道组装 |
| `main` | 函数 | 正常流程 + barge-in 两个场景，打印 trace | 演示 |

数据流：`vad.process(audio_chunk)` →（VAD）`vad_speech` →（STT）`transcript` →（LLM）`text` →（TTS）`tts_audio` →（Transport）存入 `delivered`；控制流：`transport.process(cancel, upstream)` → tts → llm → stt → vad。

---

## 3. 逐段精讲

### 3.1 Frame 与 Processor 基类

```python
@dataclass
class Frame:
    kind: str
    payload: Any
    direction: str = "downstream"


class Processor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.next: Processor | None = None
        self.prev: Processor | None = None
        self.trace: list[str] = []

    def process(self, frame: Frame) -> None:
        self.trace.append(f"{self.name} saw {frame.kind}")
        if self.next is not None and frame.direction == "downstream":
            self.next.process(frame)
        elif self.prev is not None and frame.direction == "upstream":
            self.prev.process(frame)
```

- `Frame` 用一个 `kind` 字符串区分类型；Pipecat 真实实现是每种帧一个类（音频帧、文本帧、系统帧等），这里简化成一个通用类。
- `Processor` 是一个**双向链表节点**：`next` 指向下游、`prev` 指向上游。`direction` 决定往哪边走。
- 基类 `process` 的语义是"**我不认识这个帧，原样转发**"。子类只处理自己关心的帧，其余调用 `super().process(frame)`——这是 Pipecat 处理器的核心约定：不认识的帧必须往下传，否则会"吞帧"导致管道卡住。
- ⚠️ trace 文案是 `"{name} saw {kind}"`，但子类是在**产出新帧后**调用 `super().process(新帧)`，所以 `vad saw vad_speech` 实际含义是"vad **发出了** vad_speech"，而不是"看到了"。读 trace 时要注意。

### 3.2 VAD 与 STT

```python
class VAD(Processor):
    def process(self, frame: Frame) -> None:
        if frame.kind == "audio_chunk":
            is_speech = bool(frame.payload)
            self.trace.append(f"VAD: speech={is_speech}")
            if is_speech:
                super().process(Frame("vad_speech", frame.payload))
        else:
            super().process(frame)


class STT(Processor):
    def process(self, frame: Frame) -> None:
        if frame.kind == "vad_speech":
            transcript = str(frame.payload)
            self.trace.append(f"STT: -> {transcript!r}")
            super().process(Frame("transcript", transcript))
        else:
            super().process(frame)
```

- VAD 用 `bool(payload)` 判断"有没有说话"：空字符串、`0`、`None` 都算静音（实测 `""` 和 `0` 都输出 `speech=False` 且不再往下传）。真实 VAD（如讲义提到的 Silero）是对音频帧打分的小模型，20–60 ms。
- 静音帧被**丢弃**，下游完全看不到——这正是 VAD 的价值：不把噪声和静音送进昂贵的 STT。
- STT 把 payload 直接当成转写结果。真实 STT 会输出 partial（中间结果）与 final（最终结果），并附带**置信度**——讲义的"STT confidence ignored"失败模式在这里无从体现（讲义练习 2，见测验 Q11）。
- ⚠️ 这里的"一个音频块 = 一句完整的话"，没有体现"何时算用户说完"（turn detection）。

### 3.3 LLM：查表回复，cancel 只记日志

```python
class LLM(Processor):
    def __init__(self, name: str, replies: dict[str, str]) -> None:
        super().__init__(name)
        self.replies = replies

    def process(self, frame: Frame) -> None:
        if frame.kind == "cancel":
            self.trace.append("LLM: cancelled")
            super().process(frame)
            return
        if frame.kind == "transcript":
            text = str(frame.payload)
            reply = self.replies.get(text, "[no canned reply]")
            self.trace.append(f"LLM: {text!r}  -> {reply!r}")
            super().process(Frame("text", reply))
        else:
            super().process(frame)
```

- `self.replies.get(text, "[no canned reply]")`：字典查表代替模型调用，查不到时给默认值。
- 讲义提到 LLM 的上下文是"user/assistant 交替"，这里没有维护对话历史。
- ⚠️ 收到 `cancel` 时只写一行 trace 再继续向上游转发，**没有任何实际效果**：没有中止生成、没有作废已产出的回复。真实系统应取消流式请求（也省钱），并在上下文中记录"助手这句话只说出了前 N 个词"。

### 3.4 TTS：barge-in 的核心——以及它为什么没生效

```python
class TTS(Processor):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.cancelled = False

    def process(self, frame: Frame) -> None:
        if frame.kind == "cancel":
            self.cancelled = True
            self.trace.append("TTS: cancel received; drop pending audio")
            super().process(frame)
            return
        if frame.kind == "text":
            self.cancelled = False
            words = str(frame.payload).split()
            emitted: list[str] = []
            for w in words:
                if self.cancelled:
                    self.trace.append(f"TTS: cut mid-word after {emitted}")
                    break
                emitted.append(w)
            self.trace.append(f"TTS: emitted {emitted}")
            super().process(Frame("tts_audio", emitted))
        else:
            super().process(frame)
```

- 设计意图：TTS 逐词"合成"，每个词之前检查 `self.cancelled`，被打断就停下，只把已说出的词发给传输层。
- ⚠️ **`if self.cancelled:` 分支是不可达代码**。循环体内只有 `emitted.append(w)`，不调用任何外部代码、不让出控制权；`cancelled` 在循环前刚被置为 `False`，单线程下没有任何途径在循环中变成 `True`。
- ⚠️ 整句拆完后**一次性**发出一个 `tts_audio` 帧，下游拿到的是完整句子。真实 TTS 是流式的：按音频块边合成边发送，这样才能在块与块之间被打断。
- ⚠️ 收到 `text` 时先把 `cancelled` 复位为 `False`：如果 cancel 先于文本到达（用户在 LLM 还在想的时候就插话了），这句"迟到的回复"照样会被完整说出（实测 `[['late', 'reply', 'still', 'spoken']]`，见测验 Q10）。
- 措辞上，"cut mid-word" 其实是"词与词之间截断"；真正的句中截断需要在音频块级别处理。

### 3.5 Transport 与 `link`

```python
class Transport(Processor):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.delivered: list[list[str]] = []

    def process(self, frame: Frame) -> None:
        if frame.kind == "tts_audio":
            self.delivered.append(list(frame.payload))
            self.trace.append(f"transport: sent {len(frame.payload)} words")
        else:
            super().process(frame)


def link(*processors: Processor) -> None:
    for a, b in zip(processors, processors[1:]):
        a.next = b
        b.prev = a
```

- Transport 是 DOWNSTREAM 的终点：`tts_audio` 不再往下传，存进 `delivered`。`list(frame.payload)` 复制一份，避免与 TTS 的列表共享引用。
- 其他帧（如 `cancel`）走基类：方向为 upstream 时交给 `prev`（TTS）——所以 transport 也是 UPSTREAM 的**起点**，这符合直觉：用户插话是在"用户那一端"被发现的。
- `link(*processors)`：`zip(processors, processors[1:])` 生成相邻对 `(vad, stt)`、`(stt, llm)`、`(llm, tts)`、`(tts, transport)`，逐对设置双向指针。

### 3.6 `main`：两个场景

```python
    print("\nscenario 2: barge-in mid-utterance")
    tts.cancelled = False
    vad.process(Frame("audio_chunk", "refund please"))
    transport.process(Frame("cancel", None, direction="upstream"))
```

- `vad.process(...)` 是一个**同步调用栈**：VAD → STT → LLM → TTS → Transport 层层调用，函数返回时整句 14 个词已经全部"送达"。
- 下一行才发出 cancel——此时没有任何东西可以取消。cancel 帧依次经过 transport → tts → llm → stt → vad，每处只留下日志。
- `tts.cancelled = False` 是多余的：TTS 收到 `text` 时自己会复位。
- 打印 trace 时没有清空 scenario 1 的记录，所以"scenario 2"标题下的 trace 实际包含了两个场景的全部条目。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字符串代替音频 | 零依赖、可读 | 看不到采样率、分块、编解码；Pipecat 处理真实 PCM 音频帧 |
| 一个通用 `Frame` 类 + `kind` 字符串 | 代码短 | 拼错 kind 不会报错；Pipecat 用不同的帧类，并区分系统帧/数据帧/控制帧 |
| 双向链表 + 同步递归调用 | 直观展示两个方向 | 无法并发，取消永远来得太晚；真实框架用异步队列，每个处理器独立运行 |
| 不认识的帧原样转发 | 处理器可自由组合、插入 | 拼错 kind 的帧会一路透传到终点，不易发现 |
| TTS 整句合成后一次性发出 | 简单 | barge-in 失效；生产必须流式、分块，并在块间检查取消 |
| cancel 只设标志/写日志 | 演示控制帧的路径 | LLM 不真正中止；需要 turn id 机制处理"取消先于数据到达" |
| LLM 用字典查表 | 可复现 | 没有对话上下文、没有流式首 token |
| 不计延迟 | 简化 | 看不到讲义的延迟预算；应加 observer/OTel span（讲义练习 1） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值（不在定义时计算），旧版本 Python 上也能写 `Processor \| None` 这类新式注解，引用尚未定义完的类也没问题 |
| `@dataclass` + 默认值 | `direction: str = "downstream"` | 自动生成构造函数；带默认值的字段放最后 |
| 类型注解 `Any` | `payload: Any` | payload 可以是任何类型 |
| 自引用类型 | `self.next: Processor \| None = None` | 一个处理器指向另一个处理器（链表） |
| 继承与 `super()` | `class VAD(Processor)`、`super().process(...)` | 子类覆盖 `process`，不处理的情况交回父类的默认转发 |
| 子类扩展构造函数 | `def __init__(self, name, replies): super().__init__(name)` | 先让父类初始化通用字段，再加自己的字段 |
| 提前 `return` | `if frame.kind == "cancel": ...; return` | 处理完特殊情况立即返回，减少嵌套 |
| `dict.get(key, default)` | `self.replies.get(text, "[no canned reply]")` | 查不到时返回默认值，不抛 `KeyError` |
| `str.split()` | `str(frame.payload).split()` | 按任意空白切分成词列表 |
| `bool()` 真值判断 | `bool(frame.payload)` | 空字符串、0、None、空列表都是 False |
| 可变参数 `*args` | `def link(*processors: Processor)` | 接收任意个位置参数，打包成元组 |
| `zip` + 切片配对 | `zip(processors, processors[1:])` | 生成相邻元素对 |
| 链式赋值到属性 | `a.next = b; b.prev = a` | 建立双向指针 |
| `list(...)` 复制 | `self.delivered.append(list(frame.payload))` | 浅拷贝，避免共享同一个列表对象 |
| f-string `!r` | `f"STT: -> {transcript!r}"` | 用 `repr` 显示，字符串带引号 |
| 关键字参数 | `Frame("cancel", None, direction="upstream")` | 按名字传参，可读性更好 |
| 元组遍历 | `for proc in (vad, stt, llm, tts, transport):` | 遍历一个临时元组 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成）：

```text
scenario 1: normal flow
  transport delivered: ['hi', 'there,', 'how', 'can', 'I', 'help', 'today?']

scenario 2: barge-in mid-utterance
  trace across pipeline
    vad: VAD: speech=True
    vad: vad saw vad_speech            ← 实际是"vad 发出 vad_speech"
    vad: VAD: speech=True              ← 这两行属于 scenario 2；上面两行是 scenario 1
    vad: vad saw vad_speech
    vad: vad saw cancel                ← cancel 一路传回到了最上游
    stt: STT: -> 'hello'
    stt: stt saw transcript
    stt: STT: -> 'refund please'
    stt: stt saw transcript
    stt: stt saw cancel
    llm: LLM: 'hello'  -> 'hi there, how can I help today?'
    llm: llm saw text
    llm: LLM: 'refund please'  -> 'sure, I can help with a refund; what order number should I look up?'
    llm: llm saw text
    llm: LLM: cancelled                ← 只是日志，没有中止任何东西
    llm: llm saw cancel
    tts: TTS: emitted ['hi', 'there,', 'how', 'can', 'I', 'help', 'today?']
    tts: tts saw tts_audio
    tts: TTS: emitted ['sure,', 'I', 'can', 'help', 'with', 'a', 'refund;', 'what', 'order', 'number', 'should', 'I', 'look', 'up?']
    tts: tts saw tts_audio
    tts: TTS: cancel received; drop pending audio   ← 已经没有 pending audio 了
    tts: tts saw cancel
    transport: transport: sent 7 words
    transport: transport: sent 14 words             ← 整句 14 个词全部送出
    transport: transport saw cancel
```

逐项解读：

- **trace 按处理器分组打印**，不是按时间顺序。真实时间顺序是：scenario 1 全链路 → scenario 2 全链路 → cancel 从 transport 逆流到 vad。
- **cancel 的路径正确**：transport → tts → llm → stt → vad，五个处理器都留下了 `saw cancel`，证明 UPSTREAM 方向的转发逻辑没问题。
- **但 barge-in 没有生效**：`TTS: cut mid-word after ...` 一次都没出现，transport 发出了完整的 14 个词。讲义说"The trace shows ... a barge-in cancel that stops TTS mid-utterance"——与实际输出不符。原因见 3.4、3.6：同步整句处理，cancel 到达时 TTS 早已说完。
- 测验 Q9 给出了流式 TTS + "第 3 个词后插话"的 transport 改写，实测只送出 `['sure,', 'I', 'can']`，TTS trace 出现 `cut after [...]`——这才是讲义想展示的效果。
- 最后两行提示"把各阶段延迟加起来"：按讲义区间，下限之和 400 ms、上限之和 990 ms、中点之和 695 ms（测验 Q3、Q12）。

---

## 7. 动手改一改

1. 修复 barge-in：让 TTS 逐词下发 `tts_audio`，transport 在收到第 N 个词后发出 cancel，验证只送出前 N 个词（参考测验 Q9）。
2. （讲义练习 2）实现置信度门控的 STT：payload 改为 `(text, confidence)`，低于阈值时直接让 TTS 说 "could you repeat that?"（参考测验 Q11）。
3. （讲义练习 3）实现最简单的语义轮次检测：VAD 送来的多个片段先在 STT 中累积，只有当累积文本以 `?` 结尾时才发出 `transcript`。思考：这条规则对"我想退款。"这类陈述句会怎样？
4. （讲义练习 1）不改原类，用"替换实例方法"的方式给每个处理器打时间戳，统计各阶段到达时刻（参考测验 Q12）。
5. 给每一轮对话加 turn id：VAD 检测到新语音时 turn id 加 1；TTS、Transport 丢弃 turn id 过期的帧。验证"cancel 先于文本到达"的场景不再说出迟到的回复（参考测验 Q10）。
6. 进阶：用 `asyncio.Queue` 把每个处理器改成独立的协程任务，cancel 帧走一条优先队列，观察取消在并发下的效果。

---

## 8. 常见坑

- **以为 trace 里出现了 "cancelled" 就是打断成功了**：要看实际送出了多少音频（`delivered`），而不是日志。
- **同步、整句处理**：任何"处理完一整句再交给下一阶段"的设计都会让 barge-in 失效，并且端到端延迟等于各阶段完整耗时之和。
- **收到新数据就复位取消标志**：取消与数据的到达顺序不确定，应按 turn id 判断，而不是按到达顺序。
- **吞帧**：子类忘了在 else 分支调用 `super().process(frame)`，不认识的帧（包括 cancel）就在这里消失，管道"卡死"。
- **trace 文案误导**：`X saw Y` 在本代码中是"X 发出 Y"；调试真实系统时，日志要区分"收到"与"发出"。
- **LLM 只记日志不中止**：被打断后模型仍在生成，既浪费 token，又可能让迟到的回复被播放。
- **忽略 STT 置信度**：把低置信度转写当真，LLM 会给出一本正经但答非所问的回复。
