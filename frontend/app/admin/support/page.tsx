"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

type AdminIdentity = {
  email: string;
  full_name: string | null;
  role: string;
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
  workspace_name: string;
  owner_email: string;
  owner_full_name: string | null;
};

type Message = {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  sender_role: string;
  body: string;
  created_at: string;
};

function messageDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function AdminSupportPage() {
  const router = useRouter();
  const [identity, setIdentity] =
    useState<AdminIdentity | null>(null);
  const [conversations, setConversations] =
    useState<Conversation[]>([]);
  const [selectedId, setSelectedId] =
    useState<string | null>(null);
  const [messages, setMessages] =
    useState<Message[]>([]);
  const [statusFilter, setStatusFilter] =
    useState("open");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadInbox() {
      setLoading(true);

      try {
        const identityResponse = await fetch(
          "/api/admin/me",
          { cache: "no-store" },
        );

        if (identityResponse.status === 401) {
          router.replace("/login?next=/admin/support");
          return;
        }

        if (identityResponse.status === 403) {
          setError("你沒有客服管理權限。");
          return;
        }

        if (!identityResponse.ok) throw new Error();

        const identityData: AdminIdentity =
          await identityResponse.json();

        const params = new URLSearchParams();
        if (statusFilter) {
          params.set("status", statusFilter);
        }

        const response = await fetch(
          `/api/admin/support/conversations?${params.toString()}`,
          { cache: "no-store" },
        );

        if (!response.ok) throw new Error();

        const data: Conversation[] =
          await response.json();

        if (!active) return;

        setIdentity(identityData);
        setConversations(data);
        setSelectedId((current) => {
          if (
            current &&
            data.some((item) => item.id === current)
          ) {
            return current;
          }
          return data[0]?.id || null;
        });
      } catch {
        if (active) {
          setError("目前無法載入客服收件匣。");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadInbox();

    return () => {
      active = false;
    };
  }, [router, statusFilter]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      return;
    }

    let active = true;

    async function loadMessages() {
      try {
        const response = await fetch(
          `/api/admin/support/conversations/${selectedId}/messages`,
          { cache: "no-store" },
        );

        if (!response.ok) return;

        const data: Message[] = await response.json();
        if (active) setMessages(data);
      } catch {
        // Retry on the next polling interval.
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
  }, [selectedId]);

  async function sendMessage(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!selectedId || !draft.trim()) return;

    setSending(true);
    setError("");

    try {
      const response = await fetch(
        `/api/admin/support/conversations/${selectedId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            body: draft.trim(),
          }),
        },
      );

      const data = await response.json().catch(
        () => ({}),
      );

      if (!response.ok) {
        setError(
          data.detail || "客服訊息送出失敗。",
        );
        return;
      }

      setDraft("");
    } catch {
      setError("目前無法送出客服訊息。");
    } finally {
      setSending(false);
    }
  }

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
    });
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="admin-state">
        正在載入客服中心…
      </main>
    );
  }

  if (!identity) {
    return (
      <main className="admin-state">
        <section className="admin-state-card">
          <div className="eyebrow">SUPPORT CENTER</div>
          <h1>客服中心無法載入</h1>
          <p>{error || "請稍後再試。"}</p>
          <a
            className="primary-button admin-state-link"
            href="/admin"
          >
            返回管理總覽
          </a>
        </section>
      </main>
    );
  }

  const selectedConversation = conversations.find(
    (item) => item.id === selectedId,
  );

  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <div className="sidebar-brand">
            <span className="brand-mark small">M</span>
            <div>
              <strong>MarketingOS</strong>
              <span>Platform Admin</span>
            </div>
          </div>

          <nav className="sidebar-nav">
            <a className="nav-item" href="/admin">
              唯讀總覽
            </a>
            <a
              className="nav-item active"
              href="/admin/support"
            >
              客服中心
            </a>
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-account">
            <strong>
              {identity.full_name || identity.email}
            </strong>
            <span>{identity.email}</span>
            <span>{identity.role}</span>
          </div>

          <button
            className="logout-button"
            onClick={logout}
          >
            登出
          </button>
        </div>
      </aside>

      <section className="admin-main admin-support-main">
        <header className="admin-header">
          <div>
            <div className="eyebrow">
              PLATFORM ADMIN · SUPPORT
            </div>
            <h1>客服中心</h1>
            <p>集中處理客戶問題與付款方案對話。</p>
          </div>

          <div className="admin-role-chip">
            {identity.role}
          </div>
        </header>

        {error ? (
          <div className="dashboard-error">{error}</div>
        ) : null}

        <div className="admin-support-layout">
          <section className="admin-card admin-support-inbox">
            <div className="admin-card-heading">
              <div>
                <div className="eyebrow">INBOX</div>
                <h2>客戶對話</h2>
              </div>

              <label className="admin-support-filter">
                狀態
                <select
                  value={statusFilter}
                  onChange={(event) =>
                    setStatusFilter(event.target.value)
                  }
                >
                  <option value="open">處理中</option>
                  <option value="">全部</option>
                  <option value="closed">已結束</option>
                </select>
              </label>
            </div>

            <div className="admin-support-list">
              {conversations.length === 0 ? (
                <p className="admin-empty">
                  目前沒有客服對話。
                </p>
              ) : (
                conversations.map((conversation) => (
                  <button
                    className={`admin-support-row ${
                      selectedId === conversation.id
                        ? "selected"
                        : ""
                    }`}
                    key={conversation.id}
                    type="button"
                    onClick={() =>
                      setSelectedId(conversation.id)
                    }
                  >
                    <strong>
                      {conversation.subject ||
                        (conversation.kind ===
                        "payment_request"
                          ? "方案付款客服"
                          : "一般問題")}
                    </strong>
                    <span>
                      {conversation.owner_full_name ||
                        conversation.owner_email}
                    </span>
                    <small>
                      {conversation.workspace_name} ·{" "}
                      {conversation.category}
                    </small>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className="admin-card admin-support-thread">
            {selectedConversation ? (
              <>
                <div className="admin-card-heading">
                  <div>
                    <div className="eyebrow">
                      {selectedConversation.kind ===
                      "payment_request"
                        ? "PAYMENT REQUEST"
                        : "CUSTOMER ISSUE"}
                    </div>
                    <h2>
                      {selectedConversation.subject ||
                        "客服對話"}
                    </h2>
                    <p className="admin-support-context">
                      {selectedConversation.owner_full_name ||
                        selectedConversation.owner_email}
                      {" · "}
                      {selectedConversation.workspace_name}
                    </p>
                  </div>

                  <span className="admin-status">
                    {selectedConversation.status}
                  </span>
                </div>

                <div className="admin-support-messages">
                  {messages.length === 0 ? (
                    <p className="admin-empty">
                      尚無訊息。
                    </p>
                  ) : (
                    messages.map((message) => (
                      <div
                        className={`admin-support-message ${
                          message.sender_role === "admin"
                            ? "admin"
                            : "customer"
                        }`}
                        key={message.id}
                      >
                        <div>{message.body}</div>
                        <small>
                          {message.sender_role === "admin"
                            ? "管理員"
                            : "客戶"}{" "}
                          · {messageDate(message.created_at)}
                        </small>
                      </div>
                    ))
                  )}
                </div>

                <form
                  className="admin-support-compose"
                  onSubmit={sendMessage}
                >
                  <textarea
                    value={draft}
                    onChange={(event) =>
                      setDraft(event.target.value)
                    }
                    maxLength={4000}
                    rows={4}
                    placeholder="輸入客服回覆..."
                    required
                  />
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={
                      sending || !draft.trim()
                    }
                  >
                    {sending
                      ? "送出中..."
                      : "回覆客戶"}
                  </button>
                </form>
              </>
            ) : (
              <div className="admin-support-empty">
                <div className="eyebrow">
                  SELECT CONVERSATION
                </div>
                <h2>選擇一個客服對話</h2>
                <p>
                  客戶送出問題後，對話會出現在這裡。
                </p>
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
