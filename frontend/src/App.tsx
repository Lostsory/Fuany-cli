import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  Check,
  ChevronDown,
  Code2,
  Command,
  FileCode2,
  FolderOpen,
  Globe,
  LoaderCircle,
  Menu,
  MessageSquare,
  Plus,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";
import type { ApprovalEvent, SessionEvent, ToolStartEvent } from "./events";

type Session = { id: string; title: string; busy: boolean };
type Health = { model: string; configured: boolean; workspace: string };
type Item = {
  role: "user" | "assistant";
  content: string;
  tools: (ToolStartEvent & { result?: string })[];
  error?: string;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `请求失败 (${response.status})`,
    );
  }
  return response.json();
}

function renderEvents(events: SessionEvent[]): Item[] {
  const items: Item[] = [];
  for (const event of events) {
    if (event.type === "user") {
      items.push({ role: "user", content: event.content, tools: [] });
      items.push({ role: "assistant", content: "", tools: [] });
      continue;
    }
    const item = items.at(-1);
    if (!item || item.role !== "assistant") continue;
    if (event.type === "delta") item.content += event.content;
    if (event.type === "tool_start") item.tools.push({ ...event });
    if (event.type === "tool_end") {
      const tool = item.tools.find((tool) => tool.id === event.id);
      if (tool) tool.result = event.result;
    }
    if (event.type === "error") item.error = event.content;
    if (
      event.type === "done" &&
      (!item.content || event.reason !== "completed")
    ) {
      item.content += `${item.content ? "\n\n" : ""}${event.content}`;
    }
  }
  return items;
}

