import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { clearSessionCookies, setSessionCookies } from "@/lib/auth-cookies";
import { backendFetch } from "@/lib/backend";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("marketingos_refresh_token")?.value;
  if (!refreshToken) {
    const response = NextResponse.json({ detail: "Session expired" }, { status: 401 });
    clearSessionCookies(response);
    return response;
  }
  try {
    const upstream = await backendFetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (upstream.status === 401) {
      const response = NextResponse.json({ detail: "Session expired" }, { status: 401 });
      clearSessionCookies(response);
      return response;
    }
    if (!upstream.ok) {
      return NextResponse.json(
        { detail: "Session service unavailable" },
        { status: 502 },
      );
    }
    const data = await upstream.json();
    if (!data.access_token || !data.refresh_token) throw new Error("Invalid token response");
    const response = NextResponse.json({ ok: true });
    setSessionCookies(response, data.access_token, data.refresh_token, data.expires_in || 1800);
    return response;
  } catch {
    return NextResponse.json({ detail: "Session service unavailable" }, { status: 502 });
  }
}
