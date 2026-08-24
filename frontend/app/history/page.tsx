"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import type {
  MeResponse,
  Brand,
  ContentItem,
} from "./_lib/history-types";

import {
  formatDate,
  statusLabel,
  platformLabel,
} from "./_lib/history-formatters";

import {
  HistoryToolbar,
} from "./_components/HistoryToolbar";

import {
  HistorySummary,
} from "./_components/HistorySummary";

import {
  HistoryList,
} from "./_components/HistoryList";

import {
  useContentHistory,
} from "./_hooks/useContentHistory";

export default function HistoryPage() {
  const router = useRouter();

  const {
    workspace,
    setWorkspace,
    brands,
    setBrands,
    selectedBrandId,
    setSelectedBrandId,
    items,
    setItems,
    statusFilter,
    setStatusFilter,
    platformFilter,
    setPlatformFilter,
    loading,
    setLoading,
    historyLoading,
    setHistoryLoading,
    error,
    setError,
    expandedId,
    setExpandedId,
    filteredItems,
    completedCount,
    failedCount,
    pendingCount,
  } = useContentHistory();

  

  

  

  

  

  

  

  

  

  

  async function loadHistory(
    workspaceId: string,
    brandId: string,
  ) {
    setHistoryLoading(true);
    setError("");

    try {
      const response =
        await fetch(
          `/api/workspaces/${workspaceId}/brands/${brandId}/content`,
          {
            cache: "no-store",
          },
        );

      if (
        response.status === 401
      ) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          "Unable to load content history",
        );
      }

      const data: ContentItem[] =
        await response.json();

      setItems(data);
    } catch {
      setError(
        "無法載入內容歷史。",
      );
      setItems([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    async function boot() {
      try {
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
          throw new Error();
        }

        const meData: MeResponse =
          await meResponse.json();

        const currentWorkspace =
          meData.workspaces[0];

        if (!currentWorkspace) {
          throw new Error();
        }

        setWorkspace(
          currentWorkspace,
        );

        const brandResponse =
          await fetch(
            `/api/workspaces/${currentWorkspace.id}/brands`,
            {
              cache: "no-store",
            },
          );

        if (!brandResponse.ok) {
          throw new Error();
        }

        const brandData: Brand[] =
          await brandResponse.json();

        setBrands(brandData);

        if (
          brandData.length > 0
        ) {
          const firstBrand =
            brandData[0];

          setSelectedBrandId(
            firstBrand.id,
          );

          await loadHistory(
            currentWorkspace.id,
            firstBrand.id,
          );
        }
      } catch {
        setError(
          "無法載入 Content History。",
        );
      } finally {
        setLoading(false);
      }
    }

    void boot();
  }, []);

  async function changeBrand(
    brandId: string,
  ) {
    setSelectedBrandId(
      brandId,
    );

    setExpandedId(null);

    if (
      workspace &&
      brandId
    ) {
      await loadHistory(
        workspace.id,
        brandId,
      );
    }
  }

  async function copyContent(
    content: string,
  ) {
    await navigator.clipboard.writeText(
      content,
    );
  }

  async function logout() {
    await fetch(
      "/api/auth/logout",
      {
        method: "POST",
      },
    );

    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="dashboard-loading">
        正在載入內容歷史...
      </main>
    );
  }

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
              className="nav-item"
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

            <a
              className="nav-item active"
              href="/history"
            >
              內容歷史
            </a>

            <span className="nav-item disabled">
              發布排程
            </span>
          </nav>
        </div>

        <button
          className="logout-button"
          onClick={logout}
        >
          登出
        </button>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <div className="eyebrow">
              CONTENT HISTORY
            </div>

            <h1>
              內容歷史
            </h1>

            <p>
              查看每個品牌的 AI
              文案與任務狀態。
            </p>
          </div>
        </header>

        <HistoryToolbar
          brands={brands}
          selectedBrandId={selectedBrandId}
          changeBrand={changeBrand}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          platformFilter={platformFilter}
          setPlatformFilter={setPlatformFilter}
        />

        <HistorySummary
          items={items}
          completedCount={completedCount}
          failedCount={failedCount}
          pendingCount={pendingCount}
        />

        {error ? (
          <div className="dashboard-error">
            {error}
          </div>
        ) : null}

        <HistoryList
          historyLoading={historyLoading}
          filteredItems={filteredItems}
          expandedId={expandedId}
          setExpandedId={setExpandedId}
          copyContent={copyContent}
        />
      </section>
    </main>
  );
}
