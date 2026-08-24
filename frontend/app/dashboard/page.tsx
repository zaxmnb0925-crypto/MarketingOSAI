"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Workspace = { id: string; name: string; slug: string; role: string };
type MeResponse = {
  user: { id: string; email: string; full_name: string | null; is_active: boolean };
  workspaces: Workspace[];
};
type UsageResponse = {
  workspace_id: string;
  generations: { total: number; completed: number; failed: number; pending: number; draft: number };
  plan: { code: string; name: string; cycle_start: string; cycle_end: string; status: string; auto_renew: boolean };
};

function dateFormat(value: string) {
  return new Intl.DateTimeFormat("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
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
        const usageResponse = await fetch(`/api/workspaces/${workspace.id}/usage`, { cache: "no-store" });
        if (!usageResponse.ok) throw new Error();
        setUsage(await usageResponse.json());
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
          {usage ? <div className="plan-chip">{usage.plan.name} Plan</div> : null}
        </header>
        {error ? <div className="dashboard-error">{error}</div> : null}
        {usage ? <>
          <section className="metric-grid">
            <article className="metric-card featured"><div className="metric-label">內容生成</div><strong>{usage.generations.completed}</strong><small>總任務 {usage.generations.total}</small></article>
            <article className="metric-card"><div className="metric-label">等待中</div><strong>{usage.generations.pending}</strong><small>草稿 {usage.generations.draft}</small></article>
            <article className="metric-card"><div className="metric-label">失敗</div><strong>{usage.generations.failed}</strong><small>生成活動統計</small></article>
            <article className="metric-card"><div className="metric-label">目前方案</div><strong>{usage.plan.name}</strong><small>{usage.plan.status}</small></article>
          </section>
          <section className="dashboard-panel workspace-panel">
            <div><div className="eyebrow">SUBSCRIPTION</div><h2>{usage.plan.name} 方案</h2><p>目前週期： {dateFormat(usage.plan.cycle_start)} → {dateFormat(usage.plan.cycle_end)}</p></div>
            <div className="subscription-status"><span className="status-dot" />{usage.plan.status}</div>
          </section>
        </> : <section className="dashboard-panel"><p>無法取得 Usage 資料。</p></section>}
      </section>
    </main>
  );
}
