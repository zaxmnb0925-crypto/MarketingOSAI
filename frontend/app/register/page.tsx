"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";


export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (password !== confirmation) {
      setError("兩次輸入的密碼不一致。");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName.trim(),
          workspace_name: workspaceName.trim(),
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        if (response.status === 409) {
          setError("此 Email 已經註冊，請直接登入。");
        } else if (response.status === 429) {
          setError("註冊嘗試過於頻繁，請稍後再試。");
        } else {
          setError(data?.detail || "目前無法完成註冊。");
        }
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
    <main className="auth-page register-page">
      <section className="auth-panel register-panel">
        <div className="brand-mark">M</div>
        <div className="eyebrow">START FREE</div>
        <h1 className="auth-title">建立 MarketingOS 帳號</h1>
        <p className="auth-description">
          建立你的品牌 Workspace，立即使用免費方案開始規劃內容。
        </p>

        <form className="auth-form register-form" onSubmit={submit}>
          <div className="register-field-grid">
            <label>
              姓名
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                autoComplete="name"
                maxLength={120}
                required
              />
            </label>
            <label>
              公司／品牌名稱
              <input
                value={workspaceName}
                onChange={(event) => setWorkspaceName(event.target.value)}
                autoComplete="organization"
                maxLength={150}
                required
              />
            </label>
          </div>

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              maxLength={255}
              required
            />
          </label>

          <div className="register-field-grid">
            <label>
              密碼
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
            <label>
              確認密碼
              <input
                type="password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
          </div>

          {error ? <div className="auth-error">{error}</div> : null}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "建立中…" : "免費建立帳號"}
          </button>
        </form>

        <p className="register-notice">
          註冊後會建立專屬 Workspace 並啟用免費方案。
          客戶端不顯示內部 AI 用量或成本資料。
        </p>
        <p className="auth-switch">
          已經有帳號？<a href="/login">返回登入</a>
        </p>
      </section>
    </main>
  );
}
