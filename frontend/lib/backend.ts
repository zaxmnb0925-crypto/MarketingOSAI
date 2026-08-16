export const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  "http://backend:8000";

export async function backendFetch(
  path: string,
  init?: RequestInit,
) {
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
  });
}
