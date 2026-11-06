# 我的 AI Engineering 学习课程

完整个人学习副本，包含 **Phase 00–20 的 21 个阶段、543 个编号小节**，以及本地已有的中文教材、代码讲解、测验、CoderPad、分关练习和学习笔记。

## 从这里开始

- [中英双语课程总目录](phases/000-总目录/README.md)：逐节查看掌握目标、课程衔接、为什么有用及建议练习。
- [个人学习笔记](phases/2026%20-%20学习笔记/README.md)：回顾已有笔记与自测。
- [中文教材索引](phases/中文教程索引.md)：直接进入中文讲义。
- [CoderPad 总入口](CODERPAD_INDEX.md)：选择独立编码练习。
- [课程原始主文档](COURSE_README.md)与[路线图](ROADMAP.md)：查看原课程说明与结构。

## 当前学习入口

- [Phase 13 工具与协议](phases/000-总目录/13-工具与协议.md)
- [13.02 Function Calling 深入比较](phases/13-tools-and-protocols/02-function-calling-deep-dive/docs/en.md)
- [13.02 CoderPad](phases/13-tools-and-protocols/02-function-calling-deep-dive/coderpad/README.md)
- [13.01 分关练习](phases/13-tools-and-protocols/01-the-tool-interface/exam/README.md)

## 怎样练习

`docs/` 是教材，`code/` 是课堂实现，`coderpad/` 是有限范围的编码练习，`exam/` 是实际存在的分关题，`outputs/` 是课程提供的可复用材料。每套题的输入输出和限制以它的 README、PROMPT 为准。

以当前课程为例，从仓库根目录运行：

```bash
python3 phases/13-tools-and-protocols/02-function-calling-deep-dive/code/main.py
cd phases/13-tools-and-protocols/02-function-calling-deep-dive/coderpad
python3 run_tests.py --list
python3 run_tests.py --core
```

`--list` 只收集测试；初始 starter 的 TODO 失败属于待完成练习。独立作答期间先关闭 `solution/` 与面试官材料；`--solution` 验证参考答案，不能作为自己的完成记录。分关题按各课说明逐关解锁，全部 skipped 不代表通过。

中文讲义是辅助阅读材料，遇到术语或数字疑问请对照英文。历史验证文件不代表本次学习已运行或通过；Phase 20 的 09–12 原本缺少正文，总目录已标注现存代码入口。

## 同步范围

同步课程正文、代码、练习、项目及辅助脚本。PDF、`phases-pdf/` 导出目录、安装包、虚拟环境、缓存、模型权重与本地密钥通过 `.gitignore` 或同步筛选排除。PDF 仍保存在本地课程目录中。

上游自动翻译、电子书和网站发布 workflows 未导入本个人学习副本。`site/data.js`、`catalog.json` 与 lockfile 等生成物不作为学习源文件提交。

## 来源与许可

原始课程来自 [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)，上游基础版本为 `5b5ab48cd63d7ae5b4002985d9ac9de4ed86c2c0`，同时包含本地已有的学习增补。原作者版权和 MIT 许可保留于 [LICENSE](LICENSE)。本仓库的提交历史继续保留此前的 Phase 13 学习快照。
