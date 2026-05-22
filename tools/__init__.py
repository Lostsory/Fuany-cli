"""工具包：import 任一子模块即触发它顶层的 @register —— 工具「自动发现」。

对照 Hermes：model_tools.py 被 import 时，各 tools/*.py 顶层的
registry.register(...) 自动执行完成注册，无需手维护一份 import 列表。
这里把那个机制做成最小版：入口 `import tools` 一句，下面列出的模块全部加载、
其顶层 @register 全部生效。

加一组新工具 = 新建 tools/xxx.py + 在这里加一行 `from . import xxx`。
（这就是判据「加工具只改一处」里那"一处"的体现 —— 加的是模块，不碰循环。）
"""

from . import (
    files,
    search,  # noqa: F401  # import 即注册，别删这行
    shell,
    skill,
    task,
    web,
)
