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

type Subscription = {
  plan_code: string;
  plan_name: string;
  status: string;
  cycle_start: string;
  cycle_end: string;
};

type Plan = {
  code: string;
  name: string;
  price_twd: number;
  promotional_price_minor: number | null;
  currency: string;
};

type PaymentRequest = {
  id: string;
  requested_plan_code: string;
  status: string;
  created_at: string;
};

const ACTIVE_REQUEST_STATUSES = [
  "requested",
  "contacted",
  "payment_pending",
];

function dateFormat(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    requested: "待聯繫",
    contacted: "已聯繫",
    payment_pending: "待確認付款",
    fulfilled: "已完成",
    cancelled: "已取消",
  };

  return labels[status] || status;
}

function hasActiveRequest(
  requests: PaymentRequest[],
  planCode: string,
) {
  return requests.some(
    (request) =>
      request.requested_plan_code === planCode &&
      ACTIVE_REQUEST_STATUSES.includes(request.status),
  );
}

function planIsBlocked(
  plan: Plan,
  currentPlan: string,
  requests: PaymentRequest[],
) {
  return (
    plan.code === "free" ||
    plan.code === currentPlan ||
    hasActiveRequest(requests, plan.code)
  );
}

export default function BillingPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [requests, setRequests] = useState<PaymentRequest[]>([]);
  const [selectedPlan, setSelectedPlan] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function loadBilling() {
      try {
        const meResponse = await fetch("/api/auth/me", {
          cache: "no-store",
        });

        if (meResponse.status === 401) {
          router.replace("/login?next=/billing");
          return;
        }

        if (!meResponse.ok) throw new Error();

        const meData: MeResponse = await meResponse.json();
        const workspace = meData.workspaces[0];

        if (!workspace) throw new Error();

        const [
          subscriptionResponse,
          plansResponse,
          requestsResponse,
        ] = await Promise.all([
          fetch(`/api/workspaces/${workspace.id}/subscription`, {
            cache: "no-store",
          }),
          fetch("/api/subscription-plans", {
            cache: "no-store",
          }),
          fetch(`/api/workspaces/${workspace.id}/payment-requests`, {
            cache: "no-store",
          }),
        ]);

        if (
          !subscriptionResponse.ok ||
          !plansResponse.ok ||
          !requestsResponse.ok
        ) {
          throw new Error();
        }

        const subscriptionData: Subscription =
          await subscriptionResponse.json();
        const planData: Plan[] = await plansResponse.json();
        const requestData: PaymentRequest[] =
          await requestsResponse.json();

        setMe(meData);
        setSubscription(subscriptionData);
        setPlans(planData);
        setRequests(requestData);

        const firstAvailable = planData.find(
          (plan) =>
            !planIsBlocked(
              plan,
              subscriptionData.plan_code,
              requestData,
            ),
        );

        setSelectedPlan(firstAvailable?.code || "");
      } catch {
        setMessage("目前無法載入方案與帳務資料。");
      } finally {
        setLoading(false);
      }
    }

    void loadBilling();
  }, [router]);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  async function submitRequest() {
    const workspace = me?.workspaces[0];

    if (!workspace || !subscription || !selectedPlan) return;

    setSubmitting(true);
    setMessage("");

    try {
      const response = await fetch(
        `/api/workspaces/${workspace.id}/payment-requests`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            requested_plan_code: selectedPlan,
            customer_note: note.trim() || null,
          }),
        },
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 409) {
          setMessage(
            data.detail === "Free plan is already included"
              ? "Free 方案已包含在帳號中。"
              : data.detail === "Workspace is already on this plan"
                ? "目前已經是這個方案。"
                : "這個方案已有處理中的申請。",
          );
        } else {
          setMessage("方案申請送出失敗，請稍後再試。");
        }
        return;
      }

      setRequests((items) => [data, ...items]);
      setNote("");
      setSelectedPlan("");
      setMessage("方案申請已送出，客服將與您聯繫付款方式。");
      window.dispatchEvent(
        new CustomEvent("marketingos:open-support", {
          detail: { paymentRequestId: data.id },
        }),
      );
    } catch {
      setMessage("目前無法送出方案申請。");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="dashboard-loading">
        正在載入方案與帳務...
      </main>
    );
  }

  if (!me || !subscription) {
    return (
      <main className="dashboard-loading">
        {message || "無法載入方案資料。"}
      </main>
    );
  }

  const currentPlan = subscription.plan_code;

  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand">
            <span className="brand-mark small">M</span>
            <strong>MarketingOS</strong>
          </div>

          <nav className="sidebar-nav">
            <a className="nav-item" href="/dashboard">總覽</a>
            <a className="nav-item" href="/brands">品牌管理</a>
            <a className="nav-item" href="/create">AI 創作</a>
            <a className="nav-item" href="/history">內容歷史</a>
            <a className="nav-item" href="/governance">品質治理</a>
            <a className="nav-item active" href="/billing">方案與帳務</a>
          </nav>
        </div>

        <button className="logout-button" onClick={logout}>
          登出
        </button>
      </aside>

      <section className="dashboard-main billing-page">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">BILLING</div>
            <h1>方案與帳務</h1>
            <p>{me.workspaces[0].name}</p>
          </div>
        </header>

        <section className="dashboard-panel vertical billing-current">
          <div>
            <div className="eyebrow">CURRENT PLAN</div>
            <h2>{subscription.plan_name} 方案</h2>
            <p>
              目前週期： {dateFormat(subscription.cycle_start)}
              {" → "}
              {dateFormat(subscription.cycle_end)}
            </p>
          </div>

          <div className="subscription-status">
            <span className="status-dot" />
            {subscription.status}
          </div>
        </section>

        <section className="dashboard-panel vertical">
          <div className="eyebrow">UPGRADE</div>
          <h2>選擇方案</h2>
          <p>選擇升級方案後提交申請，客服會與您確認付款方式。</p>

          <div className="billing-plan-grid">
            {plans.map((plan) => {
              const blocked = planIsBlocked(
                plan,
                currentPlan,
                requests,
              );
              const pending = hasActiveRequest(
                requests,
                plan.code,
              );
              const current = plan.code === currentPlan;

              return (
                <button
                  key={plan.code}
                  type="button"
                  disabled={blocked}
                  className={`plan-option billing-plan-option ${
                    selectedPlan === plan.code ? "selected" : ""
                  }`}
                  onClick={() => setSelectedPlan(plan.code)}
                >
                  <strong>{plan.name}</strong>

                  <span>
                    {plan.promotional_price_minor !== null ? (
                      <>
                        <del>
                          NT$ {plan.price_twd.toLocaleString()}
                        </del>{" "}
                        <strong>
                          優惠價 NT${" "}
                          {(
                            plan.promotional_price_minor / 100
                          ).toLocaleString()}{" "}
                          / 月
                        </strong>
                      </>
                    ) : (
                      <>NT$ {plan.price_twd.toLocaleString()} / 月</>
                    )}
                  </span>

                  <small>
                    {current
                      ? "目前方案"
                      : plan.code === "free"
                        ? "已包含"
                        : pending
                          ? "申請處理中"
                          : "可申請升級"}
                  </small>
                </button>
              );
            })}
          </div>

          <textarea
            className="dashboard-note"
            placeholder="備註（選填，例如希望客服聯絡的方式）"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />

          <button
            className="dashboard-action"
            type="button"
            disabled={submitting || !selectedPlan}
            onClick={submitRequest}
          >
            {submitting ? "送出中..." : "聯繫客服／申請方案"}
          </button>

          {message ? (
            <p className="dashboard-message">{message}</p>
          ) : null}
        </section>

        <section className="dashboard-panel vertical">
          <div className="eyebrow">REQUEST HISTORY</div>
          <h2>申請紀錄</h2>

          {requests.length === 0 ? (
            <p>目前沒有方案申請紀錄。</p>
          ) : (
            <div className="billing-request-list">
              {requests.map((request) => (
                <div className="request-row" key={request.id}>
                  <span>{request.requested_plan_code}</span>
                  <span>{statusLabel(request.status)}</span>
                  <small>{dateFormat(request.created_at)}</small>
                  <button
                    className="request-support-button"
                    type="button"
                    onClick={() =>
                      window.dispatchEvent(
                        new CustomEvent("marketingos:open-support", {
                          detail: {
                            paymentRequestId: request.id,
                          },
                        }),
                      )
                    }
                  >
                    聯絡客服
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
