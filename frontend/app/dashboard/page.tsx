"use client";

import {
  useEffect,
  useState,
} from "react";

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


type UsageResponse = {
  workspace_id: string;

  generations: {
    total: number;
    completed: number;
    failed: number;
    pending: number;
    draft: number;
  };

  tokens: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };

  cost: {
    estimated_cost_usd: string;
    average_completed_cost_usd: string;
  };

  credits: {
    balance: number;
    lifetime_used: number;
    cycle_granted: number;
    cycle_used: number;
    cycle_remaining: number;
    usage_percent: string;
  };

  plan: {
    code: string;
    name: string;
    price_twd: number;
    monthly_credits: number;
    cycle_start: string;
    cycle_end: string;
    status: string;
    auto_renew: boolean;
  };

  profit: {
    usd_to_twd_rate: string;
    ai_cost_twd: string;
    plan_revenue_twd: string;
    projected_gross_profit_twd: string;
    projected_gross_margin_percent: string;
    average_completed_cost_twd: string;
    cost_per_cycle_credit_twd: string;
  };
};


function numberFormat(
  value: number,
) {
  return new Intl.NumberFormat(
    "zh-TW",
  ).format(value);
}


function moneyFormat(
  value: string | number,
) {
  return new Intl.NumberFormat(
    "zh-TW",
    {
      maximumFractionDigits: 2,
      minimumFractionDigits: 0,
    },
  ).format(Number(value));
}


function dateFormat(
  value: string,
) {
  return new Intl.DateTimeFormat(
    "zh-TW",
    {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    },
  ).format(new Date(value));
}


