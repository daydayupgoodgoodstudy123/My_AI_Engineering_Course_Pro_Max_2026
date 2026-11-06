<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="security--secrets-api-key-rotation-audit-logs-guardrails"></a>

# 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails

> 取消通过中央金库(Hashircorp Vault, AWS 密钥管理器, Azure 密钥 Vault) 秘密的无序扩展。 永远不要在配置文件、 VCS 电子表格中保存证书, 使用 IAM 功能来取代静态密钥; 使用 CI/ CD 的 OIDC 。 AI- Gateway 模式是2026 年的解决方案: 应用程序 + 网关 提供商, 并有连接在运行时从金库提取证书的网关 。 在金库中旋转, 所有应用程序在分钟内会接收到 —— 不重新调配, 没有“ 谁有新密钥” 信息。 旋转策略 $ 90 天; 扫描每个文件的 TruffleHog/ GitGuardian/ Gitleaks commit零信任:外交部、安全总局、区域管制局/ABAC,短命 tokensPII清洗使用实体识别来掩码PHI/PII,然后传送; tokenization 绘制稳定占位符的敏感值,以便 LLM 保存代码/关系语义。 网络反射 : LLM 仅提供VPC/VNet子网的专用服务 `api.openai.com`, `api.anthropic.com` 2026年事件驱动器:通过破坏CI/CD证书,在数千个客户部署中进行排泄,从而造成Vercel供应链攻击。

**类型：** 了解
**语言:** Python (stdlib, 玩具 PII- 灌木机+审计日志作者)
**先修要求:** 阶段17 · 19(AI网关),阶段17 · 13(AU)Observability)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出四个秘密管理的反模式( VCS 中的配置文件、 硬编码信封、 电子表格、 静态密钥) 并命名替换对象 。
- 解释人工智能门路-从天窗中拉出的模式,作为2026年的生产标准。
- 执行符合 PII 的洗涤器 tokenization 语义学能生存下来
- 说明2026年Vercel供应链事件,以及它教给CI/CD证书卫生的内容。

<a id="the-problem"></a>

## 问题

实习生 commits `.env` 与 API 键。 他们快速删除它。 键已经在 git 历史- GitGuardian 扫描它, 你的旋转过程是“ 抢走团队, 更新40个配置文件, 重新调配所有服务 ” 8小时后, 一半的服务在现场, 一半在等待部署窗口 。

单独用户 prompts 包括"我的SSN是123 -45 -6789" Prompt 开始 OpenAI。 您有BAA, 但内部政策是先掩蔽 PII , 然后转发 。

单独地说,你的心电图组 LLM 程序可以到达任何网络主机。 有人通过 DNS 将数据从数据中提取到攻击者控制域名, 没有东西能阻挡它 。

警卫 LLM 服务必须针对所有三个矢量。 跳过支持的证书。 PII 刷新, 网络向导过滤 。 Audit logs.

<a id="the-concept"></a>

## 概念

<a id="centralized-vault--iam-role-pull"></a>

### 中央保险库+IM-作用拉动

**Vault**：HashiCorp Vault、AWS Secrets Manager、Azure Key Vault、GCP Secret Manager。作为唯一可信的数据源。

**土著协会的作用**:应用程序/门路通过 IAM 身份认证,而不是静态密钥。 token.

**AI-Gateway 模式**:网关拉动 `OPENAI_API_KEY` 请求时从金库中调出。 在金库中旋转; 下次请求获得新密钥。 不重新部署 。

<a id="rotation-policy--90-days"></a>

### 轮调政策 90天

所有 API 密钥, 保险库根 tokens自动旋转,手动旋转记录并跟踪。

<a id="secret-scanning"></a>

### 秘密扫描

- **TruffleHog** - 正则+ 英特罗比 commits.
- **GitGuardian** 商业,高精度。
- **Gitleaks** - OSS,在CI运行。

运行在每一个 commit. 如果发现新的秘密,则封锁公关。

<a id="zero-trust-posture"></a>

### 零信任态势

- 外交部要求所有账户都提供。
- 经由SAML/OIDC, SSO。
- 区域局(基于作用)或非洲银行(基于归属),用于细小的谷物接入。
- Short-lived tokens (小时,而不是几天)。
- 设备姿势—— 只有带有磁盘加密的连锁设备 。

<a id="pii--phi-scrubbing"></a>

### PII/PHI清洗

之前的 prompt 离开您的以下:

