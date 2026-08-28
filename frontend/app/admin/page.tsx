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

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorkspacePage(0);
    setQuery(searchInput.trim());
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
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
            <span className="nav-item disabled">操作功能尚未開放</span>
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
                  <thead><tr><th>日期</th><th>方式</th><th>金額</th><th>狀態</th><th>參考編號</th></tr></thead>
                  <tbody>
                    {payments?.items.map((payment) => (
                      <tr key={payment.id}>
                        <td>{formatDate(payment.received_at || payment.created_at)}</td>
                        <td>{payment.method}</td>
                        <td>{formatMoney(payment.amount_minor, payment.currency)}</td>
                        <td><span className="admin-status">{payment.status}</span></td>
                        <td>{payment.external_reference || "—"}</td>
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
