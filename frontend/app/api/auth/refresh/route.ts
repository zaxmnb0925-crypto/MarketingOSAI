import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  REFRESH_TOKEN_COOKIE,
  REMEMBER_ME_COOKIE,
  applySessionCookies,
  clearSessionCookies,
  refreshBackendToken,
  shouldRemember,
} from "@/lib/auth-session";

export async function POST() {
  const cookieStore = await cookies();

  const refreshToken = cookieStore.get(
    REFRESH_TOKEN_COOKIE,
  )?.value;

  const rememberMe = shouldRemember(
    cookieStore.get(REMEMBER_ME_COOKIE)?.value,
  );

  if (!refreshToken) {
    const result = NextResponse.json(
      {
        detail: "Not authenticated",
      },
      {
        status: 401,
      },
    );

    clearSessionCookies(result);
    return result;
  }

  try {
    const refreshResult =
      await refreshBackendToken(refreshToken);

    if (!refreshResult.tokens) {
      const isBackendError =
        refreshResult.status >= 500;

      const result = NextResponse.json(
        {
          detail: isBackendError
            ? "Backend unavailable"
            : "Not authenticated",
        },
        {
          status: isBackendError ? 502 : 401,
        },
      );

      if (!isBackendError) {
        clearSessionCookies(result);
      }

      return result;
    }

    const result = NextResponse.json({
      ok: true,
    });

    applySessionCookies(
      result,
      refreshResult.tokens,
      rememberMe,
    );

    return result;
  } catch {
    return NextResponse.json(
      {
        detail: "Backend unavailable",
      },
      {
        status: 502,
      },
    );
  }
}
