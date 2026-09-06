"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          workspace_name: workspaceName.trim(),
          password,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(
          data?.detail === "Email already registered"
            ? "此 Email 已經註冊。"
            : data?.detail || "註冊失敗，請確認填寫資料。",
        );
        return;
      }

      router.replace("/dashboard");
      router.refresh();
    } catch {
      setError("目前無法連線至註冊服務。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Link className="auth-back-link" href="/">← 返回 MarketingOS</Link>
        <div className="brand-mark">M</div>
        <div className="eyebrow">MARKETINGOS AI</div>
        <h1 className="auth-title">建立你的工作空間</h1>
        <p className="auth-description">
          註冊後會建立一個專屬的 MarketingOS Workspace。
        </p>

        <form className="auth-form" onSubmit={submit}>
          <label>
            姓名
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" required />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>
          <label>
            Workspace 名稱
            <input value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} placeholder="例如：我的品牌工作室" required />
          </label>
          <label>
            密碼
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required />
          </label>

          {error ? <div className="auth-error">{error}</div> : null}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "建立中..." : "建立免費帳號"}
          </button>
        </form>

        <div className="auth-links">
          已經有帳號？ <Link href="/login">登入</Link>
        </div>
        <div className="auth-security">安全註冊 · HttpOnly Session</div>
      </section>
    </main>
  );
}
