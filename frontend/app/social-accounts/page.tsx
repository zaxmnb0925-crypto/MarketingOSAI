"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
  role?: string;
};

type MeResponse = {
  workspaces?: Workspace[];
};

type SocialAccount = {
  id: string;
  platform: string;
  status: string;
  account_name?: string | null;
  username?: string | null;
  last_synced_at?: string | null;
  token_expires_at?: string | null;
  last_error?: string | null;
};

const platformLabels: Record<string, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  threads: "Threads",
  linkedin: "LinkedIn",
  x: "X",
};

const statusLabels: Record<string, string> = {
  pending: "等待連接",
  connected: "已連接",
  expired: "授權已過期",
  revoked: "授權已撤銷",
  error: "連接錯誤",
};

function getDetail(data: unknown, fallback: string): string {
  if (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    typeof data.detail === "string"
  ) {
    return data.detail;
  }

  return fallback;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
  }).format(date);
}

export default function SocialAccountsPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadPage() {
    setLoading(true);
    setError("");

    try {
      const meResponse = await fetch("/api/auth/me", {
        cache: "no-store",
      });

      if (meResponse.status === 401) {
        router.replace("/login");
        return;
      }

      const meData = (await meResponse.json()) as MeResponse;
      const currentWorkspace = meData.workspaces?.[0];

      if (!currentWorkspace) {
        throw new Error("目前沒有可用的 Workspace。");
      }

      setWorkspace(currentWorkspace);

      const accountResponse = await fetch(
        `/api/workspaces/${encodeURIComponent(currentWorkspace.id)}/social-accounts`,
        { cache: "no-store" },
      );
      const accountData = await accountResponse.json().catch(() => null);

      if (accountResponse.status === 401) {
        router.replace("/login");
        return;
      }

      if (!accountResponse.ok) {
        throw new Error(
          getDetail(accountData, "目前無法載入社群帳號。"),
        );
      }

      if (!Array.isArray(accountData)) {
        throw new Error("社群帳號回應格式錯誤。");
      }

      setAccounts(accountData as SocialAccount[]);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "目前無法載入社群帳號。",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPage();
  }, [router]);

  async function connectMeta() {
    if (!workspace) return;

    setConnecting(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `/api/workspaces/${encodeURIComponent(workspace.id)}/oauth/meta/connect`,
        { method: "POST" },
      );
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          getDetail(data, "目前無法啟動 Meta 授權。"),
        );
      }

      if (!data || typeof data.authorization_url !== "string") {
        throw new Error("Meta 授權網址回應格式錯誤。");
      }

      setNotice("即將前往 Meta 授權頁面。");
      window.location.assign(data.authorization_url);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "目前無法啟動 Meta 授權。",
      );
      setConnecting(false);
    }
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="dashboard-loading">
        正在載入社群帳號...
      </main>
    );
  }

  if (!workspace) {
    return (
      <main className="dashboard-loading">
        {error || "目前沒有可用的 Workspace。"}
      </main>
    );
  }

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
            <a className="nav-item" href="/billing">方案與帳務</a>
            <a className="nav-item active" href="/social-accounts">社群帳號</a>
          </nav>
        </div>

        <button className="logout-button" onClick={logout}>
          登出
        </button>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">社群帳號連線</div>
            <h1>社群帳號</h1>
            <p>{workspace.name} · 管理社群發布帳號</p>
          </div>
        </header>

        {error ? (
          <div className="dashboard-error">{error}</div>
        ) : null}

        {notice ? (
          <div className="dashboard-notice">{notice}</div>
        ) : null}

        <section className="dashboard-panel vertical">
          <div className="social-account-toolbar">
            <div>
              <div className="eyebrow">帳號連線</div>
              <h2>已連接帳號</h2>
              <p>
                連接後才能建立發布草稿；實際發布仍需人工確認。
              </p>
            </div>

            <div className="social-account-actions">
              <button
                className="dashboard-secondary-action"
                type="button"
                onClick={() => void loadPage()}
                disabled={loading || connecting}
              >
                重新整理
              </button>
              <button
                className="dashboard-action"
                type="button"
                onClick={() => void connectMeta()}
                disabled={connecting}
              >
                {connecting ? "準備授權中..." : "連接 Meta"}
              </button>
            </div>
          </div>

          {accounts.length === 0 ? (
            <div className="social-account-empty">
              <div className="eyebrow">NOT CONNECTED</div>
              <h2>尚未連接社群帳號</h2>
              <p>
                請先連接 Meta，授權 Facebook 或 Instagram
                頁面後，再回到本頁重新整理。
              </p>
              <button
                className="dashboard-action"
                type="button"
                onClick={() => void connectMeta()}
                disabled={connecting}
              >
                {connecting
                  ? "準備授權中..."
                  : "連接 Facebook / Instagram"}
              </button>
            </div>
          ) : (
            <div className="social-account-grid">
              {accounts.map((account) => (
                <article
                  className="social-account-card"
                  key={account.id}
                >
                  <div className="social-account-card-header">
                    <div>
                      <div className="eyebrow">
                        {platformLabels[account.platform] ||
                          account.platform}
                      </div>
                      <h3>
                        {account.account_name ||
                          account.username ||
                          "未命名帳號"}
                      </h3>
                    </div>
                    <span className="social-account-status">
                      {statusLabels[account.status] ||
                        account.status}
                    </span>
                  </div>

                  <p>使用者名稱：{account.username || "—"}</p>
                  <p>最後同步：{formatDate(account.last_synced_at)}</p>
                  <p>授權到期：{formatDate(account.token_expires_at)}</p>

                  {account.last_error ? (
                    <p className="social-account-error">
                      {account.last_error}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="dashboard-panel vertical">
          <div className="eyebrow">發布安全</div>
          <h2>發布流程</h2>
          <p>
            連接帳號 → 建立發布草稿 → 送審與 dry-run
            → 人工確認發布。
          </p>
          <p>
            系統不會因為連接帳號而自動發布內容。
          </p>
        </section>
      </section>
    </main>
  );
}
