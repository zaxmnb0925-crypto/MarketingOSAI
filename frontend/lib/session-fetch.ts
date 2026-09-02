let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = fetch("/api/auth/refresh", {
      method: "POST",
      cache: "no-store",
    })
      .then((response) => response.ok)
      .catch(() => false)
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export async function sessionFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
) {
  let response = await fetch(input, init);
  if (response.status !== 401) return response;
  if (!await refreshSession()) return response;
  response = await fetch(input, init);
  return response;
}
