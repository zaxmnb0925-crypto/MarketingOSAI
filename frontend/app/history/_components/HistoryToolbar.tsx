import type {
  Brand,
} from "../_lib/history-types";

type HistoryToolbarProps = {
  brands: Brand[];
  selectedBrandId: string;
  changeBrand: (
    brandId: string,
  ) => Promise<void>;
  statusFilter: string;
  setStatusFilter: (
    value: string,
  ) => void;
  platformFilter: string;
  setPlatformFilter: (
    value: string,
  ) => void;
};

export function HistoryToolbar({
  brands,
  selectedBrandId,
  changeBrand,
  statusFilter,
  setStatusFilter,
  platformFilter,
  setPlatformFilter,
}: HistoryToolbarProps) {
  return (
<section className="history-toolbar">
          <label>
            品牌
            <select
              value={
                selectedBrandId
              }
              onChange={(event) =>
                void changeBrand(
                  event.target.value,
                )
              }
            >
              {brands.map(
                (brand) => (
                  <option
                    key={brand.id}
                    value={brand.id}
                  >
                    {brand.name}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            狀態
            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(
                  event.target.value,
                )
              }
            >
              <option value="all">
                全部
              </option>
              <option value="completed">
                已完成
              </option>
              <option value="failed">
                失敗
              </option>
              <option value="pending">
                等待中
              </option>
              <option value="draft">
                草稿
              </option>
            </select>
          </label>

          <label>
            平台
            <select
              value={platformFilter}
              onChange={(event) =>
                setPlatformFilter(
                  event.target.value,
                )
              }
            >
              <option value="all">
                全部
              </option>
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
          </label>
        </section>
  );
}
