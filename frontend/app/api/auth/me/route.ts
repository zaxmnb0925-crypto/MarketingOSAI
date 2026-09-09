import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  REMEMBER_ME_COOKIE,
  applySessionCookies,
  clearSessionCookies,
  refreshBackendToken,
  shouldRemember,
} from "@/lib/auth-session";

async function fetchMe(accessToken: string) {
  return backendFetch("/api/auth/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

async function proxyResponse(response: Response) {
  const data = await response.json().catch(() => ({
    detail: "Authentication service returned invalid data",
  }));

  return NextResponse.json(data, {
    status: response.status,
  });
}

export async function GET() {
  const cookieStore = await cookies();

  const accessToken = cookieStore.get(
    ACCESS_TOKEN_COOKIE,
  )?.value;

  const refreshToken = cookieStore.get(
    REFRESH_TOKEN_COOKIE,
  )?.value;

  const rememberMe = shouldRemember(
    cookieStore.get(REMEMBER_ME_COOKIE)?.value,
  );

  if (!accessToken && !refreshToken) {
    return NextResponse.json(
      {
        detail: "Not authenticated",
      },
      {
        status: 401,
      },
    );
  }

  try {
    if (accessToken) {
      const response = await fetchMe(accessToken);

      if (
        response.ok ||
        response.status !== 401 ||
        !refreshToken
      ) {
        const result = await proxyResponse(response);

        if (response.status === 401 && !refreshToken) {
          clearSessionCookies(result);
        }

        return result;
      }
    }

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

    const meResponse = await fetchMe(
      refreshResult.tokens.access_token,
    );

    if (!meResponse.ok) {
      const result = await proxyResponse(meResponse);

      if (meResponse.status < 500) {
        clearSessionCookies(result);
      }

      return result;
    }

    const data = await meResponse.json();

    const result = NextResponse.json(data, {
      status: meResponse.status,
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
