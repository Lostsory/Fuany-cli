import os
from types import SimpleNamespace

import pytest

from state import (
    FileSeen,
    get_depth,
    get_read_state,
    hash_content,
    reset_read_state,
    set_read_state,
)
from tools.files import edit, write
from tools.search import MAX_FILE_CHARS, read_file


@pytest.fixture
def read_state():
    state = {}
    token = set_read_state(state)
    try:
        yield state
    finally:
        reset_read_state(token)


@pytest.mark.parametrize("operation", ["edit", "write"])
@pytest.mark.parametrize("external_change", [False, True])
def test_file_guard_with_hash(tmp_path, read_state, operation, external_change):
    path = tmp_path / "example.txt"
    original = "你好，original\n"
    path.write_text(original, encoding="utf-8")
    read_file(str(path))
    seen = read_state[str(path)]
    assert seen.content_hash == hash_content(original)
    assert not hasattr(seen, "content")

    if external_change:
        path.write_text("外部修改\n", encoding="utf-8")
    # 显式改变时间，不依赖文件系统的时间精度或等待。
    os.utime(path, (seen.mtime + 10, seen.mtime + 10))
    result = (
        edit(str(path), "original", "edited")
        if operation == "edit"
        else write(str(path), "replacement\n")
    )
    if external_change:
        assert "文件已被外部修改" in result
        assert path.read_text(encoding="utf-8") == "外部修改\n"
    else:
        expected = "你好，edited\n" if operation == "edit" else "replacement\n"
        assert path.read_text(encoding="utf-8") == expected
        assert read_state[str(path)].content_hash == hash_content(expected)


def test_read_hashes_full_text_before_output_truncation(tmp_path, read_state):
    path = tmp_path / "large.txt"
    content = "文" * (MAX_FILE_CHARS + 1)
    path.write_text(content, encoding="utf-8")
    assert "已截断" in read_file(str(path))
    assert read_state[str(path)].content_hash == hash_content(content)


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("depth", [0, 1])
def test_agent_state_cleanup(monkeypatch, read_state, fails, depth):
    import mini_cc

    read_state["parent"] = FileSeen(0, hash_content("parent"))
    agent_state = {}
    parent_depth = get_depth()

    def create(**kwargs):
        assert get_read_state() is agent_state
        assert get_depth() == depth
        agent_state["file"] = FileSeen(0, hash_content("file"))
        if fails:
            raise RuntimeError("agent failed")
        delta = SimpleNamespace(content="done", tool_calls=None)
        return iter(
            [SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=delta)])]
        )

    monkeypatch.setattr(
        mini_cc,
        "build_llm",
        lambda: SimpleNamespace(
            client=SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=create))
            ),
            model="test",
            context_window=10000,
        ),
    )

    def run():
        return mini_cc.agent_answer(
            "test", [], read_state=agent_state, depth=depth, quiet=True, max_turns=2
        )

    if fails:
        with pytest.raises(RuntimeError, match="agent failed"):
            run()
    else:
        assert run().content == "done"
    if depth > 0:
        assert agent_state == {}
    else:
        assert "file" in agent_state
    assert get_read_state() is read_state
    assert get_depth() == parent_depth
    assert "parent" in read_state