export default function DashboardPage() {
  const router = useRouter();

  const [me, setMe] =
    useState<MeResponse | null>(
      null,
    );

  const [usage, setUsage] =
    useState<UsageResponse | null>(
      null,
    );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");


  useEffect(() => {
    async function loadDashboard() {
      try {
        setError("");

        const meResponse =
          await fetch(
            "/api/auth/me",
            {
              cache: "no-store",
            },
          );

        if (
          meResponse.status === 401
        ) {
          router.replace("/login");
          return;
        }

        if (!meResponse.ok) {
          throw new Error(
            "Unable to load account",
          );
        }

        const meData: MeResponse =
          await meResponse.json();

        if (
          !meData.workspaces ||
          meData.workspaces.length === 0
        ) {
          throw new Error(
            "No workspace available",
          );
        }

        setMe(meData);

        const workspace =
          meData.workspaces[0];

        const usageResponse =
          await fetch(
            `/api/workspaces/${workspace.id}/usage`,
            {
              cache: "no-store",
            },
          );

        if (
          usageResponse.status === 401
        ) {
          router.replace("/login");
          return;
        }

        if (!usageResponse.ok) {
          throw new Error(
            "Unable to load usage",
          );
        }

        const usageData:
          UsageResponse =
          await usageResponse.json();

        setUsage(usageData);
      } catch {
        setError(
          "目前無法載入 Dashboard 資料。",
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [router]);


  async function logout() {
    await fetch(
      "/api/auth/logout",
      {
        method: "POST",
      },
    );

    router.replace("/login");
    router.refresh();
  }


  if (loading) {
    return (
      <main className="dashboard-loading">
        <div>
          <div className="loading-logo">
            M
          </div>

          <p>
            正在載入 MarketingOS AI...
          </p>
        </div>
      </main>
    );
  }


  if (!me) {
    return (
      <main className="dashboard-loading">
        <div>
          <p>
            {error ||
              "無法載入帳號。"}
          </p>

          <button
            className="primary-button"
            onClick={() =>
              router.replace(
                "/login",
              )
            }
          >
            返回登入
          </button>
        </div>
      </main>
    );
  }


  const workspace =
    me.workspaces[0];

  const creditsPercent =
    usage
      ? Math.min(
          Number(
            usage.credits
              .usage_percent,
          ),
          100,
        )
      : 0;


  return (
    <main className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand">
            <span className="brand-mark small">
              M
            </span>

            <div>
              <strong>
                MarketingOS
              </strong>

              <span>
                AI Workspace
              </span>
            </div>
          </div>

          <nav className="sidebar-nav">
            <a
              className="nav-item active"
              href="/dashboard"
            >
              總覽
            </a>

            <a
              className="nav-item"
              href="/brands"
            >
              品牌管理
            </a>

            <a
              className="nav-item"
              href="/create"
            >
              AI 創作
            </a>

            <span className="nav-item disabled">
              發布排程
            </span>

            <a
              className="nav-item"
              href="/history"
            >
              內容歷史
            </a>
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-account">
            <strong>
              {me.user.full_name ||
                "MarketingOS User"}
            </strong>

            <span>
              {me.user.email}
            </span>
          </div>

          <button
            className="logout-button"
            onClick={logout}
          >
            登出
          </button>
        </div>
      </aside>


      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">
              OVERVIEW
            </div>

            <h1>
              工作空間總覽
            </h1>

            <p>
              {workspace.name}
              {" · "}
              {workspace.role}
            </p>
          </div>

          {usage ? (
            <div className="plan-chip">
              {usage.plan.name}
              {" Plan"}
            </div>
          ) : null}
        </header>


        {error ? (
          <div className="dashboard-error">
            {error}
          </div>
        ) : null}


        {usage ? (
          <>
            <section className="metric-grid">
              <article className="metric-card featured">
                <div className="metric-label">
                  AI Credits
                </div>

                <strong>
                  {numberFormat(
                    usage.credits
                      .balance,
                  )}
                </strong>

                <small>
                  每月{" "}
                  {numberFormat(
                    usage.credits
                      .cycle_granted,
                  )}{" "}
                  Credits
                </small>
              </article>


              <article className="metric-card">
                <div className="metric-label">
                  AI 歷史成本
                </div>

                <strong>
                  NT$
                  {moneyFormat(
                    usage.profit
                      .ai_cost_twd,
                  )}
                </strong>

                <small>
                  US$
                  {
                    usage.cost
                      .estimated_cost_usd
                  }
                </small>
              </article>


              <article className="metric-card">
                <div className="metric-label">
                  內容生成
                </div>

                <strong>
                  {numberFormat(
                    usage.generations
                      .completed,
                  )}
                </strong>

                <small>
                  總任務{" "}
                  {numberFormat(
                    usage.generations
                      .total,
                  )}
                </small>
              </article>


              <article className="metric-card">
                <div className="metric-label">
                  目前方案
                </div>

                <strong>
                  {usage.plan.name}
                </strong>

                <small>
                  NT$
                  {numberFormat(
                    usage.plan
                      .price_twd,
                  )}
                  {" / 月"}
                </small>
              </article>
            </section>


            <section className="dashboard-grid">
              <article className="dashboard-panel vertical">
                <div className="panel-header">
                  <div>
                    <div className="eyebrow">
                      CREDIT USAGE
                    </div>

                    <h2>
                      本期 AI Credits
                    </h2>
                  </div>

                  <strong className="panel-number">
                    {
                      usage.credits
                        .usage_percent
                    }
                    %
                  </strong>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-value"
                    style={{
                      width:
                        `${creditsPercent}%`,
                    }}
                  />
                </div>

                <div className="credit-summary">
                  <div>
                    <span>
                      已使用
                    </span>

                    <strong>
                      {numberFormat(
                        usage.credits
                          .cycle_used,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      剩餘
                    </span>

                    <strong>
                      {numberFormat(
                        usage.credits
                          .cycle_remaining,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      配額
                    </span>

                    <strong>
                      {numberFormat(
                        usage.credits
                          .cycle_granted,
                      )}
                    </strong>
                  </div>
                </div>
              </article>


              <article className="dashboard-panel vertical">
                <div>
                  <div className="eyebrow">
                    PROJECTED PROFIT
                  </div>

                  <h2>
                    AI 成本與方案效益
                  </h2>
                </div>

                <div className="profit-grid">
                  <div>
                    <span>
                      方案定價
                    </span>

                    <strong>
                      NT$
                      {moneyFormat(
                        usage.profit
                          .plan_revenue_twd,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      AI 成本
                    </span>

                    <strong>
                      NT$
                      {moneyFormat(
                        usage.profit
                          .ai_cost_twd,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      投影毛利
                    </span>

                    <strong>
                      NT$
                      {moneyFormat(
                        usage.profit
                          .projected_gross_profit_twd,
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>
                      投影毛利率
                    </span>

                    <strong>
                      {
                        usage.profit
                          .projected_gross_margin_percent
                      }
                      %
                    </strong>
                  </div>
                </div>

                <p className="panel-note">
                  此處為方案定價相對 AI
                  成本的投影，尚未代表實際收款，
                  也尚未扣除 VPS、金流、客服與其他營運成本。
                </p>
              </article>
            </section>


            <section className="dashboard-grid bottom-grid">
              <article className="dashboard-panel vertical">
                <div>
                  <div className="eyebrow">
                    AI ACTIVITY
                  </div>

                  <h2>
                    內容任務
                  </h2>
                </div>

                <div className="activity-list">
                  <div>
                    <span>
                      已完成
                    </span>

                    <strong className="good">
                      {
                        usage.generations
                          .completed
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      失敗
                    </span>

                    <strong className="bad">
                      {
                        usage.generations
                          .failed
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      等待中
                    </span>

                    <strong>
                      {
                        usage.generations
                          .pending
                      }
                    </strong>
                  </div>

                  <div>
                    <span>
                      草稿
                    </span>

                    <strong>
                      {
                        usage.generations
                          .draft
                      }
                    </strong>
                  </div>
                </div>
              </article>


              <article className="dashboard-panel vertical">
                <div>
                  <div className="eyebrow">
                    TOKEN USAGE
                  </div>

                  <h2>
                    Token 使用量
                  </h2>
                </div>

                <div className="token-total">
                  {numberFormat(
                    usage.tokens
                      .total_tokens,
                  )}
                </div>

                <div className="token-row">
                  <span>
                    Input
                  </span>

                  <strong>
                    {numberFormat(
                      usage.tokens
                        .input_tokens,
                    )}
                  </strong>
                </div>

                <div className="token-row">
                  <span>
                    Output
                  </span>

                  <strong>
                    {numberFormat(
                      usage.tokens
                        .output_tokens,
                    )}
                  </strong>
                </div>
              </article>
            </section>


            <section className="dashboard-panel workspace-panel">
              <div>
                <div className="eyebrow">
                  SUBSCRIPTION
                </div>

                <h2>
                  {usage.plan.name}
                  {" 方案"}
                </h2>

                <p>
                  目前週期：
                  {" "}
                  {dateFormat(
                    usage.plan
                      .cycle_start,
                  )}
                  {" → "}
                  {dateFormat(
                    usage.plan
                      .cycle_end,
                  )}
                </p>
              </div>

              <div className="subscription-status">
                <span className="status-dot" />

                {usage.plan.status}
              </div>
            </section>
          </>
        ) : (
          <section className="dashboard-panel">
            <p>
              無法取得 Usage 資料。
            </p>
          </section>
        )}
      </section>
    </main>
  );
}
