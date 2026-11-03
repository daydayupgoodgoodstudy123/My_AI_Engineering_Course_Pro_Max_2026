<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-registry-supply-chain-admission-drift-and-rollback"></a>

# MCP 注册表供应链：准入、漂移与 Rollback

> 注册条目可以说明出版商申报的内容。 产品注册证明您所获取的、 您所观察到的、 您所批准的以及您能够安全恢复的。

**类型：** 构建
**语言:** Python
**先修要求:** 阶段13 · 17(门户和登记册),阶段13 · 18(生产认证)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 单独的登记处出版物、包装来源、运行时间发现和当地批准。
- 校验 MCP 服务器命名空间, 但不信任在它自己的记录中的名称 。
- 书刊、执行来源、来源和活描述证据
- 检测登记状况的变化和入场后运行时间的移动。
- 将路径移回先前认可的版本, 不重写历史 。
- 保持一个明显的篡改入场分类账 解释每一项决定

<a id="the-problem"></a>

## 问题

你找找看,你找找看,你找找看,你找找看 `com.example/inventory` 。 它的描述看起来是正确的。 它的软件包已经存在。 服务器的答案 `server/discover`.

这不是一个事实,而是来自不同当局的一系列事实:

1. 一名经认证的命名空间出版商提交了一份记录。
2. 包裹登记簿为具有特定身份和消化器的文物提供服务。
3. 一个运行中的端点报告了协议版本、能力、工具和诊断服务器信息。
4. 你们的组织决定允许这种精确的组合。

将这些事实拼凑到“ 它在登记处, 所以信任它” 创建了一个供应链盲点。 一个有效的出版物仍然可以被折旧。 如果您不将其摘要输入, 包标签可以指向一个意外的文物。 服务器可以在审查后添加一个破坏性工具 。 rollback 能够静默地选择一个从未被接受的版本。

固定是接收控制器 在每个边界都有证据

<a id="the-registry-is-an-index-not-your-approval-system"></a>

## 注册是索引,不是你的批准系统

官方 MCP 注册存储服务器元数据。 `server.json` 记录服务器版本并宣布一个或多个软件包或远程端点。公布规则添加命名空间认证、软件包所有权检查、限制注册规则以及一个狭窄的发布元数据位置。

控制器回答出版问题,你的生产政策仍然回答部署问题:

| Boundary | 问题 | 证据所有人 |
|---|---|---|
| Namespace | 出版商是否允许使用这个名字? | 注册验证加上已校验的命名空间输入 |
| Record | 出版商宣布了这个版本的内容? | Immutable `server.json` digest |
| 执行来源 | 执行哪个软件包或远程端点 ? | 申报源字段、核实的所有权结果、运输和可信赖的文摘 |
| 运行时 | 现在的终点会暴露什么? | `server/discover` 和工具描述符 |
| Admission | 你的政策是否批准这个精确的设置? | 本地针和分类账条目 |
| Operations | 安全吗? 还有什么能取代它? | 漂浮检查,状态同步,健康, rollback route |

书记官处的系统格式和 MCP 协议版本是独立的。 记录可以使用已公布的 `2025-12-11` 支持实时服务器的服务器图案 MCP `2026-07-28`绝对不能从另一个角度推断

```figure
mcp-registry-admission
```

<a id="seven-controls-in-one-admission-decision"></a>

## 7项一次性入境决定中的管制

<a id="1-namespace-verification"></a>

### 1. 命名空间核查

正式注册名称使用经认证的命名空间。 验证的域名可以映射到反向域名前缀。 例如, 控制 `example.com` 可以建立 `com.example/*`.

不接受字符串前缀检查 :

```python
server_name.startswith("com.example")
```

这也是接受的 `com.exampleevil/tool`。在 `/`,需要非空的弹片,并精确比较命名空间段。更重要的是,将已核实的命名空间从认证结果中传递到允许的状态。不要从不信任的记录中获得信任。

GitHub- 支持的命名空间和域支持的命名空间使用不同的认证路径。将任一路径都普通化为一个输入:精确的校验命名空间字符串。

<a id="2-provenance-join"></a>

### 2. 证明书合二为一

软件包记录,声明和取回的文物必须加入明确的字段:

