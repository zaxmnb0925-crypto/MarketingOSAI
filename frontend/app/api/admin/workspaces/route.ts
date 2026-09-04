import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";


export async function GET(request: Request) {
  const token = (await cookies()).get(
    "marketingos_access_token",
  )?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const incoming = new URL(request.url);
  const query = new URLSearchParams();

  for (const key of ["q", "limit", "offset"]) {
    const value = incoming.searchParams.get(key);
    if (value !== null) query.set(key, value);
  }

  try {
    const response = await backendFetch(
      `/api/platform-admin/workspaces?${query.toString()}`,
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
      { detail: "Workspace service unavailable" },
      { status: 502 },
    );
  }
}
