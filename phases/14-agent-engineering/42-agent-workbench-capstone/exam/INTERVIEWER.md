# 面试官手册：WBPack（14/42）

候选人计时期间不要看。候选人手里只有 README、`wbpack/` 和 `tests/`。

## 开场（2 分钟）

- 时长 60 分钟，请候选人说出思路、随时澄清，可以查官方文档。
- 目标是原样通过测试，不要求全部做完。记录每关时间和 pytest 次数。
- 每关卡住约 5 分钟时，一次给一级提示，不代写代码。

## 澄清问题的标准答案

只在候选人问到时用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 安装失败要回滚吗？ | "Part 1 preserves the old version marker but does not undo completed copies. Part 4 implements rollback separately." |
| 1 | force 能删除团队自己的文件吗？ | "No. Copy only owned paths, keep unlisted files and report them." |
| 2 | TSV 字段可以包含什么？ | "Use Python csv TSV quoting. Preserve Unicode, spaces, row order, digests, components and integer permission bits." |
| 3 | schema 变化总是 major 吗？ | "Yes in this exercise. Script changes listed in migration_paths are also major; other runtime changes are minor." |
| 3 | 版本可以跳着发布吗？ | "Use exactly the next classified increment. A major or minor resets its lower fields." |
| 3 | 本地删除文件算修改吗？ | "Yes. Do not recreate a locally deleted file when upstream is unchanged." |
| 4 | itemize 码是 rsync 标准吗？ | "No. They are the four private codes documented in _line and parsed by this test." |
| 4 | 注入的写入失败会部分写坏文件吗？ | "The hook raises before that operation mutates disk. Roll back only completed non-skip operations." |
| 5 | 未选中的坏组件要检查吗？ | "No. Only validate the requested reference closure." |

## 每关：要看什么、提示、追问

### Part 1 安装器（目标 12 分钟）

坑：
1. `_ci_enabled` 只检查 `.github`，调用它的 `_ci_files` 随后枚举不存在的 workflows，抛 FileNotFoundError。
2. 拒绝覆盖只看 AGENTS.md，团队已有的规则文档会被静默覆盖。
3. 未管理文件按 basename 判断，嵌套目录里同名的团队文档没有进入报告。
4. 复制前写版本锁，第二个文件复制失败时锁声称新版已经安装。
5. 变更预览为每个包路径重扫整个仓库清单。应对 24000 个路径和 2200 个包路径做一次索引。

护栏：索引必须按完整相对路径；force 保留团队文件。性能限值 0.08 秒，慢/快版本的本机多次实测均留出至少 8 倍余量。

看什么：先读 traceback，理解 pack 拥有的路径，再修失败原子边界；每次只修一层。

提示：
- H1："Which precondition makes the workflows listing safe?"
- H2："What exactly does the version marker promise after a failed copy?"
- H3：指出 CI 条件、已有文件预检查和版本写入位置。

追问："What would you need to make the whole installer atomic across a crash?"（事务日志、暂存与恢复；Part 4 只模拟进程内回滚。）

### Part 2 清单（目标 10 分钟）

坑：
- 权限整数要用八进制写进 TSV，再按八进制读回，0755 不是十进制 755。
- 每个损坏或缺失的清单项都要报出具体路径，不能遇到第一个错误就返回。
- 再次保存要替换清单，不能把两版包的文件混起来。

顺带覆盖带空格与非 ASCII 的路径、字段原样往返、顺序和空包。TSV quoting 直接使用 csv，不把手写转义作为主坑。

追问："What does a matching digest prove about provenance?"（只证明字节一致；不证明发布者可信，签名另议。）

### Part 3 版本与三方升级（目标 15 分钟）

坑：
- 先看文件变化的责任组件与 migration_paths，再选 none/patch/minor/major；移除 schema 也算变化。
- local、base、incoming 三方比较；双方都变成相同新内容时无冲突，本地删除也必须保护。
- 上游删除但本地改过时不能删；上游新增撞上不同的本地文件时也不是干净新增。
- 版本字段是数字；minor 跨 9 到 10，major/minor 都重置低位。

权限变化、完全未变和用户独有文件作为顺带检查。

提示：先列出三方相等关系，再为每种关系命名。

追问："How do you turn the plan into a migration runbook?"（先解 conflict、备份状态、执行 major 迁移、校验、最后发布版本锁。）

### Part 4 安装日志（目标 13 分钟）

坑：
- 一次操作完成后马上 yield，不能先读完整个操作源。
- undo log 只记录完成的非 skip 操作，按相反顺序恢复；失败那一步还没有改盘。
- 回滚要恢复原字节和权限，新建的文件应消失，被删的文件应回来。
- dry-run 使用相同前向日志，既不写盘也不调写入钩子。

路径中的空格由整行保留；四个码是题目私有格式。测试检查精确行内容。

追问："What happens if rollback itself fails?"（保留可恢复日志并报告未恢复项；本题未模拟这一层。）

### Part 5 组件闭包（目标 10 分钟）

坑：
- 从所选组件自动引入全部引用，依赖在前；共享 schema 只装一次。
- 排除策略在间接引用上同样生效，要给出从请求到被排除文件的完整路径。
- 只走可达部分；无关的缺失引用不能阻止安装。
- requires 和 requested 的顺序决定独立组件的输出顺序。

循环与缺失组件错误作为结构边界；不会读取磁盘目录树或解压归档。

追问："How do you find references in a real pack?"（显式组件元数据或静态校验；不能靠猜文档中的任意文本。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | traceback、实际数据、一次修一处、定向重跑 |
| 代码质量 | 15 | 修根因，明确 pack 所有权和失败边界 |
| 沟通 | 15 | 复述需求、主动澄清、解释取舍 |
| 生产意识 | 10 | 迁移、发布来源、崩溃恢复和回滚失败 |

每项记录具体证据，没观察到写“未观察”。提示次数和用时单独记。