- 软件包登记类型
- 软件包标识符
- 软件包版本
- 核实的所有权结果
- 下载的文物摘要

也验证已申报的软件包传输。 仅带有远程端点的记录是有效的, 并且不能因缺少软件包而被拒绝。 对于远程源, 请加入已申报的 URL 和 运输类型, 以独立核实终端所有权, 并加入可信任连接或部署证据摘要 。

课程代码支持两种源类别,并且将选定的源与书记官处的源、服务器名称、登记册版本、记录摘要和证据摘要一起杂在一起。 由此得出的源摘要是整套证据的缩略指针。 它不能替代证据的保存。

永远不接受只有您试图验证的文物提供的文摘。 在信任的边界处计算, 或者从您验证其验证结果的软件包服务接收 。

<a id="3-pin-the-decision-not-only-the-version"></a>

### 3. 将决定,而不仅仅是案文

登记册版本是独特的出版物标识符,已公布的元数据不可更改。已修改的记录需要新版本。建议采用语义版,但书记官处不要求,也不接受版本范围。

意思是 `^1.4` 并非入门针,“最晚”也不是。

```json
{
  "server": "com.example/inventory",
  "version": "1.0.0",
  "recordDigest": "...",
  "source": {"kind": "package", "registryType": "pypi"},
  "sourceDigest": "...",
  "toolsetDigest": "...",
  "provenanceDigest": "...",
  "registryStatus": "active"
}
```

平整多个层可以让您识别哪个边界已经更改。 在相同的登记册版本下, 记录摘要转换是书记官处的完整性故障。 在同一个软件包协调或远程部署下, 源摘要修改是执行源完整性故障。 工具摘要转换是运行时漂移 。

<a id="4-live-drift-detection"></a>

### 4. 实时漂流探测

接收时要观察实际接收流量的服务器。 `server/discover`,通过您信任的路径列出或以其他方式获取曝光的工具描述符,并核实:

- `2026-07-28` 是在 `supportedVersions`
- 当地需要的所有能力都具备
- 每个工具描述符都有所需的身份和图案表层
- 常规描述摘要符合事后检查的输入针

可选结果 `_meta["io.modelcontextprotocol/serverInfo"]` 值是自报显示、日志和调试上下文。记录它作为诊断证据,但从不使用它来建立命名空间、软件包所有权、终端所有权、注册或其他任何安全决定。 `serverInfo` 外号 `_meta` 不属于合同领域,不应被推广为诊断证据。

仅对顺序没有意义的字段进行常规化。样本在散列前按稳定的名称排序工具列表,因此无害列表顺序的更改不会导致漂移。它不会丢弃描述性字段。新工具,改变图案,修改描述,或新的说明会改变插针。

样本将错误的描述符和任何描述符摘要化变化作为漂移处理,隔开针,删除其活动路径,并将版本的块块作为 rollback 制作政策可能只允许通过新的审查进行编辑改动,因为描述会影响模型工具的选择。 agent behavior.

<a id="5-registry-status-is-live-state"></a>

### 5. 登记状况为实时状态

书记官处 API 附加响应级别 `_meta` 对象,每个服务器记录旁边。 `_meta["io.modelcontextprotocol.registry/official"]`。通过答复 `_meta` 接受和读取的标的 `_meta["io.modelcontextprotocol.registry/official"].status`直接 `_meta.status` 值不是官方的线条形状。 不要混淆响应元数据与发布记录本身 `_meta`状态可以是:

- `active`:默认返回并有资格在当地入境
- `deprecated`:仍然可以发现一个警告,但不再是一个安全的自动选择
- `deleted`:默认隐藏,而历史记录则通过删除或递增视图保存

进入后同步状态。 如果一个活动版本被折旧或删除, 将隔离其插针并停止将新工作转至它。 保留证据。 从默认列表中删除不允许删除您的审计线索 。

发布者提供的自定义元数据仅属于以下 `_meta.io.modelcontextprotocol.registry/publisher-provided` 由注册处管理的响应元数据是分开的。 不要让出版商设定自己的官方身份 。

<a id="6-rollback-means-route-restoration"></a>

### 6. Rollback 表示路线恢复

不可更改的出版物在 rollback. Rollback 选择先前被接纳、目前符合资格的插针并更改活动路线。

安全目标必须:

