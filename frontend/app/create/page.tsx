"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";

import { useRouter } from "next/navigation";
import { sessionFetch } from "@/lib/session-fetch";

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

  const [result, setResult] =
    useState<GenerateResponse | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [generating, setGenerating] =
    useState(false);

  const [error, setError] =
    useState("");


  useEffect(() => {
    async function load() {
      try {
        const meResponse =
          await sessionFetch(
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
          await sessionFetch(
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
          setBrandId(
            brandData[0].id,
          );
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

    try {
      const response =
        await sessionFetch(
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
                objective || null,
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
    } catch {
      setError(
        "目前無法連線至 AI 生成服務。",
      );
    } finally {
      setGenerating(false);
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
                rows={5}
              />
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


            {result?.generation
              .generated_content ? (
              <>
                <div className="generated-content">
                  {
                    result.generation
                      .generated_content
                  }
                </div>

                <button
                  type="button"
                  className="secondary-button"
                  onClick={() =>
                    navigator.clipboard
                      .writeText(
                        result.generation
                          .generated_content ||
                          "",
                      )
                  }
                >
                  複製文案
                </button>
              </>
            ) : (
              <div className="result-empty">
                <div>
                  <strong>
                    尚未生成內容
                  </strong>

                  <p>
                    選擇品牌、平台並輸入主題，
                    AI 生成結果會顯示在這裡。
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
