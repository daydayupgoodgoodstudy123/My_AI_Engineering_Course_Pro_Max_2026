# 参考解释：Dev Environment

## 核心：开发环境探针汇总

缺失探针与执行失败是不同问题；有退出码零但没有输出也不能报告就绪。

准确合同：probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run.

## 加分：版本兼容判断

把版本拆成整数元组后比较，避免 3.9 在字符串比较中大于 3.10。

准确合同：version and minimum are strings of exactly three nonnegative decimal components separated by dots. Reject malformed strings with ValueError. Return version tuple>=minimum tuple and version major<=maximum_major; maximum_major is an exact nonnegative integer or raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
