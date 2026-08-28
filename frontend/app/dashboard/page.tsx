"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Workspace = { id: string; name: string; slug: string; role: string };
type MeResponse = {
  user: { id: string; email: string; full_name: string | null; is_active: boolean };
  workspaces: Workspace[];
};
type SubscriptionResponse = {
  workspace_id: string;
  plan_code: string;
  plan_name: string;
  cycle_start: string;
  cycle_end: string;
  status: string;
};

function dateFormat(value: string) {
  return new Intl.DateTimeFormat("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        const meResponse = await fetch("/api/auth/me", { cache: "no-store" });
        if (meResponse.status === 401) { router.replace("/login"); return; }
        if (!meResponse.ok) throw new Error();
        const meData: MeResponse = await meResponse.json();
        const workspace = meData.workspaces[0];
        if (!workspace) throw new Error();
        setMe(meData);
        const subscriptionResponse = await fetch(
          `/api/workspaces/${workspace.id}/subscription`,
          { cache: "no-store" },
        );
        if (!subscriptionResponse.ok) throw new Error();
        setSubscription(await subscriptionResponse.json());
      } catch {
        setError("目前無法載入 Dashboard 資料。");
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

  if (loading) return <main className="dashboard-loading">正在載入 MarketingOS AI...</main>;
  if (!me) return <main className="dashboard-loading">{error || "無法載入帳號。"}</main>;
  const workspace = me.workspaces[0];

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand"><span className="brand-mark small">M</span><strong>MarketingOS</strong></div>
          <nav className="sidebar-nav">
            <a className="nav-item active" href="/dashboard">總覽</a>
            <a className="nav-item" href="/brands">品牌管理</a>
            <a className="nav-item" href="/create">AI 創作</a>
            <a className="nav-item" href="/history">內容歷史</a>
          </nav>
        </div>
        <button className="logout-button" onClick={logout}>登出</button>
      </aside>
      <section className="dashboard-main">
        <header className="dashboard-header">
          <div><div className="eyebrow">OVERVIEW</div><h1>工作空間總覽</h1><p>{workspace.name}{" · "}{workspace.role}</p></div>
          {subscription ? <div className="plan-chip">{subscription.plan_name} Plan</div> : null}
        </header>
        {error ? <div className="dashboard-error">{error}</div> : null}
        {subscription ? <>
          <section className="dashboard-panel workspace-panel">
            <div><div className="eyebrow">SUBSCRIPTION</div><h2>{subscription.plan_name} 方案</h2><p>目前週期： {dateFormat(subscription.cycle_start)} → {dateFormat(subscription.cycle_end)}</p></div>
            <div className="subscription-status"><span className="status-dot" />{subscription.status}</div>
          </section>
        </> : <section className="dashboard-panel"><p>無法取得方案資料。</p></section>}
      </section>
    </main>
  );
}
