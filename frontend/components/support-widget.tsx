"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import { usePathname } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
};

type MeResponse = {
  workspaces: Workspace[];
};

type Conversation = {
  id: string;
  workspace_id: string;
  payment_request_id: string | null;
  kind: string;
  category: string;
  subject: string | null;
  status: string;
  channel: string;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

type Message = {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_role: string;
  body: string;
  created_at: string;
};

type OpenSupportDetail = {
  paymentRequestId?: string;
};

function messageDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function SupportWidget() {
  const pathname = usePathname();
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [open, setOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingPaymentRequestId, setPendingPaymentRequestId] = useState<
    string | null
  >(null);
  const [category, setCategory] = useState("general");
  const [subject, setSubject] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (
      !pathname ||
      pathname === "/" ||
      pathname.startsWith("/admin") ||
      pathname.startsWith("/login") ||
      pathname.startsWith("/register")
    ) {
      setWorkspaceId(null);
      setOpen(false);
      return;
    }

    let active = true;

    async function loadIdentity() {
      try {
        const response = await fetch("/api/auth/me", {
          cache: "no-store",
        });

        if (!response.ok) {
          if (active) setWorkspaceId(null);
          return;
        }

        const data: MeResponse = await response.json();
        const workspace = data.workspaces[0];

        if (active && workspace) {
          setWorkspaceId(workspace.id);
          setWorkspaceName(workspace.name);
        }
      } catch {
        if (active) setWorkspaceId(null);
      }
    }

    void loadIdentity();

    return () => {
      active = false;
    };
  }, [pathname]);

  useEffect(() => {
    function handleOpen(event: Event) {
      const detail = (
        event as CustomEvent<OpenSupportDetail>
      ).detail;

      setPendingPaymentRequestId(
        detail?.paymentRequestId || null,
      );
      setCategory(detail?.paymentRequestId ? "payment" : "general");
      setSubject(
        detail?.paymentRequestId
          ? "方案付款客服"
          : "",
      );
      setSelectedId(null);
      setError("");
      setOpen(true);
    }

    window.addEventListener(
      "marketingos:open-support",
      handleOpen,
    );

    return () => {
      window.removeEventListener(
        "marketingos:open-support",
        handleOpen,
      );
    };
  }, []);

  useEffect(() => {
    if (!open || !workspaceId) return;

    let active = true;
    setLoading(true);

    async function loadConversations() {
      try {
        const response = await fetch(
          `/api/workspaces/${workspaceId}/support/conversations`,
          { cache: "no-store" },
        );

        if (!response.ok) {
          if (active) {
            setError("目前無法載入客服對話。");
          }
          return;
        }

        const data: Conversation[] = await response.json();

        if (!active) return;

        setConversations(data);

        if (pendingPaymentRequestId) {
          const paymentConversation = data.find(
            (item) =>
              item.payment_request_id ===
              pendingPaymentRequestId,
          );
          setSelectedId(
            paymentConversation?.id || null,
          );
        } else if (
          selectedId &&
          data.some((item) => item.id === selectedId)
        ) {
          setSelectedId(selectedId);
        }
      } catch {
        if (active) {
          setError("目前無法連線至客服服務。");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadConversations();

    return () => {
      active = false;
    };
  }, [
    open,
    workspaceId,
    pendingPaymentRequestId,
  ]);

  useEffect(() => {
    if (!open || !workspaceId || !selectedId) {
      setMessages([]);
      return;
    }

    let active = true;

    async function loadMessages() {
      try {
        const response = await fetch(
          `/api/workspaces/${workspaceId}/support/conversations/${selectedId}/messages`,
          { cache: "no-store" },
        );

        if (!response.ok) return;

        const data: Message[] = await response.json();

        if (active) setMessages(data);
      } catch {
        // Polling will retry on the next interval.
      }
    }

    void loadMessages();
    const interval = window.setInterval(
      loadMessages,
      3000,
    );

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [
    open,
    workspaceId,
    selectedId,
  ]);

  async function sendMessage(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!workspaceId || !draft.trim()) return;

    setSending(true);
    setError("");

    try {
      const target = selectedId
        ? `/api/workspaces/${workspaceId}/support/conversations/${selectedId}/messages`
        : `/api/workspaces/${workspaceId}/support/conversations`;

      const body = selectedId
        ? { body: draft.trim() }
        : {
            category,
            subject: subject.trim() || null,
            message: draft.trim(),
            payment_request_id:
              pendingPaymentRequestId,
          };

      const response = await fetch(target, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(
          data.detail || "訊息送出失敗，請稍後再試。",
        );
        return;
      }

      if (!selectedId) {
        setConversations((items) => [
          data,
          ...items,
        ]);
        setSelectedId(data.id);
        setPendingPaymentRequestId(null);
        setCategory("general");
        setSubject("");
      }

      setDraft("");
    } catch {
      setError("目前無法送出客服訊息。");
    } finally {
      setSending(false);
    }
  }

  function startNewConversation() {
    setSelectedId(null);
    setPendingPaymentRequestId(null);
    setCategory("general");
    setSubject("");
    setDraft("");
    setError("");
  }

  if (!workspaceId) return null;

  const selectedConversation = conversations.find(
    (item) => item.id === selectedId,
  );

  return (
    <>
      <button
        className="support-launcher"
        type="button"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
        aria-label="開啟客服中心"
      >
        <span className="support-launcher-icon">?</span>
        <span>客服中心</span>
      </button>

      {open ? (
        <section
          className="support-panel"
          aria-label="客服中心"
        >
          <header className="support-panel-header">
            <div>
              <div className="eyebrow">SUPPORT CENTER</div>
              <h2>客服中心</h2>
              <p>{workspaceName}</p>
            </div>

            <button
              className="support-close"
              type="button"
              onClick={() => setOpen(false)}
              aria-label="關閉客服中心"
            >
              ×
            </button>
          </header>

          <div className="support-conversation-bar">
            <strong>我的對話</strong>
            <button
              className="support-new-button"
              type="button"
              onClick={startNewConversation}
            >
              新問題
            </button>
          </div>

          <div className="support-conversation-list">
            {loading ? (
              <p className="support-muted">
                載入對話中...
              </p>
            ) : conversations.length === 0 ? (
              <p className="support-muted">
                尚無客服對話，請直接描述遇到的問題。
              </p>
            ) : (
              conversations.map((conversation) => (
                <button
                  className={`support-conversation-row ${
                    selectedId === conversation.id
                      ? "selected"
                      : ""
                  }`}
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(conversation.id);
                    setPendingPaymentRequestId(null);
                    setError("");
                  }}
                >
                  <strong>
                    {conversation.subject ||
                      (conversation.kind ===
                      "payment_request"
                        ? "方案付款客服"
                        : "一般問題")}
                  </strong>
                  <span>
                    {conversation.category} ·{" "}
                    {conversation.status === "open"
                      ? "處理中"
                      : "已結束"}
                  </span>
                </button>
              ))
            )}
          </div>

          <div className="support-thread">
            {selectedConversation ? (
              <div className="support-thread-title">
                <strong>
                  {selectedConversation.subject ||
                    "客服對話"}
                </strong>
                <small>
                  {selectedConversation.kind ===
                  "payment_request"
                    ? "付款申請專屬對話"
                    : "一般客服對話"}
                </small>
              </div>
            ) : (
              <div className="support-compose-fields">
                <label>
                  問題類型
                  <select
                    value={category}
                    onChange={(event) =>
                      setCategory(event.target.value)
                    }
                  >
                    <option value="general">一般問題</option>
                    <option value="system">系統問題</option>
                    <option value="login">登入問題</option>
                    <option value="ai">AI 使用問題</option>
                    <option value="payment">付款方案</option>
                    <option value="other">其他</option>
                  </select>
                </label>

                <label>
                  主旨（選填）
                  <input
                    value={subject}
                    onChange={(event) =>
                      setSubject(event.target.value)
                    }
                    maxLength={255}
                    placeholder="例如：AI 創作無法送出"
                  />
                </label>
              </div>
            )}

            <div className="support-messages">
              {selectedId && messages.length === 0 ? (
                <p className="support-muted">
                  尚無訊息，請輸入內容開始對話。
                </p>
              ) : (
                messages.map((message) => (
                  <div
                    className={`support-message ${
                      message.sender_role === "customer"
                        ? "customer"
                        : "admin"
                    }`}
                    key={message.id}
                  >
                    <div>{message.body}</div>
                    <small>
                      {message.sender_role === "customer"
                        ? "我"
                        : "客服"}{" "}
                      · {messageDate(message.created_at)}
                    </small>
                  </div>
                ))
              )}
            </div>

            {error ? (
              <p className="support-error">{error}</p>
            ) : null}

            <form
              className="support-compose"
              onSubmit={sendMessage}
            >
              <textarea
                value={draft}
                onChange={(event) =>
                  setDraft(event.target.value)
                }
                maxLength={4000}
                placeholder="請描述你遇到的問題..."
                rows={3}
                required
              />
              <button
                className="primary-button"
                type="submit"
                disabled={sending || !draft.trim()}
              >
                {sending ? "送出中..." : "送出訊息"}
              </button>
            </form>
          </div>
        </section>
      ) : null}
    </>
  );
}
