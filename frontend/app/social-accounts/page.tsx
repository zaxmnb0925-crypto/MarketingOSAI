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

type SocialAccountQuota = {
  plan_code: string;
  used: number;
  limit: number | null;
  remaining: number | null;
};

const platformLabels: Record<string, string> = {
  facebook: "臉書粉絲專頁",
  instagram: "Instagram",
  threads: "Threads",
  linkedin: "LinkedIn",
  x: "X",
};

const planLabels: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  business: "Business",
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

function isSocialAccountQuota(
  data: unknown,
): data is SocialAccountQuota {
  if (
    typeof data !== "object" ||
    data === null
  ) {
    return false;
  }

  const candidate = data as Record<string, unknown>;

  return (
    typeof candidate.plan_code === "string" &&
    typeof candidate.used === "number" &&
    (
      candidate.limit === null ||
      typeof candidate.limit === "number"
    ) &&
    (
      candidate.remaining === null ||
      typeof candidate.remaining === "number"
    )
  );
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
  const [quota, setQuota] =
    useState<SocialAccountQuota | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [quotaError, setQuotaError] = useState("");

  async function loadPage() {
    setLoading(true);
    setError("");
    setQuota(null);
    setQuotaError("");

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

      const quotaResponse = await fetch(
        `/api/workspaces/${encodeURIComponent(currentWorkspace.id)}/social-accounts/quota`,
        { cache: "no-store" },
      );
      const quotaData = await quotaResponse.json().catch(
        () => null,
      );

      if (quotaResponse.status === 401) {
        router.replace("/login");
        return;
      }

      if (!quotaResponse.ok) {
        setQuotaError(
          getDetail(
            quotaData,
            "目前無法載入社群帳號額度。",
          ),
        );
      } else if (!isSocialAccountQuota(quotaData)) {
        setQuotaError("社群帳號額度回應格式錯誤。");
      } else {
        setQuota(quotaData);
      }
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
              <div className="eyebrow">方案額度</div>
              <h2>社群資產綁定額度</h2>
              <p>
                目前方案可綁定的社群帳號數量。
              </p>
            </div>
          </div>

          {quota ? (
            <div className="social-account-grid">
              <article className="social-account-card">
                <div className="social-account-card-header">
                  <div>
                    <div className="eyebrow">目前方案</div>
                    <h3>
                      {planLabels[quota.plan_code] ||
                        quota.plan_code}
                    </h3>
                  </div>
                  <span className="social-account-status">
                    {quota.limit === null
                      ? "彈性使用"
                      : `上限 ${quota.limit} 組`}
                  </span>
                </div>

                <p>
                  {quota.limit === null
                    ? `已使用 ${quota.used} 組（無固定上限）`
                    : `已使用 ${quota.used} / ${quota.limit} 組`}
                </p>
                <p>
                  剩餘：
                  {quota.remaining === null
                    ? "不設固定上限"
                    : `${quota.remaining} 組`}
                </p>
                <p>
                  額度只計算目前啟用中的社群資產。
                </p>

                {quota.limit !== null &&
                quota.remaining === 0 ? (
                  <p className="social-account-error">
                    目前方案額度已用滿；請先解除既有帳號
                    或升級方案。
                  </p>
                ) : null}
              </article>
            </div>
          ) : quotaError ? (
            <div className="dashboard-error">
              {quotaError}
            </div>
          ) : (
            <p>載入方案額度中...</p>
          )}
        </section>

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
              <div className="eyebrow">尚未連接</div>
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
