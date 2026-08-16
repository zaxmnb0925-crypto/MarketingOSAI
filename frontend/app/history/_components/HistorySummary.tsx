import type {
  ContentItem,
} from "../_lib/history-types";

type HistorySummaryProps = {
  items: ContentItem[];
  completedCount: number;
  failedCount: number;
  pendingCount: number;
  totalTokens: number;
};

export function HistorySummary({
  items,
  completedCount,
  failedCount,
  pendingCount,
  totalTokens,
}: HistorySummaryProps) {
  return (
<section className="history-summary-grid">
          <article>
            <span>
              全部紀錄
            </span>
            <strong>
              {items.length}
            </strong>
          </article>

          <article>
            <span>
              已完成
            </span>
            <strong>
              {completedCount}
            </strong>
          </article>

          <article>
            <span>
              失敗
            </span>
            <strong>
              {failedCount}
            </strong>
          </article>

          <article>
            <span>
              等待中
            </span>
            <strong>
              {pendingCount}
            </strong>
          </article>

          <article>
            <span>
              Token
            </span>
            <strong>
              {totalTokens.toLocaleString(
                "zh-TW",
              )}
            </strong>
          </article>
        </section>
  );
}
