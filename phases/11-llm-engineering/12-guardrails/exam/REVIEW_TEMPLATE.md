# PIISpan 复盘

日期：____ 时长：____ 环境：____ 是否先看参考：____

| 关 | 首错/根因 | 修改与保留的反例 | H1/H2/H3 | 用时 | 独立解释 |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

- 完整匹配、capture groups、原始 codepoint offset 各是什么？
- P2 GIVEN AuditSpan codec 负责哪些字段/恢复？候选如何组合安全 outer manifest、独立 key audit、blob 地址与 digest 校验？
- priority chain、被拒 bridge、相邻和重复 occurrence 能否手算？输出是否回到原文顺序？
- GIVEN sandwich/driver 负责什么？candidate 是否保留精确 check 值与原始 codepoint audit？
- 输入拦截、输出硬拦截与 scrub-only 如何核证据？进入输出阶段是否有 model_called 和一个 scrub check？
- detector failure 数和 blocked request 数是否混淆？
- 这里实际验证了哪些有限 fixture，哪些安全/模型/生产能力没有证明？
