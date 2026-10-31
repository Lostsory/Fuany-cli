import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import server
from mini_cc import TurnTerminal
from registry import _ask_permission


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "DEEPSEEK_API_KEY", "test-key")
    server.sessions.clear()
    with TestClient(server.app) as client:
        yield client
    server.sessions.clear()


def session_id(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()["id"]


def stream_events(response):
    assert response.status_code == 200
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_stream_and_history(client, monkeypatch):
    def fake_agent(question, messages, **kwargs):
        messages.append({"role": "user", "content": question})
        kwargs["on_event"]({"type": "delta", "content": "你好"})
        messages.append({"role": "assistant", "content": "你好"})
        return TurnTerminal(reason="completed", content="你好")

    monkeypatch.setattr(server, "agent_answer", fake_agent)
    sid = session_id(client)
    events = stream_events(
        client.post(f"/api/sessions/{sid}/chat", json={"message": "你好"})
    )
    assert [e["type"] for e in events] == ["delta", "done"]
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["title"] == "你好"
    assert not detail["busy"]
    assert detail["events"][0] == {"type": "user", "content": "你好"}
    assert len(server.sessions[sid].messages) == 3


@pytest.mark.parametrize("allowed", [True, False])
def test_browser_permission_and_concurrent_guard(client, monkeypatch, allowed):
    def fake_agent(question, messages, **kwargs):
        decision = _ask_permission("write_file", {"path": "example.txt"})
        kwargs["on_event"]({"type": "delta", "content": str(decision)})
        return TurnTerminal(reason="completed", content=str(decision))

    monkeypatch.setattr(server, "agent_answer", fake_agent)
    sid = session_id(client)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post, f"/api/sessions/{sid}/chat", json={"message": "write"}
        )
        deadline = time.monotonic() + 5
        approval_id = None
        while time.monotonic() < deadline:
            with server.sessions[sid].lock:
                approval_id = next(iter(server.sessions[sid].approvals), None)
            if approval_id:
                break
            time.sleep(0.01)
        assert approval_id
        assert (
            client.post(
                f"/api/sessions/{sid}/chat", json={"message": "another"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/sessions/{sid}/approvals/{approval_id}",
                json={"allowed": allowed},
            ).status_code
            == 200
        )
        events = stream_events(future.result(timeout=5))
    assert next(e for e in events if e["type"] == "delta")["content"] == str(allowed)
    assert (
        client.post(
            f"/api/sessions/{sid}/approvals/{approval_id}", json={"allowed": True}
        ).status_code
        == 404
    )


def test_error_rolls_back_model_history(client, monkeypatch):
    def broken_agent(question, messages, **kwargs):
        messages.append({"role": "user", "content": question})
        raise RuntimeError("provider failure")

    monkeypatch.setattr(server, "agent_answer", broken_agent)
    sid = session_id(client)
    events = stream_events(
        client.post(f"/api/sessions/{sid}/chat", json={"message": "test"})
    )
    assert events[-1]["type"] == "error"
    assert len(server.sessions[sid].messages) == 1
    assert not server.sessions[sid].busy


def test_validation_and_origin(client):
    sid = session_id(client)
    assert (
        client.post(f"/api/sessions/{sid}/chat", json={"message": " "}).status_code
        == 422
    )
    assert client.get("/api/sessions/missing").status_code == 404
    assert (
        client.post(
            "/api/sessions", headers={"origin": "https://example.com"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/sessions", headers={"origin": "http://testserver"}
        ).status_code
        == 201
    )


def test_missing_key(client, monkeypatch):
    monkeypatch.setattr(server, "DEEPSEEK_API_KEY", None)
    monkeypatch.setattr(server, "PROVIDER", "deepseek")
    sid = session_id(client)
    assert (
        client.post(f"/api/sessions/{sid}/chat", json={"message": "hi"}).status_code
        == 503
    )
    assert not server.sessions[sid].busy
