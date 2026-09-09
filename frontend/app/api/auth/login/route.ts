import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { applySessionCookies } from "@/lib/auth-session";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await backendFetch(
      "/api/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        data,
        {
          status: response.status,
        },
      );
    }

    const result = NextResponse.json({
      ok: true,
    });

    const rememberMe =
      typeof body === "object" &&
      body !== null &&
      body.remember_me !== false;

    applySessionCookies(
      result,
      data,
      rememberMe,
    );

    return result;
  } catch {
    return NextResponse.json(
      {
        detail: "Login service unavailable",
      },
      {
        status: 502,
      },
    );
  }
}