1. 持有完整的入院记录。
2. 登记处在你们的政策下仍然活跃着
3. 不得通过运行时间或安全证据隔离。
4. 仍然决心完成这个包裹 和现场描述
5. 进行体检

样本侧重于前三个条件。 真正的调节器应该重新拉伸软件包, 在激活前重新检查活端点 。

<a id="7-append-an-admission-ledger"></a>

### 7. 附加入职分类账

入门数据库显示什么是活动。一个分类账解释了原因 。

每个样本条目都包含序列、时间、事件、服务器、版本、结果、理由、证据、前一个条目的散列和它自己的散列。 更改旧的结果会中断对条目及以后链接的验证 。

这是明显的篡改, 而不是神奇的篡改。 锁定周期分类账头位于一个单独的信托域, 如签名的发布元数据或一次写入存储 。 限制谁可以附加 。 tokens,将证明、工具参数和私人端点数据从证据中包起来。

<a id="build-it"></a>

## 动手实现

运行控制器在 `code/main.py`。它只使用 Python 标准库。

以有限的演示开始 :

```bash
cd phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift
python3 code/main.py
```

演示进行五项操作:

1. Admit `1.0.0` 与匹配命名空间、 软件包来源、 协议、 能力和工具 。
2. Admit `1.1.0` 让它活跃起来
3. 在运行时观察一个意外的删除工具 。
4. 观察书记官处的地位 `1.1.0` become `deprecated`.
5. 恢复到仍然被接纳的路径 `1.0.0` pin.

预期形状 :

```json
{
  "admitted": [true, true],
  "driftAllowed": false,
  "rollbackAllowed": true,
  "activeVersion": "1.0.0",
  "ledgerValid": true
}
```

阅读执行顺序:

1. `namespace_for_domain()` 和 `namespace_matches()` 建立精确的命名权限 。
2. `digest()` 和 `normalized_tools()` 产生决定性的证据。
3. `RegistryAdmissionController.admit()` 加入出版、来源、运行时间和政策。
4. `check_live()` 比较新观察与针。
5. `observe_registry_status()` 检疫版本 其注册状态发生变化。
6. `rollback()` 只激活先前认可的合格目标 。
7. `AdmissionLedger.verify()` 检测到记录历史的变化。

<a id="use-it"></a>

## 实际应用

将控制器置于发现和路径之间:

```text
Registry sync -> artifact verifier -> live discovery -> admission controller -> route table
                                               |                 |
                                               v                 v
                                          evidence store    admission ledger
```

使用不同的身份来完成这些任务。 注册同步工作需要阅读元数据。 人工制品验证程序需要获取软件包。 路径调节器需要权限才能激活一个经批准的针。 没有一个需要每一个证书 。

Make rollout 状态 。 “ 核准” 是指通过的证据政策。 “ 授权” 指目前选择该政策的途径。 “ 检疫” 指它无法接受新的工作。 “ 暂停” 指另一个被认可的版本正在激活。 不要将所有四个含义编码在一个布尔。

在曝光服务器前运行接收 `tools/list`否则客户可以在出版和政策之间出现差距时发现工具 evaluation.

<a id="interactive-lab"></a>

## 交互式实验

你会看到一个边界一次失败。

<a id="lab-a-namespace-collision"></a>

### 实验室 A: 命名空间碰撞

打开 a Python 代码目录中的 shell :

```bash
cd phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/code
python3 -q
```

跑步,快跑,快点跑

```python
from main import namespace_matches
namespace_matches("com.example/inventory", "com.example")
namespace_matches("com.exampleevil/inventory", "com.example")
```

第一项结果是 `True`;第二个是 `False`。将精确的比较替换为 `startswith` 并观察第二个名字为何跨越边界。 在继续之前恢复精确的比较 。

<a id="lab-b-descriptor-drift"></a>

### B实验室:说明性漂移

```python
from main import *
times = iter(f"2026-08-21T12:00:{n:02d}+00:00" for n in range(10))
c = RegistryAdmissionController(clock=lambda: next(times))
meta = {OFFICIAL_META_KEY: {"status": "active"}}
c.admit(sample_record("1.0.0"), meta, "com.example", evidence_for("1.0.0"), sample_live("1.0.0"))
c.check_live("com.example/inventory", "1.0.0", sample_live("1.0.0", True))
```

