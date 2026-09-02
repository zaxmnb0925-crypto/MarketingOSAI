"use client";

import { brandToForm, type Brand, type BrandForm } from "./_lib/brands-form";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { sessionFetch } from "@/lib/session-fetch";

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type MeResponse = {
  user: {
    email: string;
    full_name: string | null;
  };
  workspaces: Workspace[];
};


const emptyForm: BrandForm = {
  name: "",
  industry: "",
  website: "",
  description: "",
  tone: "",
  target_audience: "",
  brand_voice: "",
  value_proposition: "",
  products_services: "",
  keywords: "",
  forbidden_words: "",
  default_cta: "",
  language: "zh-TW",
  country: "Taiwan",
  brand_guidelines: "",
};


export default function BrandsPage() {
  const router = useRouter();

  const [workspaceId, setWorkspaceId] =
    useState("");

  const [brands, setBrands] =
    useState<Brand[]>([]);

  const [selectedId, setSelectedId] =
    useState<string | null>(null);

  const [form, setForm] =
    useState<BrandForm>(emptyForm);

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState("");

  async function loadBrands(
    targetWorkspaceId: string,
  ) {
    const response = await sessionFetch(
      `/api/workspaces/${targetWorkspaceId}/brands`,
      {
        cache: "no-store",
      },
    );

    if (response.status === 401) {
      router.replace("/login");
      return;
    }

    if (!response.ok) {
      throw new Error(
        "Unable to load brands",
      );
    }

    const data: Brand[] =
      await response.json();

    setBrands(data);
  }

  useEffect(() => {
    async function boot() {
      try {
        const response =
          await sessionFetch(
            "/api/auth/me",
            {
              cache: "no-store",
            },
          );

        if (response.status === 401) {
          router.replace("/login");
          return;
        }

        if (!response.ok) {
          throw new Error(
            "Unable to load account",
          );
        }

        const me: MeResponse =
          await response.json();

        const workspace =
          me.workspaces[0];

        if (!workspace) {
          throw new Error(
            "No workspace found",
          );
        }

        setWorkspaceId(
          workspace.id,
        );

        await loadBrands(
          workspace.id,
        );
      } catch (error) {
        setMessage(
          error instanceof Error
            ? error.message
            : "載入失敗",
        );
      } finally {
        setLoading(false);
      }
    }

    void boot();
  }, []);

  function startCreate() {
    setSelectedId(null);
    setForm(emptyForm);
    setMessage("");
  }

  function startEdit(
    brand: Brand,
  ) {
    setSelectedId(brand.id);
    setForm(
      brandToForm(brand),
    );
    setMessage("");
  }

  function updateField(
    key: keyof BrandForm,
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function saveBrand(
    event: FormEvent,
  ) {
    event.preventDefault();

    if (!workspaceId) {
      return;
    }

    if (!form.name.trim()) {
      setMessage(
        "品牌名稱為必填。",
      );
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const url = selectedId
        ? `/api/workspaces/${workspaceId}/brands/${selectedId}`
        : `/api/workspaces/${workspaceId}/brands`;

      const response =
        await sessionFetch(url, {
          method: selectedId
            ? "PATCH"
            : "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(
            form,
          ),
        });

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data?.detail ===
            "string"
            ? data.detail
            : "儲存品牌失敗",
        );
      }

      await loadBrands(
        workspaceId,
      );

      setSelectedId(
        data.id,
      );

      setForm(
        brandToForm(data),
      );

      setMessage(
        selectedId
          ? "Brand Brain 已更新。"
          : "品牌已建立。",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "儲存失敗",
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteBrand() {
    if (
      !workspaceId ||
      !selectedId
    ) {
      return;
    }

    const brand =
      brands.find(
        (item) =>
          item.id === selectedId,
      );

    if (
      !window.confirm(
        `確定刪除 ${
          brand?.name || "此品牌"
        }？`,
      )
    ) {
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const response =
        await sessionFetch(
          `/api/workspaces/${workspaceId}/brands/${selectedId}`,
          {
            method: "DELETE",
          },
        );

      if (!response.ok) {
        let detail =
          "刪除品牌失敗";

        try {
          const data =
            await response.json();

          if (
            typeof data?.detail ===
            "string"
          ) {
            detail =
              data.detail;
          }
        } catch {
          // no-op
        }

        throw new Error(detail);
      }

      await loadBrands(
        workspaceId,
      );

      setSelectedId(null);
      setForm(emptyForm);

      setMessage(
        "品牌已刪除。",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "刪除失敗",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="brand-page">
        <div className="brand-loading">
          載入品牌資料中…
        </div>
      </main>
    );
  }

  return (
    <main className="brand-page">
      <div className="brand-shell">
        <header className="brand-header">
          <div>
            <p className="brand-eyebrow">
              MarketingOS AI
            </p>

            <h1>
              品牌管理
            </h1>

            <p className="brand-subtitle">
              建立 Brand Brain，
              讓 AI 了解每一個品牌。
            </p>
          </div>

          <div className="brand-header-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                router.push(
                  "/dashboard",
                )
              }
            >
              Dashboard
            </button>

            <button
              type="button"
              className="primary-button"
              onClick={startCreate}
            >
              ＋ 新增品牌
            </button>
          </div>
        </header>

        <div className="brand-layout">
          <aside className="brand-sidebar">
            <div className="brand-sidebar-title">
              我的品牌
              <span>
                {brands.length}
              </span>
            </div>

            <div className="brand-list">
              {brands.map(
                (brand) => (
                  <button
                    key={brand.id}
                    type="button"
                    className={
                      selectedId ===
                      brand.id
                        ? "brand-list-item active"
                        : "brand-list-item"
                    }
                    onClick={() =>
                      startEdit(
                        brand,
                      )
                    }
                  >
                    <strong>
                      {brand.name}
                    </strong>

                    <span>
                      {brand.industry ||
                        "尚未設定產業"}
                    </span>
                  </button>
                ),
              )}

              {brands.length ===
                0 && (
                <div className="brand-empty">
                  尚未建立品牌。
                </div>
              )}
            </div>
          </aside>

          <section className="brand-editor">
            <div className="brand-editor-heading">
              <div>
                <p className="brand-section-label">
                  Brand Brain
                </p>

                <h2>
                  {selectedId
                    ? "編輯品牌"
                    : "建立新品牌"}
                </h2>
              </div>

              {selectedId && (
                <button
                  type="button"
                  className="danger-button"
                  disabled={saving}
                  onClick={
                    deleteBrand
                  }
                >
                  刪除品牌
                </button>
              )}
            </div>

            <form
              className="brand-form"
              onSubmit={saveBrand}
            >
              <div className="brand-form-grid">
                <label>
                  品牌名稱 *
                  <input
                    required
                    value={form.name}
                    onChange={(e) =>
                      updateField(
                        "name",
                        e.target.value,
                      )
                    }
                    placeholder="例如：Alpha Coffee"
                  />
                </label>

                <label>
                  產業
                  <input
                    value={
                      form.industry
                    }
                    onChange={(e) =>
                      updateField(
                        "industry",
                        e.target.value,
                      )
                    }
                    placeholder="餐飲、電商、美容、物流…"
                  />
                </label>

                <label>
                  國家 / 市場
                  <input
                    value={
                      form.country
                    }
                    onChange={(e) =>
                      updateField(
                        "country",
                        e.target.value,
                      )
                    }
                  />
                </label>

                <label>
                  語言
                  <input
                    value={
                      form.language
                    }
                    onChange={(e) =>
                      updateField(
                        "language",
                        e.target.value,
                      )
                    }
                    placeholder="zh-TW"
                  />
                </label>

                <label className="brand-full">
                  官方網站
                  <input
                    type="url"
                    value={
                      form.website
                    }
                    onChange={(e) =>
                      updateField(
                        "website",
                        e.target.value,
                      )
                    }
                    placeholder="https://..."
                  />
                </label>

                <label className="brand-full">
                  品牌介紹
                  <textarea
                    value={
                      form.description
                    }
                    onChange={(e) =>
                      updateField(
                        "description",
                        e.target.value,
                      )
                    }
                    placeholder="品牌是誰、主要提供什麼…"
                  />
                </label>

                <label>
                  品牌語調
                  <input
                    value={form.tone}
                    onChange={(e) =>
                      updateField(
                        "tone",
                        e.target.value,
                      )
                    }
                    placeholder="專業親切"
                  />
                </label>

                <label>
                  預設 CTA
                  <input
                    value={
                      form.default_cta
                    }
                    onChange={(e) =>
                      updateField(
                        "default_cta",
                        e.target.value,
                      )
                    }
                    placeholder="立即了解更多"
                  />
                </label>

                <label className="brand-full">
                  目標客群
                  <textarea
                    value={
                      form.target_audience
                    }
                    onChange={(e) =>
                      updateField(
                        "target_audience",
                        e.target.value,
                      )
                    }
                  />
                </label>

                <label className="brand-full">
                  Brand Voice
                  <textarea
                    value={
                      form.brand_voice
                    }
                    onChange={(e) =>
                      updateField(
                        "brand_voice",
                        e.target.value,
                      )
                    }
                  />
                </label>

                <label className="brand-full">
                  價值主張
                  <textarea
                    value={
                      form.value_proposition
                    }
                    onChange={(e) =>
                      updateField(
                        "value_proposition",
                        e.target.value,
                      )
                    }
                  />
                </label>

                <label className="brand-full">
                  產品 / 服務
                  <textarea
                    value={
                      form.products_services
                    }
                    onChange={(e) =>
                      updateField(
                        "products_services",
                        e.target.value,
                      )
                    }
                  />
                </label>

                <label className="brand-full">
                  品牌關鍵字
                  <textarea
                    value={
                      form.keywords
                    }
                    onChange={(e) =>
                      updateField(
                        "keywords",
                        e.target.value,
                      )
                    }
                    placeholder="以逗號分隔"
                  />
                </label>

                <label className="brand-full">
                  禁止詞
                  <textarea
                    value={
                      form.forbidden_words
                    }
                    onChange={(e) =>
                      updateField(
                        "forbidden_words",
                        e.target.value,
                      )
                    }
                    placeholder="AI 不得使用的詞彙或宣稱"
                  />
                </label>

                <label className="brand-full">
                  品牌規範
                  <textarea
                    value={
                      form.brand_guidelines
                    }
                    onChange={(e) =>
                      updateField(
                        "brand_guidelines",
                        e.target.value,
                      )
                    }
                    placeholder="文案、視覺、法規或品牌限制"
                  />
                </label>
              </div>

              {message && (
                <div className="brand-message">
                  {message}
                </div>
              )}

              <div className="brand-save-row">
                <button
                  type="submit"
                  className="primary-button"
                  disabled={saving}
                >
                  {saving
                    ? "儲存中…"
                    : selectedId
                      ? "儲存 Brand Brain"
                      : "建立品牌"}
                </button>
              </div>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
