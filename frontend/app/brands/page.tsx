"use client";

import { brandToForm, type Brand, type BrandForm } from "./_lib/brands-form";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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
    const response = await fetch(
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
          await fetch(
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

  function applyLogisticsTemplate() {
    setSelectedId(null);
    setForm({
      ...emptyForm,
      name: "可樂星集運",
      industry: "跨境集運／物流",
      description:
        "可樂星集運協助台灣消費者整理、合併從中國大陸購買的商品，提供到貨確認、包裹整併與寄送台灣服務，讓跨境購物更清楚、方便、安心。",
      tone: "專業、親切、透明",
      target_audience:
        "台灣個人消費者、常在淘寶、拼多多及其他中國大陸電商平台購物，需要將多筆包裹集中寄回台灣的人。",
      brand_voice:
        "使用台灣繁體中文，語氣專業但不生硬、親切但不浮誇。先說重點，再清楚說明流程、費用、時效與可能限制。避免誇大承諾；遇到延誤或異常時，要誠實說明並提供下一步。",
      value_proposition:
        "把分散在中國大陸的多筆包裹集中管理，一次確認到貨、合併寄送台灣，減少追蹤與溝通成本，讓跨境購物更簡單。",
      products_services:
        "中國大陸包裹到貨確認、包裹合併、集運寄送台灣、物流狀態查詢與客服協助。",
      keywords:
        "跨境集運、包裹合併、淘寶集運、寄送台灣、到貨確認、費用透明",
      forbidden_words:
        "保證到貨、絕對最低價、百分之百不延誤",
      default_cta: "立即查詢包裹",
      brand_guidelines:
        "使用台灣繁體中文；費用、流程與時效要清楚說明，不做無法證實的保證。",
    });
    setMessage(
      "已套用集運範本，請確認內容後儲存。",
    );
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
        await fetch(url, {
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
        await fetch(
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
              先填基本資料，其餘內容可稍後補充；
              儲存後 AI 會依照這些內容產生文案。
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
              className="secondary-button brand-template-button"
              onClick={applyLogisticsTemplate}
            >
              套用集運範本
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
                  品牌資料庫
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
                <div className="brand-form-intro brand-full">
                  <span className="brand-form-intro-icon">
                    ✦
                  </span>
                  <div>
                    <strong>不用一次想完，先從基本資料開始</strong>
                    <p>
                      品牌名稱、產業、品牌介紹與目標客群填好後，
                      AI 就能開始理解你的品牌。
                    </p>
                  </div>
                </div>

                <div className="brand-form-section brand-full">
                  <span className="brand-form-section-number">
                    01
                  </span>
                  <div>
                    <strong>基本資料</strong>
                    <p>先告訴 AI 你的品牌是誰，以及在哪裡提供服務。</p>
                  </div>
                </div>

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

                <div className="brand-form-section brand-full">
                  <span className="brand-form-section-number">
                    02
                  </span>
                  <div>
                    <strong>品牌定位</strong>
                    <p>說明服務對象、品牌差異與希望客戶採取的行動。</p>
                  </div>
                </div>

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

                <div className="brand-form-section brand-full">
                  <span className="brand-form-section-number">
                    03
                  </span>
                  <div>
                    <strong>AI 寫作規則</strong>
                    <p>告訴 AI 應該用什麼語氣，以及哪些事情不能亂說。</p>
                  </div>
                </div>

                <label className="brand-full">
                  AI 寫作語氣
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

                <div className="brand-form-section brand-full">
                  <span className="brand-form-section-number">
                    04
                  </span>
                  <div>
                    <strong>進階限制（可選）</strong>
                    <p>關鍵字、禁止詞與品牌規範可之後慢慢補充。</p>
                  </div>
                </div>

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
                      ? "儲存品牌資料"
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
