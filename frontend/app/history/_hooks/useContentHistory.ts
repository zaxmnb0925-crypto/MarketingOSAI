import {
  useMemo,
  useState,
} from "react";

import type {
  Workspace,
  Brand,
  ContentItem,
} from "../_lib/history-types";

export function useContentHistory() {
const [workspace, setWorkspace] =
    useState<Workspace | null>(
      null,
    );

const [brands, setBrands] =
    useState<Brand[]>([]);

const [
    selectedBrandId,
    setSelectedBrandId,
  ] = useState("");

const [items, setItems] =
    useState<ContentItem[]>([]);

const [statusFilter, setStatusFilter] =
    useState("all");

const [
    platformFilter,
    setPlatformFilter,
  ] = useState("all");

const [loading, setLoading] =
    useState(true);

const [historyLoading, setHistoryLoading] =
    useState(false);

const [error, setError] =
    useState("");

const [
    expandedId,
    setExpandedId,
  ] = useState<string | null>(
    null,
  );


  const filteredItems =
    useMemo(() => {
      return items.filter(
        (item) => {
          if (
            statusFilter !== "all" &&
            item.status !==
              statusFilter
          ) {
            return false;
          }

          if (
            platformFilter !== "all" &&
            item.platform !==
              platformFilter
          ) {
            return false;
          }

          return true;
        },
      );
    }, [
      items,
      statusFilter,
      platformFilter,
    ]);


  const completedCount =
    items.filter(
      (item) =>
        item.status ===
        "completed",
    ).length;


  const failedCount =
    items.filter(
      (item) =>
        item.status ===
        "failed",
    ).length;


  const pendingCount =
    items.filter(
      (item) =>
        item.status ===
        "pending",
    ).length;




  return {
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
  };
}
