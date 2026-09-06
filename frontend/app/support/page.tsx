"use client";

import Link from "next/link";
import {
  FormEvent,
  useState,
} from "react";

type InquiryResult = {
  id: string;
  status: string;
  created_at: string;
};

const categories = [
  ["system", "系統問題"],
  ["login", "登入問題"],
  ["ai", "AI 創作問題"],
  ["payment", "付款與方案"],
  ["other", "其他問題"],
] as const;

export default function PublicSupportPage() {
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("system");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [result, setResult] =
    useState<InquiryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitInquiry(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setResult(null);
    setLoading(true);

    try {
      const response = await fetch(
        "/api/public/support/inquiries",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email,
            category,
            subject,
            message,
          }),
        },
      );

      const data = await response.json().catch(
        () => ({}),
      );

      if (!response.ok) {
        setError(
          typeof data.detail === "string"
            ? data.detail
            : "問題回報送出失敗，請稍後再試。",
        );
        return;
      }

      setResult(data as InquiryResult);
      setEmail("");
      setSubject("");
      setMessage("");
    } catch {
      setError("目前無法連線至客服服務。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="public-support-page">
      <header className="public-nav">
        <Link className="public-brand" href="/">
          <span className="brand-mark small">M</span>
          <strong>MarketingOS</strong>
        </Link>

        <nav className="public-nav-links">
          <Link href="/">首頁</Link>
          <Link href="/login">登入</Link>
          <Link
            className="public-nav-cta"
            href="/register"
          >
            免費開始
          </Link>
        </nav>
      </header>

      <section className="public-support-main">
        <div className="eyebrow">PUBLIC SUPPORT</div>
        <h1>問題回報</h1>
        <p className="public-support-lead">
          如果無法登入，或遇到系統、AI、付款問題，
          請留下可聯繫的 Email 與問題內容。
        </p>

        {result ? (
          <section className="public-support-success">
            <div className="eyebrow">REQUEST RECEIVED</div>
            <h2>已收到你的問題回報</h2>
            <p>
              請保留以下回報編號，客服會依此處理。
            </p>
            <code>{result.id}</code>
            <div className="public-hero-actions">
              <Link
                className="dashboard-action"
                href="/login"
              >
                返回登入
              </Link>
              <Link
                className="dashboard-secondary-action"
                href="/"
              >
                回到首頁
              </Link>
            </div>
          </section>
        ) : (
          <form
            className="public-support-card"
            onSubmit={submitInquiry}
          >
            <div className="public-support-form-grid">
              <label>
                聯絡 Email
                <input
                  type="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(event.target.value)
                  }
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </label>

              <label>
                問題類別
                <select
                  value={category}
                  onChange={(event) =>
                    setCategory(event.target.value)
                  }
                >
                  {categories.map(([value, label]) => (
                    <option
                      key={value}
                      value={value}
                    >
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              問題標題
              <input
                value={subject}
                onChange={(event) =>
                  setSubject(event.target.value)
                }
                placeholder="例如：無法登入工作空間"
                maxLength={255}
                required
              />
            </label>

            <label>
              問題描述
              <textarea
                value={message}
                onChange={(event) =>
                  setMessage(event.target.value)
                }
                placeholder="請描述發生的問題、操作步驟與畫面訊息。"
                maxLength={4000}
                rows={8}
                required
              />
            </label>

            {error ? (
              <div className="auth-error">
                {error}
              </div>
            ) : null}

            <button
              className="primary-button"
              type="submit"
              disabled={loading}
            >
              {loading ? "送出中..." : "送出問題回報"}
            </button>
          </form>
        )}

        <p className="public-support-note">
          已登入的客戶可直接使用右下角客服聊天窗，
          進行即時文字交流。
        </p>
      </section>
    </main>
  );
}
