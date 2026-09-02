export const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  "http://backend:8000";

export const BACKEND_TIMEOUT_MS = 15_000;

export async function backendFetch(
  path: string,
  init?: RequestInit,
) {
  const timeoutSignal = AbortSignal.timeout(BACKEND_TIMEOUT_MS);
  const signal = init?.signal
    ? AbortSignal.any([init.signal, timeoutSignal])
    : timeoutSignal;
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
    signal,
  });
}
