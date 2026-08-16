import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

export async function POST() {
  const cookieStore = await cookies();

  const refreshToken = cookieStore.get(
    "marketingos_refresh_token",
  )?.value;

  if (refreshToken) {
    try {
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
    } catch {
      // Cookies are still cleared locally.
    }
  }

  const response = NextResponse.json({
    ok: true,
  });

  response.cookies.set(
    "marketingos_access_token",
    "",
    {
      httpOnly: true,
      sameSite: "lax",
      secure:
        process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 0,
    },
  );

  response.cookies.set(
    "marketingos_refresh_token",
    "",
    {
      httpOnly: true,
      sameSite: "lax",
      secure:
        process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 0,
    },
  );

  return response;
}