const suggestions = [
  {
    icon: Code2,
    title: "读懂这个项目",
    text: "梳理目录结构与核心实现",
    prompt: "帮我梳理当前项目的目录结构、技术栈和核心运行流程。",
  },
  {
    icon: FileCode2,
    title: "一起写点代码",
    text: "从一个想法开始实现",
    prompt:
      "先阅读当前项目，帮我找出一个值得改善的用户体验问题，给我一个具体实现方案。",
  },
  {
    icon: Terminal,
    title: "排查一个问题",
    text: "定位原因，找到解决办法",
    prompt: "帮我检查当前项目中可能存在的问题，先阅读代码，给出有依据的分析。",
  },
  {
    icon: Globe,
    title: "探索新知识",
    text: "搜索资料，收集灵感",
    prompt: "搜索 React 和 FastAPI 的官方文档，整理前后端流式聊天的实现思路。",
  },
];

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [sidebar, setSidebar] = useState(false);
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const eventsRef = useRef<SessionEvent[]>([]);
  const pending = useRef(false);

  useEffect(() => {
    Promise.all([api<Health>("/health"), api<Session[]>("/sessions")])
      .then(([info, list]) => {
        setHealth(info);
        setSessions(list.reverse());
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (busy) return;
        setActive(null);
        eventsRef.current = [];
        setEvents([]);
        setDraft("");
        setError("");
        setSidebar(false);
        input.current?.focus();
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [busy]);

  function replaceEvents(next: SessionEvent[]) {
    eventsRef.current = next;
    setEvents(next);
  }
  function appendEvent(event: SessionEvent) {
    replaceEvents([...eventsRef.current, event]);
  }

  async function openSession(id: string) {
    if (pending.current) return;
    setLoading(true);
    setError("");
    setSidebar(false);
    try {
      const session = await api<Session & { events: SessionEvent[] }>(
        `/sessions/${id}`,
      );
      setActive(id);
      replaceEvents(session.events);
      setBusy(session.busy);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    if (pending.current || busy) return;
    setActive(null);
    replaceEvents([]);
    setDraft("");
    setError("");
    setSidebar(false);
    input.current?.focus();
  }

  async function send(message = draft) {
    const question = message.trim();
    if (!question || pending.current || busy || loading) return;
    pending.current = true;
    setStreaming(true);
    setBusy(true);
    setError("");
    setDraft("");
    try {
      let id = active;
      if (!id) {
        const session = await api<Session>("/sessions", { method: "POST" });
        id = session.id;
        setActive(id);
        setSessions((list) => [
          { ...session, title: question.slice(0, 32) },
          ...list,
        ]);
      }
      const response = await fetch(`/api/sessions/${id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail ?? "请求失败");
      }
      if (!response.body) throw new Error("浏览器不支持流式响应");
      appendEvent({ type: "user", content: question });
      setSessions((list) =>
        list.map((s) =>
          s.id === id && s.title === "新对话"
            ? { ...s, title: question.slice(0, 32) }
            : s,
        ),
      );
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finished = false;
      try {
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value, { stream: !done });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            if (!frame.startsWith("data: ")) continue;
            const event: SessionEvent = JSON.parse(frame.slice(6));
            appendEvent(event);
            if (event.type === "done" || event.type === "error")
              finished = true;
          }
          if (done) break;
        }
        if (!finished) throw new Error("连接中断，请刷新会话查看状态");
      } finally {
        reader.releaseLock();
      }
    } catch (e) {
      setError((e as Error).message);
      setDraft(question);
    } finally {
      pending.current = false;
      setStreaming(false);
      setBusy(false);
      input.current?.focus();
    }
  }

  const approval = events.find(
    (e): e is ApprovalEvent =>
      e.type === "approval" &&
      !events.some(
        (other) => other.type === "approval_resolved" && other.id === e.id,
      ),
  );
  async function approve(allowed: boolean) {
    if (!approval || !active) return;
    setSubmittingApproval(true);
    try {
      await api(`/sessions/${active}/approvals/${approval.id}`, {
        method: "POST",
        body: JSON.stringify({ allowed }),
      });
      appendEvent({ type: "approval_resolved", id: approval.id, allowed });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmittingApproval(false);
    }
  }

  const items = renderEvents(events);
  const title = sessions.find((s) => s.id === active)?.title ?? "新对话";
  return (
    <div className="app-shell">
      {sidebar && (
        <button
          className="sidebar-scrim"
          aria-label="关闭侧边栏"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className={`sidebar ${sidebar ? "is-open" : ""}`}>
        <a
          className="brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            newChat();
          }}
        >
          <span className="brand-mark">
            <Command size={20} />
          </span>
          fuany<span className="brand-tag">WORKSPACE</span>
        </a>
        <button className="new-chat" onClick={newChat} disabled={busy}>
          <Plus size={17} />
          新建对话<span>⌘ K</span>
        </button>
        <div className="nav-label">你的工作空间</div>
        <div className="workspace">
          <FolderOpen size={16} />
          <span>{health?.workspace ?? "Fuany-cli"}</span>
          <span className="local-badge">本地</span>
        </div>
        <div className="nav-label history-label">
          最近对话 <span>{sessions.length.toString().padStart(2, "0")}</span>
        </div>
        <nav className="history" aria-label="最近对话">
          {sessions.length === 0 && (
            <p className="history-empty">
              新的想法，从这里开始。
              <br />
              你的对话会显示在这里。
            </p>
          )}
          {sessions.map((session) => (
            <button
              disabled={busy || loading}
              key={session.id}
              onClick={() => openSession(session.id)}
              className={active === session.id ? "selected" : ""}
            >
              <MessageSquare size={15} />
              <span>{session.title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection">
            <span className={`status-dot ${health ? "" : "offline"}`} />
            {health ? "本地工作空间已连接" : "等待后端连接"}
          </div>
          <div className="profile">
            <span className="avatar">Q</span>
            <div>
              个人工作空间<small>让想法一步步成形</small>
            </div>
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>
      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-path">
            <button
              className="mobile-menu icon-button"
              aria-label="打开侧边栏"
              onClick={() => setSidebar(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">工作空间</span>
            <span className="breadcrumb">/</span>
            <span className="conversation-title">{title}</span>
          </div>
          <span className="private-note">
            <ShieldCheck size={14} />
            本地运行 · 由你掌控
          </span>
        </header>
        <div className={`conversation ${items.length ? "has-messages" : ""}`}>
          {!items.length ? (
            <section className="welcome">
              <div className="welcome-eyebrow">
                <span /> YOUR IDEAS, IN MOTION
              </div>
              <div className="welcome-symbol">
                <Command size={31} strokeWidth={1.5} />
              </div>
              <h1>
                从一个想法，
                <br />
                <span>到下一步行动。</span>
              </h1>
              <p className="welcome-description">
                你的 AI 编程伙伴。读代码、解问题、实现想法，
                <br className="desktop-break" />
                在熟悉的工作空间里，把事情一步步做好。
              </p>
              <div className="suggestions">
                {suggestions.map(({ icon: Icon, title, text, prompt }) => (
                  <button
                    key={title}
                    onClick={() => {
                      setDraft(prompt);
                      input.current?.focus();
                    }}
                    disabled={loading}
                  >
                    <Icon size={19} strokeWidth={1.6} />
                    <ArrowUpRight className="suggestion-arrow" size={16} />
                    <strong>{title}</strong>
                    <span>{text}</span>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section
              className="messages"
              aria-label="对话消息"
              aria-busy={busy}
            >
              {items.map((item, i) => (
                <article key={i} className={`message ${item.role}`}>
                  <div
                    className={`message-avatar ${item.role === "assistant" ? "agent-avatar" : ""}`}
                  >
                    {item.role === "assistant" ? <Command size={17} /> : "Q"}
                  </div>
                  <div className="message-body">
                    <div className="message-label">
                      {item.role === "assistant" ? "Fuany" : "你"}
                      {item.role === "assistant" && <span>AI 伙伴</span>}
                    </div>
                    {item.content && (
                      <div className="markdown">
                        <Markdown remarkPlugins={[remarkGfm]}>
                          {item.content}
                        </Markdown>
                      </div>
                    )}
                    {item.tools.map((tool) => (
                      <details className="tool-card" key={tool.id}>
                        <summary>
                          {tool.result === undefined && busy ? (
                            <LoaderCircle className="loading-spinner" size={14} />
                          ) : (
                            <Check size={14} />
                          )}
                          <code>{tool.name}</code>
                          <span>
                            {tool.result === undefined
                              ? busy
                                ? "执行中"
                                : "已中断"
                              : "已返回"}
                          </span>
                          <ChevronDown size={14} />
                        </summary>
                        <pre>{JSON.stringify(tool.args, null, 2)}</pre>
                        {tool.result !== undefined && <pre>{tool.result}</pre>}
                      </details>
                    ))}
                    {item.error && <p className="inline-error">{item.error}</p>}
                    {busy &&
                      i === items.length - 1 &&
                      !item.content &&
                      !item.tools.length && (
                        <div className="thinking">
                          <span />
                          <span />
                          <span />
                        </div>
                      )}
                  </div>
                </article>
              ))}
              <div ref={bottom} />
            </section>
          )}
        </div>
        <div className="composer-area">
          {busy && !streaming && (
            <div className="notice">
              该会话正在后台执行。
              <button onClick={() => active && openSession(active)}>
                刷新状态
              </button>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button aria-label="关闭错误提示" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {health && !health.configured && (
            <div className="notice">
              在项目 .env 中配置 DEEPSEEK_API_KEY 并重启后端，即可开始对话。
            </div>
          )}
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <textarea
              ref={input}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="描述你的想法，或者问一个问题…"
              aria-label="输入消息"
              rows={3}
              maxLength={50000}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className="composer-toolbar">
              <div className="model-chip">
                <span className="model-dot" />
                {health?.model ?? "DeepSeek"}
                <span className="model-divider" />
                Agent
              </div>
              <div className="send-controls">
                <span>{busy ? "正在处理…" : "Enter 发送"}</span>
                <button
                  className="send-button"
                  type="submit"
                  disabled={
                    !draft.trim() || busy || loading || !health?.configured
                  }
                  aria-label="发送消息"
                >
                  {busy ? (
                    <LoaderCircle className="loading-spinner" size={18} />
                  ) : (
                    <ArrowUp size={19} />
                  )}
                </button>
              </div>
            </div>
          </form>
          <footer>
            <span>
              <Sparkles size={12} /> 为专注创造而生
            </span>
            <span>AI 可能出错，请核实重要信息</span>
          </footer>
        </div>
      </main>
      {approval && (
        <div className="modal-backdrop">
          <section
            className="approval-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-title"
          >
            <span className="approval-icon">
              <ShieldCheck size={24} />
            </span>
            <h2 id="approval-title">执行前，需要你的确认</h2>
            <p>Fuany 请求执行以下操作。请检查参数后决定是否允许。</p>
            <strong>{approval.name}</strong>
            <pre>{JSON.stringify(approval.args, null, 2)}</pre>
            <div className="approval-actions">
              <button
                autoFocus
                disabled={submittingApproval}
                onClick={() => approve(false)}
              >
                拒绝
              </button>
              <button
                disabled={submittingApproval}
                className="allow-button"
                onClick={() => approve(true)}
              >
                允许本次操作
              </button>
            </div>
            <small>授权仅对本次工具调用生效，5 分钟未处理将自动拒绝。</small>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
