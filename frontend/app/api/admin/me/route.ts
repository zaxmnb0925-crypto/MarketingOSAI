import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";


export async function GET() {
  const token = (await cookies()).get(
    "marketingos_access_token",
  )?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  try {
    const response = await backendFetch(
      "/api/platform-admin/me",
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );
    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Admin identity service unavailable" },
      { status: 502 },
    );
  }
}
