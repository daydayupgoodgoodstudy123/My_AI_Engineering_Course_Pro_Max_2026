# 参考解释：The Harness as a Library — Subagents and Session Store

## 核心：独立权限与批准

批准不能绕过独立 capability 授权；allow 也不代表已经执行或被 OS 隔离。

准确合同：If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes.

## 加分：词法路径包含边界

使用栈处理词法路径分量，任何越过 root 的动作立即拒绝；这不能验证 symlink。

准确合同：Use POSIX lexical paths only: root must be absolute, relative must not be absolute. Normalize '.' and '..'; reject any attempt to pop above root with ValueError. Return normalized absolute path string. No filesystem or symlink checks are made. root is already normalized without trailing slash except '/'.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
