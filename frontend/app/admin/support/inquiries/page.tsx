"use client";

import {
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

type AdminIdentity = {
  email: string;
  full_name: string | null;
  role: string;
};

type Inquiry = {
  id: string;
  email: string;
  category: string;
  subject: string;
  message: string;
  status: string;
  channel: string;
  created_at: string;
  updated_at: string;
};

const categoryLabels: Record<string, string> = {
  general: "一般問題",
  system: "系統問題",
  login: "登入問題",
  ai: "AI 創作問題",
  payment: "付款與方案",
  other: "其他問題",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function AdminSupportInquiriesPage() {
  const router = useRouter();
  const [identity, setIdentity] =
    useState<AdminIdentity | null>(null);
  const [inquiries, setInquiries] =
    useState<Inquiry[]>([]);
  const [statusFilter, setStatusFilter] =
    useState("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadInquiries() {
      setLoading(true);
      setError("");

      try {
        const identityResponse = await fetch(
          "/api/admin/me",
          { cache: "no-store" },
        );

        if (identityResponse.status === 401) {
          router.replace(
            "/login?next=/admin/support/inquiries",
          );
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
        params.set("limit", "100");

        const response = await fetch(
          `/api/admin/support/inquiries?${params.toString()}`,
          { cache: "no-store" },
        );

        if (!response.ok) throw new Error();

        const data: Inquiry[] =
          await response.json();

        if (!active) return;

        setIdentity(identityData);
        setInquiries(data);
      } catch {
        if (active) {
          setError("目前無法載入公開問題回報。");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadInquiries();

    return () => {
      active = false;
    };
  }, [router, statusFilter]);

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
    });
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="admin-state">
        正在載入公開問題回報…
      </main>
    );
  }

  if (!identity) {
    return (
      <main className="admin-state">
        <section className="admin-state-card">
          <div className="eyebrow">PUBLIC INQUIRIES</div>
          <h1>公開問題回報無法載入</h1>
          <p>{error || "請稍後再試。"}</p>
          <a
            className="primary-button admin-state-link"
            href="/admin/support"
          >
            返回客服中心
          </a>
        </section>
      </main>
    );
  }

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
            <a className="nav-item" href="/admin/support">
              客服中心
            </a>
            <a
              className="nav-item active"
              href="/admin/support/inquiries"
            >
              公開問題回報
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

      <section className="admin-main admin-inquiries-main">
        <header className="admin-header">
          <div>
            <div className="eyebrow">
              PUBLIC SUPPORT INBOX
            </div>
            <h1>公開問題回報</h1>
            <p>
              提供給無法登入或尚未登入訪客的問題回報。
            </p>
          </div>

          <label className="admin-filter">
            狀態
            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
            >
              <option value="open">待處理</option>
              <option value="">全部</option>
              <option value="closed">已結案</option>
            </select>
          </label>
        </header>

        {error ? (
          <div className="dashboard-error">{error}</div>
        ) : null}

        <section className="admin-card">
          <div className="admin-card-heading">
            <div>
              <div className="eyebrow">INQUIRIES</div>
              <h2>{inquiries.length} 筆回報</h2>
            </div>
          </div>

          <div className="admin-inquiry-list">
            {inquiries.map((inquiry) => (
              <article
                className="admin-inquiry-card"
                key={inquiry.id}
              >
                <div className="admin-inquiry-heading">
                  <div>
                    <strong>{inquiry.subject}</strong>
                    <span>
                      {categoryLabels[inquiry.category] ||
                        inquiry.category}
                    </span>
                  </div>
                  <span
                    className="admin-status"
                  >
                    {inquiry.status}
                  </span>
                </div>

                <p>{inquiry.message}</p>

                <div className="admin-inquiry-meta">
                  <a href={`mailto:${inquiry.email}`}>
                    {inquiry.email}
                  </a>
                  <span>{formatDate(inquiry.created_at)}</span>
                  <code>{inquiry.id}</code>
                </div>
              </article>
            ))}

            {inquiries.length === 0 ? (
              <p className="admin-empty">
                目前沒有符合條件的公開問題回報。
              </p>
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}
