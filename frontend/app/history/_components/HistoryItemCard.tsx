import type {
  ContentItem,
} from "../_lib/history-types";

import {
  formatDate,
  platformLabel,
  statusLabel,
} from "../_lib/history-formatters";

type HistoryItemCardProps = {
  item: ContentItem;
  expanded: boolean;
  setExpandedId: (
    value: string | null,
  ) => void;
  copyContent: (
    content: string,
  ) => Promise<void>;
};

export function HistoryItemCard({
  item,
  expanded,
  setExpandedId,
  copyContent,
}: HistoryItemCardProps) {
  return (
<article
                    className="history-card"
                    key={item.id}
                  >
                    <div className="history-card-top">
                      <div>
                        <div className="history-badges">
                          <span
                            className={
                              `history-status ${item.status}`
                            }
                          >
                            {statusLabel(
                              item.status,
                            )}
                          </span>

                          <span className="history-platform">
                            {platformLabel(
                              item.platform,
                            )}
                          </span>
                        </div>

                        <h2>
                          {item.topic}
                        </h2>

                        <p>
                          {item.objective ||
                            "未設定行銷目的"}
                        </p>
                      </div>

                      <div className="history-date">
                        {formatDate(
                          item.created_at,
                        )}
                      </div>
                    </div>

                    <div className="history-meta-grid">
                      <div>
                        <span>
                          Model
                        </span>
                        <strong>
                          {item.model ||
                            "—"}
                        </strong>
                      </div>

                      <div>
                        <span>
                          Input
                        </span>
                        <strong>
                          {item.input_tokens ??
                            "—"}
                        </strong>
                      </div>

                      <div>
                        <span>
                          Output
                        </span>
                        <strong>
                          {item.output_tokens ??
                            "—"}
                        </strong>
                      </div>

                      <div>
                        <span>
                          Cost
                        </span>
                        <strong>
                          {item.estimated_cost_usd
                            ? `US$${item.estimated_cost_usd}`
                            : "—"}
                        </strong>
                      </div>
                    </div>

                    {item.status ===
                      "completed" &&
                    item.generated_content ? (
                      <>
                        <div
                          className={
                            expanded
                              ? "history-content expanded"
                              : "history-content"
                          }
                        >
                          {
                            item.generated_content
                          }
                        </div>

                        <div className="history-actions">
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              setExpandedId(
                                expanded
                                  ? null
                                  : item.id,
                              )
                            }
                          >
                            {expanded
                              ? "收合"
                              : "展開全文"}
                          </button>

                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() =>
                              void copyContent(
                                item.generated_content ||
                                  "",
                              )
                            }
                          >
                            複製文案
                          </button>
                        </div>
                      </>
                    ) : null}

                    {item.status ===
                      "failed" ? (
                      <div className="history-error-box">
                        {item.error_message ||
                          "此任務執行失敗。"}
                      </div>
                    ) : null}

                    {item.status ===
                      "pending" ? (
                      <div className="history-warning-box">
                        此筆仍為 pending。
                        若為早期測試資料，
                        後續會透過資料清理流程標記。
                      </div>
                    ) : null}

                    {item.status ===
                      "draft" ? (
                      <div className="history-draft-box">
                        這是一筆草稿，
                        尚未完成 AI 生成。
                      </div>
                    ) : null}
                  </article>
  );
}
