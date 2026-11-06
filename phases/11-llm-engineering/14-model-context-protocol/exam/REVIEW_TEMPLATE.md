# 复盘模板

- 开场__ / P1__ / P2__ / P3__ / P4__ / P5__，合计__分钟。
- P1：factory 生产了什么？正确消费者为何拒绝？三类 identity 与 inventory 输出各有什么证据？
- P2：spec 的字段、参数顺序、URI 与 handler_name 如何保留？未知 handler 如何处理？
- P3：列出三类 descriptor/result 字段；导出的嵌套容器能否改写已注册 Entry？哪些能力/metadata 已给定？为什么空目录仍有 capability？
- P4：实际变更由谁应用？changed_fields 与 after/tombstone 如何证明本次变化？
- P5：记录重复 catalog 名的两条完整路径；own entries、children 与不同 primitive kind 是否都保留？不同 scope 的同身份条目是否保留各自 descriptor？
- 每关试过的错修：__；真实 expected/actual：__；最小改动与过修风险：__。
- 证明边界：本地 compiler/artifact 是否等于完整 MCP conformance、网络 transport 或安全审批？哪些没有验证？
