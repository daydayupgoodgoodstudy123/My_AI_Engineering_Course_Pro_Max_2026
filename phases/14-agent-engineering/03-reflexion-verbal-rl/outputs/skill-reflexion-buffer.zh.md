---
name: reflexion-buffer
description: Maintain an episodic-memory buffer of reflections for verbal RL with TTL, dedup, and scoped scope.
version: 1.0.0
phase: 14
lesson: 03
tags: [reflexion, episodic-memory, self-healing, verbal-rl, sleep-time]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务类( 重现类型) agent 运行,例如“ 函数” 、 “ 关闭支持票 ” , 保持一个反射的偶发缓冲。 每个反射记录一个失败模式和自然语言的纠正洞察力。 缓冲器将预设为下一个任务类的试验 。

显示 :

1. 反射捕获。 在测试结束时, 评估员得分低于门槛值, 释放一线反射 : “ 我未能做 X 因为 Y; 下次是 Z ” 。 除非能够复制, 否则会丢弃外部失败的反射( 网络、 上游500 ) 。
2. TTL 和 didup。 反省在默认的 N 试验后过期( 建议 10) 。 精确的重复崩溃 。 近于重复 (> 0.9 的对小 embedding 模型,或共享子字符串  80%)只保留最新。
3. 范围政策。 三个范围:任务类(每个任务名称)、用户(同一用户的跨任务), agent (覆盖所有用户) 默认是任务类。 只有在反射是指用户的偏好时, 才会向用户范围飞升; 绝不升级为 agent 范围自动。
4. 压缩。 当缓冲超过预算时, 运行睡眠时间压缩: 组合近乎重复、 总结、 合并。 压缩会从热路流中流出 — — 不要推迟主机 agent回应
5. Prompt 集成。 以一个子弹列表, 将一个题为“ 我从先前试验中学到的东西”的块块划为“ 。 ” prompt; 溢出部分放在一个单独的概要项目上(......), 4个关于超时的老式思考”)。

艰难的拒绝 :

- 将反射写成“ 下次要小心一点” 。 这是不可操作的。 用一个 prompt 迫使下个时间的具体教学
- 基于墙时数而非试算的反射时间。 TTL 应为离线重播运行进行试验范围而不是时间范围 。
- 存储参考机密的反射( Q)API keys, tokens, PII) 。在承诺使用缓冲之前,拒绝特定“含有机密”类错误。

拒绝规则 :

- 如果没有评价员,则拒绝推荐第05课(自备/CRITIC反射需要信号,而不是直觉。
- 如果任务类是一发( 永远不重复) , 则拒绝; 偶发内存对一项不再重复的任务没有作用 。

输出: 一个结构化缓冲文件( T)JSON 带有反射对象: 试运行 ID、任务类、范围、文本,创建_时间,ttl_其余)a prompt 和一份“静态反射”报告 列出即将过期的条目

结尾处有“ 下一步读什么” 注释, 指向 06 (Lesson 06) (N)context compression)如果缓冲剂一直撞击它的顶部,或课程08(Letta睡眠时间计算)将压紧线从热路移开。
