import { NextResponse } from "next/server";

const CROSS_SITE = "cross-site";
const HTTP_PROTOCOL = "http";
const HTTPS_PROTOCOL = "https";

function rejection() {
  return NextResponse.json(
    { detail: "Cross-origin request rejected" },
    { status: 403 },
  );
}

function expectedOrigin(request: Request) {
  const requestUrl = new URL(request.url);
  const forwardedProto =
    request.headers.get("x-forwarded-proto");

  let protocol = requestUrl.protocol;

  if (forwardedProto !== null) {
    const normalized =
      forwardedProto.trim().toLowerCase();

    if (
      normalized !== HTTP_PROTOCOL &&
      normalized !== HTTPS_PROTOCOL
    ) {
      return null;
    }

    protocol = `${normalized}:`;
  }

  /*
   * Nginx overwrites Host and X-Forwarded-Proto before
   * forwarding requests. Deliberately do not trust
   * X-Forwarded-Host supplied by an external client.
   */
  const host = request.headers.get("host")?.trim();

  if (
    !host ||
    host.includes(",") ||
    /[\s/\\@]/.test(host)
  ) {
    return null;
  }

  try {
    return new URL(`${protocol}//${host}`).origin;
  } catch {
    return null;
  }
}

function suppliedOrigin(value: string) {
  try {
    const parsed = new URL(value);

    if (
      parsed.protocol !== "http:" &&
      parsed.protocol !== "https:"
    ) {
      return null;
    }

    if (
      parsed.username ||
      parsed.password ||
      parsed.pathname !== "/" ||
      parsed.search ||
      parsed.hash
    ) {
      return null;
    }

    return parsed.origin;
  } catch {
    return null;
  }
}

export function rejectCrossOrigin(request: Request) {
  const fetchSite =
    request.headers
      .get("sec-fetch-site")
      ?.trim()
      .toLowerCase();

  if (fetchSite === CROSS_SITE) {
    return rejection();
  }

  const origin = request.headers.get("origin");

  if (origin) {
    const actual = suppliedOrigin(origin);
    const expected = expectedOrigin(request);

    if (
      actual === null ||
      expected === null ||
      actual !== expected
    ) {
      return rejection();
    }
  }

  return null;
}