检查原因和路径状态。 软件包和注册记录没有改变。 运行时间工具表面确实改变了, 因此控制器隔离并禁用了插针。 这就是为什么安装后必须继续供应链控制 。

<a id="lab-c-status-and-rollback"></a>

### 实验室C:状态和 rollback

Admit `1.1.0`标记它已经退化, 并尝试两者 rollback targets:

```python
c.admit(sample_record("1.1.0"), meta, "com.example", evidence_for("1.1.0"), sample_live("1.1.0"))
c.observe_registry_status("com.example/inventory", "1.1.0", "deprecated")
c.rollback("com.example/inventory", "1.1.0", "unsafe retry")
c.rollback("com.example/inventory", "1.0.0", "restore known release")
c.ledger.verify()
```

拒绝隔离目标。 接受较早的活性针。 分类账仍然有效 。

<a id="practice-lab"></a>

## 练习实验

使用两个人扩展控制器 approval gate.

Requirements:

- 将批准作为签名的证据参考文件保存,而不是在插针中保留可变名称。
- 需要两个不同的审查者身份, 用于包含工具的 `destructiveHint: true`.
- 拒绝重复的审查身份 。
- 在批准不完整时保留分类账中的初始登录尝试。
- 添加零、一、重复和两个不同的批准测试。
- 不记录签名、 证书或完整的私人工具参数 。

成功意味着一个破坏性工具在两个身份批准准确记录、软件包和工具摘要之前不能生效。

<a id="shipped-artifact"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-registry-admission.md`。在审查新的书记官处版本或调查漂移时,使用它作为平坦、可重复使用的运行簿。它界定了输入、拒绝规则、证据包、状态对账和 rollback 无需取决于样本类名称的证明。

<a id="verify-it"></a>

## 验证

运行演示和确定性套房:

```bash
cd phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

核查应证明:

- 拒绝类似前缀的准确命名空间边框
- 只有正式命名空间登记状态才能使版本符合资格
- 未核实或错配的软件包和远程证据被拒绝
- 发布器元数据不能冒充由登记册管理的元数据
- 工具排序已正常化, 但不隐藏描述符更改
- 软件包和工具结构错误, 安全拒绝
- `serverInfo` 保留诊断权,从未提供入境许可
- 说明性漂移检疫、禁用和路障 rollback 转到针
- 状态更改隔离活性针
- rollback 无法选择隔离或未知版本
- 检测到分类账篡改

<a id="production-failure-modes"></a>

## 生产失败模式

| Failure | 为什么会发生这种情况 | 所需回应 |
|---|---|---|
| 名称看起来有效, 但名称空间从未认证 | 政策信任的记录文本 | 拒绝, 直到信任的命名空间验证器提供准确的前缀 |
| 同一软件包坐标返回新字节 | 可变上游或损耗的分布 | 停止激活, 保留两个摘要, 调查取回边界 |
| “最新”改动,未经审查 | 浮点数跳出针 | 只解决准确的被接纳版本和摘要 |
| 批准后出现新工具 | 运行时流或不同的部署 | 隔离路线并捕捉到一个新的描述器观察 |
| 预设版本仍然有效 | 状态同步缺失或延迟 | 在一个时间表上和激活前的调和状态 |
| 删除的记录从默认同步中消失 | 客户只要求活动记录 | 使用递增或删除的认知对账并保存本地历史 |
| Rollback 目标从未被接受 | 线路控制和批准状态已断开 | Refuse rollback 并运行目标的新注册 |
| 攻击者重写所有条目后, 账簿会在当地验证 | 散列链没有外部锚 | 将签名的分类账头发布到单独的信托域 |
| 证据包含持证人 tokens 工具参数 | 正在复制全部请求 | 收集时间重编, 只存储最小的证明 |

<a id="operational-rule"></a>

## 操作规则

发表答复“这个身份能公布这个名字吗?” 接纳答复“我们是否执行这个确切的文物,并揭露这种确切的行为?” rollback 选择证据而不是内存。

<a id="further-reading"></a>

## 进一步阅读

- [官方登记服务器。json requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md)
- [正式登记处](https://registry.modelcontextprotocol.io/openapi.yaml)
- [MCP 2026-07-28服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
