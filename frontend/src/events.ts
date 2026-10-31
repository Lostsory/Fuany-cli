// 与 events.py 的 JSON 事件契约保持一致。
export type TerminalReason = "completed" | "max_turns" | "prompt_too_long";

export type TextDeltaEvent = { type: "delta"; content: string };
export type ToolStartEvent = {
  type: "tool_start";
  id: string;
  name: string;
  args: Record<string, unknown>;
};
export type ToolEndEvent = {
  type: "tool_end";
  id: string;
  name: string;
  result: string;
};
export type AgentEvent = TextDeltaEvent | ToolStartEvent | ToolEndEvent;

export type UserEvent = { type: "user"; content: string };
export type ApprovalEvent = {
  type: "approval";
  id: string;
  name: string;
  args: Record<string, unknown>;
};
export type ApprovalResolvedEvent = {
  type: "approval_resolved";
  id: string;
  allowed: boolean;
};
export type DoneEvent = {
  type: "done";
  reason: TerminalReason;
  content: string;
  turn_count: number;
  limit_tokens: number | null;
  grace_used: boolean;
};
export type ErrorEvent = { type: "error"; content: string };

export type SessionEvent =
  | AgentEvent
  | UserEvent
  | ApprovalEvent
  | ApprovalResolvedEvent
  | DoneEvent
  | ErrorEvent;
