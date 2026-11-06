# 复盘模板

- 时间：开场__ / P1__ / P2__ / P3__ / P4__ / P5__，总__分钟。
- Part 1：首个异常的正确消费者是什么？生产者应该返回什么？cohort、缓存安全与观测重放各用了什么证据？
- Part 2：同用户跨实验、同 request 多 attempts、原 role/token/cost 如何持久化？bucket 与所选版本有什么区别？
- Part 3：rollout/shadow 的角色表是什么？guard 替换文本、provider 失败与实际付费事实如何分开？
- Part 4：哪些字段允许进入 content、哪些只属于 telemetry？driver 与候选投影各负责什么？
- Part 5：找到了哪些实际配置路径？为何不使用全局 primary 或其他 template 的版本补齐缺失？
- 每关记录一个试过的错修：改动__、预期__、真实失败__、责任__。
- 边界：本地 replay、fixture guard/evaluator、静态配置 readiness 能证明什么？哪些线上能力没有验证？
