import json
from types import SimpleNamespace as NS

import pytest

import mini_cc
from events import AgentEvent


def chunk(*, content=None, calls=None):
    return NS(usage=None, choices=[NS(delta=NS(content=content, tool_calls=calls))])


@pytest.mark.parametrize(
    "names", [["tool_search"], ["tool_search", "read_file"], ["bash"]]
)
def test_agent_emits_tool_events_and_discovers_tools(monkeypatch, names):
    requests = []
    calls = [
        NS(index=i, id=f"call-{i}", function=NS(name=name, arguments="{}"))
        for i, name in enumerate(names)
    ]

    def create(**kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            return iter([chunk(calls=calls)])
        return iter([chunk(content="完成")])

    monkeypatch.setattr(
        mini_cc,
        "build_llm",
        lambda: NS(
            client=NS(chat=NS(completions=NS(create=create))),
            model="test",
            context_window=10000,
        ),
    )
    monkeypatch.setattr(
        mini_cc,
        "call_tool",
        lambda name, args: (
            json.dumps({"matches": ["web_search"]}) if name == "tool_search" else "ok"
        ),
    )
    events: list[AgentEvent] = []
    messages = [{"role": "system", "content": "test"}]
    terminal = mini_cc.agent_answer(
        "test", messages, quiet=True, on_event=events.append, max_turns=3
    )
    assert terminal.content == "完成"
    assert [e["name"] for e in events if e["type"] == "tool_start"] == names
    assert [e["name"] for e in events if e["type"] == "tool_end"] == names
    assert events[-1] == {"type": "delta", "content": "完成"}
    initial = {t["function"]["name"] for t in requests[0]["tools"]}
    following = {t["function"]["name"] for t in requests[1]["tools"]}
    assert "web_search" not in initial
    assert ("web_search" in following) == ("tool_search" in names)