1. 实体确认(spaCy 净入学率,Presidio,商业)。
2. 与实体匹配的面具 : `"My SSN is 123-45-6789"` → `"My SSN is [SSN_TOKEN_A3F]"`.
3. Consistent tokenization (Mesh 方法):同一占位符的相同值图,因此 LLM 保护关系。
4. 选择反向映射 LLM response.

静态 Regex 过滤器可捕捉基本模式; NER 捕获更多。 使用两种方法 。

<a id="input--output-guardrails"></a>

### 输入+输出 guardrails

输入: 已知块 jailbreaks,禁止议题;每个用户的费率限制。

输出: 泄漏机密的正文清洗( R)API 关键模式、拒绝情况下的电子邮件模式、违反政策行为的分类。

<a id="network-egress-whitelist"></a>

### 网络反射白列表

LLM 专用子网服务:
- Whitelist: `api.openai.com`, `api.anthropic.com`,矢量 DB 端点, 保险箱端点。
- 其它的都给我放下
- 通过只使用许可列表的解析器( 避免 DNS 漏网退出) 进行 DNS 。

<a id="audit-log"></a>

### Audit log

每一个不可变的日志 LLM 拨打:
- Timestamp.
- 用户/租户。
- Prompt 散列( 非原) prompt ) 隐私)
- 型号+版本。
- Token counts.
- 成本.
- 反应仓。
- 任意 guardrail trips.

保留各项监管要求(SOC 2 1年,HIPAA 6年)。

<a id="the-2026-vercel-incident"></a>

### 2026年的瓦尔塞尔事件

供应链攻击: 损坏了 CIS/CD 证书, 并被通过数千个客户配置 。 课程: CI/ CD 证书是等效的 。 保存在保险库中 。 范围很窄 。 积极旋转 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 轮调政策: 90天。
- 扫描每个 commit特鲁夫勒霍格/吉特瓜德恩/吉特拉克斯。
- 2026年Vercel:CI/CD的信用暴露了 数千个客户的封口漏掉了
- Audit log 保留期:SOC 2 = 1年,HIPAA = 6年。

```figure
i4-vault-rotation
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行符合要求的玩具 PII 洗涤器 tokenization 和仅附件的 audit log.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-llm-security-plan.md`以监管范围和现状为背景,计划保险库的迁移、洗涤、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移、转移或转移 audit log.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`发送两个 prompts 确认两者都有相同的占位符
2. 设计网络向外迁移政策 vLLM- 紧急空降系统部署呼叫 OpenAI + Anthropic + 节能。
3. 你发现一个钥匙在 git 历史(2年) 。 正确的回答是什么? 旋转键、 擦拭历史还是两者兼而有之? 理由。
4. 你的 audit log 设计保留层(热30d,暖12mo,冷6yr)。
5. 问一下,是不是反向...tokenization (将实际价值重新改为 LLM 与保持占位符可见度相比,这值得考虑。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Vault | 秘密商店 | 中央证书管理服务 |
| 土著协会的作用 | "身份验证" | 应用程序承担的角色; 返回短寿命的信用 |
| CI/CD的OIDC | "cloud-issued tokens" | CI中没有静态密钥—— 通过 OIDC 识别 |
| 特鲁夫勒霍格/吉特瓜德恩/吉特拉克斯 | 秘密扫描仪 | Commit- 时间秘密侦查 |
| 非洲区域局/非洲-巴西 | "出入控制" | 基于角色的对基于属性的 |
| PII 洗涤 | "数据掩码" | 删除敏感实体或给定其符号 |
| Consistent tokenization | "稳定占位符" | 相同值 + 相同 token 每一次,每次 |
| 网格办法 | "Mesh tokenization" | Semantic-preserving tokenization pattern |
| 反向白列表 | 出境许可 | 仅允许域名可访问 |
| Audit log | "不可改变的历史" | 仅附加遵约记录 |

<a id="further-reading"></a>

## 进一步阅读

- [多普勒-高级 LLM Security](https://www.doppler.com/blog/advanced-llm-security)
- [端口键 - 管理 LLM API 带有秘密引用的密钥](https://portkey.ai/blog/secret-references-ai-api-key-management/)
- [数据犬 LLM Guardrails 最佳实践](https://www.datadoghq.com/blog/llm-guardrails-best-practices/)
- [跳跃服务器- 秘密管理最佳做法 2026年](https://www.jumpserver.com/blog/secret-management-best-practices-2026)
- [微软 普里西迪奥](https://github.com/microsoft/presidio) PII探测和匿名。
- [哈希公司空降设备](https://developer.hashicorp.com/vault/docs)
