import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

export const ACCESS_TOKEN_COOKIE = "marketingos_access_token";
export const REFRESH_TOKEN_COOKIE = "marketingos_refresh_token";
export const REMEMBER_ME_COOKIE = "marketingos_remember_me";

const REMEMBER_ME_MAX_AGE = 60 * 60 * 24 * 30;

const BASE_COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export type SessionTokens = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export type SessionRefreshResult = {
  status: number;
  tokens: SessionTokens | null;
};

function isSessionTokens(value: unknown): value is SessionTokens {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.access_token === "string" &&
    typeof candidate.refresh_token === "string" &&
    typeof candidate.expires_in === "number"
  );
}

export function shouldRemember(value?: string): boolean {
  return value !== "0";
}

export function applySessionCookies(
  response: NextResponse,
  tokens: SessionTokens,
  rememberMe: boolean,
): void {
  response.cookies.set(
    ACCESS_TOKEN_COOKIE,
    tokens.access_token,
    {
      ...BASE_COOKIE_OPTIONS,
      ...(rememberMe
        ? { maxAge: tokens.expires_in || 1800 }
        : {}),
    },
  );

  response.cookies.set(
    REFRESH_TOKEN_COOKIE,
    tokens.refresh_token,
    {
      ...BASE_COOKIE_OPTIONS,
      ...(rememberMe
        ? { maxAge: REMEMBER_ME_MAX_AGE }
        : {}),
    },
  );

  response.cookies.set(
    REMEMBER_ME_COOKIE,
    rememberMe ? "1" : "0",
    {
      ...BASE_COOKIE_OPTIONS,
      ...(rememberMe
        ? { maxAge: REMEMBER_ME_MAX_AGE }
        : {}),
    },
  );
}

export function clearSessionCookies(
  response: NextResponse,
): void {
  for (const name of [
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    REMEMBER_ME_COOKIE,
  ]) {
    response.cookies.set(
      name,
      "",
      {
        ...BASE_COOKIE_OPTIONS,
        maxAge: 0,
      },
    );
  }
}

export async function refreshBackendToken(
  refreshToken: string,
): Promise<SessionRefreshResult> {
  const response = await backendFetch(
    "/api/auth/refresh",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    },
  );

  const data: unknown =
    await response.json().catch(() => null);

  return {
    status: response.status,
    tokens: isSessionTokens(data) ? data : null,
  };
}
