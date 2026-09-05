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

type Plan = {
  code: string;
  name: string;
  price_twd: number;
  monthly_credits: number;
  list_price_minor: number;
  promotional_price_minor: number | null;
  currency: string;
};

type PaymentRequest = {
  id: string;
  workspace_id: string;
  requested_plan_code: string;
  status: string;
  customer_note: string | null;
  created_at: string;
};

function dateFormat(value: string) {
  return new Intl.DateTimeFormat("zh-TW", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [requests, setRequests] = useState<PaymentRequest[]>([]);
  const [selectedPlan, setSelectedPlan] = useState("");
  const [customerNote, setCustomerNote] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [requesting, setRequesting] = useState(false);
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

        const [subscriptionResponse, plansResponse, requestsResponse] =
          await Promise.all([
            fetch(`/api/workspaces/${workspace.id}/subscription`, {
              cache: "no-store",
            }),
            fetch("/api/subscription-plans", { cache: "no-store" }),
            fetch(`/api/workspaces/${workspace.id}/payment-requests`, {
              cache: "no-store",
            }),
          ]);

        if (!subscriptionResponse.ok) throw new Error();

        setSubscription(await subscriptionResponse.json());

        if (plansResponse.ok) {
          const planData: Plan[] = await plansResponse.json();
          setPlans(planData);
          setSelectedPlan(planData[0]?.code || "");
        }

        if (requestsResponse.ok) {
          setRequests(await requestsResponse.json());
        }
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

  async function submitPaymentRequest() {
    if (!selectedPlan || !workspace) return;

    setRequesting(true);
    setRequestMessage("");

    const response = await fetch(
      `/api/workspaces/${workspace.id}/payment-requests`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requested_plan_code: selectedPlan,
          customer_note: customerNote.trim() || null,
        }),
      },
    );

    if (!response.ok) {
      setRequestMessage("申請送出失敗，請稍後再試。");
      setRequesting(false);
      return;
    }

    const created: PaymentRequest = await response.json();
    setRequests((items) => [created, ...items]);
    setCustomerNote("");
    setRequestMessage("方案申請已送出，客服將與您聯繫付款方式。");
    setRequesting(false);
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
            <a className="nav-item" href="/governance">品質治理</a>
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
        {plans.length > 0 ? (
          <section className="dashboard-panel">
            <div className="eyebrow">PLANS</div>
            <h2>選擇方案</h2>
            <p>選擇方案後提交申請，客服會與您確認付款方式。</p>

            <div className="plan-options">
              {plans.map((plan) => (
                <button
                  key={plan.code}
                  type="button"
                  className={`plan-option ${selectedPlan === plan.code ? "selected" : ""}`}
                  onClick={() => setSelectedPlan(plan.code)}
                >
                  <strong>{plan.name}</strong>
                  <span>
  {plan.promotional_price_minor !== null ? (
    <>
      <del>NT$ {plan.price_twd.toLocaleString()}</del>{" "}
      <strong>
        優惠價 NT$ {(plan.promotional_price_minor / 100).toLocaleString()} / 月
      </strong>
    </>
  ) : (
    <>NT$ {plan.price_twd.toLocaleString()} / 月</>
  )}
</span>
                  <small>{plan.monthly_credits.toLocaleString()} AI credits</small>
                </button>
              ))}
            </div>

            <textarea
              className="dashboard-note"
              placeholder="備註（選填，例如希望客服聯絡的方式）"
              value={customerNote}
              onChange={(event) => setCustomerNote(event.target.value)}
            />

            <button
              className="dashboard-action"
              type="button"
              disabled={requesting || !selectedPlan}
              onClick={submitPaymentRequest}
            >
              {requesting ? "送出中..." : "聯繫客服／申請方案"}
            </button>

            {requestMessage ? (
              <p className="dashboard-message">{requestMessage}</p>
            ) : null}

            {requests.length > 0 ? (
              <div className="request-history">
                <h3>申請紀錄</h3>
                {requests.map((request) => (
                  <div className="request-row" key={request.id}>
                    <span>{request.requested_plan_code}</span>
                    <span>{request.status}</span>
                    <small>{dateFormat(request.created_at)}</small>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

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
