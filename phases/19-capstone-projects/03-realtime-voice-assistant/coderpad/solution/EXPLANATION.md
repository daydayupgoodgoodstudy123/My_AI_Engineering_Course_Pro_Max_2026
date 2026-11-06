# 参考解释：Capstone 03 — Real-Time Voice Assistant (ASR to LLM to TTS)

## 核心：能量 VAD 边界

先平方求均值再开根号；阈值相等时为语音是题目规定的边界。

准确合同：For each numeric audio chunk, return RMS>=threshold; an empty chunk has RMS 0. threshold must be >=0 or raise ValueError. No model or microphone access.

## 加分：合法状态转换

允许边应显式列出，终态不再接受新转换，包括重放到同一状态。

准确合同：Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
