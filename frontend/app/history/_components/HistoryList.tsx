import type {
  ContentItem,
} from "../_lib/history-types";

import {
  HistoryItemCard,
} from "./HistoryItemCard";

type HistoryListProps = {
  historyLoading: boolean;
  filteredItems: ContentItem[];
  expandedId: string | null;
  setExpandedId: (
    value: string | null,
  ) => void;
  copyContent: (
    content: string,
  ) => Promise<void>;
  openInEditor: (
    item: ContentItem,
  ) => void;
};

export function HistoryList({
  historyLoading,
  filteredItems,
  expandedId,
  setExpandedId,
  copyContent,
  openInEditor,
}: HistoryListProps) {
  return (
<section className="history-list">
          {historyLoading ? (
            <div className="history-empty">
              載入中…
            </div>
          ) : filteredItems.length ===
            0 ? (
            <div className="history-empty">
              沒有符合條件的內容紀錄。
            </div>
          ) : (
            filteredItems.map(
              (item) => {
                const expanded =
                  expandedId ===
                  item.id;

                return (
                  <HistoryItemCard
                    key={item.id}
                    item={item}
                    expanded={expanded}
                    setExpandedId={setExpandedId}
                    copyContent={copyContent}
                    openInEditor={openInEditor}
                  />
                );
              },
            )
          )}
        </section>
  );
}
