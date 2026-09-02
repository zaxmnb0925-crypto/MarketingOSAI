import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";
import { setSessionCookies } from "@/lib/auth-cookies";


export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await backendFetch(
      "/api/auth/register",
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
      return NextResponse.json(data, {
        status: response.status,
      });
    }

    const result = NextResponse.json(
      { ok: true },
      { status: 201 },
    );

    if (!data.access_token || !data.refresh_token) {
      throw new Error("Invalid token response");
    }
    setSessionCookies(
      result,
      data.access_token,
      data.refresh_token,
      data.expires_in || 1800,
    );

    return result;
  } catch {
    return NextResponse.json(
      { detail: "Registration service unavailable" },
      { status: 502 },
    );
  }
}
