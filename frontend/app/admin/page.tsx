"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";


type AdminIdentity = {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
};

type Workspace = {
  id: string;
  name: string;
  slug: string;
  created_at: string;
};

type WorkspaceList = {
  items: Workspace[];
  total: number;
  limit: number;
  offset: number;
};

type Subscription = {
  workspace_id: string;
  plan_code: string;
  status: string;
  starts_at: string;
  expires_at: string | null;
  renewal_price_minor: number;
  billing_currency: string;
};

type Payment = {
  id: string;
  method: string;
  amount_minor: number;
  currency: string;
  status: string;
  received_at: string | null;
  external_reference: string | null;
  created_at: string;
};

type PaymentList = {
  items: Payment[];
  total: number;
  limit: number;
  offset: number;
};

type PaymentRequest = {
  id: string;
  workspace_id: string;
  workspace_name: string;
  owner_email: string;
  owner_full_name: string | null;
  requested_plan_code: string;
  status: string;
  customer_note: string | null;
  created_at: string;
};

const PAGE_SIZE = 20;
const PAYMENT_PAGE_SIZE = 10;


function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}


function formatMoney(amount: number, currency: string) {
  return new Intl.NumberFormat("zh-TW", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount / 100);
}


export default function AdminPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<AdminIdentity | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [workspacePage, setWorkspacePage] = useState(0);
  const [workspaces, setWorkspaces] = useState<WorkspaceList | null>(null);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [subscriptionMessage, setSubscriptionMessage] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [paymentPage, setPaymentPage] = useState(0);
  const [payments, setPayments] = useState<PaymentList | null>(null);
  const [paymentMessage, setPaymentMessage] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [targetPlan, setTargetPlan] = useState("pro");
  const [actionMessage, setActionMessage] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [paymentRequests, setPaymentRequests] = useState<PaymentRequest[]>([]);
  const [paymentRequestMessage, setPaymentRequestMessage] = useState("");

  const handleAuthentication = useCallback(
    (status: number) => {
      if (status === 401) {
        router.replace("/login?next=/admin");
        return true;
      }
      return false;
    },
    [router],
  );

  useEffect(() => {
    async function loadIdentity() {
      try {
        const response = await fetch("/api/admin/me", {
          cache: "no-store",
        });
        if (handleAuthentication(response.status)) return;
        if (response.status === 403) {
          setForbidden(true);
          return;
        }
        if (!response.ok) throw new Error();
        setIdentity(await response.json());
      } catch {
        setError("目前無法載入管理員身分。");
      } finally {
        setLoading(false);
      }
    }
    void loadIdentity();
  }, [handleAuthentication]);

  useEffect(() => {
    if (!identity) return;
    async function loadWorkspaces() {
      setError("");
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(workspacePage * PAGE_SIZE),
      });
      if (query) params.set("q", query);
      try {
        const response = await fetch(
          `/api/admin/workspaces?${params.toString()}`,
          { cache: "no-store" },
        );
        if (handleAuthentication(response.status)) return;
        if (response.status === 403) {
          setForbidden(true);
          return;
        }
        if (!response.ok) throw new Error();
        const data: WorkspaceList = await response.json();
        setWorkspaces(data);
        setSelected((current) =>
          current && data.items.some((item) => item.id === current.id)
            ? current
            : data.items[0] || null,
        );
      } catch {
        setError("目前無法載入 Workspace 清單。");
      }
    }
    void loadWorkspaces();
  }, [handleAuthentication, identity, query, workspacePage]);

  useEffect(() => {
    if (!selected) {
      setSubscription(null);
      setPayments(null);
      return;
    }
    async function loadSubscription() {
      setSubscription(null);
      setSubscriptionMessage("");
      try {
        const response = await fetch(
          `/api/admin/workspaces/${selected!.id}/subscription`,
          { cache: "no-store" },
        );
        if (handleAuthentication(response.status)) return;
        if (response.status === 403) {
          setSubscriptionMessage("此管理員角色無訂閱讀取權限。");
          return;
        }
        if (response.status === 404) {
          setSubscriptionMessage("此 Workspace 尚無訂閱資料。");
          return;
        }
        if (!response.ok) throw new Error();
        setSubscription(await response.json());
      } catch {
        setSubscriptionMessage("目前無法載入訂閱資料。");
      }
    }
    void loadSubscription();
  }, [handleAuthentication, selected]);

  useEffect(() => {
    if (!selected) return;
    async function loadPayments() {
      setPayments(null);
      setPaymentMessage("");
      const params = new URLSearchParams({
        limit: String(PAYMENT_PAGE_SIZE),
        offset: String(paymentPage * PAYMENT_PAGE_SIZE),
      });
      if (paymentStatus) params.set("status", paymentStatus);
      try {
        const response = await fetch(
          `/api/admin/workspaces/${selected!.id}/payments?${params.toString()}`,
          { cache: "no-store" },
        );
        if (handleAuthentication(response.status)) return;
        if (response.status === 403) {
          setPaymentMessage("此管理員角色無付款紀錄讀取權限。");
          return;
        }
        if (!response.ok) throw new Error();
        setPayments(await response.json());
      } catch {
        setPaymentMessage("目前無法載入付款紀錄。");
      }
    }
    void loadPayments();
  }, [handleAuthentication, paymentPage, paymentStatus, selected]);

  useEffect(() => {
    if (!identity) return;

    async function loadPaymentRequests() {
      try {
        const response = await fetch("/api/admin/payment-requests", {
          cache: "no-store",
        });

        if (handleAuthentication(response.status)) return;
        if (response.status === 403) {
          setPaymentRequestMessage("此管理員角色無付款申請讀取權限。");
          return;
        }
        if (!response.ok) throw new Error();

        setPaymentRequests(await response.json());
      } catch {
        setPaymentRequestMessage("目前無法載入付款申請。");
      }
    }

    void loadPaymentRequests();
  }, [handleAuthentication, identity]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkspacePage(0);
    setQuery(searchInput.trim());
  }

  async function contactPaymentRequest(requestId: string) {
    setActionBusy(true);
    setActionMessage("");

    const response = await fetch(
      `/api/admin/payment-requests/${requestId}/contact`,
      { method: "POST" },
    );

    if (!response.ok) {
      setActionMessage("更新申請狀態失敗。");
      setActionBusy(false);
      return;
    }

    const updated: PaymentRequest = await response.json();

    setPaymentRequests((items) =>
      items.map((item) =>
        item.id === updated.id ? { ...item, status: updated.status } : item,
      ),
    );
    setActionMessage("已標記為已聯繫。");
    setActionBusy(false);
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  async function recordPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;

    setActionBusy(true);
    setActionMessage("");

    const response = await fetch(
      `/api/admin/workspaces/${selected.id}/payments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method: paymentMethod,
          amount_minor: Math.round(Number(paymentAmount) * 100),
          currency: "TWD",
          external_reference: paymentReference || null,
          idempotency_key: `admin-${selected.id}-${Date.now()}`,
        }),
      },
    );

    if (!response.ok) {
      setActionMessage("付款紀錄建立失敗，請確認金額與權限。");
      setActionBusy(false);
      return;
    }

    setPaymentAmount("");
    setPaymentReference("");
    setActionMessage("付款紀錄已建立，請在下方確認收款。");
    setActionBusy(false);
    setPaymentStatus("pending");
    setPaymentPage(0);
  }

  async function confirmPayment(paymentId: string) {
    if (!selected) return;

    const payment = payments?.items.find((item) => item.id === paymentId);
    if (!payment) {
      setActionMessage("找不到要確認的付款紀錄。");
      return;
    }

    const confirmableRequests = paymentRequests.filter(
      (request) =>
        request.workspace_id === selected.id &&
        request.requested_plan_code === targetPlan &&
        ["contacted", "payment_pending"].includes(request.status),
    );

    if (confirmableRequests.length === 0) {
      setActionMessage(
        "找不到此 Workspace 可確認的方案申請，請先由客戶提出申請並標記為已聯繫。",
      );
      return;
    }

    if (confirmableRequests.length > 1) {
      setActionMessage(
        "此方案有多筆可確認申請，為避免誤綁付款，請先整理重複申請。",
      );
      return;
    }

    const paymentRequest = confirmableRequests[0];
    if (!paymentRequest) {
      setActionMessage("找不到可綁定的方案申請。");
      return;
    }

    const reason = window.prompt("請輸入確認收款原因：", "已確認收到客戶款項");
    if (!reason?.trim()) return;

    setActionBusy(true);
    setActionMessage("");

    const response = await fetch(
      `/api/admin/workspaces/${selected.id}/payments/${paymentId}/confirm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_plan_code: targetPlan,
          price_selection:
            targetPlan === "pro" && payment.amount_minor === 99000
              ? "promotion"
              : "list",
          reason: reason.trim(),
          payment_request_id: paymentRequest.id,
          request_id: `confirm-${paymentId}-${Date.now()}`,
        }),
      },
    );

    if (!response.ok) {
      setActionMessage("確認收款失敗，請檢查方案、付款金額或權限。");
      setActionBusy(false);
      return;
    }

    setActionMessage("收款已確認，客戶方案已啟用。");
    setActionBusy(false);
    window.location.reload();
  }

  if (loading) {
    return <main className="admin-state">正在驗證管理員身分…</main>;
  }

  if (forbidden) {
    return (
      <main className="admin-state">
        <section className="admin-state-card">
          <div className="eyebrow">403 · FORBIDDEN</div>
          <h1>你沒有 Platform Admin 權限</h1>
          <p>此頁僅供已授權的平台管理員使用。</p>
          <a className="primary-button admin-state-link" href="/dashboard">
            返回客戶工作區
          </a>
        </section>
      </main>
    );
  }

  if (!identity) {
    return <main className="admin-state">{error || "無法載入管理控制台。"}</main>;
  }

  const workspacePages = workspaces
    ? Math.max(1, Math.ceil(workspaces.total / PAGE_SIZE))
    : 1;
  const paymentPages = payments
    ? Math.max(1, Math.ceil(payments.total / PAYMENT_PAGE_SIZE))
    : 1;

  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div>
          <div className="sidebar-brand">
            <span className="brand-mark small">M</span>
            <div><strong>MarketingOS</strong><span>Platform Admin</span></div>
          </div>
          <nav className="sidebar-nav">
            <a className="nav-item active" href="/admin">唯讀總覽</a>
            <a className="nav-item" href="/admin/support">客服中心</a>
          </nav>
        </div>
        <div className="sidebar-bottom">
          <div className="sidebar-account">
            <strong>{identity.full_name || identity.email}</strong>
            <span>{identity.email}</span>
            <span>{identity.role}</span>
          </div>
          <button className="logout-button" onClick={logout}>登出</button>
        </div>
      </aside>

      <section className="admin-main">
        <header className="admin-header">
          <div>
            <div className="eyebrow">PLATFORM ADMIN · READ ONLY</div>
            <h1>平台管理控制台</h1>
            <p>搜尋 Workspace，檢視訂閱與付款紀錄。</p>
          </div>
          <div className="admin-role-chip">{identity.role}</div>
        </header>

        {error ? <div className="dashboard-error">{error}</div> : null}

        <div className="admin-layout">
          <section className="admin-card workspace-browser">
            <form className="admin-search" onSubmit={search}>
              <label htmlFor="workspace-search">Workspace 搜尋</label>
              <div>
                <input
                  id="workspace-search"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="名稱或 slug"
                  maxLength={150}
                />
                <button type="submit">搜尋</button>
              </div>
            </form>

            <div className="admin-list" aria-label="Workspace 清單">
              {workspaces?.items.map((workspace) => (
                <button
                  className={`workspace-row ${selected?.id === workspace.id ? "selected" : ""}`}
                  key={workspace.id}
                  onClick={() => {
                    setSelected(workspace);
                    setPaymentPage(0);
                  }}
                  type="button"
                >
                  <strong>{workspace.name}</strong>
                  <span>{workspace.slug}</span>
                  <small>{formatDate(workspace.created_at)}</small>
                </button>
              ))}
              {workspaces && workspaces.items.length === 0 ? (
                <p className="admin-empty">找不到符合條件的 Workspace。</p>
              ) : null}
            </div>

            <div className="admin-pagination">
              <button
                disabled={workspacePage === 0}
                onClick={() => setWorkspacePage((page) => page - 1)}
                type="button"
              >上一頁</button>
              <span>{workspacePage + 1} / {workspacePages}</span>
              <button
                disabled={workspacePage + 1 >= workspacePages}
                onClick={() => setWorkspacePage((page) => page + 1)}
                type="button"
              >下一頁</button>
            </div>
          </section>

          <div className="admin-detail">
            <section className="admin-card">
              <div className="admin-card-heading">
                <div>
                  <div className="eyebrow">SUBSCRIPTION</div>
                  <h2>{selected?.name || "尚未選擇 Workspace"}</h2>
                </div>
                {subscription ? <span className="admin-status">{subscription.status}</span> : null}
              </div>
              {subscription ? (
                <dl className="admin-facts">
                  <div><dt>方案</dt><dd>{subscription.plan_code}</dd></div>
                  <div><dt>續約價格</dt><dd>{formatMoney(subscription.renewal_price_minor, subscription.billing_currency)}</dd></div>
                  <div><dt>開始日</dt><dd>{formatDate(subscription.starts_at)}</dd></div>
                  <div><dt>到期日</dt><dd>{formatDate(subscription.expires_at)}</dd></div>
                </dl>
              ) : <p className="admin-empty">{subscriptionMessage || "請從左側選擇 Workspace。"}</p>}
            </section>

            <section className="admin-card">
              <div className="admin-card-heading">
                <div>
                  <div className="eyebrow">BILLING ACTIONS</div>
                  <h2>登錄客戶付款</h2>
                </div>
              </div>

              <form className="admin-facts" onSubmit={recordPayment}>
                <label>
                  付款方式
                  <input value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)} required />
                </label>
                <label>
                  金額（TWD）
                  <input type="number" min="1" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} required />
                </label>
                <label>
                  方案
                  <select value={targetPlan} onChange={(event) => setTargetPlan(event.target.value)}>
                    <option value="pro">Pro</option>
                    <option value="business">Business</option>
                  </select>
                </label>
                <label>
                  參考編號
                  <input value={paymentReference} onChange={(event) => setPaymentReference(event.target.value)} />
                </label>
                <button className="primary-button" type="submit" disabled={!selected || actionBusy}>
                  登錄付款
                </button>
              </form>

              {actionMessage ? <p className="admin-empty">{actionMessage}</p> : null}
            </section>

            <section className="admin-card">
              <div className="admin-card-heading">
                <div>
                  <div className="eyebrow">CUSTOMER REQUESTS</div>
                  <h2>客戶方案申請</h2>
                </div>
              </div>

              {paymentRequestMessage ? (
                <p className="admin-empty">{paymentRequestMessage}</p>
              ) : paymentRequests.length === 0 ? (
                <p className="admin-empty">目前沒有客戶方案申請。</p>
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>客戶</th>
                        <th>Workspace</th>
                        <th>方案</th>
                        <th>狀態</th>
                        <th>申請日期</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paymentRequests.map((request) => (
                        <tr key={request.id}>
                          <td>
                            {request.owner_full_name || "—"}<br />
                            <small>{request.owner_email}</small>
                          </td>
                          <td>{request.workspace_name}</td>
                          <td>{request.requested_plan_code}</td>
                          <td>
                            <span className="admin-status">{request.status}</span>
                          </td>
                          <td>{formatDate(request.created_at)}</td>
                          <td>
                            {request.status === "requested" ? (
                              <button
                                type="button"
                                className="primary-button"
                                disabled={actionBusy}
                                onClick={() => void contactPaymentRequest(request.id)}
                              >
                                已聯繫
                              </button>
                            ) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="admin-card">
              <div className="admin-card-heading payment-heading">
                <div>
                  <div className="eyebrow">PAYMENT RECORDS</div>
                  <h2>付款紀錄</h2>
                </div>
                <label>
                  狀態
                  <select
                    value={paymentStatus}
                    onChange={(event) => {
                      setPaymentStatus(event.target.value);
                      setPaymentPage(0);
                    }}
                  >
                    <option value="">全部</option>
                    <option value="pending">待確認</option>
                    <option value="confirmed">已確認</option>
                    <option value="rejected">已拒絕</option>
                    <option value="refunded">已退款</option>
                  </select>
                </label>
              </div>

              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>日期</th><th>方式</th><th>金額</th><th>狀態</th><th>參考編號</th><th>操作</th></tr></thead>
                  <tbody>
                    {payments?.items.map((payment) => (
                      <tr key={payment.id}>
                        <td>{formatDate(payment.received_at || payment.created_at)}</td>
                        <td>{payment.method}</td>
                        <td>{formatMoney(payment.amount_minor, payment.currency)}</td>
                        <td><span className="admin-status">{payment.status}</span></td>
                        <td>{payment.external_reference || "—"}</td>
                        <td>
                          {payment.status === "pending" ? (
                            <button
                              type="button"
                              className="primary-button"
                              disabled={actionBusy}
                              onClick={() => void confirmPayment(payment.id)}
                            >
                              確認收款並啟用
                            </button>
                          ) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {payments && payments.items.length === 0 ? <p className="admin-empty">沒有符合條件的付款紀錄。</p> : null}
              {!payments && paymentMessage ? <p className="admin-empty">{paymentMessage}</p> : null}
              <div className="admin-pagination">
                <button disabled={paymentPage === 0} onClick={() => setPaymentPage((page) => page - 1)} type="button">上一頁</button>
                <span>{paymentPage + 1} / {paymentPages}</span>
                <button disabled={!payments || paymentPage + 1 >= paymentPages} onClick={() => setPaymentPage((page) => page + 1)} type="button">下一頁</button>
              </div>
            </section>
          </div>
        </div>
      </section>
    </main>
  );
}
