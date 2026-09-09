"use client";

import {
  FormEvent,
  useState,
} from "react";

import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [rememberMe, setRememberMe] =
    useState(true);

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const response = await fetch(
        "/api/auth/login",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            email,
            password,
            remember_me: rememberMe,
          }),
        },
      );

      const data =
        await response.json();

      if (!response.ok) {
        setError(
          data?.detail ||
            "登入失敗，請檢查帳號與密碼。",
        );

        return;
      }

      const nextPath = new URLSearchParams(
        window.location.search,
      ).get("next");

      router.replace(
        nextPath === "/admin" ||
        nextPath === "/governance"
          ? nextPath
          : "/dashboard",
      );
      router.refresh();
    } catch {
      setError(
        "目前無法連線至登入服務。",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="brand-mark">
          M
        </div>

        <div className="eyebrow">
          MarketingOS AI
        </div>

        <h1 className="auth-title">
          歡迎回來
        </h1>

        <p className="auth-description">
          登入你的 AI 行銷工作空間。
        </p>

        <form
          className="auth-form"
          autoComplete="on"
          onSubmit={handleSubmit}
        >
          <label>
            Email
            <input
              id="login-username"
              name="username"
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(
                  event.target.value,
                )
              }
              autoComplete="username"
              required
            />
          </label>

          <label>
            密碼
            <input
              id="login-password"
              name="password"
              type="password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value,
                )
              }
              autoComplete="current-password"
              required
            />
          </label>

          <div className="auth-remember-row">
            <input
              id="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(event) =>
                setRememberMe(event.target.checked)
              }
            />
            <label htmlFor="remember-me">
              記住登入狀態（30天）
            </label>
          </div>

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
            {loading
              ? "登入中..."
              : "登入 MarketingOS"}
          </button>
        </form>

        <div className="auth-links">
          還沒有帳號？ <a href="/register">免費註冊</a>
        </div>

        <div className="auth-links">
          遇到系統問題？ <a href="/support">公開問題回報</a>
        </div>

        <div className="auth-security">
          安全登入 · HttpOnly Session
        </div>
      </section>
    </main>
  );
}
