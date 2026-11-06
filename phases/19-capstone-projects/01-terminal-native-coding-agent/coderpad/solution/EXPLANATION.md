# 参考解释：Capstone 01 — Terminal-Native Coding Agent

## 核心：精确命令策略

逐参数精确比较，不执行命令，也不把字符串前缀匹配当成授权。

准确合同：Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing.

## 加分：词法路径包含边界

使用栈处理词法路径分量，任何越过 root 的动作立即拒绝；这不能验证 symlink。

准确合同：Use POSIX lexical paths only: root must be absolute, relative must not be absolute. Normalize '.' and '..'; reject any attempt to pop above root with ValueError. Return normalized absolute path string. No filesystem or symlink checks are made. root is already normalized without trailing slash except '/'.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
