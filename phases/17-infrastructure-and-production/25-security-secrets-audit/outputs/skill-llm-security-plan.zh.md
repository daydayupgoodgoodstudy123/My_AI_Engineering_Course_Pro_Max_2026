---
name: llm-security-plan
description: Produce an LLM security plan covering secrets vault, PII scrubbing with consistent tokenization, network egress allowlist, audit log retention, and zero-trust posture.
version: 1.0.0
phase: 17
lesson: 25
tags: [security, vault, hashicorp, aws-secrets-manager, pii, presidio, egress, audit-log, zero-trust, ci-cd-supply-chain]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于监管范围(SOC 2, HIPAA, GDPR),目前的认证状态和网络/代表态势产生了一个安全计划。

显示 :

1. 跳跃迁移。 选取金库( HashiCorp, AWS 密钥管理器, Azure 密钥管理器, GCP 密钥管理器) 。 网关模式 : 应用程序 ” 通道连接 ” 。 取消硬编码的 env 和 配置文件证书 。
2. 秘密扫描。 启用 TruffleHog/ GitGuardian / Gitleaks 的每个 commit. 封锁公关 检查。
3. 轮调政策:90天;尽可能自动化;专门轮流使用CI/CD证书(建议短30天)。
4. PII 擦拭、实体识别(Presidio + regex) tokenization (相同值  同一占位符) 用于保存语义 。
5. 反向允许列表。 白列表 LLM 提供方域、 矢量 DB、 保险箱端点。 DNS 允许列表解析器 。
6. Audit log。仅附加、不可更改。需要字段:用户、租户、 prompt反应散列, tokens, 成本, guardrail 旅行:每个框架保留(SOC 2 1y/HIPAA 6y)。
7. 光学和光学科学中心,OIDC身份联合会(没有静态云键),光学和光学中心证书范围狭窄,将2026年的Vercel供应链事件作为动机。

艰难的拒绝 :
- 配置文件中的静态密钥。 拒绝 。
- 正在原始存储 prompts 在 audit log拒绝——只有管理框架明确要求的除外。
- 允许向 `*` 或"互联网",拒绝 - 白名单。

拒绝规则 :
- 如果客户不接受保险库(空格要求),则拒绝正常计划,并设计一个基于文件的旋转后退。 明确注明它不那么安全。
- 如果PII清洗因“延迟”原因而拒绝,则拒绝—— 潜伏通常小于20毫秒,监管风险则会小于20毫秒。
- 如果需要旋转90天, 用于金库根 token拒绝 - 它变成了一个突破矢量。

输出:一个一页计划, 包括金库、扫描、旋转、清洗、反射、 audit log以单一的度量结束:每月秘密扫描点数;目标零。
