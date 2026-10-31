"""Local web interface for the existing CLI agent (one uvicorn worker)."""

import asyncio
import copy
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from config import DEEPSEEK_API_KEY, SYSTEM
from events import SessionEvent
from llm import PROVIDER, _CONFIG
from mini_cc import agent_answer
from registry import permission_handler
from state import FileSeen

app = FastAPI(title="Fuany", version="0.1.0")
logger = logging.getLogger(__name__)


@dataclass
class Approval:
    ready: threading.Event = field(default_factory=threading.Event)
    allowed: bool = False


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "新对话"
    messages: list[ChatCompletionMessageParam] = field(
        default_factory=lambda: [{"role": "system", "content": SYSTEM}]
    )
    events: list[SessionEvent] = field(default_factory=list)
    read_state: dict[str, FileSeen] = field(default_factory=dict)
    busy: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    approvals: dict[str, Approval] = field(default_factory=dict)


sessions: dict[str, Session] = {}
sessions_lock = threading.Lock()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=50_000)


class ApprovalRequest(BaseModel):
    allowed: bool


@app.middleware("http")
async def local_origin_only(request: Request, call_next):
    # Same-origin UI + Vite dev proxy. Never allow arbitrary websites to run tools.
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
        from starlette.responses import JSONResponse

        return JSONResponse(
            {"detail": "Cross-origin requests are disabled"}, status_code=403
        )
    return await call_next(request)


def get_session(session_id: str) -> Session:
    with sessions_lock:
        session = sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在，请新建对话")
    return session


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model": _CONFIG[PROVIDER]["model"],
        "configured": PROVIDER != "deepseek" or bool(DEEPSEEK_API_KEY),
        "workspace": Path.cwd().name,
    }


@app.get("/api/sessions")
def list_sessions():
    with sessions_lock:
        snapshot = list(sessions.values())
    return [{"id": s.id, "title": s.title, "busy": s.busy} for s in snapshot]


@app.post("/api/sessions", status_code=201)
def create_session():
    session = Session()
    with sessions_lock:
        sessions[session.id] = session
    return {"id": session.id, "title": session.title, "busy": False}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str):
    session = get_session(session_id)
    with session.lock:
        return {
            "id": session.id,
            "title": session.title,
            "busy": session.busy,
            "events": copy.deepcopy(session.events),
        }


@app.post("/api/sessions/{session_id}/approvals/{approval_id}")
def approve(session_id: str, approval_id: str, body: ApprovalRequest):
    session = get_session(session_id)
    with session.lock:
        approval = session.approvals.pop(approval_id, None)
        if approval is None:
            raise HTTPException(404, "该授权已处理或已过期")
        approval.allowed = body.allowed
        approval.ready.set()
    return {"ok": True}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest):
    session = get_session(session_id)
    question = body.message.strip()
    if not question:
        raise HTTPException(422, "消息不能为空")
    if PROVIDER == "deepseek" and not DEEPSEEK_API_KEY:
        raise HTTPException(503, "请先在 .env 中配置 DEEPSEEK_API_KEY，然后重启后端")
    with session.lock:
        if session.busy:
            raise HTTPException(409, "该会话仍在执行中")
        session.busy = True
        if session.title == "新对话":
            session.title = question[:32]
        session.events.append({"type": "user", "content": question})

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[SessionEvent | None] = asyncio.Queue()
    disconnected = threading.Event()

    def emit(event: SessionEvent) -> None:
        if disconnected.is_set():
            raise InterruptedError("客户端已断开")
        with session.lock:
            session.events.append(event)
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def ask(name: str, args: dict[str, object]) -> bool:
        approval_id = str(uuid4())
        approval = Approval()
        with session.lock:
            session.approvals[approval_id] = approval
        try:
            emit({"type": "approval", "id": approval_id, "name": name, "args": args})
            for _ in range(300):
                if approval.ready.wait(1):
                    emit(
                        {
                            "type": "approval_resolved",
                            "id": approval_id,
                            "allowed": approval.allowed,
                        }
                    )
                    return approval.allowed
                if disconnected.is_set():
                    return False
            emit({"type": "approval_resolved", "id": approval_id, "allowed": False})
            return False
        finally:
            with session.lock:
                session.approvals.pop(approval_id, None)
                if not any(
                    event["type"] == "approval_resolved" and event["id"] == approval_id
                    for event in session.events
                ):
                    session.events.append(
                        {
                            "type": "approval_resolved",
                            "id": approval_id,
                            "allowed": False,
                        }
                    )

    def run():
        previous_messages = copy.deepcopy(session.messages)
        token = permission_handler.set(ask)
        try:
            terminal = agent_answer(
                question,
                session.messages,
                read_state=session.read_state,
                quiet=True,
                on_event=emit,
            )
            emit(
                {
                    "type": "done",
                    "reason": terminal.reason,
                    "content": terminal.content,
                    "turn_count": terminal.turn_count,
                    "limit_tokens": terminal.limit_tokens,
                    "grace_used": terminal.grace_used,
                }
            )
        except Exception as exc:
            session.messages[:] = previous_messages
            session.read_state.clear()
            if disconnected.is_set():
                with session.lock:
                    session.events.append(
                        {
                            "type": "error",
                            "content": "连接已断开，本次对话已中断。已完成的工具操作仍然生效。",
                        }
                    )
            elif not isinstance(exc, InterruptedError):
                logger.exception("Agent run failed")
                emit(
                    {
                        "type": "error",
                        "content": "请求失败，请检查后端配置或网络后重试。",
                    }
                )
        finally:
            permission_handler.reset(token)
            with session.lock:
                session.busy = False
                for approval in session.approvals.values():
                    approval.ready.set()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    async def stream():
        worker = asyncio.create_task(asyncio.to_thread(run))
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            disconnected.set()
            # Let an in-flight tool finish; never mark the session idle prematurely.
            worker.add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Build frontend first to serve the full app from http://127.0.0.1:8000.
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


def main():
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000)
