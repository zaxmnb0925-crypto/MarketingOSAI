import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/backend";


type RouteContext = {
  params: Promise<{
    workspaceId: string;
  }>;
};


export async function GET(
  _request: Request,
  context: RouteContext,
) {
  const token = (await cookies()).get(
    "marketingos_access_token",
  )?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { workspaceId } = await context.params;

  try {
    const response = await backendFetch(
      `/api/platform-admin/workspaces/${encodeURIComponent(workspaceId)}/subscription`,
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
      { detail: "Subscription service unavailable" },
      { status: 502 },
    );
  }
}
