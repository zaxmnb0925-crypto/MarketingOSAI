"use client";

import { useEffect, useState } from "react";


type PublicPlan = {
  code: string;
  name: string;
  description: string | null;
  billing_period: string;
  currency: string;
  list_price_minor: number;
  promotional_price_minor: number | null;
  price_display_note: string | null;
  manual_quote_required: boolean;
};


function price(plan: PublicPlan) {
  const amount = plan.promotional_price_minor ?? plan.list_price_minor;
  return new Intl.NumberFormat("zh-TW", {
    style: "currency",
    currency: plan.currency,
    maximumFractionDigits: 0,
  }).format(amount / 100);
}


export default function PricingPage() {
  const [plans, setPlans] = useState<PublicPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadPlans() {
      try {
        const response = await fetch("/api/public/plans", {
          cache: "no-store",
        });
        if (!response.ok) throw new Error();
        setPlans(await response.json());
      } catch {
        setError("目前無法載入方案價格，請稍後再試。");
      } finally {
        setLoading(false);
      }
    }
    void loadPlans();
  }, []);

  return (
    <main className="marketing-page pricing-page">
      <nav className="public-nav" aria-label="主要導覽">
        <a className="public-brand" href="/"><span className="brand-mark small">M</span><strong>MarketingOS AI</strong></a>
        <div className="public-nav-links"><a href="/">首頁</a><a href="/login">登入</a><a className="public-nav-cta" href="/register">免費開始</a></div>
      </nav>

      <section className="pricing-hero">
        <div className="public-kicker">PUBLIC PRICING</div>
        <h1>公開、清楚的方案價格</h1>
        <p>從免費方案開始。客戶頁面不顯示內部 AI 用量、成本或平台會計資料。</p>
      </section>

      {loading ? <div className="pricing-state">正在載入方案…</div> : null}
      {error ? <div className="pricing-state pricing-error">{error}</div> : null}

      {!loading && !error ? (
        <section className="pricing-grid" aria-label="方案價格">
          {plans.map((plan) => (
            <article className={`pricing-card ${plan.code === "pro" ? "featured" : ""}`} key={plan.code}>
              {plan.code === "pro" ? <div className="pricing-badge">推薦方案</div> : null}
              <div className="public-kicker">{plan.code}</div>
              <h2>{plan.name}</h2>
              <p className="pricing-description">{plan.description || "MarketingOS AI 方案"}</p>
              <div className="pricing-price"><strong>{price(plan)}</strong><span>／月</span></div>
              {plan.promotional_price_minor !== null && plan.promotional_price_minor < plan.list_price_minor ? (
                <p className="pricing-list-price">原價 {new Intl.NumberFormat("zh-TW", { style: "currency", currency: plan.currency, maximumFractionDigits: 0 }).format(plan.list_price_minor / 100)}</p>
              ) : null}
              {plan.price_display_note ? <p className="pricing-note">{plan.price_display_note}</p> : null}
              <a className="public-primary pricing-action" href="/register">{plan.code === "free" ? "免費開始" : "建立帳號"}</a>
            </article>
          ))}
        </section>
      ) : null}

      <section className="pricing-disclosure">
        <h2>價格與功能說明</h2>
        <p>目前幣別為 TWD。付費方案須依平台確認流程生效；實際開通內容以方案說明及確認結果為準。</p>
        <p>更多廣告平台、即時關鍵字與群體智慧仍在產品 Roadmap，並非目前方案承諾功能。</p>
      </section>
    </main>
  );
}
