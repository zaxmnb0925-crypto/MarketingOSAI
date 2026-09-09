import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import {
  REFRESH_TOKEN_COOKIE,
  clearSessionCookies,
} from "@/lib/auth-session";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(
    REFRESH_TOKEN_COOKIE,
  )?.value;

  try {
    if (refreshToken) {
      await backendFetch(
        "/api/auth/logout",
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
    }
  } catch {
    // Always clear browser cookies even if the backend is unavailable.
  }

  const result = NextResponse.json({
    ok: true,
  });

  clearSessionCookies(result);
  return result;
}
