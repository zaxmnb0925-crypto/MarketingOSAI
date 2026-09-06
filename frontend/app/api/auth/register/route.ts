import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await backendFetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const result = NextResponse.json({ ok: true }, {
      status: response.status,
    });

    result.cookies.set("marketingos_access_token", data.access_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: data.expires_in || 1800,
    });

    if (data.refresh_token) {
      result.cookies.set("marketingos_refresh_token", data.refresh_token, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 24 * 30,
      });
    }

    return result;
  } catch {
    return NextResponse.json(
      { detail: "Registration service unavailable" },
      { status: 502 },
    );
  }
}
