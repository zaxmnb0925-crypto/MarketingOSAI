"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useRouter } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
  slug?: string;
  role?: string;
};

type MeResponse = {
  workspaces?: Workspace[];
};

type Brand = {
  id: string;
  name: string;
};

type ContentGeneration = {
  id: string;
  brand_id: string;
  platform: string;
  topic: string;
  objective: string | null;
  status: string;
  generated_content: string | null;
  created_at: string;
  updated_at: string;
};

type SocialAccount = {
  id: string;
  platform: string;
  status: string;
  account_name?: string | null;
  username?: string | null;
  is_active?: boolean;
};

type SocialQuota = {
  plan_code: string;
  used: number;
  limit: number;
  remaining: number;
};

const platformLabels: Record<string, string> = {
  facebook: "臉書粉絲專頁",
  instagram: "Instagram",
  threads: "Threads",
  linkedin: "LinkedIn",
  x: "X",
};

const planLabels: Record<string, string> = {
  free: "免費版",
  pro: "專業版",
  business: "企業版",
};

const contentStatusLabels: Record<string, string> = {
  draft: "草稿",
  completed: "已完成",
  pending: "處理中",
  failed: "生成失敗",
};

function platformLabel(platform: string) {
  return platformLabels[platform] || platform;
}

function getDetail(data: unknown, fallback: string) {
  if (
    data &&
    typeof data === "object" &&
    "detail" in data
  ) {
    const detail = (data as { detail?: unknown }).detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }

  return fallback;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function PublicationDraftPage() {
  const router = useRouter();

  const [workspace, setWorkspace] =
    useState<Workspace | null>(null);
  const [brands, setBrands] =
    useState<Brand[]>([]);
  const [brandId, setBrandId] =
    useState("");
  const [generations, setGenerations] =
    useState<ContentGeneration[]>([]);
  const [accounts, setAccounts] =
    useState<SocialAccount[]>([]);
  const [quota, setQuota] =
    useState<SocialQuota | null>(null);
  const [selectedGenerationId, setSelectedGenerationId] =
    useState("");
  const [selectedAccountId, setSelectedAccountId] =
    useState("");
  const [loading, setLoading] =
    useState(true);
  const [contentLoading, setContentLoading] =
    useState(false);
  const [submitting, setSubmitting] =
    useState(false);
  const [error, setError] =
    useState("");
  const [notice, setNotice] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspaceData() {
      setLoading(true);
      setError("");

      try {
        const meResponse = await fetch(
          "/api/auth/me",
          { cache: "no-store" },
        );
        const meData = (await meResponse.json().catch(
          () => null,
        )) as MeResponse | null;

        if (meResponse.status === 401) {
          router.replace("/login");
          return;
        }

        if (!meResponse.ok) {
          throw new Error(
            getDetail(meData, "目前無法載入登入資訊。"),
          );
        }

        const currentWorkspace =
          meData?.workspaces?.[0];

        if (!currentWorkspace) {
          throw new Error("目前沒有可用的 Workspace。");
        }

        const workspaceId = encodeURIComponent(
          currentWorkspace.id,
        );

        const [
          brandResponse,
          accountResponse,
          quotaResponse,
        ] = await Promise.all([
          fetch(`/api/workspaces/${workspaceId}/brands`, {
            cache: "no-store",
          }),
          fetch(
            `/api/workspaces/${workspaceId}/social-accounts`,
            { cache: "no-store" },
          ),
          fetch(
            `/api/workspaces/${workspaceId}/social-accounts/quota`,
            { cache: "no-store" },
          ),
        ]);

        const [
          brandData,
          accountData,
          quotaData,
        ] = await Promise.all([
          brandResponse.json().catch(() => null),
          accountResponse.json().catch(() => null),
          quotaResponse.json().catch(() => null),
        ]);

        if (
          brandResponse.status === 401 ||
          accountResponse.status === 401 ||
          quotaResponse.status === 401
        ) {
          router.replace("/login");
          return;
        }

        if (!brandResponse.ok) {
          throw new Error(
            getDetail(brandData, "目前無法載入品牌資料。"),
          );
        }

        if (!accountResponse.ok) {
          throw new Error(
            getDetail(
              accountData,
              "目前無法載入社群帳號。",
            ),
          );
        }

        if (!Array.isArray(brandData)) {
          throw new Error("品牌資料格式錯誤。");
        }

        if (!Array.isArray(accountData)) {
          throw new Error("社群帳號資料格式錯誤。");
        }

        if (cancelled) return;

        setWorkspace(currentWorkspace);
        setBrands(brandData as Brand[]);
        setAccounts(accountData as SocialAccount[]);

        if (
          quotaResponse.ok &&
          quotaData &&
          typeof quotaData === "object"
        ) {
          setQuota(quotaData as SocialQuota);
        } else {
          setQuota(null);
        }

        const firstBrand =
          (brandData as Brand[])[0];

        if (firstBrand) {
          setBrandId(firstBrand.id);
        }
      } catch (caught) {
        if (cancelled) return;

        setError(
          caught instanceof Error
            ? caught.message
            : "目前無法載入發布草稿資料。",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadWorkspaceData();

    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    setGenerations([]);
    setSelectedGenerationId("");

    if (!brandId) {
      setContentLoading(false);
      return () => {
        cancelled = true;
      };
    }

    async function loadContent() {
      setContentLoading(true);
      setError("");

      try {
        const response = await fetch(
          `/api/workspaces/${encodeURIComponent(
            workspace?.id || "",
          )}/brands/${encodeURIComponent(
            brandId,
          )}/content`,
          { cache: "no-store" },
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
            getDetail(data, "目前無法載入內容歷史。"),
          );
        }

        if (!Array.isArray(data)) {
          throw new Error("內容歷史資料格式錯誤。");
        }

        const available = (
          data as ContentGeneration[]
        ).filter(
          (item) =>
            typeof item?.generated_content === "string" &&
            item.generated_content.trim().length > 0,
        );

        if (cancelled) return;

        setGenerations(available);
        setSelectedGenerationId(
          available[0]?.id || "",
        );
      } catch (caught) {
        if (cancelled) return;

        setError(
          caught instanceof Error
            ? caught.message
            : "目前無法載入內容歷史。",
        );
      } finally {
        if (!cancelled) {
          setContentLoading(false);
        }
      }
    }

    void loadContent();

    return () => {
      cancelled = true;
    };
  }, [brandId, router, workspace?.id]);

  const selectedGeneration =
    generations.find(
      (item) => item.id === selectedGenerationId,
    ) || null;

  const connectedAccounts = accounts.filter(
    (account) =>
      account.status === "connected" &&
      account.is_active !== false,
  );

  const compatibleAccounts = useMemo(
    () =>
      selectedGeneration
        ? connectedAccounts.filter(
            (account) =>
              account.platform ===
              selectedGeneration.platform,
          )
        : [],
    [accounts, selectedGeneration],
  );

  useEffect(() => {
    setSelectedAccountId((current) => {
      if (
        current &&
        compatibleAccounts.some(
          (account) => account.id === current,
        )
      ) {
        return current;
      }

      return compatibleAccounts[0]?.id || "";
    });
  }, [compatibleAccounts]);

  async function createPublicationDraft(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (
      !workspace ||
      !selectedGeneration ||
      !selectedAccountId
    ) {
      setError("請選擇內容與相同平台的社群帳號。");
      return;
    }

    const randomId =
      globalThis.crypto?.randomUUID?.() ||
      `${Date.now()}-${Math.random()
        .toString(36)
        .slice(2)}`;

    setSubmitting(true);

    try {
      const response = await fetch(
        `/api/workspaces/${encodeURIComponent(
          workspace.id,
        )}/publications/drafts`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            content_generation_id:
              selectedGeneration.id,
            social_account_id:
              selectedAccountId,
            idempotency_key:
              `web-draft-${randomId}`,
          }),
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
          getDetail(data, "目前無法建立發布草稿。"),
        );
      }

      setNotice(
        "發布草稿已建立，請到發布紀錄查看；後續仍需人工核准。",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "目前無法建立發布草稿。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function logout() {
    await fetch("/api/auth/logout", {
      method: "POST",
    });

    router.replace("/login");
  }

  return (
    <div className="dashboard-shell">
      <aside className="dashboard-sidebar">
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
          <a className="nav-item" href="/social-accounts">社群帳號</a>
          <a className="nav-item" href="/publications">發布紀錄</a>
          <a
            className="nav-item active"
            href="/publications/draft"
          >
            建立發布草稿
          </a>
        </nav>

        <button
          className="logout-button"
          onClick={logout}
        >
          登出
        </button>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">發布草稿</div>
            <h1>建立發布草稿</h1>
            <p>
              {workspace?.name || "目前 Workspace"} ·
              先審核內容，再進入受控發布流程
            </p>
          </div>

          <a
            className="dashboard-secondary-action"
            href="/publications"
          >
            返回發布紀錄
          </a>
        </header>

        {error ? (
          <div className="dashboard-error">{error}</div>
        ) : null}

        {notice ? (
          <div className="dashboard-notice">
            {notice}{" "}
            <a href="/publications">查看發布紀錄</a>
          </div>
        ) : null}

        <section className="dashboard-panel vertical">
          <div className="eyebrow">安全發布流程</div>
          <h2>只建立草稿，不會自動發布</h2>
          <p>
            選擇已有 AI 文案的內容，並指定相同平台的已連接社群帳號。
            建立草稿後仍需人工核准，這個動作不會呼叫 Meta 發布。
          </p>

          {quota ? (
            <p className="dashboard-notice">
              目前方案：
              {planLabels[quota.plan_code] ||
                quota.plan_code}
              {" · "}社群資產已使用 {quota.used} /{" "}
              {quota.limit} 組，剩餘 {quota.remaining} 組。
            </p>
          ) : null}

          {loading ? (
            <p>載入發布草稿資料中...</p>
          ) : brands.length === 0 ? (
            <div className="social-account-empty">
              <h2>目前沒有可用品牌</h2>
              <p>請先建立品牌，再選擇要發布的內容。</p>
            </div>
          ) : (
            <form
              className="form-grid"
              onSubmit={createPublicationDraft}
            >
              <label className="form-field">
                <span>品牌</span>
                <select
                  value={brandId}
                  onChange={(event) =>
                    setBrandId(event.target.value)
                  }
                >
                  {brands.map((brand) => (
                    <option
                      key={brand.id}
                      value={brand.id}
                    >
                      {brand.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="form-field">
                <span>內容來源</span>
                <select
                  value={selectedGenerationId}
                  disabled={
                    contentLoading ||
                    generations.length === 0
                  }
                  onChange={(event) =>
                    setSelectedGenerationId(
                      event.target.value,
                    )
                  }
                >
                  <option value="">
                    {contentLoading
                      ? "載入內容中..."
                      : "請選擇已有 AI 文案的內容"}
                  </option>

                  {generations.map((generation) => (
                    <option
                      key={generation.id}
                      value={generation.id}
                    >
                      {platformLabel(
                        generation.platform,
                      )}
                      {"｜"}
                      {generation.topic}
                      {"｜"}
                      {formatDate(
                        generation.created_at,
                      )}
                    </option>
                  ))}
                </select>
              </label>

              {selectedGeneration ? (
                <div className="publication-preview">
                  <div className="eyebrow">內容預覽</div>
                  <p>
                    {platformLabel(
                      selectedGeneration.platform,
                    )}
                    {" · "}
                    {contentStatusLabels[
                      selectedGeneration.status
                    ] || selectedGeneration.status}
                  </p>
                  <p
                    style={{
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {selectedGeneration.generated_content}
                  </p>
                </div>
              ) : (
                <p>
                  此品牌目前沒有可用的 AI 文案。
                  請先到 AI 創作或內容歷史建立內容。
                </p>
              )}

              <label className="form-field">
                <span>發布帳號</span>
                <select
                  value={selectedAccountId}
                  disabled={
                    !selectedGeneration ||
                    compatibleAccounts.length === 0
                  }
                  onChange={(event) =>
                    setSelectedAccountId(
                      event.target.value,
                    )
                  }
                >
                  <option value="">
                    {!selectedGeneration
                      ? "請先選擇內容"
                      : "請選擇相同平台的已連接帳號"}
                  </option>

                  {compatibleAccounts.map((account) => (
                    <option
                      key={account.id}
                      value={account.id}
                    >
                      {platformLabel(account.platform)}
                      {"｜"}
                      {account.account_name ||
                        account.username ||
                        "未命名帳號"}
                    </option>
                  ))}
                </select>
              </label>

              {connectedAccounts.length === 0 ? (
                <p>
                  目前沒有可用的已連接社群帳號，
                  請先到
                  <a href="/social-accounts">
                    社群帳號
                  </a>
                  連接 Meta。
                </p>
              ) : selectedGeneration &&
                compatibleAccounts.length === 0 ? (
                <p>
                  目前沒有與此內容平台相符的已連接帳號。
                  請回到社群帳號頁確認連線。
                </p>
              ) : null}

              <div className="social-account-actions">
                <button
                  className="dashboard-action"
                  type="submit"
                  disabled={
                    submitting ||
                    !selectedGeneration ||
                    !selectedAccountId
                  }
                >
                  {submitting
                    ? "建立中..."
                    : "建立發布草稿"}
                </button>

                <a
                  className="dashboard-secondary-action"
                  href="/publications"
                >
                  查看發布紀錄
                </a>
              </div>
            </form>
          )}
        </section>
      </main>
    </div>
  );
}
