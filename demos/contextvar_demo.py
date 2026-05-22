"""ContextVar 父子 read_state 隔离 demo —— 教学独立文件。

模拟 mini-cc 真实的 read_state 机制(state.py:_read_state_var),展示:
- 父子 agent 各有自己的 dict
- 嵌套 set/reset 自动栈式恢复
- 工具函数 (read_file) 不显式传 state,通过 get_state() 拿当前层的

1:1 对应关系:
  Demo `_state_var`           ↔ state.py:_read_state_var
  Demo `get_state()`          ↔ state.py:get_read_state()
  Demo `agent_answer()`       ↔ mini_cc.py:agent_answer()
  Demo `read_file()`          ↔ tools/search.py:read_file()
  Demo "spawn_child" 路径     ↔ tools/task.py:task() 调子 agent_answer

跑法:
    python demos/contextvar_demo.py
(从 mini-claude-code 目录,无外部依赖)
"""

from contextvars import ContextVar

# ============================================
# 模块级 ContextVar(对应 state.py:_read_state_var)
# ============================================
_state_var: ContextVar[dict] = ContextVar("state")


def get_state() -> dict:
    """对应 state.py:get_read_state()。"""
    try:
        return _state_var.get()
    except LookupError:
        return {"__不存在__": True}  # 没 set 过


def set_state(d: dict):
    """对应 state.py:set_read_state()。"""
    return _state_var.set(d)


def reset_state(token):
    """对应 state.py:reset_read_state()。"""
    _state_var.reset(token)


# ============================================
# 模拟工具(对应 tools/search.py:read_file)
# 注意:工具不显式传 state 参数,通过 get_state() 拿
# ============================================
def read_file(name: str):
    state = get_state()
    state[name] = f"content_of_{name}"
    print(f"    📖 read_file({name!r}): id(state)={id(state)} state={state}")


# ============================================
# 模拟 agent_answer(对应 mini_cc.py:agent_answer)
# ============================================
def agent_answer(label: str, ops: list, *, read_state=None):
    print(f"\n{'─' * 50}")
    print(f">>> 进 [{label}] agent_answer")

    # 跟 mini_cc.py 一模一样的逻辑:
    if read_state is None:
        read_state = {}
        print(f"    [{label}] read_state=None,新建空 dict id={id(read_state)}")
    else:
        print(f"    [{label}] 拿到外部传入 read_state id={id(read_state)}")

    token = set_state(read_state)
    print(f"    [{label}] set_state 完成,此时 get_state() = {get_state()}")
    print(f"    [{label}] 也就是 id={id(get_state())}(同上面新建的 dict)")

    try:
        for op in ops:
            if op.startswith("read:"):
                file = op.split(":", 1)[1]
                read_file(file)
            elif op == "spawn_child":
                print(f"\n    [{label}] >>>>>> 调 task,spawn 子 agent <<<<<<")
                # 对应 tools/task.py:task() 调子 agent_answer
                agent_answer("child", ["read:b.py", "read:d.py"], read_state={})
                print(f"    [{label}] 子完成回来,我现在 get_state() = {get_state()}")
                print(
                    f"    [{label}] id={id(get_state())} —— "
                    f"{'还是父的!' if id(get_state()) == id(read_state) else '怎么变了??'}"
                )
    finally:
        reset_state(token)
        print(f"<<< [{label}] 退出 agent_answer,reset 后 get_state() = {get_state()}")


# ============================================
# 主流程
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("ContextVar 父子 read_state 隔离 demo")
    print("=" * 60)
    print(f"\n初始(还没进任何 agent),get_state() = {get_state()}")
    print("(注:'__不存在__' = ContextVar 还没 set 过)")
    # 模拟用户问:父读 a.py,spawn 子(子读 b.py + d.py),父继续读 c.py
    agent_answer(
        "parent",
        [
            "read:a.py",  # 父读 a.py
            "spawn_child",  # 调子(子内部读 b.py 和 d.py)
            "read:c.py",  # 子完成后,父继续读 c.py
        ],
    )

    print(f"\n所有 agent 完成后,get_state() = {get_state()}")

    print("\n" + "=" * 60)
    print("关键观察点(对照输出):")
    print("=" * 60)
    print(
        """
1. 父 set_state({}) 后,父的 read_file('a.py') 写进的是父的 dict
2. 调 spawn_child → 子 agent_answer 内 set_state({}),
   此时 get_state() 返回的是子的新 dict(id 跟父的不一样)
3. 子的 read_file('b.py') / read_file('d.py') 写进子的 dict,
   父的 dict 完全没动(里面还只有 a.py)
4. 子 finally reset_state(token_child) 后,
   父继续 get_state() 拿到的是父的 dict(a.py 还在,id 跟最初一样)
5. 父 read_file('c.py') 写进父的 dict,
   现在父的 dict 有 a.py + c.py(子的 b.py / d.py 没出现)
6. 父 finally reset_state(token_parent) 后,_var 回到 unset 状态
   get_state() 返回 {'__不存在__': True}

—————————————————————————————————————————————————————————
这就是 ContextVar 的红利:
- 工具函数 read_file 不需要 state 参数
- 每层 agent 进 try 时 set 自己的 dict
- 嵌套调用自动 push,出 try 自动 pop
- 父子 dict 是不同对象(id 不同),互不污染
"""
    )
