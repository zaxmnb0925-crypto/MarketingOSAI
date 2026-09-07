"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";

import { useRouter } from "next/navigation";

type Workspace = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

type MeResponse = {
  user: {
    id: string;
    email: string;
    full_name: string | null;
    is_active: boolean;
  };

  workspaces: Workspace[];
};

type Brand = {
  id: string;
  workspace_id: string;
  name: string;
  industry: string | null;
  website: string | null;
  description: string | null;
  tone: string | null;
};

type GenerateResponse = {
  generation: {
    id: string;
    status: string;
    generated_content: string | null;
  };

  forbidden_word_hits: string[];
};

const OBJECTIVE_PRESETS = [
  "提高社群互動",
  "介紹新品或服務",
  "導向預約或購買",
  "建立品牌信任",
] as const;

const TONE_OPTIONS = [
  { value: "", label: "沿用品牌語氣" },
  { value: "親切自然", label: "親切自然" },
  { value: "專業可信", label: "專業可信" },
  { value: "活潑有活力", label: "活潑有活力" },
  { value: "溫暖故事感", label: "溫暖故事感" },
  { value: "簡潔有力", label: "簡潔有力" },
] as const;

export default function CreatePage() {
  const router = useRouter();

  const [workspace, setWorkspace] =
    useState<Workspace | null>(null);

  const [brands, setBrands] =
    useState<Brand[]>([]);

  const [brandId, setBrandId] =
    useState("");

  const [platform, setPlatform] =
    useState("instagram");

  const [topic, setTopic] =
    useState("");

  const [objective, setObjective] =
    useState("");

  const [audience, setAudience] =
    useState("");

  const [tone, setTone] =
    useState("");

  const [contentLength, setContentLength] =
    useState("standard");

  const [callToAction, setCallToAction] =
    useState("");

  const [keywords, setKeywords] =
    useState("");

  const [result, setResult] =
    useState<GenerateResponse | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [generating, setGenerating] =
    useState(false);

  const [error, setError] =
    useState("");

  const [editableContent, setEditableContent] =
    useState("");

  const [copied, setCopied] =
    useState(false);

  const [saving, setSaving] =
    useState(false);

  const [saveMessage, setSaveMessage] =
    useState("");


  useEffect(() => {
    async function load() {
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

        const query =
          new URLSearchParams(
            window.location.search,
          );

        const requestedBrandId =
          query.get("brandId");

        const initialBrand =
          brandData.find(
            (brand) =>
              brand.id === requestedBrandId,
          ) || brandData[0];

        if (initialBrand) {
          setBrandId(initialBrand.id);
        }

        const requestedGenerationId =
          query.get("generationId");

        if (
          initialBrand &&
          requestedGenerationId
        ) {
          const draftResponse =
            await fetch(
              `/api/workspaces/${currentWorkspace.id}/brands/${initialBrand.id}/content/${requestedGenerationId}/draft`,
              {
                method: "POST",
              },
            );

          const draftData =
            await draftResponse.json().catch(
              () => null,
            );

          if (
            !draftResponse.ok ||
            !draftData?.id
          ) {
            setError(
              "無法載入歷史草稿。",
            );
          } else {
            setPlatform(
              draftData.platform ||
                "instagram",
            );
            setTopic(
              draftData.topic || "",
            );
            setObjective(
              draftData.objective || "",
            );
            setResult({
              generation: {
                id: draftData.id,
                status:
                  draftData.status ||
                  "draft",
                generated_content:
                  draftData.generated_content ||
                  "",
              },
              forbidden_word_hits: [],
            });
            setEditableContent(
              draftData.generated_content ||
                "",
            );
            setSaveMessage(
              "已從歷史紀錄建立新的草稿副本。",
            );
            window.history.replaceState(
              null,
              "",
              "/create",
            );
          }
        }
      } catch {
        setError(
          "無法載入品牌資料。",
        );
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router]);


  async function generate(
    event: FormEvent,
  ) {
    event.preventDefault();

    if (
      !workspace ||
      !brandId ||
      !topic.trim()
    ) {
      setError(
        "請選擇品牌並輸入主題。",
      );
      return;
    }

    setGenerating(true);
    setError("");
    setResult(null);
    setEditableContent("");
    setCopied(false);
    setSaveMessage("");

    try {
      const response =
        await fetch(
          `/api/workspaces/${workspace.id}/brands/${brandId}/content/generate`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              platform,
              topic,
              objective:
                objective.trim() || null,
              audience:
                audience.trim() || null,
              tone:
                tone || null,
              content_length:
                contentLength,
              call_to_action:
                callToAction.trim() || null,
              keywords:
                keywords.trim() || null,
            }),
          },
        );

      const data =
        await response.json();

      if (!response.ok) {
        const detail =
          data?.detail;

        if (
          typeof detail ===
          "string"
        ) {
          setError(detail);
        } else if (
          detail?.message
        ) {
          setError(
            detail.message,
          );
        } else {
          setError(
            "AI 生成失敗。",
          );
        }

        return;
      }

      setResult(data);
      setEditableContent(
        data.generation.generated_content || "",
      );
      setCopied(false);
      setSaveMessage("");
    } catch {
      setError(
        "目前無法連線至 AI 生成服務。",
      );
    } finally {
      setGenerating(false);
    }
  }


  async function copyGenerated() {
    if (!editableContent.trim()) return;

    try {
      await navigator.clipboard.writeText(
        editableContent,
      );
      setCopied(true);
      window.setTimeout(
        () => setCopied(false),
        1600,
      );
    } catch {
      setCopied(false);
    }
  }


  async function saveGenerated() {
    if (
      !workspace ||
      !brandId ||
      !result?.generation.id ||
      !editableContent.trim()
    ) {
      return;
    }

    setSaving(true);
    setError("");
    setSaveMessage("");

    try {
      const response = await fetch(
        `/api/workspaces/${workspace.id}/brands/${brandId}/content/${result.generation.id}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            generated_content: editableContent,
          }),
        },
      );

      const saved = await response.json().catch(() => null);

      if (!response.ok || !saved?.id) {
        const detail = saved?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : typeof detail?.message === "string"
              ? detail.message
              : "文案儲存失敗。";

        setError(message);
        return;
      }

      const savedContent =
        typeof saved.generated_content === "string"
          ? saved.generated_content
          : editableContent.trim();

      setResult((current) => {
        if (!current) return current;

        return {
          ...current,
          generation: {
            ...current.generation,
            id: saved.id,
            status: saved.status || "draft",
            generated_content: savedContent,
          },
        };
      });

      setEditableContent(savedContent);
      setSaveMessage("已儲存修改，歷史紀錄會保留這個草稿版本。");
    } catch {
      setError("目前無法儲存文案。");
    } finally {
      setSaving(false);
    }
  }


  function regenerate() {
    const form =
      document.getElementById("ai-creator-form");

    if (form instanceof HTMLFormElement) {
      form.requestSubmit();
    }
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
        正在載入 AI 創作工具...
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
              className="nav-item active"
              href="/create"
            >
              AI 創作
            </a>

            <span className="nav-item disabled">
              發布排程
            </span>

            <a
              className="nav-item"
              href="/history"
            >
              內容歷史
            </a>

            <a className="nav-item" href="/social-accounts">社群帳號</a>
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
              AI CONTENT
            </div>

            <h1>
              AI 文案生成器
            </h1>

            <p>
              根據 Brand Brain
              自動產生符合品牌語氣的社群內容。
            </p>
          </div>
        </header>


        <div className="creator-layout">
          <form
            id="ai-creator-form"
            className="creator-panel"
            onSubmit={generate}
          >
            <div className="form-group">
              <label>
                品牌
              </label>

              <select
                value={brandId}
                onChange={(event) =>
                  setBrandId(
                    event.target.value,
                  )
                }
                required
              >
                {brands.map(
                  (brand) => (
                    <option
                      value={brand.id}
                      key={brand.id}
                    >
                      {brand.name}
                    </option>
                  ),
                )}
              </select>
            </div>


            <div className="form-group">
              <label>
                發布平台
              </label>

              <select
                value={platform}
                onChange={(event) =>
                  setPlatform(
                    event.target.value,
                  )
                }
              >
                <option value="instagram">
                  Instagram
                </option>

                <option value="facebook">
                  Facebook
                </option>

                <option value="threads">
                  Threads
                </option>

                <option value="linkedin">
                  LinkedIn
                </option>

                <option value="x">
                  X
                </option>

                <option value="google_business">
                  Google 商家
                </option>
              </select>
            </div>


            <div className="form-group">
              <label>
                主題
              </label>

              <input
                value={topic}
                onChange={(event) =>
                  setTopic(
                    event.target.value,
                  )
                }
                placeholder="例如：夏日下午的手沖咖啡"
                required
              />
            </div>


            <div className="creator-brief-header">
              <div>
                <div className="eyebrow">
                  CREATIVE BRIEF
                </div>

                <strong>
                  讓 AI 更貼近你的需求
                </strong>
              </div>

              <span className="field-help">
                選填，會套用品牌規範
              </span>
            </div>

            <div
              className="creator-preset-row"
              aria-label="快速套用行銷目的"
            >
              {OBJECTIVE_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className={
                    objective === preset
                      ? "creator-preset-button active"
                      : "creator-preset-button"
                  }
                  onClick={() =>
                    setObjective(preset)
                  }
                >
                  {preset}
                </button>
              ))}
            </div>

            <div className="form-group">
              <label>
                行銷目的
              </label>

              <textarea
                value={objective}
                onChange={(event) =>
                  setObjective(
                    event.target.value,
                  )
                }
                placeholder="例如：提升品牌互動並介紹新品"
                maxLength={300}
                rows={3}
              />
            </div>

            <div className="creator-brief-grid">
              <div className="form-group">
                <label>
                  目標客群
                </label>

                <input
                  value={audience}
                  onChange={(event) =>
                    setAudience(
                      event.target.value,
                    )
                  }
                  placeholder="例如：台灣 25–40 歲上班族"
                  maxLength={200}
                />
              </div>

              <div className="form-group">
                <label>
                  內容語氣
                </label>

                <select
                  value={tone}
                  onChange={(event) =>
                    setTone(event.target.value)
                  }
                >
                  {TONE_OPTIONS.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>
                  內容篇幅
                </label>

                <select
                  value={contentLength}
                  onChange={(event) =>
                    setContentLength(
                      event.target.value,
                    )
                  }
                >
                  <option value="short">
                    精簡
                  </option>

                  <option value="standard">
                    標準
                  </option>

                  <option value="long">
                    完整
                  </option>
                </select>
              </div>

              <div className="form-group">
                <label>
                  行動呼籲 CTA
                </label>

                <input
                  value={callToAction}
                  onChange={(event) =>
                    setCallToAction(
                      event.target.value,
                    )
                  }
                  placeholder="例如：立即預約諮詢"
                  maxLength={200}
                />
              </div>
            </div>

            <div className="form-group">
              <label>
                必帶關鍵字
              </label>

              <input
                value={keywords}
                onChange={(event) =>
                  setKeywords(
                    event.target.value,
                  )
                }
                placeholder="用逗號分隔，例如：手沖咖啡,台北,新品"
                maxLength={300}
              />

              <span className="field-help">
                AI 會自然融入，不會硬塞關鍵字。
              </span>
            </div>


            {error ? (
              <div className="auth-error">
                {error}
              </div>
            ) : null}


            <button
              type="submit"
              className="primary-button"
              disabled={
                generating ||
                brands.length === 0
              }
            >
              {generating
                ? "AI 正在生成..."
                : "生成文案"}
            </button>
          </form>


          <section className="creator-result">
            <div className="creator-result-header">
              <div>
                <div className="eyebrow">
                  OUTPUT
                </div>

                <h2>
                  生成結果
                </h2>
              </div>

              {result ? (
                <span className="generation-status">
                  {
                    result.generation
                      .status
                  }
                </span>
              ) : null}
            </div>


            {result ? (
              <>
                <textarea
                  className="generated-content-editor"
                  value={editableContent}
                  onChange={(event) =>
                    setEditableContent(
                      event.target.value,
                    )
                  }
                  aria-label="AI 生成內容"
                />

                <div className="result-actions">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={saveGenerated}
                    disabled={
                      saving ||
                      !editableContent.trim()
                    }
                  >
                    {saving ? "儲存中..." : "儲存修改"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={copyGenerated}
                  >
                    {copied
                      ? "已複製"
                      : "複製文案"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={regenerate}
                    disabled={generating}
                  >
                    {generating
                      ? "重新生成中..."
                      : "重新生成"}
                  </button>
                </div>

                {saveMessage ? (
                  <div className="save-message">
                    {saveMessage}
                  </div>
                ) : null}

                {result &&
                result.forbidden_word_hits.length > 0 ? (
                  <div className="policy-warning">
                    已偵測品牌禁用詞：
                    {" "}
                    {result.forbidden_word_hits.join("、")}
                  </div>
                ) : null}
              </>
            ) : (
              <div className="result-empty">
                <div>
                  <strong>
                    尚未生成內容
                  </strong>

                  <p>
                    選擇品牌、平台並輸入主題，
                    再補充創作簡報，AI 會產生更精準的文案。
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
