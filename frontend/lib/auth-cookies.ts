import { NextResponse } from "next/server";

const secure = process.env.NODE_ENV === "production";

function appendLegacyRefreshDeletion(response: NextResponse) {
  response.headers.append(
    "Set-Cookie",
    [
      "marketingos_refresh_token=",
      "Path=/",
      "Max-Age=0",
      "HttpOnly",
      "SameSite=Lax",
      secure ? "Secure" : "",
    ].filter(Boolean).join("; "),
  );
}

export function setSessionCookies(
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
) {
  response.cookies.set("marketingos_access_token", accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: expiresIn,
  });
  response.cookies.set("marketingos_refresh_token", refreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/api/auth",
    maxAge: 60 * 60 * 24 * 30,
  });
  // Remove the legacy broad-path refresh cookie during migration.
  appendLegacyRefreshDeletion(response);
}

export function clearSessionCookies(response: NextResponse) {
  response.cookies.set("marketingos_access_token", "", {
    httpOnly: true, sameSite: "lax", secure, path: "/", maxAge: 0,
  });
  response.cookies.set("marketingos_refresh_token", "", {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/api/auth",
    maxAge: 0,
  });
  appendLegacyRefreshDeletion(response);
}
