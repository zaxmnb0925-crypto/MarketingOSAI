 "use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
};

type MeResponse = {
  workspaces?: Workspace[];
};

type Publication = {
  id: string;
  platform: string;
  status: string;
  target_account_name?: string | null;
  content_snapshot: string;
  created_at: string;
  published_at?: string | null;
};

const platformLabels: Record<string, string> = {
  facebook: "臉書粉絲專頁",
  instagram: "Instagram",
  threads: "Threads",
  linkedin: "LinkedIn",
  x: "X",
};

const statusLabels: Record<string, string> = {
  draft: "草稿",
  approved: "已核准",
  publishing: "發布中",
  published: "已發布",
  failed: "發布失敗",
  reconciliation_required: "待核對",
};

function getDetail(data: unknown, fallback: string): string {
  if (
    typeof data === "object" &&
    data !== null &&
    "detail" in data
  ) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }

  return fallback;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function PublicationsPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);
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

      const response = await fetch(
        `/api/workspaces/${encodeURIComponent(currentWorkspace.id)}/publications`,
        { cache: "no-store" },
      );
      const data = await response.json().catch(() => null);

      if (response.status === 401) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          getDetail(data, "目前無法載入發布紀錄。"),
        );
      }

      if (!Array.isArray(data)) {
        throw new Error("發布紀錄回應格式錯誤。");
      }

      setPublications(data as Publication[]);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "目前無法載入發布紀錄。",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPage();
  }, [router]);

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
    });
    router.replace("/login");
  }

  async function approvePublication(
    publicationId: string,
  ) {
    if (!workspace) {
      return;
    }

    if (
      !window.confirm(
        "確認核准這份發布草稿？核准後仍需另外確認才會正式發布。",
      )
    ) {
      return;
    }

    setError("");

    try {
      const response = await fetch(
        `/api/workspaces/${encodeURIComponent(
          workspace.id,
        )}/publications/${encodeURIComponent(
          publicationId,
        )}/approve`,
        {
          method: "POST",
        },
      );

      const data = await response.json().catch(
        () => null,
      );

      if (response.status === 401) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          getDetail(data, "目前無法核准發布草稿。"),
        );
      }

      await loadPage();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "目前無法核准發布草稿。",
      );
    }
  }

  async function postPublicationAction(
    publicationId: string,
    action: string,
    body?: unknown,
  ) {
    if (!workspace) {
      throw new Error("目前沒有可用的 Workspace。");
    }

    const response = await fetch(
      `/api/workspaces/${encodeURIComponent(
        workspace.id,
      )}/publications/${encodeURIComponent(
        publicationId,
      )}/${action}`,
      {
        method: "POST",
        ...(body === undefined
          ? {}
          : {
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(body),
            }),
      },
    );

    const data = await response.json().catch(
      () => null,
    );

    if (response.status === 401) {
      router.replace("/login");
      throw new Error("登入已逾時。");
    }

    if (!response.ok) {
      throw new Error(
        getDetail(data, "正式發布流程未通過。"),
      );
    }

    return data as Record<string, unknown>;
  }

  async function publishPublication(
    publicationId: string,
  ) {
    if (!window.confirm(
      "確認正式發布到 Facebook？這會對外發布內容。",
    )) {
      return;
    }

    setError("");
    setNotice("");

    try {
      const activation = await postPublicationAction(
        publicationId,
        "publish-activation",
      );

      const confirmation =
        await postPublicationAction(
          publicationId,
          "publish-confirmation",
        );

      const result = await postPublicationAction(
        publicationId,
        "publish",
        {
          activation: activation.activation,
          confirmation: confirmation.confirmation,
          content_hash: confirmation.content_hash,
        },
      );

      setNotice(
        result.status === "published"
          ? "已正式發布到 Facebook。"
          : "發布請求已送出，請重新整理確認狀態。",
      );

      await loadPage();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "正式發布流程未通過。",
      );
    }
  }

  async function runDryRun(
    publicationId: string,
  ) {
    if (!workspace) {
      return;
    }

    setError("");
    setNotice("");

    try {
      const response = await fetch(
        `/api/workspaces/${encodeURIComponent(
          workspace.id,
        )}/publications/${encodeURIComponent(
          publicationId,
        )}/dry-run`,
        {
          method: "POST",
        },
      );

      const data = await response.json().catch(
        () => null,
      );

      if (response.status === 401) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          getDetail(data, "發布前檢查未通過。"),
        );
      }

      setNotice(
        `發布前檢查通過：${data.platform} · ` +
        `內容 ${data.content_length} 字 · ` +
        `SHA-256 ${data.content_hash}`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "發布前檢查未通過。",
      );
    }
  }

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-sidebar">
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
            <a className="nav-item active" href="/publications">發布紀錄</a>
            <a className="nav-item" href="/publications/draft">建立發布草稿</a>
            <a className="nav-item" href="/social-accounts">社群帳號</a>
          </nav>
        </div>

        <button className="logout-button" onClick={() => void logout()}>
          登出
        </button>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">發布紀錄</div>
            <h1>發布工作台</h1>
            <p>
              {workspace?.name ?? "目前 Workspace"} · 查看發布草稿與處理狀態
            </p>
          </div>
        </header>

        {error ? (
          <div className="dashboard-error">{error}</div>
        ) : null}
        {notice ? (
          <div className="dashboard-success">{notice}</div>
        ) : null}

        <section className="dashboard-panel vertical">
          <div className="social-account-toolbar">
            <div>
              <div className="eyebrow">唯讀檢視</div>
              <h2>發布草稿與狀態</h2>
              <p>
                目前僅供查看，不會自動發布內容。
              </p>
            </div>

            <button
              className="dashboard-secondary-action"
              type="button"
              onClick={() => void loadPage()}
              disabled={loading}
            >
              重新整理
            </button>
          </div>

          {loading ? (
            <p>載入發布紀錄中...</p>
          ) : publications.length === 0 ? (
            <div className="social-account-empty">
              <div className="eyebrow">尚無紀錄</div>
              <h2>目前沒有發布紀錄</h2>
              <p>
                建立發布草稿後，相關內容會顯示在這裡。
              </p>
            </div>
          ) : (
            <div className="social-account-grid">
              {publications.map((publication) => (
                <article
                  className="social-account-card"
                  key={publication.id}
                >
                  <div className="social-account-card-header">
                    <div>
                      <div className="eyebrow">
                        {platformLabels[publication.platform] ||
                          "其他平台"}
                      </div>
                      <h3>
                        {publication.target_account_name ||
                          "未命名發布帳號"}
                      </h3>
                    </div>

                    <span className="social-account-status">
                      {statusLabels[publication.status] ||
                        "處理中"}
                    </span>
                  </div>

                  <p>
                    建立時間：{formatDate(publication.created_at)}
                  </p>

                  {publication.published_at ? (
                    <p>
                      發布時間：{formatDate(publication.published_at)}
                    </p>
                  ) : null}

                  <div style={{ whiteSpace: "pre-wrap" }}>
                    {publication.content_snapshot}
                  </div>

                  {publication.status === "draft" ? (
                    <button
                      className="dashboard-primary-action"
                      type="button"
                      onClick={() =>
                        void approvePublication(publication.id)
                      }
                    >
                      人工核准
                    </button>
                  ) : null}
                  {publication.status === "approved" ? (
                    <button
                      className="dashboard-secondary-action"
                      type="button"
                      onClick={() =>
                        void runDryRun(publication.id)
                      }
                    >
                      發布前檢查
                    </button>
                  ) : null}
                  {publication.status === "approved" ? (
                    <button
                      className="dashboard-primary-action"
                      type="button"
                      onClick={() =>
                        void publishPublication(publication.id)
                      }
                    >
                      正式發布
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          )}

          <p>
            正式發布仍需通過人工核准與安全檢查。
          </p>
        </section>
      </section>
    </main>
  );
}
