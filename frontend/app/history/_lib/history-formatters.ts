function formatDate(
  value?: string,
) {
  if (!value) {
    return "—";
  }

  try {
    return new Intl.DateTimeFormat(
      "zh-TW",
      {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      },
    ).format(
      new Date(value),
    );
  } catch {
    return value;
  }
}

function statusLabel(
  status: string,
) {
  const map: Record<
    string,
    string
  > = {
    completed: "已完成",
    failed: "失敗",
    pending: "等待中",
    draft: "草稿",
  };

  return map[status] || status;
}

function platformLabel(
  platform: string,
) {
  const map: Record<
    string,
    string
  > = {
    instagram: "Instagram",
    facebook: "Facebook",
    threads: "Threads",
    linkedin: "LinkedIn",
    x: "X",
  };

  return map[platform] || platform;
}

export {
  formatDate,
  statusLabel,
  platformLabel,
};
