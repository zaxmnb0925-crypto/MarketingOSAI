"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

type MeResponse = {
  user: {
    id: string;
    email: string;
    full_name: string | null;
    is_active: boolean;
  };
  workspaces: Workspace[];
};

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        const response = await fetch("/api/auth/me", {
          cache: "no-store",
        });

        if (response.status === 401) {
          router.replace("/login?next=/dashboard");
          return;
        }

        if (!response.ok) throw new Error();

        const data: MeResponse = await response.json();

        if (!data.workspaces[0]) {
          setError("目前帳號尚未建立 Workspace。");
          return;
        }

        setMe(data);
      } catch {
        setError("目前無法載入工作空間資料。");
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [router]);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="dashboard-loading">
        正在載入 MarketingOS AI...
      </main>
    );
  }

  if (!me) {
    return (
      <main className="dashboard-loading">
        {error || "無法載入帳號。"}
      </main>
    );
  }

  const workspace = me.workspaces[0];

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand">
            <span className="brand-mark small">M</span>
            <strong>MarketingOS</strong>
          </div>

          <nav className="sidebar-nav">
            <a className="nav-item active" href="/dashboard">總覽</a>
            <a className="nav-item" href="/brands">品牌管理</a>
            <a className="nav-item" href="/create">AI 創作</a>
            <a className="nav-item" href="/history">內容歷史</a>
            <a className="nav-item" href="/governance">品質治理</a>
            <a className="nav-item" href="/billing">方案與帳務</a>

            <a className="nav-item" href="/social-accounts">社群帳號</a>
          </nav>
        </div>

        <button className="logout-button" onClick={logout}>
          登出
        </button>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">WORKSPACE</div>
            <h1>工作空間總覽</h1>
            <p>{workspace.name} · {workspace.role}</p>
          </div>
        </header>

        {error ? <div className="dashboard-error">{error}</div> : null}

        <section className="dashboard-panel vertical dashboard-welcome">
          <div className="eyebrow">WELCOME</div>
          <h2>開始建立你的品牌內容</h2>
          <p>
            先建立或選擇品牌，再使用 AI 創作內容。所有資料只會存在於目前的 Workspace。
          </p>

          <div className="dashboard-quick-actions">
            <a className="dashboard-action" href="/create">
              開始 AI 創作
            </a>
            <a className="dashboard-secondary-action" href="/brands">
              管理品牌
            </a>
          </div>
        </section>

        <section className="dashboard-panel vertical">
          <div className="eyebrow">QUICK ACCESS</div>
          <h2>快速進入</h2>

          <div className="dashboard-link-grid">
            <a className="dashboard-link-card" href="/brands">
              <strong>品牌管理</strong>
              <span>建立 Brand Brain，集中管理品牌資料。</span>
            </a>

            <a className="dashboard-link-card" href="/history">
              <strong>內容歷史</strong>
              <span>查看過去產生的內容與處理狀態。</span>
            </a>

            <a className="dashboard-link-card" href="/governance">
              <strong>品質治理</strong>
              <span>檢視品質政策與內容治理紀錄。</span>
            </a>
          </div>
        </section>
      </section>
    </main>
  );
}
